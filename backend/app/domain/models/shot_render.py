from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

SHOT_RENDER_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ShotRender(Base):
    """镜头生成版本历史。M2 仅建表,不写入业务数据(M3b 起使用)。"""

    __tablename__ = "shot_renders"
    __table_args__ = (
        UniqueConstraint("shot_id", "version_no", name="uq_shot_renders_shot_version"),
        Index("ix_shot_renders_shot_id", "shot_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*SHOT_RENDER_STATUS_VALUES, name="shot_render_status"),
        nullable=False,
        default="queued",
    )
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ShotCharacterRef(Base):
    """storyboards ⇄ characters 多对多。复合主键 (shot_id, character_id)。"""

    __tablename__ = "shot_character_refs"

    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True
    )
