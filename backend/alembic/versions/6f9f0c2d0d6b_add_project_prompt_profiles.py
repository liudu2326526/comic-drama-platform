"""add project prompt profiles

Revision ID: 6f9f0c2d0d6b
Revises: 1b4e5fd2c7a9
Create Date: 2026-04-23 18:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f9f0c2d0d6b"
down_revision: Union[str, None] = "1b4e5fd2c7a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("character_prompt_profile_draft", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("character_prompt_profile_applied", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("scene_prompt_profile_draft", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("scene_prompt_profile_applied", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "scene_prompt_profile_applied")
    op.drop_column("projects", "scene_prompt_profile_draft")
    op.drop_column("projects", "character_prompt_profile_applied")
    op.drop_column("projects", "character_prompt_profile_draft")
