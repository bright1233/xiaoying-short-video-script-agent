"""Model decision adapters. The mock is a flow fixture, not model evidence."""

import json
import os
import re
from typing import Any


SYSTEM_PROMPT = """你是短视频脚本 Agent。每次仅输出一个 JSON 对象：
{"action":"search|set_draft|estimate|check|finish|request_input", "args":{}, "reason":"简短依据"}。
可用动作：search(args.query)，set_draft(args.draft)，estimate，check，finish，request_input(args.missing_fields)。
set_draft 的 args.draft 格式必须是：{"title":"标题","scenes":[{"shot":"画面","narration":"旁白","subtitle":"字幕","planned_seconds":8,"fact_claims":["支持字幕"],"material_ids":["P01"]}]}。
必须先检索素材，再写脚本。产品事实仅能使用检索到的 facts 原文；在场景 fact_claims 中逐条登记，并填写对应 material_ids。没有素材证据时，不描述具体产品界面、操作步骤或额外能力，例如点击入口、拖动控件、导出、一键、自动识别。
脚本不得虚构量化效果。每次 set_draft 后必须重新 estimate 和 check；通过且总时长不超过目标才可 finish。
检索为空时最多改写查询一次；连续两次为空必须 request_input，禁止第三次空检索。工具失败后可根据剩余步数重试或结束。
输出严格 JSON，不要 Markdown，不要内部推理。"""


class LiveModel:
    def __init__(self):
        from langchain_openai import ChatOpenAI

        key = os.getenv("QWEN_API_KEY")
        base_url = os.getenv("QWEN_BASE_URL")
        model = os.getenv("QWEN_MODEL")
        if not all((key, base_url, model)):
            raise ValueError("缺少 QWEN_API_KEY、QWEN_BASE_URL 或 QWEN_MODEL")
        self.model = ChatOpenAI(
            model=model, api_key=key, base_url=base_url,
            temperature=0, timeout=int(os.getenv("MODEL_TIMEOUT_SECONDS", "30")),
            max_retries=0,
        )

    def decide(self, state: dict[str, Any]) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage

        context = {
            "request": state["request"], "retrieved": state["retrieved"],
            "draft": state["draft"], "draft_version": state["draft_version"],
            "duration": state["duration"], "rules": state["rules"],
            "observations": state["history"][-5:],
            "search_queries": [h["args"].get("query") for h in state["history"]
                               if h["action"] == "search"],
            "steps_left": state["max_steps"] - state["steps"],
            "tools_left": state["max_tools"] - state["tool_calls"],
        }
        response = self.model.bind(response_format={"type": "json_object"}).invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, ensure_ascii=False)),
        ])
        content = response.content
        if not isinstance(content, str):
            raise ValueError("模型未返回文本动作")
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        decision = json.loads(content)
        if not isinstance(decision, dict):
            raise ValueError("模型动作不是 JSON 对象")
        return decision


class MockModel:
    """Deterministic test fixture; never described as live decision evidence."""

    def decide(self, state: dict[str, Any]) -> dict:
        req = state["request"]
        last = state["history"][-1] if state["history"] else None
        if last and last.get("error"):
            if not last.get("retried") and state["steps"] < state["max_steps"] - 1:
                return {"action": last["action"], "args": last["args"], "reason": "工具失败，重试一次"}
            return {"action": "finish", "args": {}, "reason": "工具仍不可用"}
        if not state["retrieved"]:
            searches = sum(h["action"] == "search" for h in state["history"])
            if searches >= 1:
                return {"action": "request_input", "args": {"missing_fields": ["material"]},
                        "reason": "检索无素材，请求补充资料"}
            return {"action": "search", "args": {"query": req["topic"]},
                    "reason": "查找可引用的素材事实"}
        if not state["draft"]:
            material = state["retrieved"][0]
            fact = material["facts"][0]
            initial = 38 if req["target_duration_sec"] == 30 else min(req["target_duration_sec"], 24)
            first = max(1, initial // 2)
            second = max(1, initial - first)
            draft = {"title": f"{req['topic']}：快速了解", "scenes": [
                {"shot": "展示创作场景", "narration": f"{fact}，一起看看如何呈现。",
                 "subtitle": fact, "planned_seconds": first,
                 "fact_claims": [fact], "material_ids": [material["material_id"]]},
                {"shot": "展示画面结果", "narration": "根据内容需要调整画面。",
                 "subtitle": "继续创作", "planned_seconds": second,
                 "fact_claims": [], "material_ids": []}]}
            if req.get("mock_scenario") == "rule_risk":
                draft["scenes"][0]["narration"] += "效率提升80%。"
            return {"action": "set_draft", "args": {"draft": draft}, "reason": "依据检索事实形成初稿"}
        if state["duration_version"] != state["draft_version"]:
            return {"action": "estimate", "args": {}, "reason": "当前脚本尚未估时"}
        if state["duration"]["total_seconds"] > req["target_duration_sec"]:
            draft = json.loads(json.dumps(state["draft"], ensure_ascii=False))
            target = req["target_duration_sec"]
            first = max(1, target // 2)
            draft["scenes"][0]["planned_seconds"] = first
            draft["scenes"][1]["planned_seconds"] = max(1, target - first)
            draft["scenes"][0]["narration"] = draft["scenes"][0]["fact_claims"][0]
            draft["scenes"][1]["narration"] = "继续创作"
            return {"action": "set_draft", "args": {"draft": draft}, "reason": "估时超限，压缩分镜与旁白"}
        if state["rules_version"] != state["draft_version"]:
            return {"action": "check", "args": {}, "reason": "当前脚本尚未检查规则"}
        if not state["rules"]["passed"]:
            draft = json.loads(json.dumps(state["draft"], ensure_ascii=False))
            for scene in draft["scenes"]:
                scene["narration"] = scene["narration"].replace("效率提升80%。", "")
            return {"action": "set_draft", "args": {"draft": draft},
                    "reason": "规则指出量化宣称缺少依据，删除后复检"}
        return {"action": "finish", "args": {}, "reason": "当前版本通过时长和规则检查"}
