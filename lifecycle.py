"""
Commands module lifecycle hooks.

Called by ModuleRuntime during install/activate/deactivate/uninstall/upgrade.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def on_install(session: AsyncSession, hub_id: UUID) -> None:
    """Called after module installation + migration. Seed initial data if needed."""
    logger.info("Commands module installed for hub %s", hub_id)

    # Create default settings
    from .models import OrdersSettings

    settings = OrdersSettings(hub_id=hub_id)
    session.add(settings)
    await session.flush()
    logger.info("Created default commands settings for hub %s", hub_id)


async def on_activate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is activated."""
    logger.info("Commands module activated for hub %s", hub_id)


async def on_deactivate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is deactivated. Clean up caches."""
    logger.info("Commands module deactivated for hub %s", hub_id)


async def on_uninstall(session: AsyncSession, hub_id: UUID) -> None:
    """Called before module uninstall. Final cleanup."""
    logger.info("Commands module uninstalled for hub %s", hub_id)


async def on_upgrade(session: AsyncSession, hub_id: UUID, from_version: str, to_version: str) -> None:
    """Called when the module is updated. Run data migrations between versions."""
    logger.info(
        "Commands module upgraded from %s to %s for hub %s",
        from_version, to_version, hub_id,
    )
