"""add style reference assets

Revision ID: e5f6a7b8c9d0
Revises: d4f5a6b7c8d9
Create Date: 2026-04-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JOB_KIND_VALUES = (
    "'parse_novel', 'gen_storyboard', 'extract_characters',"
    "'gen_character_asset', 'gen_character_asset_single',"
    "'gen_scene_asset', 'gen_scene_asset_single',"
    "'register_character_asset', 'lock_scene_asset',"
    "'gen_shot_draft',"
    "'render_shot', 'render_shot_video', 'render_batch', 'export_video',"
    "'gen_character_prompt_profile', 'gen_scene_prompt_profile',"
    "'regen_character_assets_batch', 'regen_scene_assets_batch',"
    "'gen_character_style_reference', 'gen_scene_style_reference'"
)

OLD_JOB_KIND_VALUES = (
    "'parse_novel', 'gen_storyboard', 'extract_characters',"
    "'gen_character_asset', 'gen_character_asset_single',"
    "'gen_scene_asset', 'gen_scene_asset_single',"
    "'register_character_asset', 'lock_scene_asset',"
    "'gen_shot_draft',"
    "'render_shot', 'render_shot_video', 'render_batch', 'export_video',"
    "'gen_character_prompt_profile', 'gen_scene_prompt_profile',"
    "'regen_character_assets_batch', 'regen_scene_assets_batch'"
)


def upgrade() -> None:
    op.add_column("projects", sa.Column("character_style_reference_image_url", sa.String(length=512), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_prompt", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_status", sa.String(length=32), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_error", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_image_url", sa.String(length=512), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_prompt", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_status", sa.String(length=32), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_error", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("full_body_image_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("headshot_image_url", sa.String(length=512), nullable=True))
    op.execute(f"ALTER TABLE jobs MODIFY COLUMN kind ENUM({JOB_KIND_VALUES}) NOT NULL")


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind IN ('gen_character_style_reference', 'gen_scene_style_reference')")
    op.execute(f"ALTER TABLE jobs MODIFY COLUMN kind ENUM({OLD_JOB_KIND_VALUES}) NOT NULL")
    op.drop_column("characters", "headshot_image_url")
    op.drop_column("characters", "full_body_image_url")
    op.drop_column("projects", "scene_style_reference_error")
    op.drop_column("projects", "scene_style_reference_status")
    op.drop_column("projects", "scene_style_reference_prompt")
    op.drop_column("projects", "scene_style_reference_image_url")
    op.drop_column("projects", "character_style_reference_error")
    op.drop_column("projects", "character_style_reference_status")
    op.drop_column("projects", "character_style_reference_prompt")
    op.drop_column("projects", "character_style_reference_image_url")
