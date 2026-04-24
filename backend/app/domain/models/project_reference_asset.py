from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

PROJECT_REFERENCE_ASSET_KIND_VALUES = ["manual"]


class ProjectReferenceAsset(Base):
    __tablename__ = "project_reference_assets"
    __table_args__ = (
        Index("ix_project_reference_assets_project_id", "project_id"),
        Index("ix_project_reference_assets_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Enum(*PROJECT_REFERENCE_ASSET_KIND_VALUES, name="project_reference_asset_kind"),
        nullable=False,
        default="manual",
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
