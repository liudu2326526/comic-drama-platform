from sqlalchemy import Boolean, CHAR, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

CHARACTER_ROLE_VALUES = ["protagonist", "supporting", "atmosphere"]


class Character(Base, TimestampMixin):
    __tablename__ = "characters"
    __table_args__ = (Index("ix_characters_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    role_type: Mapped[str] = mapped_column(
        Enum(*CHARACTER_ROLE_VALUES, name="character_role_type"),
        nullable=False,
        default="supporting",
    )
    is_protagonist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_style_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
