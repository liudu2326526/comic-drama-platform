"""add shot video renders

Revision ID: f8c1f7b6d3aa
Revises: 1b4e5fd2c7a9
Create Date: 2026-04-23 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8c1f7b6d3aa"
down_revision: Union[str, None] = "1b4e5fd2c7a9"
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
            'render_shot', 'render_shot_video', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )
    op.add_column("storyboards", sa.Column("current_video_render_id", sa.CHAR(length=26), nullable=True))
    op.create_table(
        "shot_video_renders",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("shot_id", sa.CHAR(length=26), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "succeeded", "failed", name="shot_video_render_status"),
            nullable=False,
        ),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=True),
        sa.Column("params_snapshot", sa.JSON(), nullable=True),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("last_frame_url", sa.String(length=512), nullable=True),
        sa.Column("provider_task_id", sa.String(length=128), nullable=True),
        sa.Column("provider_status", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["shot_id"], ["storyboards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_id", "version_no", name="uq_shot_video_renders_shot_version"),
    )
    op.create_index("ix_shot_video_renders_shot_id", "shot_video_renders", ["shot_id"], unique=False)
    op.create_index("ix_shot_video_renders_provider_task_id", "shot_video_renders", ["provider_task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shot_video_renders_provider_task_id", table_name="shot_video_renders")
    op.drop_index("ix_shot_video_renders_shot_id", table_name="shot_video_renders")
    op.drop_table("shot_video_renders")
    op.drop_column("storyboards", "current_video_render_id")
    op.execute("DELETE FROM jobs WHERE kind = 'render_shot_video'")
    op.execute(
        """
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard', 'extract_characters',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'render_shot', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )
