from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

SHOT_VIDEO_RENDER_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ShotVideoRender(Base):
    __tablename__ = "shot_video_renders"
    __table_args__ = (
        UniqueConstraint("shot_id", "version_no", name="uq_shot_video_renders_shot_version"),
        Index("ix_shot_video_renders_shot_id", "shot_id"),
        Index("ix_shot_video_renders_provider_task_id", "provider_task_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*SHOT_VIDEO_RENDER_STATUS_VALUES, name="shot_video_render_status"),
        nullable=False,
        default="queued",
    )
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    params_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_frame_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
