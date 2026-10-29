"""Check that committed live evidence demonstrates observed decisions."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "examples"


def _case(name):
    output = json.loads((ROOT / "outputs" / f"{name}.json").read_text(encoding="utf-8"))
    trace = json.loads((ROOT / "traces" / f"{name}.json").read_text(encoding="utf-8"))
    assert output["body"]["model_mode"] == "live"
    assert output["body"]["trace"] == trace
    return output["body"], trace


def test_live_normal_uses_rule_failure_to_revise_and_recheck():
    body, trace = _case("live_normal")
    assert body["status"] == "completed"
    assert body["estimated_duration_sec"] <= 30
    failure = next(i for i, x in enumerate(trace) if x["action"] == "check"
                   and "规则未通过" in x["result_summary"])
    assert trace[failure]["next_action"] == "set_draft"
    assert any(x["action"] == "check" and x["result_summary"] == "规则通过"
               for x in trace[failure + 1:])
    assert "P01" in body["material_ids"]


def test_live_no_material_changes_action_after_empty_searches():
    body, trace = _case("live_no_material")
    assert body["status"] == "needs_input"
    searches = [x for x in trace if x["action"] == "search"]
    assert len(searches) == 2
    assert all("0 条素材" in x["result_summary"] for x in searches)
    assert searches[-1]["next_action"] == "request_input"
    assert trace[-1]["action"] == "request_input"
