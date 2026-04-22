from sqlalchemy import CHAR, DECIMAL, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

STORYBOARD_STATUS_VALUES = ["pending", "generating", "succeeded", "failed", "locked"]


class StoryboardShot(Base, TimestampMixin):
    __tablename__ = "storyboards"
    __table_args__ = (
        UniqueConstraint("project_id", "idx", name="uq_storyboards_project_idx"),
        Index("ix_storyboards_project_id", "project_id"),
        Index("ix_storyboards_scene_id", "scene_id"),
        Index("ix_storyboards_project_scene", "project_id", "scene_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(DECIMAL(4, 1), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*STORYBOARD_STATUS_VALUES, name="storyboard_status"),
        nullable=False,
        default="pending",
    )
    current_render_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
    # scene_id 的 FK 约束在 Alembic 0002 里显式加(需要 scenes 先建好)
    scene_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
