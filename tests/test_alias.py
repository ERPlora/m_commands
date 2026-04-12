"""Tests for Kitchen Orders aliases exported from commands package."""

from __future__ import annotations

from commands import KitchenOrder, KitchenOrderItem
from commands.models import Order, OrderItem


def test_kitchen_order_is_order():
    assert KitchenOrder is Order


def test_kitchen_order_item_is_order_item():
    assert KitchenOrderItem is OrderItem
