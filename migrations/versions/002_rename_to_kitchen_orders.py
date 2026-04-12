"""Rename all orders_* tables to kitchen_orders_* and update MODULE_ID.

Revision ID: 002
Revises: 001
Create Date: 2026-04-12

BREAKING: MODULE_ID changed from 'commands' to 'kitchen_orders'.
Tables renamed:
  commands_settings        -> kitchen_orders_settings
  orders_kitchen_station   -> kitchen_orders_station
  orders_order             -> kitchen_orders_order
  orders_order_item        -> kitchen_orders_order_item
  orders_order_modifier    -> kitchen_orders_order_modifier
  orders_product_station   -> kitchen_orders_product_station
  orders_category_station  -> kitchen_orders_category_station

Constraints and indexes are recreated under new names.
No data is lost — only table and constraint names change.
"""

from __future__ import annotations

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Drop FK constraints that reference tables we are about to rename
    # -----------------------------------------------------------------------
    # orders_order_item references orders_order and orders_kitchen_station
    with op.batch_alter_table("orders_order_item") as batch_op:
        batch_op.drop_constraint("orders_order_item_order_id_fkey", type_="foreignkey")
        batch_op.drop_constraint("orders_order_item_station_id_fkey", type_="foreignkey")

    # orders_order_modifier references orders_order_item
    with op.batch_alter_table("orders_order_modifier") as batch_op:
        batch_op.drop_constraint("orders_order_modifier_order_item_id_fkey", type_="foreignkey")

    # orders_product_station references orders_kitchen_station
    with op.batch_alter_table("orders_product_station") as batch_op:
        batch_op.drop_constraint("orders_product_station_station_id_fkey", type_="foreignkey")

    # orders_category_station references orders_kitchen_station
    with op.batch_alter_table("orders_category_station") as batch_op:
        batch_op.drop_constraint("orders_category_station_station_id_fkey", type_="foreignkey")

    # -----------------------------------------------------------------------
    # 2. Drop old indexes
    # -----------------------------------------------------------------------
    op.drop_index("ix_kitchen_station_hub_active", table_name="orders_kitchen_station")
    op.drop_index("ix_orders_order_hub_status", table_name="orders_order")
    op.drop_index("ix_orders_order_hub_created", table_name="orders_order")
    op.drop_index("ix_orders_order_hub_type", table_name="orders_order")
    op.drop_index("ix_order_item_status", table_name="orders_order_item")
    op.drop_index("ix_order_item_station_status", table_name="orders_order_item")

    # -----------------------------------------------------------------------
    # 3. Rename tables
    # -----------------------------------------------------------------------
    op.rename_table("commands_settings", "kitchen_orders_settings")
    op.rename_table("orders_kitchen_station", "kitchen_orders_station")
    op.rename_table("orders_order", "kitchen_orders_order")
    op.rename_table("orders_order_item", "kitchen_orders_order_item")
    op.rename_table("orders_order_modifier", "kitchen_orders_order_modifier")
    op.rename_table("orders_product_station", "kitchen_orders_product_station")
    op.rename_table("orders_category_station", "kitchen_orders_category_station")

    # -----------------------------------------------------------------------
    # 4. Recreate indexes under new names
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_kitchen_orders_station_hub_active",
        "kitchen_orders_station", ["hub_id", "is_active"],
    )
    op.create_index(
        "ix_kitchen_orders_order_hub_status",
        "kitchen_orders_order", ["hub_id", "status"],
    )
    op.create_index(
        "ix_kitchen_orders_order_hub_created",
        "kitchen_orders_order", ["hub_id", "created_at"],
    )
    op.create_index(
        "ix_kitchen_orders_order_hub_type",
        "kitchen_orders_order", ["hub_id", "order_type"],
    )
    op.create_index(
        "ix_kitchen_orders_item_status",
        "kitchen_orders_order_item", ["hub_id", "status"],
    )
    op.create_index(
        "ix_kitchen_orders_item_station_status",
        "kitchen_orders_order_item", ["hub_id", "station_id", "status"],
    )

    # -----------------------------------------------------------------------
    # 5. Recreate FK constraints pointing to renamed tables
    # -----------------------------------------------------------------------
    with op.batch_alter_table("kitchen_orders_order_item") as batch_op:
        batch_op.create_foreign_key(
            "kitchen_orders_order_item_order_id_fkey",
            "kitchen_orders_order", ["order_id"], ["id"], ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "kitchen_orders_order_item_station_id_fkey",
            "kitchen_orders_station", ["station_id"], ["id"], ondelete="SET NULL",
        )

    with op.batch_alter_table("kitchen_orders_order_modifier") as batch_op:
        batch_op.create_foreign_key(
            "kitchen_orders_order_modifier_order_item_id_fkey",
            "kitchen_orders_order_item", ["order_item_id"], ["id"], ondelete="CASCADE",
        )

    with op.batch_alter_table("kitchen_orders_product_station") as batch_op:
        batch_op.create_foreign_key(
            "kitchen_orders_product_station_station_id_fkey",
            "kitchen_orders_station", ["station_id"], ["id"], ondelete="CASCADE",
        )

    with op.batch_alter_table("kitchen_orders_category_station") as batch_op:
        batch_op.create_foreign_key(
            "kitchen_orders_category_station_station_id_fkey",
            "kitchen_orders_station", ["station_id"], ["id"], ondelete="CASCADE",
        )

    # -----------------------------------------------------------------------
    # 6. Rename unique constraints on renamed tables
    # -----------------------------------------------------------------------
    with op.batch_alter_table("kitchen_orders_settings") as batch_op:
        batch_op.drop_constraint("uq_commands_settings_hub", type_="unique")
        batch_op.create_unique_constraint("uq_kitchen_orders_settings_hub", ["hub_id"])

    with op.batch_alter_table("kitchen_orders_station") as batch_op:
        batch_op.drop_constraint("uq_kitchen_station_hub_name", type_="unique")
        batch_op.create_unique_constraint("uq_kitchen_orders_station_hub_name", ["hub_id", "name"])

    with op.batch_alter_table("kitchen_orders_product_station") as batch_op:
        batch_op.drop_constraint("uq_product_station_hub_product", type_="unique")
        batch_op.create_unique_constraint(
            "uq_kitchen_orders_product_station_hub_product", ["hub_id", "product_id"],
        )

    with op.batch_alter_table("kitchen_orders_category_station") as batch_op:
        batch_op.drop_constraint("uq_category_station_hub_category", type_="unique")
        batch_op.create_unique_constraint(
            "uq_kitchen_orders_category_station_hub_category", ["hub_id", "category_id"],
        )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Reverse: drop new FKs and indexes, rename tables back, recreate old ones
    # -----------------------------------------------------------------------
    with op.batch_alter_table("kitchen_orders_category_station") as batch_op:
        batch_op.drop_constraint("kitchen_orders_category_station_station_id_fkey", type_="foreignkey")
        batch_op.drop_constraint("uq_kitchen_orders_category_station_hub_category", type_="unique")

    with op.batch_alter_table("kitchen_orders_product_station") as batch_op:
        batch_op.drop_constraint("kitchen_orders_product_station_station_id_fkey", type_="foreignkey")
        batch_op.drop_constraint("uq_kitchen_orders_product_station_hub_product", type_="unique")

    with op.batch_alter_table("kitchen_orders_order_modifier") as batch_op:
        batch_op.drop_constraint("kitchen_orders_order_modifier_order_item_id_fkey", type_="foreignkey")

    with op.batch_alter_table("kitchen_orders_order_item") as batch_op:
        batch_op.drop_constraint("kitchen_orders_order_item_order_id_fkey", type_="foreignkey")
        batch_op.drop_constraint("kitchen_orders_order_item_station_id_fkey", type_="foreignkey")

    with op.batch_alter_table("kitchen_orders_settings") as batch_op:
        batch_op.drop_constraint("uq_kitchen_orders_settings_hub", type_="unique")

    with op.batch_alter_table("kitchen_orders_station") as batch_op:
        batch_op.drop_constraint("uq_kitchen_orders_station_hub_name", type_="unique")

    op.drop_index("ix_kitchen_orders_item_station_status", table_name="kitchen_orders_order_item")
    op.drop_index("ix_kitchen_orders_item_status", table_name="kitchen_orders_order_item")
    op.drop_index("ix_kitchen_orders_order_hub_type", table_name="kitchen_orders_order")
    op.drop_index("ix_kitchen_orders_order_hub_created", table_name="kitchen_orders_order")
    op.drop_index("ix_kitchen_orders_order_hub_status", table_name="kitchen_orders_order")
    op.drop_index("ix_kitchen_orders_station_hub_active", table_name="kitchen_orders_station")

    op.rename_table("kitchen_orders_category_station", "orders_category_station")
    op.rename_table("kitchen_orders_product_station", "orders_product_station")
    op.rename_table("kitchen_orders_order_modifier", "orders_order_modifier")
    op.rename_table("kitchen_orders_order_item", "orders_order_item")
    op.rename_table("kitchen_orders_order", "orders_order")
    op.rename_table("kitchen_orders_station", "orders_kitchen_station")
    op.rename_table("kitchen_orders_settings", "commands_settings")

    op.create_index("ix_kitchen_station_hub_active", "orders_kitchen_station", ["hub_id", "is_active"])
    op.create_index("ix_orders_order_hub_status", "orders_order", ["hub_id", "status"])
    op.create_index("ix_orders_order_hub_created", "orders_order", ["hub_id", "created_at"])
    op.create_index("ix_orders_order_hub_type", "orders_order", ["hub_id", "order_type"])
    op.create_index("ix_order_item_status", "orders_order_item", ["hub_id", "status"])
    op.create_index("ix_order_item_station_status", "orders_order_item", ["hub_id", "station_id", "status"])

    with op.batch_alter_table("orders_settings") as batch_op:
        batch_op.create_unique_constraint("uq_commands_settings_hub", ["hub_id"])

    with op.batch_alter_table("orders_kitchen_station") as batch_op:
        batch_op.create_unique_constraint("uq_kitchen_station_hub_name", ["hub_id", "name"])

    with op.batch_alter_table("orders_product_station") as batch_op:
        batch_op.create_unique_constraint("uq_product_station_hub_product", ["hub_id", "product_id"])

    with op.batch_alter_table("orders_category_station") as batch_op:
        batch_op.create_unique_constraint("uq_category_station_hub_category", ["hub_id", "category_id"])

    with op.batch_alter_table("orders_order_item") as batch_op:
        batch_op.create_foreign_key(
            "orders_order_item_order_id_fkey",
            "orders_order", ["order_id"], ["id"], ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "orders_order_item_station_id_fkey",
            "orders_kitchen_station", ["station_id"], ["id"], ondelete="SET NULL",
        )

    with op.batch_alter_table("orders_order_modifier") as batch_op:
        batch_op.create_foreign_key(
            "orders_order_modifier_order_item_id_fkey",
            "orders_order_item", ["order_item_id"], ["id"], ondelete="CASCADE",
        )

    with op.batch_alter_table("orders_product_station") as batch_op:
        batch_op.create_foreign_key(
            "orders_product_station_station_id_fkey",
            "orders_kitchen_station", ["station_id"], ["id"], ondelete="CASCADE",
        )

    with op.batch_alter_table("orders_category_station") as batch_op:
        batch_op.create_foreign_key(
            "orders_category_station_station_id_fkey",
            "orders_kitchen_station", ["station_id"], ["id"], ondelete="CASCADE",
        )
