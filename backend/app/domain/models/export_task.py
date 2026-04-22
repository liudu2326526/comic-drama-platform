from datetime import datetime

from sqlalchemy import CHAR, DECIMAL, DateTime, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

EXPORT_TASK_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ExportTask(Base):
    """M2 建表占位,M4 使用。"""

    __tablename__ = "export_tasks"
    __table_args__ = (Index("ix_export_tasks_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Enum(*EXPORT_TASK_STATUS_VALUES, name="export_task_status"),
        nullable=False,
        default="queued",
    )
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(DECIMAL(6, 1), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExportShotSnapshot(Base):
    """导出的镜头版本快照,复合主键 (export_task_id, shot_id)。"""

    __tablename__ = "export_shot_snapshots"

    export_task_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("export_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), primary_key=True
    )
    render_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("shot_renders.id", ondelete="RESTRICT"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
