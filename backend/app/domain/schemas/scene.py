from pydantic import BaseModel, Field, model_validator
from typing import Any


class SceneOut(BaseModel):
    id: str
    name: str
    theme: str | None
    summary: str | None
    description: str | None
    meta: list[str] = []              # 前端展示串,由 meta 摘要化
    locked: bool
    template_id: str | None
    reference_image_url: str | None
    usage: str   # "场景复用 N 镜头"(由 aggregate 拼;单条接口也返回)


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    theme: str | None = Field(default=None, max_length=32)
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = None
    meta: dict[str, Any] | None = None
    template_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for f in ("name", "theme", "template_id"):
                if f in data and data[f] is None:
                    raise ValueError(f"{f} 不允许显式 null")
        return data


class SceneGenerateRequest(BaseModel):
    template_whitelist: list[str] = []    # 限定模板;空 = 不限


class SceneLockRequest(BaseModel):
    pass


class GenerateJobAck(BaseModel):
    job_id: str
    sub_job_ids: list[str] = []
