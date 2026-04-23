"""add prompt profile job kinds

Revision ID: 88f4e19a3f2d
Revises: 6f9f0c2d0d6b
Create Date: 2026-04-23 18:30:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "88f4e19a3f2d"
down_revision: Union[str, None] = "6f9f0c2d0d6b"
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
            'render_shot', 'render_shot_video', 'render_batch', 'export_video',
            'gen_character_prompt_profile', 'gen_scene_prompt_profile',
            'regen_character_assets_batch', 'regen_scene_assets_batch'
        ) NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind IN ('gen_character_prompt_profile', 'gen_scene_prompt_profile', 'regen_character_assets_batch', 'regen_scene_assets_batch')")
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
