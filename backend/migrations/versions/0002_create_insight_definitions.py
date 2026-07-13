"""create insight_definitions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insight_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("insight_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("from_table_name", sa.String(length=200), nullable=False),
        sa.Column("where_clause_template", sa.Text(), nullable=False),
        sa.Column("slot_definitions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_yaml_path", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_insight_definitions_insight_type",
        "insight_definitions",
        ["insight_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_insight_definitions_insight_type", table_name="insight_definitions")
    op.drop_table("insight_definitions")
