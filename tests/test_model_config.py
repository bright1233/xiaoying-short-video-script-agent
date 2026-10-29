from pathlib import Path

import pytest

from src.model_adapter import LiveModel


def test_example_config_selects_qwen_flash_and_beijing_endpoint():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "QWEN_MODEL=qwen3.8-flash" in text
    assert "QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1" in text
    assert "QWEN_API_KEY=\n" in text


def test_live_adapter_requires_local_key(monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    with pytest.raises(ValueError, match="QWEN_API_KEY"):
        LiveModel()


def test_live_adapter_requests_json_object_response():
    class FakeResponse:
        content = '{"action":"search","args":{"query":"字幕"},"reason":"检索"}'

    class FakeModel:
        def __init__(self):
            self.bound = None

        def bind(self, **kwargs):
            self.bound = kwargs
            return self

        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    adapter = LiveModel.__new__(LiveModel)
    adapter.model = FakeModel()
    state = {"request": {}, "retrieved": [], "draft": None, "draft_version": 0,
             "duration": None, "rules": None, "history": [], "max_steps": 12,
             "steps": 0, "max_tools": 10, "tool_calls": 0}
    assert adapter.decide(state)["action"] == "search"
    assert adapter.model.bound == {"response_format": {"type": "json_object"}}
