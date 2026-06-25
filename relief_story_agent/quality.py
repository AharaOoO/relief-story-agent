from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    issues: list[str]


class QualityGate:
    high_conflict_terms = ("大吵大闹", "激烈争吵", "咆哮", "互相辱骂", "压迫观众")
    preachy_terms = ("生活很美好", "你要加油", "必须坚强", "努力就会", "鸡汤")
    total_resolution_terms = ("彻底解决", "问题全部解决", "大圆满", "从此再也")
    required_beats = ("压力入口", "轻微冲突", "温柔异动", "情绪释放", "余味结尾")

    def check_script_text(self, text: str) -> QualityGateResult:
        issues: list[str] = []
        if self._contains_any(text, self.high_conflict_terms):
            issues.append("high_conflict")
        if self._contains_any(text, self.preachy_terms):
            issues.append("preachy")
        if self._contains_any(text, self.total_resolution_terms):
            issues.append("total_resolution")
        return QualityGateResult(passed=not issues, issues=issues)

    def check_script_object(self, script: dict) -> QualityGateResult:
        issues: list[str] = []
        text = str(script)
        text_result = self.check_script_text(text)
        issues.extend(text_result.issues)

        duration = int(script.get("duration_seconds") or 0)
        if duration and not 60 <= duration <= 120:
            issues.append("duration_out_of_range")

        if not str(script.get("core_sentence") or "").strip():
            issues.append("missing_core_sentence")

        beat_names = {str(beat.get("name") or "") for beat in script.get("beats") or []}
        for required in self.required_beats:
            if required not in beat_names:
                issues.append(f"missing_beat:{required}")

        return QualityGateResult(passed=not issues, issues=issues)

    @staticmethod
    def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

