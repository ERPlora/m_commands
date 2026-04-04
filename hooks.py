"""
Commands module hook registrations.

Registers actions and filters on the HookRegistry during module load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.hooks.registry import HookRegistry

logger = logging.getLogger(__name__)

MODULE_ID = "commands"


def register_hooks(hooks: HookRegistry, module_id: str) -> None:
    """
    Register hooks for the commands module.

    Called by ModuleRuntime during module load.
    """
    # Action: link order to sale after checkout
    hooks.add_action(
        "sales.after_checkout",
        _link_order_to_sale,
        priority=20,
        module_id=module_id,
    )


async def _link_order_to_sale(sale=None, body=None, request=None, **kwargs) -> None:
    """Link existing order to the completed sale."""
    if body is None or sale is None:
        return

    order_id = body.get("order_id") if isinstance(body, dict) else None
    if not order_id:
        return

    try:
        from app.core.db.query import HubQuery

        session = kwargs.get("session")
        hub_id = kwargs.get("hub_id")
        if session is None or hub_id is None:
            return

        from .models import Order

        order = await HubQuery(Order, session, hub_id).get(order_id)
        if order:
            order.sale_id = sale.id
            order.status = "paid"
            await session.flush()
            logger.info("Linked order %s to sale %s", order.order_number, sale.id)
    except Exception:
        logger.exception("Failed to link order to sale")
