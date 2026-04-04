"""Initial commands module schema.

Revision ID: 001
Revises: -
Create Date: 2026-04-04

Creates tables: commands_settings, orders_kitchen_station, orders_order,
orders_order_item, orders_order_modifier, orders_product_station,
orders_category_station.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CommandsSettings
    op.create_table(
        "commands_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_print_tickets", sa.Boolean(), server_default="true"),
        sa.Column("show_prep_time", sa.Boolean(), server_default="true"),
        sa.Column("alert_threshold_minutes", sa.Integer(), server_default="15"),
        sa.Column("use_rounds", sa.Boolean(), server_default="true"),
        sa.Column("auto_fire_on_round", sa.Boolean(), server_default="false"),
        sa.Column("default_order_type", sa.String(20), server_default="dine_in"),
        sa.Column("sound_on_new_order", sa.Boolean(), server_default="true"),
        sa.UniqueConstraint("hub_id", name="uq_commands_settings_hub"),
    )

    # KitchenStation
    op.create_table(
        "orders_kitchen_station",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_es", sa.String(100), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("color", sa.String(7), server_default="#F97316"),
        sa.Column("icon", sa.String(50), server_default="flame-outline"),
        sa.Column("printer_name", sa.String(100), server_default=""),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.UniqueConstraint("hub_id", "name", name="uq_kitchen_station_hub_name"),
    )
    op.create_index("ix_kitchen_station_hub_active", "orders_kitchen_station", ["hub_id", "is_active"])

    # Order
    op.create_table(
        "orders_order",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_number", sa.String(50), nullable=False, index=True),
        sa.Column("table_id", sa.Uuid(), sa.ForeignKey("tables_table.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sale_id", sa.Uuid(), sa.ForeignKey("sales_sale.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers_customer.id", ondelete="SET NULL"), nullable=True),
        sa.Column("waiter_id", sa.Uuid(), nullable=True),
        sa.Column("order_type", sa.String(20), server_default="dine_in"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("round_number", sa.Integer(), server_default="1"),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("subtotal", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("tax", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("discount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("total", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_orders_order_hub_status", "orders_order", ["hub_id", "status"])
    op.create_index("ix_orders_order_hub_created", "orders_order", ["hub_id", "created_at"])
    op.create_index("ix_orders_order_hub_type", "orders_order", ["hub_id", "order_type"])

    # OrderItem
    op.create_table(
        "orders_order_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("station_id", sa.Uuid(), sa.ForeignKey("orders_kitchen_station.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("quantity", sa.Integer(), server_default="1"),
        sa.Column("total", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("modifiers", sa.Text(), server_default=""),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("seat_number", sa.Integer(), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_order_item_status", "orders_order_item", ["hub_id", "status"])
    op.create_index("ix_order_item_station_status", "orders_order_item", ["hub_id", "station_id", "status"])

    # OrderModifier
    op.create_table(
        "orders_order_modifier",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_item_id", sa.Uuid(), sa.ForeignKey("orders_order_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), server_default="0.00"),
    )

    # ProductStation
    op.create_table(
        "orders_product_station",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), sa.ForeignKey("orders_kitchen_station.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("hub_id", "product_id", name="uq_product_station_hub_product"),
    )

    # CategoryStation
    op.create_table(
        "orders_category_station",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), sa.ForeignKey("orders_kitchen_station.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("hub_id", "category_id", name="uq_category_station_hub_category"),
    )


def downgrade() -> None:
    op.drop_table("orders_category_station")
    op.drop_table("orders_product_station")
    op.drop_table("orders_order_modifier")
    op.drop_table("orders_order_item")
    op.drop_table("orders_order")
    op.drop_table("orders_kitchen_station")
    op.drop_table("commands_settings")
