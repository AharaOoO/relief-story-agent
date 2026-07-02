from relief_story_agent.content import CORE_TYPES, SERIES_LIBRARY, build_chief_screenwriter_prompt
from relief_story_agent.quality import QualityGate


def test_core_library_covers_multiple_low_stimulation_story_kernels():
    assert "矛盾冲突内核" in CORE_TYPES
    assert "奇幻解压内核" in CORE_TYPES
    assert "Q版萌系内核" in CORE_TYPES
    assert "陌生人善意内核" in CORE_TYPES
    assert len(CORE_TYPES) >= 9


def test_series_library_contains_first_wave_series():
    names = {item["name"] for item in SERIES_LIBRARY}
    assert names == {
        "便利店的夜晚",
        "压力小怪物",
        "未完成事务所",
        "雨停之前",
        "小精灵值夜班",
        "今天也没关系",
    }


def test_chief_screenwriter_prompt_is_broad_not_healing_only():
    prompt = build_chief_screenwriter_prompt(
        idea="下班后不想回复消息",
        audience_pressure="长期内耗的上班族",
        preferred_style="现实或Q版",
        duration_seconds=90,
    )

    assert "低刺激情绪缓冲短片" in prompt
    assert "不是单一治愈模板" in prompt
    assert "矛盾冲突内核" in prompt
    assert "Q版萌系内核" in prompt
    assert "压力入口、轻微冲突、温柔异动、情绪释放、余味结尾" in prompt


def test_chief_screenwriter_prompt_supports_five_minute_duration_contract():
    prompt = build_chief_screenwriter_prompt(
        idea="海边夜班故事",
        duration_seconds=150,
    )

    assert "目标时长：150 秒" in prompt
    assert "60-120 秒" not in prompt


def test_quality_gate_accepts_supported_duration_above_120_seconds():
    gate = QualityGate()
    script = {
        "duration_seconds": 150,
        "core_sentence": "疲惫的人也可以暂时停下来。",
        "beats": [{"name": name} for name in gate.required_beats],
    }

    result = gate.check_script_object(script)

    assert result.passed
    assert "duration_out_of_range" not in result.issues


def test_quality_gate_rejects_duration_above_five_minutes():
    gate = QualityGate()
    script = {
        "duration_seconds": 301,
        "core_sentence": "疲惫的人也可以暂时停下来。",
        "beats": [{"name": name} for name in gate.required_beats],
    }

    result = gate.check_script_object(script)

    assert not result.passed
    assert "duration_out_of_range" in result.issues


def test_quality_gate_rejects_preachy_or_high_conflict_script():
    result = QualityGate().check_script_text(
        "角色大吵大闹后说：生活很美好，你要加油，所有问题都彻底解决了。"
    )

    assert not result.passed
    assert "high_conflict" in result.issues
    assert "preachy" in result.issues
    assert "total_resolution" in result.issues


def test_quality_gate_rejects_gore_or_ooc_in_script_and_storyboard():
    gate = QualityGate()
    
    script_result = gate.check_script_text("角色在这里突然表现得非常血腥，简直是崩人设了！")
    assert not script_result.passed
    assert "gore" in script_result.issues
    assert "ooc" in script_result.issues
    
    storyboard = [{"prompt": "There is a lot of blood and violence, totally out of character."}]
    storyboard_result = gate.check_storyboard_object(storyboard)
    assert not storyboard_result.passed
    assert "gore" in storyboard_result.issues
    assert "ooc" in storyboard_result.issues
