"""broadcasts

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("media_file_id", sa.String(256), nullable=True),
        sa.Column("media_type", sa.String(16), nullable=True),
        sa.Column("target", sa.String(16), nullable=False, server_default="all"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broadcasts_author_tg_id", "broadcasts", ["author_tg_id"])
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_broadcasts_status", table_name="broadcasts")
    op.drop_index("ix_broadcasts_author_tg_id", table_name="broadcasts")
    op.drop_table("broadcasts")
