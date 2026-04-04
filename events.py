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
