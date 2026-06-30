from __future__ import annotations

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.prompt_profiles import PromptProfileStore, SYSTEM_DEFAULT_ID
from relief_story_agent.providers import FakeModelProvider


def _client(tmp_path):
    profile_store = PromptProfileStore(tmp_path / "profiles")
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        profile_store=profile_store,
    )
    return TestClient(create_app(orchestrator)), profile_store


def test_prompt_profile_api_crud_clone_and_reset(tmp_path):
    client, store = _client(tmp_path)

    listed = client.get("/api/prompt-profiles")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [SYSTEM_DEFAULT_ID]

    created = client.post(
        "/api/prompt-profiles",
        json={
            "name": "My workflow",
            "description": "Six-stage templates",
            "stages": {
                "chief_screenwriter": "Write a grounded story.",
                "deepseek_polish": "Polish the script.",
                "quality_gate": "Audit script logic.",
                "gpt_prompt_writer": "Create shots.",
                "gpt_prompt_audit": "Audit shots.",
                "gpt_prompt_reviser": "Revise shots.",
            },
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]
    assert created.json()["version"] == 1
    assert created.json()["content_hash"]

    fetched = client.get(f"/api/prompt-profiles/{profile_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    body["description"] = "Updated"
    body["stages"]["quality_gate"] = "Use the strict gate."

    updated = client.put(f"/api/prompt-profiles/{profile_id}", json=body)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["stages"]["quality_gate"] == "Use the strict gate."

    cloned = client.post(
        f"/api/prompt-profiles/{profile_id}/clone",
        json={"name": "Copy"},
    )
    assert cloned.status_code == 201
    assert cloned.json()["id"] != profile_id
    assert cloned.json()["name"] == "Copy"

    reset = client.post(f"/api/prompt-profiles/{profile_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["version"] == 3
    assert (
        reset.json()["stages"]["quality_gate"]
        == store.get(SYSTEM_DEFAULT_ID).stages.quality_gate
    )

    deleted = client.delete(f"/api/prompt-profiles/{profile_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/prompt-profiles/{profile_id}").status_code == 404


def test_prompt_profile_api_protects_system_default_and_validates_path_id(tmp_path):
    client, _ = _client(tmp_path)
    system_profile = client.get(
        f"/api/prompt-profiles/{SYSTEM_DEFAULT_ID}"
    ).json()

    update = client.put(
        f"/api/prompt-profiles/{SYSTEM_DEFAULT_ID}",
        json=system_profile,
    )
    delete = client.delete(f"/api/prompt-profiles/{SYSTEM_DEFAULT_ID}")

    assert update.status_code == 409
    assert update.json()["detail"]["code"] == "prompt_profile_read_only"
    assert delete.status_code == 409
    assert delete.json()["detail"]["code"] == "prompt_profile_read_only"


def test_run_freezes_prompt_profile_snapshot_at_creation(tmp_path):
    client, store = _client(tmp_path)
    profile = store.clone(SYSTEM_DEFAULT_ID, "Snapshot")
    profile.stages.chief_screenwriter = "Snapshot version one"
    profile = store.update(profile)

    created = client.post(
        "/api/runs",
        json={
            "idea": "Snapshot test",
            "approval_mode": "manual",
            "prompt_profile": {
                "profile_id": profile.id,
                "profile_version": profile.version,
                "stage_overrides": {"deepseek_polish": "Run-only override"},
            },
        },
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    profile.stages.chief_screenwriter = "Snapshot version two"
    store.update(profile)

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["prompt_snapshot"]["chief_screenwriter"] == "Snapshot version one"
    assert run["prompt_snapshot"]["deepseek_polish"] == "Run-only override"

