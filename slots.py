"""
Commands module slot registrations.

Injects command UI into POS and other modules via the SlotRegistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.slots import SlotRegistry

MODULE_ID = "kitchen_orders"


def register_slots(slots: SlotRegistry, module_id: str) -> None:
    """
    Register POS slot content for the commands module.

    Called by ModuleRuntime during module load.
    """
    slots.register(
        "sales.pos_cart_actions",
        template="commands/pos/cart_actions.html",
        priority=10,
        module_id=module_id,
    )
    slots.register(
        "sales.pos_modals",
        template="commands/pos/modals.html",
        priority=30,
        module_id=module_id,
    )
