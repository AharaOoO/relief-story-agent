import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field

from .content import (
    DEFAULT_CHIEF_SCREENWRITER_TEMPLATE,
    DEFAULT_DEEPSEEK_POLISH_TEMPLATE,
    DEFAULT_QUALITY_GATE_TEMPLATE,
)
from .prompt_templates import (
    DEFAULT_PROMPT_WRITER_TEMPLATE,
    DEFAULT_PROMPT_AUDIT_TEMPLATE,
    DEFAULT_PROMPT_REVISER_TEMPLATE,
)

SYSTEM_DEFAULT_ID = "system-default"

class PromptProfileStages(BaseModel):
    chief_screenwriter: str = ""
    deepseek_polish: str = ""
    quality_gate: str = ""
    gpt_prompt_writer: str = ""
    gpt_prompt_audit: str = ""
    gpt_prompt_reviser: str = ""


class PromptProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Profile"
    description: str = ""
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Literal["system", "user", "imported"] = "user"
    content_hash: str = ""
    stages: PromptProfileStages = Field(default_factory=PromptProfileStages)

    def compute_hash(self) -> str:
        data = self.stages.model_dump_json(exclude_none=True).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def update_hash(self) -> None:
        self.content_hash = self.compute_hash()

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


class PromptProfileCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _get_system_default_stages() -> PromptProfileStages:
    return PromptProfileStages(
        chief_screenwriter=DEFAULT_CHIEF_SCREENWRITER_TEMPLATE,
        deepseek_polish=DEFAULT_DEEPSEEK_POLISH_TEMPLATE,
        quality_gate=DEFAULT_QUALITY_GATE_TEMPLATE,
        gpt_prompt_writer=DEFAULT_PROMPT_WRITER_TEMPLATE,
        gpt_prompt_audit=DEFAULT_PROMPT_AUDIT_TEMPLATE,
        gpt_prompt_reviser=DEFAULT_PROMPT_REVISER_TEMPLATE,
    )


def create_system_default_profile() -> PromptProfile:
    profile = PromptProfile(
        id=SYSTEM_DEFAULT_ID,
        name="System Default",
        description="Built-in default system contracts. Cannot be deleted.",
        version=1,
        source="system",
        stages=_get_system_default_stages(),
    )
    profile.update_hash()
    return profile


class PromptProfileStore:
    def __init__(self, profiles_dir: str | Path):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_system_default()

    def _ensure_system_default(self) -> None:
        path = self.profiles_dir / f"{SYSTEM_DEFAULT_ID}.json"
        sys_def = create_system_default_profile()
        path.write_text(sys_def.model_dump_json(indent=2), encoding="utf-8")

    def _get_path(self, profile_id: str) -> Path:
        return self.profiles_dir / f"{profile_id}.json"

    def list_profiles(self) -> list[PromptProfile]:
        profiles = []
        for path in self.profiles_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(PromptProfile.model_validate(data))
            except Exception:
                pass
        return sorted(
            profiles,
            key=lambda profile: (profile.id != SYSTEM_DEFAULT_ID, profile.name.lower()),
        )

    def get(self, profile_id: str) -> PromptProfile:
        path = self._get_path(profile_id)
        if not path.exists():
            if profile_id == SYSTEM_DEFAULT_ID:
                self._ensure_system_default()
                return self.get(profile_id)
            raise ValueError(f"Profile {profile_id} not found")
        data = json.loads(path.read_text(encoding="utf-8"))
        return PromptProfile.model_validate(data)

    def create(self, profile: PromptProfile) -> PromptProfile:
        if profile.id == SYSTEM_DEFAULT_ID:
            raise ValueError("Cannot explicitly create system default profile")
        profile.update_hash()
        path = self._get_path(profile.id)
        if path.exists():
            raise ValueError(f"Profile {profile.id} already exists")
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return profile

    def update(self, profile: PromptProfile) -> PromptProfile:
        path = self._get_path(profile.id)
        if not path.exists():
            raise ValueError(f"Profile {profile.id} not found")
        
        existing = self.get(profile.id)
        if existing.source == "system" or profile.id == SYSTEM_DEFAULT_ID:
            raise ValueError("Cannot update the system default profile")
            
        profile.version = existing.version + 1
        profile.update_hash()
        profile.update_timestamp()
        
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return profile

    def reset(self, profile_id: str) -> PromptProfile:
        if profile_id == SYSTEM_DEFAULT_ID:
            raise ValueError("Cannot reset the system default profile")
        profile = self.get(profile_id)
        profile.stages = _get_system_default_stages()
        return self.update(profile)

    def delete(self, profile_id: str) -> None:
        if profile_id == SYSTEM_DEFAULT_ID:
            raise ValueError("Cannot delete the system default profile")
        path = self._get_path(profile_id)
        if path.exists():
            path.unlink()

    def clone(self, source_id: str, new_name: str) -> PromptProfile:
        source = self.get(source_id)
        cloned = PromptProfile(
            name=new_name,
            description=source.description,
            source="user",
            stages=source.stages.model_copy()
        )
        cloned.update_hash()
        return self.create(cloned)

    def import_json(self, json_data: str) -> PromptProfile:
        data = json.loads(json_data)
        profile = PromptProfile.model_validate(data)
        profile.id = str(uuid.uuid4())
        profile.source = "imported"
        profile.version = 1
        profile.update_hash()
        profile.update_timestamp()
        return self.create(profile)

    def export_json(self, profile_id: str) -> str:
        profile = self.get(profile_id)
        return profile.model_dump_json(indent=2)
