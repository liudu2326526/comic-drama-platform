"""add extract_characters job kind

Revision ID: 1b4e5fd2c7a9
Revises: 125f8a6404de
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1b4e5fd2c7a9"
down_revision: Union[str, None] = "125f8a6404de"
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
            'render_shot', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'render_shot', 'render_batch', 'export_video'
        ) NOT NULL
        """
    )
