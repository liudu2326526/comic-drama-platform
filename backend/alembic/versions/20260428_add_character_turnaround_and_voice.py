"""add character turnaround and voice metadata

Revision ID: 20260428_char_turn_voice
Revises: e5f6a7b8c9d0
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260428_char_turn_voice"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("turnaround_image_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("is_humanoid", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("characters", sa.Column("voice_profile", sa.JSON(), nullable=True))
    op.add_column("characters", sa.Column("voice_reference_audio_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("voice_asset_id", sa.String(length=128), nullable=True))
    op.execute("UPDATE characters SET is_humanoid = false WHERE role_type = 'atmosphere'")
    op.alter_column("characters", "is_humanoid", server_default=None)


def downgrade() -> None:
    op.drop_column("characters", "voice_asset_id")
    op.drop_column("characters", "voice_reference_audio_url")
    op.drop_column("characters", "voice_profile")
    op.drop_column("characters", "is_humanoid")
    op.drop_column("characters", "turnaround_image_url")
