"""character scene meta indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21 16:59:44.920787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy import inspect


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # characters 索引
    existing = {idx['name'] for idx in inspector.get_indexes('characters')}
    if 'ix_characters_project_protagonist_locked' not in existing:
        op.create_index('ix_characters_project_protagonist_locked', 'characters',
                        ['project_id', 'is_protagonist', 'locked'])
    if 'ix_characters_project_locked' not in existing:
        op.create_index('ix_characters_project_locked', 'characters',
                        ['project_id', 'locked'])
    
    # scenes 索引
    existing = {idx['name'] for idx in inspector.get_indexes('scenes')}
    if 'ix_scenes_project_locked' not in existing:
        op.create_index('ix_scenes_project_locked', 'scenes',
                        ['project_id', 'locked'])
    
    # storyboards 索引
    existing = {idx['name'] for idx in inspector.get_indexes('storyboards')}
    if 'ix_storyboards_project_scene' not in existing:
        op.create_index('ix_storyboards_project_scene', 'storyboards',
                        ['project_id', 'scene_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    existing = {idx['name'] for idx in inspector.get_indexes('storyboards')}
    if 'ix_storyboards_project_scene' in existing:
        op.drop_index('ix_storyboards_project_scene', table_name='storyboards')
    
    existing = {idx['name'] for idx in inspector.get_indexes('scenes')}
    if 'ix_scenes_project_locked' in existing:
        op.drop_index('ix_scenes_project_locked', table_name='scenes')
    
    existing = {idx['name'] for idx in inspector.get_indexes('characters')}
    if 'ix_characters_project_locked' in existing:
        op.drop_index('ix_characters_project_locked', table_name='characters')
    if 'ix_characters_project_protagonist_locked' in existing:
        op.drop_index('ix_characters_project_protagonist_locked', table_name='characters')
