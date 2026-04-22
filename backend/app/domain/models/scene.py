from sqlalchemy import Boolean, CHAR, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"
    __table_args__ = (
        Index("ix_scenes_project_id", "project_id"),
        Index("ix_scenes_project_locked", "project_id", "locked"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    theme: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_style_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
