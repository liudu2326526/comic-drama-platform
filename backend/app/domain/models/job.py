from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

JOB_KIND_VALUES = [
    "parse_novel",
    "gen_storyboard",
    "extract_characters",
    "gen_character_asset",
    "gen_character_asset_single",
    "gen_scene_asset",
    "gen_scene_asset_single",
    "register_character_asset",
    "lock_scene_asset",
    "render_shot",
    "render_batch",
    "export_video",
    "gen_character_prompt_profile",
    "gen_scene_prompt_profile",
    "regen_character_assets_batch",
    "regen_scene_assets_batch",
]
JOB_STATUS_VALUES = ["queued", "running", "succeeded", "failed", "canceled"]


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        CHAR(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    parent_id: Mapped[str | None] = mapped_column(
        CHAR(26),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(Enum(*JOB_KIND_VALUES, name="job_kind"), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*JOB_STATUS_VALUES, name="job_status"), nullable=False, default="queued"
    )
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    done: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
