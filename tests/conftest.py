"""
Test fixtures for the commands module.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from commands.models import KitchenStation, Order, OrderItem, OrdersSettings


@pytest.fixture
def hub_id():
    """Test hub UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_settings(hub_id):
    """Create sample commands settings (not persisted)."""
    return OrdersSettings(
        hub_id=hub_id,
        auto_print_tickets=True,
        show_prep_time=True,
        alert_threshold_minutes=15,
        use_rounds=True,
        auto_fire_on_round=False,
        default_order_type="dine_in",
        sound_on_new_order=True,
    )


@pytest.fixture
def sample_station(hub_id):
    """Create a sample kitchen station (not persisted)."""
    return KitchenStation(
        hub_id=hub_id,
        name="Grill",
        color="#FF5733",
        icon="flame-outline",
        printer_name="kitchen-printer-1",
        sort_order=0,
        is_active=True,
    )


@pytest.fixture
def sample_order(hub_id):
    """Create a sample order (not persisted)."""
    return Order(
        hub_id=hub_id,
        order_number="20260404-0001",
        order_type="dine_in",
        status="pending",
        priority="normal",
        round_number=1,
        subtotal=Decimal("25.00"),
        total=Decimal("25.00"),
    )


@pytest.fixture
def sample_item(hub_id, sample_order):
    """Create a sample order item (not persisted)."""
    return OrderItem(
        hub_id=hub_id,
        order_id=sample_order.id or uuid.uuid4(),
        product_name="Hamburger",
        unit_price=Decimal("12.50"),
        quantity=2,
        total=Decimal("25.00"),
        status="pending",
    )
