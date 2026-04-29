"""add character visual type and expanded roles

Revision ID: 20260429_role_visual
Revises: 20260428_char_turn_voice
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_role_visual"
down_revision = "20260428_char_turn_voice"
branch_labels = None
depends_on = None


ROLE_ENUM_WITH_LEGACY = "ENUM('protagonist','lead','supporting','antagonist','atmosphere','crowd','system')"
ROLE_ENUM_FINAL = "ENUM('lead','supporting','antagonist','atmosphere','crowd','system')"
ROLE_ENUM_DOWN = "ENUM('protagonist','supporting','atmosphere')"
VISUAL_ENUM = (
    "ENUM('human_actor','stylized_human','humanoid_monster','creature',"
    "'anomaly_entity','object_entity','crowd_group','environment_force')"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_WITH_LEGACY} NOT NULL DEFAULT 'supporting'")
    op.execute("UPDATE characters SET role_type = 'lead' WHERE role_type = 'protagonist'")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_FINAL} NOT NULL DEFAULT 'supporting'")
    op.add_column(
        "characters",
        sa.Column(
            "visual_type",
            sa.Enum(
                "human_actor",
                "stylized_human",
                "humanoid_monster",
                "creature",
                "anomaly_entity",
                "object_entity",
                "crowd_group",
                "environment_force",
                name="character_visual_type",
            ),
            nullable=False,
            server_default="human_actor",
        ),
    )
    # Best-effort legacy backfill. Old rows may need manual visual_type correction in the UI.
    op.execute("UPDATE characters SET visual_type = 'anomaly_entity' WHERE role_type = 'atmosphere' AND is_humanoid = false")
    op.execute(f"ALTER TABLE characters MODIFY visual_type {VISUAL_ENUM} NOT NULL")


def downgrade() -> None:
    op.drop_column("characters", "visual_type")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_WITH_LEGACY} NOT NULL DEFAULT 'supporting'")
    op.execute("UPDATE characters SET role_type = 'protagonist' WHERE role_type = 'lead'")
    op.execute("UPDATE characters SET role_type = 'atmosphere' WHERE role_type IN ('crowd','system')")
    op.execute("UPDATE characters SET role_type = 'supporting' WHERE role_type = 'antagonist'")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_DOWN} NOT NULL DEFAULT 'supporting'")
