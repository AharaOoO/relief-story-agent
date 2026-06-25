from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from threading import RLock
from datetime import datetime, timedelta, timezone

from .models import BatchRunState, RunState


class JsonFileRunStore:
    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.runs_dir = self.state_dir / "runs"
        self.batches_dir = self.state_dir / "batches"
        self._lock = RLock()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: RunState) -> None:
        with self._lock:
            path = self._run_path(state.run_id)
            if path.exists() and state.status == "running":
                current = RunState.model_validate_json(path.read_text(encoding="utf-8"))
                if current.cancel_requested:
                    state.cancel_requested = True
            self._write_json(path, state.model_dump())

    def get(self, run_id: str) -> RunState:
        with self._lock:
            path = self._run_path(run_id)
            if not path.exists():
                raise KeyError(run_id)
            return RunState.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[RunState]:
        with self._lock:
            return [
                RunState.model_validate_json(path.read_text(encoding="utf-8"))
                for path in sorted(self.runs_dir.glob("*.json"))
            ]

    def try_claim(self, run_id: str, owner: str, lease_seconds: float) -> RunState | None:
        with self._lock:
            try:
                run = self.get(run_id)
            except KeyError:
                return None
            if run.status == "queued":
                pass
            elif run.status == "running" and _lease_expired(run.lease_expires_at):
                pass
            else:
                return None
            now = datetime.now(timezone.utc)
            run.status = "running"
            run.execution_attempt += 1
            run.lease_owner = owner
            run.lease_seconds = lease_seconds
            run.lease_expires_at = (
                now + timedelta(seconds=lease_seconds)
            ).isoformat()
            if not run.started_at:
                run.started_at = now.isoformat()
            self._write_json(self._run_path(run_id), run.model_dump())
            return run

    def save_batch(self, state: BatchRunState) -> None:
        with self._lock:
            self._write_json(self._batch_path(state.batch_id), state.model_dump())

    def get_batch(self, batch_id: str) -> BatchRunState:
        with self._lock:
            path = self._batch_path(batch_id)
            if not path.exists():
                raise KeyError(batch_id)
            return BatchRunState.model_validate_json(path.read_text(encoding="utf-8"))

    def list_batches(self) -> list[BatchRunState]:
        with self._lock:
            return [
                BatchRunState.model_validate_json(path.read_text(encoding="utf-8"))
                for path in sorted(self.batches_dir.glob("*.json"))
            ]

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{_safe_id(run_id)}.json"

    def _batch_path(self, batch_id: str) -> Path:
        return self.batches_dir / f"{_safe_id(batch_id)}.json"

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            _replace_with_retry(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise


def _replace_with_retry(source: str, destination: Path, *, max_attempts: int = 5) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == max_attempts:
                raise
            time.sleep(0.01 * attempt)


def _safe_id(value: str) -> str:
    if not value or any(char in value for char in ('/', '\\', ':', '..')):
        raise ValueError(f"Unsafe id for file storage: {value!r}")
    return value


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
