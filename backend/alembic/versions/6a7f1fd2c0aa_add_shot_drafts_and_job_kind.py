"""add shot drafts and job kind

Revision ID: 6a7f1fd2c0aa
Revises: f8c1f7b6d3aa
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a7f1fd2c0aa"
down_revision: Union[str, None] = "f8c1f7b6d3aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard', 'extract_characters',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'gen_shot_draft',
            'render_shot', 'render_shot_video', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )

    op.create_table(
        "shot_drafts",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("shot_id", sa.CHAR(length=26), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("references_snapshot", sa.JSON(), nullable=True),
        sa.Column("optimizer_snapshot", sa.JSON(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shot_id"], ["storyboards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_id", "version_no", name="uq_shot_drafts_shot_version"),
    )
    op.create_index("ix_shot_drafts_shot_id", "shot_drafts", ["shot_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shot_drafts_shot_id", table_name="shot_drafts")
    op.drop_table("shot_drafts")
    op.execute("DELETE FROM jobs WHERE kind = 'gen_shot_draft'")
    op.execute(
        """
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard', 'extract_characters',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'render_shot', 'render_shot_video', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )
