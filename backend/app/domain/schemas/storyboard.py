from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any

class StoryboardCreate(BaseModel):
    title: str = Field(default="", max_length=128)
    description: str = Field(default="", min_length=0)
    detail: Optional[str] = None
    duration_sec: Optional[float] = Field(default=None, ge=0, le=300)
    tags: Optional[list[str]] = None
    source_excerpt: Optional[str] = None
    source_anchor: Optional[dict[str, Any]] = None
    beats: Optional[list[dict[str, Any]]] = None
    idx: Optional[int] = Field(default=None, ge=1, le=999)

class StoryboardUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    detail: Optional[str] = None
    duration_sec: Optional[float] = Field(None, ge=0, le=300)
    tags: Optional[list[str]] = None
    source_excerpt: Optional[str] = None
    source_anchor: Optional[dict[str, Any]] = None
    beats: Optional[list[dict[str, Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field in ("title", "description", "duration_sec", "tags", "source_anchor", "beats"):
            if field in data and data[field] is None:
                raise ValueError(f"{field} 不允许显式为 null")
        return data

class StoryboardReorderRequest(BaseModel):
    ordered_ids: list[str] = Field(..., min_length=1)

class BindSceneRequest(BaseModel):
    scene_id: str = Field(..., min_length=1)

class BindSceneResponse(BaseModel):
    shot_id: str
    scene_id: str
    scene_name: str
