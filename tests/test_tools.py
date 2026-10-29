from src.models import ScriptDraft
from src.tools import check_rules, estimate_duration, search_materials


def draft(seconds=(20, 18), claim="支持字幕", text="产品支持字幕"):
    return ScriptDraft.model_validate({"title": "字幕演示", "scenes": [
        {"shot": "展示操作", "narration": text, "planned_seconds": seconds[0],
         "fact_claims": [claim], "material_ids": ["P01"]},
        {"shot": "展示成片", "narration": "看一看成片", "planned_seconds": seconds[1]}
    ]})


def test_search_and_missing_material():
    assert search_materials("字幕")["items"][0]["material_id"] == "P01"
    assert search_materials("登月火箭")["count"] == 0


def test_duration_is_reproducible():
    assert estimate_duration(draft())["total_seconds"] == 38
    assert estimate_duration(draft((16, 12)))["total_seconds"] == 28


def test_rules_require_exact_fact_source_and_reject_risky_claim():
    assert check_rules(draft())["passed"]
    result = check_rules(draft(claim="效率提升80%", text="效率提升80%"))
    assert not result["passed"]
    assert any("量化效果" in issue for issue in result["issues"])
    assert any("无对应原文" in issue for issue in result["issues"])


def test_rules_reject_unverified_ui_actions():
    result = check_rules(draft(text="点击字幕入口，支持字幕"))
    assert not result["passed"]
    assert any("素材未证明的操作" in issue for issue in result["issues"])
