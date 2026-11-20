"""Pure domain rules, independent of HTTP and persistence."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime


class EventKind(str, Enum):
    intrusion = "intrusion"
    motion = "motion"
    camera_offline = "camera_offline"


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    camera_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    kind: EventKind
    confidence: float = Field(ge=0, le=1)
    zone: str = Field(min_length=1, max_length=80)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone")
        return value


def severity(event: EventIn) -> str:
    if event.kind == EventKind.camera_offline:
        return "warning"
    if event.kind == EventKind.intrusion and event.zone == "restricted" and event.confidence >= 0.8:
        return "critical"
    return "info"
