"""
Commands module REST API — FastAPI router.

JSON endpoints for external consumers (Cloud sync, CLI, webhooks).
Mounted at /api/v1/m/commands/ by ModuleRuntime.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import selectinload

from app.core.db.query import HubQuery
from app.core.dependencies import DbSession, HubId

from .models import (
    KitchenStation,
    Order,
    OrderItem,
)

api_router = APIRouter()


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@api_router.get("/orders")
async def list_orders(
    request: Request, db: DbSession, hub_id: HubId,
    status: str = "", order_type: str = "",
    offset: int = 0, limit: int = Query(default=20, le=100),
):
    """List orders with optional filters."""
    query = _q(Order, db, hub_id)
    if status:
        query = query.filter(Order.status == status)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    total = await query.count()
    orders = await query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    return JSONResponse({
        "orders": [{
            "id": str(o.id),
            "order_number": o.order_number,
            "status": o.status,
            "order_type": o.order_type,
            "priority": o.priority,
            "total": str(o.total),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        } for o in orders],
        "total": total,
    })


@api_router.get("/orders/{order_id}")
async def get_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, hub_id: HubId,
):
    """Get full order details with items."""
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items).selectinload(OrderItem.station),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    items = [i for i in order.items if not i.is_deleted]
    return JSONResponse({
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "order_type": order.order_type,
        "priority": order.priority,
        "notes": order.notes,
        "subtotal": str(order.subtotal),
        "tax": str(order.tax),
        "discount": str(order.discount),
        "total": str(order.total),
        "items": [{
            "id": str(i.id),
            "product_name": i.product_name,
            "quantity": i.quantity,
            "unit_price": str(i.unit_price),
            "total": str(i.total),
            "status": i.status,
            "station": i.station.name if i.station else None,
        } for i in items],
    })


@api_router.get("/stations")
async def list_stations(
    request: Request, db: DbSession, hub_id: HubId,
):
    """List kitchen stations."""
    stations = await _q(KitchenStation, db, hub_id).filter(
        KitchenStation.is_active == True,  # noqa: E712
    ).order_by(KitchenStation.sort_order).all()
    return JSONResponse({
        "stations": [{
            "id": str(s.id),
            "name": s.name,
            "color": s.color,
            "icon": s.icon,
            "is_active": s.is_active,
        } for s in stations],
    })
