from src.agent import run_agent
from src.models import ScriptRequest


BASE = dict(topic="字幕", audience="新手创作者", platform="抖音", target_duration_sec=30,
            style="简洁", mode="mock")


def test_mock_observes_overrun_and_rechecks():
    result = run_agent(ScriptRequest(**BASE))
    assert result.status == "completed"
    assert result.estimated_duration_sec <= 30
    actions = [step.action for step in result.trace]
    assert actions.count("set_draft") == 2
    assert actions.count("estimate") == 2
    assert actions[-1] == "finish"


def test_missing_material_requests_input():
    result = run_agent(ScriptRequest(**(BASE | {"topic": "登月火箭"})))
    assert result.status == "needs_input"
    assert result.missing_fields == ["material"]


def test_tool_failure_is_observed_and_retried():
    result = run_agent(ScriptRequest(**(BASE | {"failure_injection": "search"})))
    assert result.status == "completed"
    assert "工具失败" in result.trace[0].result_summary
    assert result.trace[0].next_action == "search"
