from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    story: str = Field(..., min_length=1)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str = Field(default="9:16", max_length=16)
    # 与 spec §13 和 ProjectDetail.setupParams 一致:list[str]
    setup_params: list[str] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str | None = Field(default=None, max_length=16)
    setup_params: list[str] | None = None


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
