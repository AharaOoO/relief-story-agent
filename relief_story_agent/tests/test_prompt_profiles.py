import json
import pytest
from pathlib import Path
from relief_story_agent.prompt_profiles import (
    PromptProfile,
    PromptProfileStore,
    SYSTEM_DEFAULT_ID,
)

def test_system_default_profile_creation(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    
    # Assert system default is created
    profiles = store.list_profiles()
    assert len(profiles) == 1
    sys_def = profiles[0]
    assert sys_def.id == SYSTEM_DEFAULT_ID
    assert sys_def.source == "system"
    assert "chief_screenwriter" in sys_def.stages.model_fields_set

def test_clone_profile(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    cloned = store.clone(SYSTEM_DEFAULT_ID, "My Custom Profile")
    
    assert cloned.id != SYSTEM_DEFAULT_ID
    assert cloned.name == "My Custom Profile"
    assert cloned.source == "user"
    assert cloned.stages.chief_screenwriter == store.get(SYSTEM_DEFAULT_ID).stages.chief_screenwriter
    
    # Modify cloned profile
    cloned.stages.chief_screenwriter = "Custom template"
    updated = store.update(cloned)
    
    assert updated.version == 2
    assert updated.stages.chief_screenwriter == "Custom template"
    
    # System default remains unchanged
    sys_def = store.get(SYSTEM_DEFAULT_ID)
    assert sys_def.stages.chief_screenwriter != "Custom template"

def test_delete_profile(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    cloned = store.clone(SYSTEM_DEFAULT_ID, "To Be Deleted")
    
    assert len(store.list_profiles()) == 2
    store.delete(cloned.id)
    assert len(store.list_profiles()) == 1
    
    # Deleting system default should raise
    with pytest.raises(ValueError, match="Cannot delete the system default profile"):
        store.delete(SYSTEM_DEFAULT_ID)

def test_import_export_profile(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    cloned = store.clone(SYSTEM_DEFAULT_ID, "Export Me")
    cloned.stages.deepseek_polish = "New deepseek polish"
    store.update(cloned)
    
    json_data = store.export_json(cloned.id)
    
    # Import it back
    imported = store.import_json(json_data)
    assert imported.id != cloned.id
    assert imported.name == "Export Me"
    assert imported.source == "imported"
    assert imported.stages.deepseek_polish == "New deepseek polish"
    assert imported.version == 1

def test_system_default_cannot_be_created_explicitly(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    profile = PromptProfile(id=SYSTEM_DEFAULT_ID, name="Hack")
    with pytest.raises(ValueError, match="Cannot explicitly create system default"):
        store.create(profile)


def test_system_default_cannot_be_updated(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    profile = store.get(SYSTEM_DEFAULT_ID)
    profile.stages.chief_screenwriter = "Broken system template"

    with pytest.raises(ValueError, match="Cannot update the system default profile"):
        store.update(profile)


def test_reset_restores_custom_profile_stages_and_increments_version(tmp_path: Path):
    store = PromptProfileStore(tmp_path)
    profile = store.clone(SYSTEM_DEFAULT_ID, "Reset me")
    profile.stages.chief_screenwriter = "Custom template"
    profile = store.update(profile)

    reset = store.reset(profile.id)

    assert reset.id == profile.id
    assert reset.name == "Reset me"
    assert reset.version == 3
    assert reset.source == "user"
    assert (
        reset.stages.chief_screenwriter
        == store.get(SYSTEM_DEFAULT_ID).stages.chief_screenwriter
    )
