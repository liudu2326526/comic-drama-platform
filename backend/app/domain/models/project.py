from sqlalchemy import CHAR, Enum, JSON, SmallInteger, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id
from app.pipeline.states import ProjectStageRaw

STAGE_VALUES = [s.value for s in ProjectStageRaw]


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(
        Enum(*STAGE_VALUES, name="project_stage"),
        nullable=False,
        default=ProjectStageRaw.DRAFT.value,
    )
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ratio: Mapped[str] = mapped_column(String(16), default="9:16", nullable=False)
    story: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_stats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    setup_params: Mapped[list | None] = mapped_column(JSON, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_shots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
