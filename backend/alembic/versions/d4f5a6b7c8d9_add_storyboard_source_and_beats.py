"""add storyboard source and beats

Revision ID: d4f5a6b7c8d9
Revises: 9c0f12ab34cd
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d4f5a6b7c8d9"
down_revision: str | None = "9c0f12ab34cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("storyboards", sa.Column("source_excerpt", sa.Text(), nullable=True))
    op.add_column("storyboards", sa.Column("source_anchor", sa.JSON(), nullable=True))
    op.add_column("storyboards", sa.Column("beats", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("storyboards", "beats")
    op.drop_column("storyboards", "source_anchor")
    op.drop_column("storyboards", "source_excerpt")
