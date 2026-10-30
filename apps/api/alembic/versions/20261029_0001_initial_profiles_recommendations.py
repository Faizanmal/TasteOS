"""Initial taste_profiles and recommendations tables.

Revision ID: 20261029_0001
Revises:
Create Date: 2026-10-29

Idempotent: skips create when tables already exist (create_all / prior runs).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261029_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "taste_profiles" not in existing:
        op.create_table(
            "taste_profiles",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("favorites", sa.JSON(), nullable=False),
            sa.Column("preferred_domains", sa.JSON(), nullable=False),
            sa.Column("exclusions", sa.JSON(), nullable=False),
            sa.Column("explicit_preferences", sa.JSON(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "is_demo", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "recommendations" not in existing:
        op.create_table(
            "recommendations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("response_payload", sa.JSON(), nullable=False),
            sa.Column("rejected_entity_ids", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if "recommendations" in existing:
        op.drop_table("recommendations")
    if "taste_profiles" in existing:
        op.drop_table("taste_profiles")
