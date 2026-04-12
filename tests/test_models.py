"""
Tests for commands module models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal

from commands.models import (
    ORDER_TYPE_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
    OrderModifier,
)


class TestOrder:
    def test_repr(self, sample_order):
        assert "#20260404-0001" in repr(sample_order)

    def test_status_display(self, sample_order):
        sample_order.status = "preparing"
        assert sample_order.status_display == "Preparing"

    def test_order_type_display(self, sample_order):
        sample_order.order_type = "takeaway"
        assert sample_order.order_type_display == "Takeaway"

    def test_priority_display(self, sample_order):
        sample_order.priority = "rush"
        assert sample_order.priority_display == "Rush"

    def test_elapsed_minutes_no_fired(self, sample_order):
        assert sample_order.elapsed_minutes == 0

    def test_elapsed_minutes_with_fired(self, sample_order):
        sample_order.fired_at = datetime.now(UTC) - timedelta(minutes=10)
        assert 9 <= sample_order.elapsed_minutes <= 11

    def test_prep_time_minutes(self, sample_order):
        now = datetime.now(UTC)
        sample_order.fired_at = now - timedelta(minutes=8)
        sample_order.ready_at = now
        assert sample_order.prep_time_minutes == 8

    def test_prep_time_minutes_none(self, sample_order):
        assert sample_order.prep_time_minutes is None

    def test_is_delayed_false(self, sample_order):
        assert sample_order.is_delayed is False

    def test_is_delayed_true(self, sample_order):
        sample_order.status = "preparing"
        sample_order.fired_at = datetime.now(UTC) - timedelta(minutes=20)
        assert sample_order.is_delayed is True

    def test_can_be_edited(self, sample_order):
        sample_order.status = "pending"
        assert sample_order.can_be_edited is True
        sample_order.status = "paid"
        assert sample_order.can_be_edited is False

    def test_calculate_totals(self, sample_order, sample_item):
        items = [sample_item]
        sample_order.calculate_totals(items)
        assert sample_order.subtotal == Decimal("25.00")
        assert sample_order.total == Decimal("25.00")

    def test_calculate_totals_with_discount(self, sample_order, sample_item):
        sample_order.discount = Decimal("5.00")
        items = [sample_item]
        sample_order.calculate_totals(items)
        assert sample_order.total == Decimal("20.00")


class TestOrderItem:
    def test_repr(self, sample_item):
        assert "2x" in repr(sample_item)
        assert "Hamburger" in repr(sample_item)

    def test_display_name_no_modifiers(self, sample_item):
        assert sample_item.display_name == "Hamburger"

    def test_display_name_with_modifiers(self, sample_item):
        sample_item.modifiers = "Extra cheese"
        assert sample_item.display_name == "Hamburger (Extra cheese)"

    def test_recalculate_total(self, sample_item):
        sample_item.quantity = 3
        sample_item.recalculate_total()
        assert sample_item.total == Decimal("37.50")

    def test_status_display(self, sample_item):
        sample_item.status = "ready"
        assert sample_item.status_display == "Ready"


class TestKitchenStation:
    def test_repr(self, sample_station):
        assert "Grill" in repr(sample_station)


class TestOrdersSettings:
    def test_repr(self, sample_settings):
        assert "OrdersSettings" in repr(sample_settings)

    def test_defaults(self, sample_settings):
        assert sample_settings.auto_print_tickets is True
        assert sample_settings.alert_threshold_minutes == 15
        assert sample_settings.default_order_type == "dine_in"


class TestOrderModifier:
    def test_repr_with_price(self, hub_id):
        m = OrderModifier(hub_id=hub_id, name="Extra cheese", price=Decimal("1.50"))
        assert "Extra cheese" in repr(m)
        assert "1.50" in repr(m)

    def test_repr_no_price(self, hub_id):
        m = OrderModifier(hub_id=hub_id, name="No onions", price=Decimal("0.00"))
        assert "No onions" in repr(m)


class TestStatusLabels:
    def test_all_statuses_have_labels(self):
        from commands.models import STATUS_CHOICES
        for s in STATUS_CHOICES:
            assert s in STATUS_LABELS

    def test_all_order_types_have_labels(self):
        from commands.models import ORDER_TYPE_CHOICES
        for t in ORDER_TYPE_CHOICES:
            assert t in ORDER_TYPE_LABELS

    def test_all_priorities_have_labels(self):
        from commands.models import PRIORITY_CHOICES
        for p in PRIORITY_CHOICES:
            assert p in PRIORITY_LABELS


class TestTableNames:
    """Verify DB table names use the kitchen_orders_ prefix (Fase 5 rename)."""

    def test_order_tablename(self):
        from commands.models import Order
        assert Order.__tablename__ == "kitchen_orders_order"

    def test_order_item_tablename(self):
        from commands.models import OrderItem
        assert OrderItem.__tablename__ == "kitchen_orders_order_item"

    def test_order_modifier_tablename(self):
        from commands.models import OrderModifier
        assert OrderModifier.__tablename__ == "kitchen_orders_order_modifier"

    def test_kitchen_station_tablename(self):
        from commands.models import KitchenStation
        assert KitchenStation.__tablename__ == "kitchen_orders_station"

    def test_product_station_tablename(self):
        from commands.models import ProductStation
        assert ProductStation.__tablename__ == "kitchen_orders_product_station"

    def test_category_station_tablename(self):
        from commands.models import CategoryStation
        assert CategoryStation.__tablename__ == "kitchen_orders_category_station"

    def test_settings_tablename(self):
        from commands.models import OrdersSettings
        assert OrdersSettings.__tablename__ == "kitchen_orders_settings"


class TestModuleID:
    """Verify MODULE_ID is kitchen_orders (Fase 5 rename)."""

    def test_module_id(self):
        import commands.module as m
        assert m.MODULE_ID == "kitchen_orders"

    def test_module_version_major(self):
        import commands.module as m
        major = int(m.MODULE_VERSION.split(".")[0])
        assert major >= 3, f"Expected major >= 3 after breaking rename, got {m.MODULE_VERSION}"
