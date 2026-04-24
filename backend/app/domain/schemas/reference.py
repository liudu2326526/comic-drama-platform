from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ReferenceOrigin(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    HISTORY = "history"


class ReferenceCandidateRead(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    alias: str
    mention_key: str
    image_url: str
    origin: ReferenceOrigin = ReferenceOrigin.AUTO
    reason: str | None = None


class ReferenceAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    image_url: str = Field(min_length=1)
    kind: Literal["manual"] = "manual"


class ReferenceMention(BaseModel):
    mention_key: str
    label: str
