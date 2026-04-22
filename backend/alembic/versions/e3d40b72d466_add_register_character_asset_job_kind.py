"""add register_character_asset job kind

Revision ID: e3d40b72d466
Revises: 9127e4141b71
Create Date: 2026-04-22 14:37:34.618717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3d40b72d466'
down_revision: Union[str, None] = '9127e4141b71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 修改 Enum 字段, 增加 'register_character_asset'
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel',
            'gen_storyboard',
            'gen_character_asset',
            'gen_character_asset_single',
            'gen_scene_asset',
            'gen_scene_asset_single',
            'register_character_asset',
            'render_shot',
            'render_batch',
            'export_video'
        ) NOT NULL
    """)


def downgrade() -> None:
    # 回滚前清理该类型的 job
    op.execute("DELETE FROM jobs WHERE kind = 'register_character_asset'")
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel',
            'gen_storyboard',
            'gen_character_asset',
            'gen_character_asset_single',
            'gen_scene_asset',
            'gen_scene_asset_single',
            'render_shot',
            'render_batch',
            'export_video'
        ) NOT NULL
    """)
