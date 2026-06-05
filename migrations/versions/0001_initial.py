"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("tg_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("lang", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_gift_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sticker_file_id", sa.String(256), nullable=True),
        sa.Column("star_cost", sa.Integer(), nullable=False),
        sa.Column("markup_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_price_xtr", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("remaining_count", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tg_gift_id", name="uq_products_tg_gift_id"),
    )
    op.create_index("ix_products_tg_gift_id", "products", ["tg_gift_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "buyer_tg_id",
            sa.BigInteger(),
            sa.ForeignKey("users.tg_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recipient_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("price_xtr", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("invoice_payload", sa.String(64), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(128), nullable=True),
        sa.Column("delivered_message_id", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invoice_payload", name="uq_orders_invoice_payload"),
    )
    op.create_index("ix_orders_buyer_tg_id", "orders", ["buyer_tg_id"])
    op.create_index("ix_orders_product_id", "orders", ["product_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_invoice_payload", "orders", ["invoice_payload"])
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_admin_tg_id", "audit_log", ["admin_tg_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_admin_tg_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_index("ix_orders_invoice_payload", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_product_id", table_name="orders")
    op.drop_index("ix_orders_buyer_tg_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_products_tg_gift_id", table_name="products")
    op.drop_table("products")
    op.drop_table("users")
