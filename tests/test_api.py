from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)
BASE = {"topic": "字幕", "audience": "新手创作者", "platform": "抖音",
        "target_duration_sec": 30, "style": "简洁", "mode": "mock"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_http_generates_checked_script():
    response = client.post("/v1/scripts/generate", json=BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["estimated_duration_sec"] <= 30
    assert body["material_ids"] == ["P01"]
    assert body["model_mode"] == "mock"


def test_missing_business_input_and_invalid_type():
    missing = client.post("/v1/scripts/generate", json={"topic": "字幕", "mode": "mock"})
    assert missing.status_code == 200
    assert missing.json()["status"] == "needs_input"
    assert "target_duration_sec" in missing.json()["missing_fields"]
    invalid = client.post("/v1/scripts/generate", json=BASE | {"target_duration_sec": -1})
    assert invalid.status_code == 422
