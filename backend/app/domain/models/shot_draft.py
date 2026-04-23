from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id


class ShotDraft(Base):
    __tablename__ = "shot_drafts"
    __table_args__ = (
        UniqueConstraint("shot_id", "version_no", name="uq_shot_drafts_shot_version"),
        Index("ix_shot_drafts_shot_id", "shot_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    references_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    optimizer_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
