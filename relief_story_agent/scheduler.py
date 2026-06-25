from __future__ import annotations

import queue
import threading
import time
import uuid
from datetime import datetime, timezone

from .models import (
    BatchFailurePolicy,
    BatchRetryRequest,
    BatchRunRequest,
    BatchRunState,
    RunRequest,
    RunRetryRequest,
    RunState,
)
from .orchestrator import StoryRunOrchestrator


class PersistentRunScheduler:
    def __init__(
        self,
        orchestrator: StoryRunOrchestrator,
        *,
        max_workers: int = 2,
        lease_seconds: float = 300.0,
        recovery_poll_seconds: float = 5.0,
    ):
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if recovery_poll_seconds <= 0:
            raise ValueError("recovery_poll_seconds must be greater than 0")
        self.orchestrator = orchestrator
        self.store = orchestrator.store
        self.max_workers = max_workers
        self.lease_seconds = lease_seconds
        self.recovery_poll_seconds = recovery_poll_seconds
        self.scheduler_id = "scheduler_" + uuid.uuid4().hex[:12]
        self._queue: queue.PriorityQueue[tuple[int, int, str | None]] = queue.PriorityQueue()
        self._queue_sequence = 0
        self._threads: list[threading.Thread] = []
        self._scheduled: set[str] = set()
        self._scheduled_entries: dict[str, tuple[int, int]] = {}
        self._active: set[str] = set()
        self._lock = threading.RLock()
        self._recovery_wakeup = threading.Event()
        self._recovery_thread: threading.Thread | None = None
        self._started = False
        self._stopping = False

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stopping = False
            for index in range(self.max_workers):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"relief-worker-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)
            self._recovery_thread = threading.Thread(
                target=self._recovery_loop,
                name="relief-recovery",
                daemon=True,
            )
            self._recovery_thread.start()
        self.recover()

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if not self._started:
                return
            self._stopping = True
            self._recovery_wakeup.set()
            for _ in self._threads:
                self._queue.put((-1_000_000_000, self._next_queue_sequence(), None))
        if wait:
            for thread in self._threads:
                thread.join(timeout=5)
            if self._recovery_thread:
                self._recovery_thread.join(timeout=5)
        with self._lock:
            self._threads.clear()
            self._recovery_thread = None
            self._recovery_wakeup.clear()
            self._started = False

    def recover(self) -> None:
        for run in self.store.list_runs():
            if run.status == "queued" or (
                run.status == "running" and _lease_expired(run.lease_expires_at)
            ):
                self.submit(run.run_id)

    def create_run(self, request: RunRequest) -> RunState:
        run = self.orchestrator.prepare_run(request)
        self.submit(run.run_id)
        return self.store.get(run.run_id)

    def create_batch(self, request: BatchRunRequest) -> BatchRunState:
        batch = self.orchestrator.prepare_batch(request)
        for item in batch.items:
            self.submit(item.run_id)
        return self.orchestrator.refresh_batch(batch.batch_id)

    def approve(self, run_id: str, payload: dict | None = None) -> RunState:
        run = self.orchestrator.queue_approval(run_id, payload)
        self.submit(run_id)
        return self.store.get(run_id)

    def retry(self, run_id: str, request: RunRetryRequest | None = None) -> RunState:
        run = self.orchestrator.queue_retry(run_id, request)
        self.submit(run_id)
        return self.store.get(run_id)

    def retry_batch(
        self,
        batch_id: str,
        request: BatchRetryRequest | None = None,
    ) -> BatchRunState:
        batch = self.orchestrator.refresh_batch(batch_id)
        for item in batch.items:
            if item.status != "failed":
                continue
            self.retry(
                item.run_id,
                RunRetryRequest(from_stage=(request.from_stage if request else None)),
            )
        return self.orchestrator.refresh_batch(batch_id)

    def cancel_batch(self, batch_id: str) -> BatchRunState:
        return self.orchestrator.cancel_batch(batch_id)

    def pause_batch(self, batch_id: str) -> BatchRunState:
        return self.orchestrator.pause_batch(batch_id)

    def resume_batch(self, batch_id: str) -> BatchRunState:
        batch = self.orchestrator.resume_batch(batch_id)
        for item in batch.items:
            if item.status == "queued":
                self.submit(item.run_id)
        return self.orchestrator.refresh_batch(batch_id)

    def cancel(self, run_id: str) -> RunState:
        run = self.orchestrator.request_cancel(run_id)
        if run.parent_batch_id:
            self.orchestrator.refresh_batch(run.parent_batch_id)
        return run

    def submit(self, run_id: str) -> None:
        self.start()
        run = self.store.get(run_id)
        if run.parent_batch_id:
            batch = self.store.get_batch(run.parent_batch_id)
            if batch.paused and run.status == "queued":
                self.orchestrator.pause_run_if_queued(run_id)
                self.orchestrator.refresh_batch(batch.batch_id)
                return
        with self._lock:
            if run_id in self._scheduled or run_id in self._active:
                return
            priority_key = -run.queue_priority
            sequence = self._next_queue_sequence()
            self._scheduled.add(run_id)
            self._scheduled_entries[run_id] = (priority_key, sequence)
            self._queue.put((priority_key, sequence, run_id))

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                idle = (
                    self._queue.unfinished_tasks == 0
                    and not self._scheduled
                    and not self._active
                )
            if idle:
                return True
            time.sleep(0.01)
        return False

    def status(self) -> dict:
        with self._lock:
            return {
                "scheduler_id": self.scheduler_id,
                "started": self._started,
                "max_workers": self.max_workers,
                "queued": len(self._scheduled),
                "active": len(self._active),
                "queued_items": self._queued_item_snapshots(),
                "active_items": self._active_item_snapshots(),
                "lease_seconds": self.lease_seconds,
                "recovery_poll_seconds": self.recovery_poll_seconds,
            }

    def _recovery_loop(self) -> None:
        while not self._recovery_wakeup.wait(self.recovery_poll_seconds):
            with self._lock:
                if self._stopping:
                    return
            self.recover()

    def _worker_loop(self) -> None:
        while True:
            _, _, run_id = self._queue.get()
            retry_run_id: str | None = None
            try:
                if run_id is None:
                    return
                with self._lock:
                    self._scheduled.discard(run_id)
                    self._scheduled_entries.pop(run_id, None)
                    self._active.add(run_id)
                claimed = self.store.try_claim(
                    run_id,
                    self.scheduler_id,
                    self.lease_seconds,
                )
                if claimed is None:
                    continue
                claimed.add_event(
                    "run_claimed",
                    message="Run claimed by background worker.",
                    data={"worker": self.scheduler_id},
                )
                self.store.save(claimed)
                self.orchestrator.execute_scheduled(run_id)
                final = self.store.get(run_id)
                if final.parent_batch_id:
                    retry_run_id = self._handle_batch_progress(final)
            finally:
                if run_id is not None:
                    with self._lock:
                        self._active.discard(run_id)
                    if retry_run_id:
                        self.submit(retry_run_id)
                self._queue.task_done()

    def _handle_batch_progress(self, run: RunState) -> str | None:
        batch = self.orchestrator.refresh_batch(run.parent_batch_id)
        policy = batch.failure_policy
        if (
            run.status == "failed"
            and not batch.paused
            and (run.last_failure is None or run.last_failure.retryable)
            and run.retry_count < policy.auto_retry_failed_items
        ):
            retry = self.orchestrator.queue_retry(run.run_id, RunRetryRequest())
            self.orchestrator.refresh_batch(batch.batch_id)
            return retry.run_id

        if self._should_pause_for_failures(batch, policy):
            self.orchestrator.pause_batch(batch.batch_id)
        return None

    @staticmethod
    def _should_pause_for_failures(
        batch: BatchRunState,
        policy: BatchFailurePolicy,
    ) -> bool:
        if batch.paused:
            return False
        failed = batch.summary.get("failed", 0)
        if failed <= 0:
            return False
        if policy.pause_on_failure_count and failed >= policy.pause_on_failure_count:
            return True
        total = batch.summary.get("total", 0)
        if policy.pause_on_failure_rate and total:
            return failed / total >= policy.pause_on_failure_rate
        return False

    def _next_queue_sequence(self) -> int:
        self._queue_sequence += 1
        return self._queue_sequence

    def _queued_item_snapshots(self) -> list[dict]:
        items = []
        ordered = sorted(
            self._scheduled_entries.items(),
            key=lambda item: item[1],
        )
        for position, (run_id, _) in enumerate(ordered, start=1):
            snapshot = self._run_snapshot(run_id)
            if snapshot:
                snapshot["position"] = position
                items.append(snapshot)
        return items

    def _active_item_snapshots(self) -> list[dict]:
        return [
            snapshot
            for run_id in sorted(self._active)
            if (snapshot := self._run_snapshot(run_id))
        ]

    def _run_snapshot(self, run_id: str) -> dict:
        try:
            run = self.store.get(run_id)
        except KeyError:
            return {}
        return {
            "run_id": run.run_id,
            "idea": run.request.idea,
            "status": run.status,
            "current_stage": run.current_stage,
            "queue_priority": run.queue_priority,
            "parent_batch_id": run.parent_batch_id,
            "updated_at": run.updated_at,
        }


def _lease_expired(value: str) -> bool:
    if not value:
        return True
    try:
        expires_at = datetime.fromisoformat(value)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)
