"""add sticker_emoji and sticker_custom_emoji_id to products

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("sticker_emoji", sa.String(16), nullable=True))
        batch.add_column(sa.Column("sticker_custom_emoji_id", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("sticker_custom_emoji_id")
        batch.drop_column("sticker_emoji")
