"""Acceptance paths and guardrails for the chosen examination task."""

from src.agent import run_agent
from src.models import ScriptRequest
from src.tools import check_rules


BASE = dict(topic="字幕", audience="新手创作者", platform="抖音", target_duration_sec=30,
            style="简洁", mode="mock")


def test_normal_and_overlength_correction_have_real_tool_observations():
    result = run_agent(ScriptRequest(**BASE))
    estimates = [step.result_summary for step in result.trace if step.action == "estimate"]
    assert result.status == "completed"
    assert estimates == ["估计总时长 38 秒", "估计总时长 30 秒"]
    assert result.trace[-1].action == "finish"
    assert all(scene.planned_seconds > 0 for scene in result.scenes)


def test_missing_business_info_and_no_material():
    assert run_agent(ScriptRequest(**(BASE | {"style": None}))).status == "needs_input"
    no_material = run_agent(ScriptRequest(**(BASE | {"topic": "登月火箭"})))
    assert no_material.status == "needs_input"
    assert no_material.title is None
    assert [x.action for x in no_material.trace].count("search") == 1


def test_tool_failure_recorded_then_recovered():
    result = run_agent(ScriptRequest(**(BASE | {"failure_injection": "estimate"})))
    assert result.status == "completed"
    assert any("工具失败" in x.result_summary for x in result.trace)
    assert [x.action for x in result.trace].count("estimate") == 3


def test_rule_risk_blocks_unsupported_effect_claim():
    draft = {"title": "夸大文案", "scenes": [{"shot": "演示字幕", "narration": "支持字幕，效率提升80%",
             "planned_seconds": 10, "fact_claims": ["支持字幕"], "material_ids": ["P01"]}]}
    result = check_rules(draft)
    assert not result["passed"]
    assert any("量化效果" in issue for issue in result["issues"])


def test_rule_risk_is_corrected_and_rechecked():
    result = run_agent(ScriptRequest(**(BASE | {"target_duration_sec": 40,
                                                "mock_scenario": "rule_risk"})))
    assert result.status == "completed"
    assert [x.action for x in result.trace].count("check") == 2
    assert any("规则未通过" in x.result_summary for x in result.trace)
    assert all("效率提升80%" not in x.narration for x in result.scenes)


def test_step_limit_is_explicit(monkeypatch):
    monkeypatch.setenv("MAX_AGENT_STEPS", "2")
    result = run_agent(ScriptRequest(**BASE))
    assert result.status == "incomplete"
    assert "上限" in result.reason


def test_tool_limit_is_explicit(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_CALLS", "1")
    result = run_agent(ScriptRequest(**BASE))
    assert result.status == "incomplete"
    assert "上限" in result.reason


def test_premature_finish_cannot_pass_gate():
    class PrematureModel:
        def decide(self, state):
            return {"action": "finish", "args": {}, "reason": "错误地提前结束"}

    result = run_agent(ScriptRequest(**BASE), model_adapter=PrematureModel())
    assert result.status == "incomplete"


def test_unrecovered_failure_cannot_be_success():
    class StopOnFailure:
        def decide(self, state):
            if state["history"] and state["history"][-1].get("error"):
                return {"action": "finish", "args": {}, "reason": "工具故障"}
            return {"action": "search", "args": {"query": "字幕"}, "reason": "先检索"}

    result = run_agent(ScriptRequest(**(BASE | {"failure_injection": "search"})),
                       model_adapter=StopOnFailure())
    assert result.status == "tool_failed"
