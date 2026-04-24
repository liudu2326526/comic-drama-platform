"""add project reference assets

Revision ID: 9c0f12ab34cd
Revises: 88f4e19a3f2d
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c0f12ab34cd"
down_revision: str | None = "88f4e19a3f2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_reference_assets",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("kind", sa.Enum("manual", name="project_reference_asset_kind"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_reference_assets_project_id", "project_reference_assets", ["project_id"])
    op.create_index(
        "ix_project_reference_assets_project_created",
        "project_reference_assets",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_reference_assets_project_created", table_name="project_reference_assets")
    op.drop_index("ix_project_reference_assets_project_id", table_name="project_reference_assets")
    op.drop_table("project_reference_assets")
