from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.schemas.reference import ReferenceMention
from app.domain.schemas.shot_render import RenderSubmitReference


class ShotVideoSubmitRequest(BaseModel):
    prompt: str = Field(min_length=1)
    references: list[RenderSubmitReference] = Field(min_length=1)
    reference_mentions: list[ReferenceMention] = Field(default_factory=list)
    duration: int | None = Field(default=None, ge=4, le=15)
    resolution: Literal["480p", "720p"]
    model_type: Literal["standard", "fast"]


class ShotVideoVersionRead(BaseModel):
    id: str
    shot_id: str
    version_no: int
    status: str
    prompt_snapshot: dict[str, Any] | None = None
    params_snapshot: dict[str, Any] | None = None
    video_url: str | None = None
    last_frame_url: str | None = None
    provider_task_id: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    is_current: bool = False
