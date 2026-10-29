"""Deterministic local business tools with explicit evidence boundaries."""

import json
import math
import re
from pathlib import Path

from src.models import ScriptDraft


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def search_materials(query: str) -> dict:
    """Search synthetic facts; broad unrelated queries return no evidence."""
    query = query.strip().lower()
    if not query:
        return {"items": [], "count": 0}
    items = []
    for item in _read_json("materials.json"):
        terms = [item["name"], *item["tags"], *item["facts"]]
        if any(term.lower() in query or query in term.lower() for term in terms):
            items.append(item)
    return {"items": items, "count": len(items)}


def estimate_duration(draft: ScriptDraft | dict) -> dict:
    draft = ScriptDraft.model_validate(draft)
    speed = _read_json("brand_rules.json")["speech_chars_per_second"]
    per_scene = []
    for index, scene in enumerate(draft.scenes, 1):
        speech = re.sub(r"\s", "", scene.narration)
        speech_seconds = math.ceil(len(speech) / speed)
        duration = max(scene.planned_seconds, speech_seconds)
        per_scene.append({"scene": index, "planned_seconds": scene.planned_seconds,
                          "speech_seconds": speech_seconds, "estimated_seconds": duration})
    return {"per_scene": per_scene,
            "total_seconds": sum(x["estimated_seconds"] for x in per_scene)}


def check_rules(draft: ScriptDraft | dict) -> dict:
    draft = ScriptDraft.model_validate(draft)
    materials = {m["material_id"]: m for m in _read_json("materials.json")}
    rules = _read_json("brand_rules.json")
    issues = []
    used_ids = set()
    for number, scene in enumerate(draft.scenes, 1):
        text = f"{scene.shot} {scene.narration} {scene.subtitle}"
        used_ids.update(scene.material_ids)
        for phrase in rules["forbidden_phrases"]:
            if phrase in text:
                issues.append(f"镜头{number}含禁用表述：{phrase}")
        source_facts = [fact for mid in scene.material_ids if mid in materials
                        for fact in materials[mid]["facts"]]
        for phrase in rules["unsupported_ui_actions"]:
            if phrase in text and not any(phrase in fact for fact in source_facts):
                issues.append(f"镜头{number}含素材未证明的操作或能力：{phrase}")
        if re.search(rules["numeric_effect_pattern"], text):
            issues.append(f"镜头{number}含未经证明的量化效果宣称")
        for material_id in scene.material_ids:
            if material_id not in materials:
                issues.append(f"镜头{number}引用不存在的素材：{material_id}")
        if scene.material_ids and not scene.fact_claims:
            issues.append(f"镜头{number}引用素材但未登记事实原文")
        for claim in scene.fact_claims:
            if not any(claim in materials[mid]["facts"] for mid in scene.material_ids
                       if mid in materials):
                issues.append(f"镜头{number}事实无对应原文：{claim}")
            if claim not in text:
                issues.append(f"镜头{number}标注事实未出现在脚本：{claim}")
    return {"passed": not issues, "issues": issues, "material_ids": sorted(used_ids)}
