import pytest
from pydantic import ValidationError

from src.models import ScriptRequest, ScriptResponse, TaskStatus


def test_missing_business_fields_are_explicit():
    request = ScriptRequest(topic="字幕", audience=" ", platform="抖音", style="简洁")
    assert request.missing_fields() == ["audience", "target_duration_sec"]


def test_invalid_duration_and_mode_are_rejected():
    with pytest.raises(ValidationError):
        ScriptRequest(target_duration_sec=0)
    with pytest.raises(ValidationError):
        ScriptRequest(mode="pretend-live")


def test_status_and_mode_are_separate():
    response = ScriptResponse(status=TaskStatus.needs_input, model_mode="mock")
    assert response.status == "needs_input"
    assert response.model_mode == "mock"
