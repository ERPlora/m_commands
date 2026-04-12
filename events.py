"""
Commands module event subscriptions.

Registers handlers on the AsyncEventBus during module load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.events.bus import AsyncEventBus

logger = logging.getLogger(__name__)

MODULE_ID = "commands"


async def register_events(bus: AsyncEventBus, module_id: str) -> None:
    """
    Register event handlers for the commands module.

    Called by ModuleRuntime during module load.
    """

    # Listen for order-related events from the sales module
    await bus.subscribe(
            "commands.order_created",
            _on_order_created,
            module_id=module_id,
        )
    await bus.subscribe(
            "commands.order_fired",
            _on_order_fired,
            module_id=module_id,
        )
    await bus.subscribe(
            "commands.order_ready",
            _on_order_ready,
            module_id=module_id,
        )

    # Listen for kitchen order requests emitted by the sales hook
    await bus.subscribe(
            "kitchen.order_required",
            _on_kitchen_order_required,
            module_id=module_id,
        )


async def _on_order_created(event: str, order=None, **kwargs) -> None:
    """Log when a new order is created."""
    if order is None:
        return
    logger.info(
        "Order created: %s (type=%s)",
        getattr(order, "order_number", "?"),
        getattr(order, "order_type", "?"),
    )


async def _on_order_fired(event: str, order=None, **kwargs) -> None:
    """Log when an order is fired to kitchen."""
    if order is None:
        return
    logger.info("Order fired to kitchen: %s", getattr(order, "order_number", "?"))


async def _on_order_ready(event: str, order=None, **kwargs) -> None:
    """Log when an order is ready."""
    if order is None:
        return
    logger.info("Order ready: %s", getattr(order, "order_number", "?"))


async def _on_kitchen_order_required(
    event: str,
    hub_id: str | None = None,
    sale_id: str | None = None,
    table_id: str | None = None,
    items: list | None = None,
    channel: str = "pos",
    **kwargs,
) -> None:
    """
    Create a kitchen Order (commands.Order) from a sale completion event.

    Idempotent: if an Order with the same sale_id already exists, skip.
    Emits ``kitchen.order_created`` after successful creation.
    """
    import uuid as _uuid

    if not hub_id or not sale_id or not items:
        logger.debug(
            "_on_kitchen_order_required: missing required payload fields — skipping"
        )
        return

    session = kwargs.get("session")
    bus = kwargs.get("bus")

    if session is None:
        logger.warning(
            "_on_kitchen_order_required: no session in kwargs for sale %s — cannot create Order",
            sale_id,
        )
        return

    try:
        from app.core.db.query import HubQuery

        from .models import Order, OrderItem, generate_order_number

        hub_uuid = _uuid.UUID(hub_id)
        sale_uuid = _uuid.UUID(sale_id)

        # Idempotency check — skip if already exists
        existing = await HubQuery(Order, session, hub_uuid).filter(
            Order.sale_id == sale_uuid,
        ).first()
        if existing is not None:
            logger.info(
                "_on_kitchen_order_required: Order already exists for sale %s (order %s) — skip",
                sale_id,
                existing.order_number,
            )
            return

        order_number = await generate_order_number(session, hub_uuid)
        table_uuid = _uuid.UUID(table_id) if table_id else None
        order_type = "dine_in" if table_uuid else ("takeaway" if channel == "pos" else channel)

        order = Order(
            hub_id=hub_uuid,
            order_number=order_number,
            sale_id=sale_uuid,
            table_id=table_uuid,
            order_type=order_type,
            status="pending",
            priority="normal",
        )
        session.add(order)
        await session.flush()

        for raw_item in items:
            product_id_str = raw_item.get("product_id")
            product_uuid = _uuid.UUID(product_id_str) if product_id_str else None
            quantity = int(raw_item.get("quantity", 1))
            notes = raw_item.get("notes", "") or ""

            order_item = OrderItem(
                hub_id=hub_uuid,
                order_id=order.id,
                product_id=product_uuid,
                product_name=raw_item.get("product_name", ""),
                quantity=quantity,
                notes=notes,
                status="pending",
            )
            session.add(order_item)

        await session.flush()

        logger.info(
            "_on_kitchen_order_required: created Order %s for sale %s (%d items)",
            order_number,
            sale_id,
            len(items),
        )

        if bus is not None:
            await bus.emit(
                "kitchen.order_created",
                sender=MODULE_ID,
                order_number=order_number,
                order_id=str(order.id),
                sale_id=sale_id,
                hub_id=hub_id,
            )

    except Exception:
        logger.exception(
            "_on_kitchen_order_required: failed to create Order for sale %s", sale_id
        )
