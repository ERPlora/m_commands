"""
Tests for commands module: kitchen.order_required → creates Order (idempotent).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.events import _on_kitchen_order_required
from commands.models import Order


class TestOnKitchenOrderRequired:
    @pytest.fixture
    def hub_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sale_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def table_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def kitchen_items(self):
        return [
            {
                "product_id": str(uuid.uuid4()),
                "product_name": "Burger",
                "quantity": 2,
                "notes": "No pickles",
            },
            {
                "product_id": str(uuid.uuid4()),
                "product_name": "Fries",
                "quantity": 1,
                "notes": "",
            },
        ]

    def _make_mock_session(self):
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    def _make_mock_bus(self):
        bus = MagicMock()
        bus.emit = AsyncMock()
        return bus

    def _make_hub_query_mock(self, return_value=None):
        """Return a HubQuery class mock whose first() returns ``return_value``."""
        mock_instance = MagicMock()
        mock_instance.filter.return_value = mock_instance
        mock_instance.first = AsyncMock(return_value=return_value)
        mock_hq_cls = MagicMock(return_value=mock_instance)
        return mock_hq_cls

    @pytest.mark.asyncio
    async def test_creates_order_from_payload(self, hub_id, sale_id, kitchen_items):
        """A valid payload creates an Order with OrderItems."""
        session = self._make_mock_session()
        bus = self._make_mock_bus()

        created_orders = []

        def capture_add(obj):
            if isinstance(obj, Order):
                created_orders.append(obj)

        session.add.side_effect = capture_add

        mock_hq_cls = self._make_hub_query_mock(return_value=None)

        with (
            patch("commands.models.generate_order_number", new=AsyncMock(return_value="20260412-0001")),
        ):
            # Patch HubQuery inside the events module's imports
            import app.core.db.query as query_mod
            original_hq = query_mod.HubQuery
            query_mod.HubQuery = mock_hq_cls
            try:
                await _on_kitchen_order_required(
                    event="kitchen.order_required",
                    hub_id=str(hub_id),
                    sale_id=str(sale_id),
                    table_id=None,
                    items=kitchen_items,
                    channel="pos",
                    session=session,
                    bus=bus,
                )
            finally:
                query_mod.HubQuery = original_hq

        assert len(created_orders) == 1
        order = created_orders[0]
        assert order.order_number == "20260412-0001"
        assert order.sale_id == sale_id
        # 1 order + 2 items = 3 adds
        assert session.add.call_count == 3

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing_order(self, hub_id, sale_id, kitchen_items):
        """When an Order with same sale_id already exists, no new Order is created."""
        session = self._make_mock_session()

        existing_order = Order(
            hub_id=hub_id,
            order_number="20260412-0001",
            sale_id=sale_id,
            status="pending",
        )

        mock_hq_cls = self._make_hub_query_mock(return_value=existing_order)

        import app.core.db.query as query_mod
        original_hq = query_mod.HubQuery
        query_mod.HubQuery = mock_hq_cls
        try:
            await _on_kitchen_order_required(
                event="kitchen.order_required",
                hub_id=str(hub_id),
                sale_id=str(sale_id),
                items=kitchen_items,
                session=session,
            )
        finally:
            query_mod.HubQuery = original_hq

        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_emits_kitchen_order_created(self, hub_id, sale_id, kitchen_items):
        """After creating an Order, emits kitchen.order_created."""
        session = self._make_mock_session()
        bus = self._make_mock_bus()

        mock_hq_cls = self._make_hub_query_mock(return_value=None)

        with patch("commands.models.generate_order_number", new=AsyncMock(return_value="20260412-0001")):
            import app.core.db.query as query_mod
            original_hq = query_mod.HubQuery
            query_mod.HubQuery = mock_hq_cls
            try:
                await _on_kitchen_order_required(
                    event="kitchen.order_required",
                    hub_id=str(hub_id),
                    sale_id=str(sale_id),
                    items=kitchen_items,
                    session=session,
                    bus=bus,
                )
            finally:
                query_mod.HubQuery = original_hq

        bus.emit.assert_awaited_once()
        assert bus.emit.call_args.args[0] == "kitchen.order_created"

    @pytest.mark.asyncio
    async def test_skips_when_no_session(self, hub_id, sale_id, kitchen_items):
        """Without a session, logs warning and returns without raising."""
        await _on_kitchen_order_required(
            event="kitchen.order_required",
            hub_id=str(hub_id),
            sale_id=str(sale_id),
            items=kitchen_items,
            # no session kwarg
        )
        # Should complete without exception

    @pytest.mark.asyncio
    async def test_skips_when_missing_required_fields(self):
        """Missing hub_id / sale_id / items → skip silently."""
        await _on_kitchen_order_required(
            event="kitchen.order_required",
            hub_id=None,
            sale_id=None,
            items=[],
        )
        # No exception raised

    @pytest.mark.asyncio
    async def test_dine_in_order_type_when_table_id_present(self, hub_id, sale_id, table_id, kitchen_items):
        """When table_id is provided, order_type should be dine_in."""
        session = self._make_mock_session()

        created_orders = []

        def capture_add(obj):
            if isinstance(obj, Order):
                created_orders.append(obj)

        session.add.side_effect = capture_add

        mock_hq_cls = self._make_hub_query_mock(return_value=None)

        with patch("commands.models.generate_order_number", new=AsyncMock(return_value="20260412-0001")):
            import app.core.db.query as query_mod
            original_hq = query_mod.HubQuery
            query_mod.HubQuery = mock_hq_cls
            try:
                await _on_kitchen_order_required(
                    event="kitchen.order_required",
                    hub_id=str(hub_id),
                    sale_id=str(sale_id),
                    table_id=str(table_id),
                    items=kitchen_items,
                    channel="pos",
                    session=session,
                )
            finally:
                query_mod.HubQuery = original_hq

        assert len(created_orders) == 1
        assert created_orders[0].order_type == "dine_in"
        assert created_orders[0].table_id == table_id
