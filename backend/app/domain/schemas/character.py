from pydantic import BaseModel, Field, model_validator
from typing import Any


class CharacterOut(BaseModel):
    id: str
    name: str
    role: str        # 中文展示值(lead→"主角" 等)
    role_type: str   # 原始 ENUM
    visual_type: str
    is_protagonist: bool
    locked: bool
    summary: str | None
    description: str | None
    meta: list[str] = []              # 前端展示串,由 meta/video_style_ref 摘要化
    reference_image_url: str | None   # 前端直接展示的 URL(aggregate 层用 OBS_PUBLIC_BASE_URL 拼)
    full_body_image_url: str | None = None
    headshot_image_url: str | None = None
    turnaround_image_url: str | None = None
    is_humanoid: bool = True
    voice_profile: dict[str, Any] | None = None
    voice_reference_audio_url: str | None = None
    voice_asset_id: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = None
    meta: dict[str, Any] | None = None
    role_type: str | None = None   # 允许从 supporting → atmosphere 等调整
    visual_type: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for f in ("name", "role_type", "visual_type"):
                if f in data and data[f] is None:
                    raise ValueError(f"{f} 不允许显式 null")
        return data


class CharacterGenerateRequest(BaseModel):
    # 允许前端手动追加"希望额外生成的角色 hint",MVP 可空
    extra_hints: list[str] = []


class CharacterLockRequest(BaseModel):
    as_protagonist: bool = False   # True → 触发 lock_protagonist


class GenerateJobAck(BaseModel):
    job_id: str
    sub_job_ids: list[str] = []
