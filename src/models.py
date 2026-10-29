"""Public API contracts and script structures."""

from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    completed = "completed"
    needs_input = "needs_input"
    incomplete = "incomplete"
    tool_failed = "tool_failed"


class ScriptRequest(BaseModel):
    topic: str | None = None
    audience: str | None = None
    platform: str | None = None
    target_duration_sec: int | None = Field(default=None, gt=0, le=300)
    style: str | None = None
    mode: str = Field(default="live", pattern="^(live|mock)$")
    mock_scenario: str | None = Field(default=None, pattern="^rule_risk$")
    failure_injection: str | None = Field(default=None, pattern="^(search|estimate|check)$")

    def missing_fields(self) -> list[str]:
        names = ("topic", "audience", "platform", "target_duration_sec", "style")
        return [name for name in names if getattr(self, name) is None or
                (isinstance(getattr(self, name), str) and not getattr(self, name).strip())]


class Scene(BaseModel):
    shot: str = Field(min_length=1)
    narration: str = ""
    subtitle: str = ""
    planned_seconds: int = Field(gt=0)
    fact_claims: list[str] = Field(default_factory=list)
    material_ids: list[str] = Field(default_factory=list)


class ScriptDraft(BaseModel):
    title: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)


class TraceStep(BaseModel):
    step: int
    action: str
    parameters: dict = Field(default_factory=dict)
    result_summary: str = ""
    next_action: str | None = None
    decision_basis: str = ""


class ScriptResponse(BaseModel):
    status: TaskStatus
    title: str | None = None
    scenes: list[Scene] = Field(default_factory=list)
    estimated_duration_sec: int | None = None
    material_ids: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    reason: str | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    model_mode: str
