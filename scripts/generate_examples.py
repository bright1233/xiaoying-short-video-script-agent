"""Produce reproducible HTTP examples from the offline flow fixture."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app


ROOT = Path(__file__).resolve().parent.parent / "examples"
BASE = {"topic": "字幕", "audience": "新手创作者", "platform": "抖音",
        "target_duration_sec": 30, "style": "简洁", "mode": "mock"}
CASES = {
    "normal_overlength": BASE,
    "missing_input": BASE | {"style": None},
    "no_material": BASE | {"topic": "登月火箭"},
    "tool_failure": BASE | {"failure_injection": "estimate"},
    "rule_risk": BASE | {"target_duration_sec": 40, "mock_scenario": "rule_risk"},
}


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    client = TestClient(app)
    for name, payload in CASES.items():
        response = client.post("/v1/scripts/generate", json=payload)
        result = response.json()
        write_json(ROOT / "inputs" / f"{name}.json", payload)
        write_json(ROOT / "outputs" / f"{name}.json",
                   {"http_status": response.status_code, "body": result})
        write_json(ROOT / "traces" / f"{name}.json", result.get("trace", []))
        print(f"{name}: HTTP {response.status_code}, {result['status']}, "
              f"{len(result.get('trace', []))} steps")


if __name__ == "__main__":
    main()
