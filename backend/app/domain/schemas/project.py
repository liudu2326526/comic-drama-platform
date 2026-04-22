from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from typing import Any


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    story: str = Field(..., min_length=1)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str = Field(default="9:16", min_length=1, max_length=16)
    # 与 spec §13 和 ProjectDetail.setupParams 一致:字符串数组,后端零转换直存直出
    setup_params: list[str] | None = None

    @model_validator(mode="after")
    def _reject_blank(self) -> "ProjectCreate":
        if not self.name.strip():
            raise ValueError("name 不能为空白")
        return self


class ProjectUpdate(BaseModel):
    """
    PATCH 语义:字段「可省略但不可显式 null」。

    - 省略字段  → model_dump(exclude_unset=True) 里没有这个 key,service 层不 setattr
    - 传字符串 → 按新值写入
    - 传 null   → 422(Pydantic validator 拒绝)
    """
    name: str | None = Field(default=None, min_length=1, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str | None = Field(default=None, min_length=1, max_length=16)
    setup_params: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field in ("name", "genre", "ratio", "setup_params"):
            if field in data and data[field] is None:
                raise ValueError(f"{field} 不允许显式为 null;若不想修改请省略该字段")
        return data


    @model_validator(mode="after")
    def _reject_blank(self) -> "ProjectUpdate":
        if self.name is not None and not self.name.strip():
            raise ValueError("name 不能为空白")
        if self.ratio is not None and not self.ratio.strip():
            raise ValueError("ratio 不能为空白")
        return self


class ProjectSummary(BaseModel):
    id: str
    name: str
    stage: str              # 中文
    stage_raw: str          # 英文 ENUM
    genre: str | None
    ratio: str
    storyboard_count: int = 0
    character_count: int = 0
    scene_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    id: str
    name: str
    stage: str
    stage_raw: str
    genre: str | None
    ratio: str
    suggestedShots: str = ""
    story: str
    summary: str = ""
    parsedStats: list[str] = []
    setupParams: list[str] = []
    projectOverview: str = ""
    storyboards: list = []
    characters: list = []
    scenes: list = []
    generationProgress: str = "0 / 0 已完成"
    generationNotes: dict = {"input": "", "suggestion": ""}
    generationQueue: list = []
    exportConfig: list[str] = []
    exportDuration: str = ""
    exportTasks: list = []


class ProjectRollbackRequest(BaseModel):
    to_stage: str


class InvalidatedSummary(BaseModel):
    shots_reset: int = 0
    characters_unlocked: int = 0
    scenes_unlocked: int = 0


class ProjectRollbackResponse(BaseModel):
    from_stage: str
    to_stage: str
    invalidated: InvalidatedSummary


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
    page: int
    page_size: int
