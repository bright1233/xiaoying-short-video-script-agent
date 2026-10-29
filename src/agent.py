"""LangGraph decision loop and hard completion gates."""

import os
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.model_adapter import LiveModel, MockModel
from src.models import ScriptDraft, ScriptRequest, ScriptResponse, TaskStatus, TraceStep
from src.tools import check_rules, estimate_duration, search_materials


class AgentState(TypedDict):
    request: dict
    retrieved: list[dict]
    draft: dict | None
    draft_version: int
    duration: dict | None
    duration_version: int
    rules: dict | None
    rules_version: int
    steps: int
    tool_calls: int
    max_steps: int
    max_tools: int
    action: dict | None
    history: list[dict]
    trace: list[dict]
    status: str | None
    reason: str | None
    missing_fields: list[str]
    injected: bool


ALLOWED_ACTIONS = {"search", "set_draft", "estimate", "check", "finish", "request_input"}


def _summary(result: Any) -> str:
    if isinstance(result, dict):
        if "items" in result:
            return f"检索到 {result['count']} 条素材：{[x['material_id'] for x in result['items']]}"
        if "total_seconds" in result:
            return f"估计总时长 {result['total_seconds']} 秒"
        if "passed" in result:
            return "规则通过" if result["passed"] else f"规则未通过：{result['issues']}"
    return str(result)[:300]


def build_graph(model_adapter):
    def agent_node(state: AgentState) -> dict:
        if state["steps"] >= state["max_steps"]:
            return {"status": TaskStatus.incomplete.value, "reason": "达到模型决策步数上限"}
        try:
            action = model_adapter.decide(state)
            name = action.get("action")
            if name not in ALLOWED_ACTIONS or not isinstance(action.get("args", {}), dict):
                raise ValueError(f"无效模型动作：{name}")
        except Exception as exc:
            return {"status": TaskStatus.tool_failed.value,
                    "reason": f"模型决策失败：{type(exc).__name__}: {exc}"}
        trace = list(state["trace"])
        if trace:
            trace[-1]["next_action"] = name
        trace.append(TraceStep(step=state["steps"] + 1, action=name,
                               parameters=action.get("args", {}),
                               decision_basis=str(action.get("reason", ""))[:200]).model_dump())
        return {"action": action, "steps": state["steps"] + 1, "trace": trace}

    def route_action(state: AgentState) -> str:
        if state["status"] is not None:
            return "end"
        if state["action"]["action"] in ("finish", "request_input"):
            return "finalize"
        if state["tool_calls"] >= state["max_tools"]:
            return "limit"
        return "tool"

    def limit_node(state: AgentState) -> dict:
        return {"status": TaskStatus.incomplete.value, "reason": "达到工具调用次数上限"}

    def tool_node(state: AgentState) -> dict:
        action = state["action"]
        name, args = action["action"], action.get("args", {})
        update: dict = {"tool_calls": state["tool_calls"] + 1}
        history = list(state["history"])
        trace = list(state["trace"])
        record = {"action": name, "args": args}
        try:
            if state["request"].get("failure_injection") == name and not state["injected"]:
                update["injected"] = True
                raise RuntimeError("注入的一次性工具故障")
            if name == "search":
                result = search_materials(str(args["query"]))
                update["retrieved"] = result["items"]
            elif name == "set_draft":
                draft = ScriptDraft.model_validate(args["draft"])
                result = {"saved_in_memory": True, "draft_version": state["draft_version"] + 1}
                update.update(draft=draft.model_dump(), draft_version=state["draft_version"] + 1,
                              duration=None, duration_version=-1, rules=None, rules_version=-1)
            elif name == "estimate":
                result = estimate_duration(state["draft"])
                update.update(duration=result, duration_version=state["draft_version"])
            elif name == "check":
                result = check_rules(state["draft"])
                update.update(rules=result, rules_version=state["draft_version"])
            else:
                raise ValueError(f"未知工具动作：{name}")
            record["result"] = result
            trace[-1]["result_summary"] = _summary(result)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["retried"] = any(h["action"] == name and h.get("error") for h in history)
            trace[-1]["result_summary"] = f"工具失败：{record['error']}"
        history.append(record)
        update.update(history=history, trace=trace)
        return update

    def finalize_node(state: AgentState) -> dict:
        action = state["action"]
        if action["action"] == "request_input":
            return {"status": TaskStatus.needs_input.value,
                    "missing_fields": action.get("args", {}).get("missing_fields", ["material"]),
                    "reason": "缺少完成脚本所需资料"}
        if state["history"] and state["history"][-1].get("error"):
            return {"status": TaskStatus.tool_failed.value,
                    "reason": f"工具故障未恢复：{state['history'][-1]['error']}"}
        draft = state["draft"]
        if not draft or not state["retrieved"]:
            return {"status": TaskStatus.incomplete.value, "reason": "未取得素材或脚本"}
        current = state["draft_version"]
        if state["duration_version"] != current or state["rules_version"] != current:
            return {"status": TaskStatus.incomplete.value, "reason": "当前脚本尚未完成复检"}
        if state["duration"]["total_seconds"] > state["request"]["target_duration_sec"]:
            return {"status": TaskStatus.incomplete.value, "reason": "脚本超过目标时长"}
        if not state["rules"]["passed"]:
            return {"status": TaskStatus.incomplete.value, "reason": "品牌或事实规则未通过"}
        ids = set(state["rules"]["material_ids"])
        if not ids or not ids <= {m["material_id"] for m in state["retrieved"]}:
            return {"status": TaskStatus.incomplete.value, "reason": "引用素材未在本次检索中取得"}
        return {"status": TaskStatus.completed.value, "reason": None}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tool", tool_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("limit", limit_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_action,
                                {"tool": "tool", "finalize": "finalize", "limit": "limit", "end": END})
    graph.add_edge("tool", "agent")
    graph.add_edge("finalize", END)
    graph.add_edge("limit", END)
    return graph.compile()


def run_agent(request: ScriptRequest, model_adapter=None) -> ScriptResponse:
    if request.missing_fields():
        return ScriptResponse(status=TaskStatus.needs_input, missing_fields=request.missing_fields(),
                              reason="缺少必需业务字段", model_mode=request.mode)
    if model_adapter is None:
        try:
            model_adapter = MockModel() if request.mode == "mock" else LiveModel()
        except Exception as exc:
            return ScriptResponse(status=TaskStatus.tool_failed, reason=str(exc), model_mode=request.mode)
    state: AgentState = {
        "request": request.model_dump(), "retrieved": [], "draft": None,
        "draft_version": 0, "duration": None, "duration_version": -1,
        "rules": None, "rules_version": -1, "steps": 0, "tool_calls": 0,
        "max_steps": int(os.getenv("MAX_AGENT_STEPS", "12")),
        "max_tools": int(os.getenv("MAX_TOOL_CALLS", "10")),
        "action": None, "history": [], "trace": [], "status": None,
        "reason": None, "missing_fields": [], "injected": False,
    }
    result = build_graph(model_adapter).invoke(state)
    draft = result["draft"] or {}
    return ScriptResponse(
        status=result["status"] or TaskStatus.incomplete.value,
        title=draft.get("title"), scenes=draft.get("scenes", []),
        estimated_duration_sec=(result["duration"] or {}).get("total_seconds"),
        material_ids=sorted({mid for scene in draft.get("scenes", [])
                             for mid in scene.get("material_ids", [])}),
        risks=(result["rules"] or {}).get("issues", []),
        missing_fields=result["missing_fields"], reason=result["reason"],
        trace=result["trace"], model_mode=request.mode,
    )
