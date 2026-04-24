from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.schemas.reference import ReferenceMention


class RenderVersionRead(BaseModel):
    id: str
    shot_id: str
    version_no: int
    status: str
    prompt_snapshot: dict[str, Any] | None = None
    image_url: str | None = None
    provider_task_id: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    is_current: bool = False


class RenderDraftReferenceRead(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    image_url: str
    reason: str


class RenderDraftRead(BaseModel):
    shot_id: str
    prompt: str
    references: list[RenderDraftReferenceRead]


class RenderSubmitReference(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    image_url: str
    alias: str | None = None
    mention_key: str | None = None
    origin: str | None = None


class RenderSubmitRequest(BaseModel):
    prompt: str
    references: list[RenderSubmitReference]
    reference_mentions: list[ReferenceMention] = Field(default_factory=list)
