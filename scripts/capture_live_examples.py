"""Capture genuine model-driven HTTP runs after Qwen credentials are configured."""

import json
import os
import argparse
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app


ROOT = Path(__file__).resolve().parent.parent / "examples"
CASES = {
    "live_normal": {"topic": "字幕", "audience": "新手创作者", "platform": "抖音",
                    "target_duration_sec": 30, "style": "简洁", "mode": "live"},
    "live_no_material": {"topic": "登月火箭", "audience": "科普爱好者", "platform": "抖音",
                         "target_duration_sec": 30, "style": "简洁", "mode": "live"},
}


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=list(CASES), help="仅运行一个 live 用例")
    args = parser.parse_args()
    if not all(os.getenv(name) for name in ("QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL")):
        raise SystemExit("缺少真实千问配置；未生成 live 证据")
    client = TestClient(app)
    selected = {args.case: CASES[args.case]} if args.case else CASES
    for name, payload in selected.items():
        response = client.post("/v1/scripts/generate", json=payload)
        body = response.json()
        save(ROOT / "inputs" / f"{name}.json", payload)
        save(ROOT / "outputs" / f"{name}.json",
             {"http_status": response.status_code, "body": body})
        save(ROOT / "traces" / f"{name}.json", body.get("trace", []))
        print(f"{name}: {body['status']}; steps={len(body.get('trace', []))}")
    print("请人工核对两条 live Trace 的工具结果及模型后续动作；本脚本不预设其合格。")


if __name__ == "__main__":
    main()
