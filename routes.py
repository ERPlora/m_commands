"""
Commands module HTMX views — FastAPI router.

Replaces Django views.py + urls.py. Uses @htmx_view decorator
(partial for HTMX requests, full page for direct navigation).
Mounted at /m/commands/ by ModuleRuntime.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from starlette.websockets import WebSocket

from app.core.db.query import HubQuery
from app.core.db.transactions import atomic
from app.core.dependencies import CurrentUser, DbSession, HubId
from app.core.htmx import add_message, htmx_redirect, htmx_view
from app.core.ws import ws_send

from .models import (
    ORDER_TYPE_CHOICES,
    ORDER_TYPE_LABELS,
    STATUS_CHOICES,
    STATUS_LABELS,
    CategoryStation,
    KitchenStation,
    Order,
    OrderItem,
    OrdersSettings,
    ProductStation,
    generate_order_number,
    get_station_for_product,
)
from .schemas import KitchenStationCreate

router = APIRouter()


def _q(model, db, hub_id):
    return HubQuery(model, db, hub_id)


def _status_choices_active():
    return [
        (s, STATUS_LABELS[s])
        for s in ("pending", "preparing", "ready", "served")
    ]


def _order_type_choices():
    return [(t, ORDER_TYPE_LABELS[t]) for t in ORDER_TYPE_CHOICES]


async def _get_settings(db, hub_id):
    settings = await _q(OrdersSettings, db, hub_id).first()
    if not settings:
        async with atomic(db) as session:
            settings = OrdersSettings(hub_id=hub_id)
            session.add(settings)
            await session.flush()
    return settings


# =============================================================================
# Active Orders (Index)
# =============================================================================

@router.get("/")
@htmx_view(module_id="commands", view_id="dashboard")
async def index(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    return await _active_orders_context(db, hub_id, request)


@router.get("/active")
@htmx_view(module_id="commands", view_id="active")
async def active_orders(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    return await _active_orders_context(db, hub_id, request)


async def _active_orders_context(db, hub_id, request):
    status_filter = request.query_params.get("status", "")
    order_type_filter = request.query_params.get("order_type", "")

    query = _q(Order, db, hub_id).filter(
        Order.status.in_(["pending", "preparing", "ready", "served"]),
    )

    if status_filter:
        query = query.filter(Order.status == status_filter)
    if order_type_filter:
        query = query.filter(Order.order_type == order_type_filter)

    orders = await query.order_by(Order.created_at.desc()).all()

    # Status counts
    counts_q = _q(Order, db, hub_id).filter(
        Order.status.in_(["pending", "preparing", "ready", "served"]),
    )
    all_active = await counts_q.all()
    counts = {}
    for o in all_active:
        counts[o.status] = counts.get(o.status, 0) + 1

    return {
        "orders": orders,
        "status_filter": status_filter,
        "order_type_filter": order_type_filter,
        "status_choices": _status_choices_active(),
        "order_type_choices": _order_type_choices(),
        "pending_count": counts.get("pending", 0),
        "preparing_count": counts.get("preparing", 0),
        "ready_count": counts.get("ready", 0),
        "served_count": counts.get("served", 0),
    }


# =============================================================================
# Order CRUD
# =============================================================================

@router.get("/{order_id}")
@htmx_view(module_id="commands", view_id="detail")
async def order_detail(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items).selectinload(OrderItem.station),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    items = [i for i in order.items if not i.is_deleted]
    return {"order": order, "items": items}


@router.get("/create")
@htmx_view(module_id="commands", view_id="create")
async def order_create(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    return {"is_new": True}


@router.post("/create")
async def order_create_post(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    form = await request.form()
    async with atomic(db) as session:
        order_num = await generate_order_number(session, hub_id)
        order = Order(
            hub_id=hub_id,
            order_number=order_num,
            order_type=form.get("order_type", "dine_in"),
            priority=form.get("priority", "normal"),
            notes=form.get("notes", ""),
            waiter_id=user.id,
        )
        table_id = form.get("table")
        if table_id:
            order.table_id = uuid.UUID(table_id)
        customer_id = form.get("customer")
        if customer_id:
            order.customer_id = uuid.UUID(customer_id)
        session.add(order)
        await session.flush()

    add_message(request, "success", f"Order #{order.order_number} created")
    return htmx_redirect(f"/m/commands/{order.id}")


@router.get("/{order_id}/edit")
@htmx_view(module_id="commands", view_id="edit")
async def order_edit(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return {"order": order, "is_new": False}


@router.post("/{order_id}/edit")
async def order_edit_post(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    form = await request.form()
    for field_name in ("order_type", "priority", "notes"):
        value = form.get(field_name)
        if value is not None:
            setattr(order, field_name, value)

    table_id = form.get("table")
    if table_id:
        order.table_id = uuid.UUID(table_id)
    customer_id = form.get("customer")
    if customer_id:
        order.customer_id = uuid.UUID(customer_id)

    round_num = form.get("round_number")
    if round_num:
        order.round_number = int(round_num)

    await db.flush()
    add_message(request, "success", f"Order #{order.order_number} updated")
    return htmx_redirect(f"/m/commands/{order.id}")


@router.post("/{order_id}/delete")
async def order_delete(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    order.is_deleted = True
    order.deleted_at = datetime.now(UTC)
    await db.flush()
    return JSONResponse({"success": True, "message": "Order deleted"})


# =============================================================================
# Order Items
# =============================================================================

@router.get("/{order_id}/add-item")
@htmx_view(module_id="commands", view_id="add_item")
async def add_item(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return {"order": order}


@router.post("/{order_id}/add-item")
async def add_item_post(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    form = await request.form()
    async with atomic(db) as session:
        product_id_str = form.get("product")
        product_id = uuid.UUID(product_id_str) if product_id_str else None

        item = OrderItem(
            hub_id=hub_id,
            order_id=order.id,
            product_id=product_id,
            product_name=form.get("product_name", ""),
            unit_price=Decimal(form.get("unit_price", "0")),
            quantity=max(1, int(form.get("quantity", "1"))),
            modifiers=form.get("modifiers", ""),
            notes=form.get("notes", ""),
        )
        seat = form.get("seat_number")
        if seat:
            item.seat_number = int(seat)

        item.recalculate_total()

        # Auto-route to station
        if product_id:
            station = await get_station_for_product(session, hub_id, product_id)
            if station:
                item.station_id = station.id

        session.add(item)
        await session.flush()

        # Recalculate order totals
        all_items = await _q(OrderItem, session, hub_id).filter(
            OrderItem.order_id == order.id,
        ).all()
        order.calculate_totals(all_items)
        await session.flush()

    add_message(request, "success", "Item added")
    return htmx_redirect(f"/m/commands/{order.id}")


@router.post("/{order_id}/items/{item_id}/update")
async def update_item_quantity(
    request: Request, order_id: uuid.UUID, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    item = await _q(OrderItem, db, hub_id).filter(
        OrderItem.order_id == order_id,
    ).get(item_id)
    if not order or not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    form = await request.form()
    quantity = form.get("quantity")
    if quantity:
        item.quantity = max(1, int(quantity))
        item.recalculate_total()

        all_items = await _q(OrderItem, db, hub_id).filter(
            OrderItem.order_id == order_id,
        ).all()
        order.calculate_totals(all_items)
        await db.flush()

    return JSONResponse({
        "success": True,
        "item_total": str(item.total),
        "order_total": str(order.total),
    })


@router.post("/{order_id}/items/{item_id}/remove")
async def remove_item(
    request: Request, order_id: uuid.UUID, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    item = await _q(OrderItem, db, hub_id).filter(
        OrderItem.order_id == order_id,
    ).get(item_id)
    if not order or not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    item.is_deleted = True
    item.deleted_at = datetime.now(UTC)

    all_items = await _q(OrderItem, db, hub_id).filter(
        OrderItem.order_id == order_id,
    ).all()
    order.calculate_totals(all_items)
    await db.flush()

    return JSONResponse({
        "success": True,
        "message": "Item removed",
        "order_total": str(order.total),
    })


@router.post("/{order_id}/items/{item_id}/ready")
async def mark_item_ready(
    request: Request, order_id: uuid.UUID, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    item = await _q(OrderItem, db, hub_id).filter(
        OrderItem.order_id == order_id,
    ).get(item_id)
    if not order or not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    item.status = "ready"
    item.completed_at = datetime.now(UTC)
    await db.flush()

    # Check if all items are ready
    active_items = [i for i in order.items if not i.is_deleted and i.fired_at is not None]
    all_ready = all(i.status in ("ready", "served", "cancelled") for i in active_items)

    if all_ready and active_items:
        order.status = "ready"
        order.ready_at = datetime.now(UTC)
        await db.flush()

    return JSONResponse({
        "success": True,
        "message": "Item ready",
        "order_ready": all_ready,
    })


# =============================================================================
# Order Workflow Actions
# =============================================================================

@router.post("/{order_id}/fire")
async def fire_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    now = datetime.now(UTC)
    order.fired_at = now
    order.status = "preparing"

    for item in order.items:
        if not item.is_deleted and item.status == "pending":
            item.status = "preparing"
            item.fired_at = now

    await db.flush()
    return JSONResponse({
        "success": True,
        "status": order.status,
        "fired_at": order.fired_at.isoformat() if order.fired_at else None,
    })


@router.post("/{order_id}/bump")
async def bump_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    now = datetime.now(UTC)
    for item in order.items:
        if not item.is_deleted and item.status in ("pending", "preparing"):
            item.status = "ready"
            item.completed_at = now

    order.status = "ready"
    order.ready_at = now
    await db.flush()

    return JSONResponse({
        "success": True,
        "status": order.status,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
    })


@router.post("/{order_id}/recall")
async def recall_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    if order.status == "ready":
        order.status = "preparing"
        order.ready_at = None
        for item in order.items:
            if not item.is_deleted and item.status == "ready":
                item.status = "preparing"
                item.completed_at = None
        await db.flush()

    return JSONResponse({"success": True, "status": order.status})


@router.post("/{order_id}/serve")
async def serve_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    order.status = "served"
    order.served_at = datetime.now(UTC)
    await db.flush()

    return JSONResponse({
        "success": True,
        "status": order.status,
        "served_at": order.served_at.isoformat() if order.served_at else None,
    })


@router.post("/{order_id}/cancel")
async def cancel_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    if order.status in ("paid", "cancelled"):
        return JSONResponse({"success": False, "message": "Cannot cancel"}, status_code=400)

    form = await request.form()
    reason = form.get("reason", "")
    order.status = "cancelled"
    if reason:
        order.notes = f"{order.notes}\nCancelled: {reason}".strip()

    for item in order.items:
        if not item.is_deleted:
            item.status = "cancelled"

    await db.flush()
    return JSONResponse({"success": True, "status": order.status})


@router.post("/{order_id}/update-status")
async def update_status(
    request: Request, order_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    form = await request.form()
    new_status = form.get("status")
    if new_status and new_status in STATUS_CHOICES:
        order.status = new_status
        await db.flush()
        return JSONResponse({"success": True, "status": new_status})
    return JSONResponse({"success": False, "message": "Invalid status"}, status_code=400)


# =============================================================================
# Item Actions
# =============================================================================

@router.post("/items/{item_id}/bump")
async def bump_item(
    request: Request, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    item = await _q(OrderItem, db, hub_id).options(
        selectinload(OrderItem.order).selectinload(Order.items),
    ).get(item_id)
    if item is None:
        return JSONResponse({"error": "Item not found"}, status_code=404)

    item.status = "ready"
    item.completed_at = datetime.now(UTC)
    await db.flush()

    # Check if all items in order are ready
    active_items = [i for i in item.order.items if not i.is_deleted]
    pending = any(i.status not in ("ready", "served", "cancelled") for i in active_items)
    if not pending:
        item.order.status = "ready"
        item.order.ready_at = datetime.now(UTC)
        await db.flush()

    return JSONResponse({
        "success": True,
        "item_status": item.status,
        "order_status": item.order.status,
    })


@router.post("/items/{item_id}/cancel")
async def cancel_item(
    request: Request, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    item = await _q(OrderItem, db, hub_id).get(item_id)
    if item is None:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    item.status = "cancelled"
    await db.flush()
    return JSONResponse({"success": True, "status": item.status})


@router.post("/items/{item_id}/quantity")
async def modify_item_quantity(
    request: Request, item_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    item = await _q(OrderItem, db, hub_id).get(item_id)
    if item is None:
        return JSONResponse({"error": "Item not found"}, status_code=404)

    body = await request.json()
    quantity = max(1, int(body.get("quantity", 1)))
    item.quantity = quantity
    item.recalculate_total()
    await db.flush()
    return JSONResponse({"success": True, "quantity": item.quantity})


# =============================================================================
# Kitchen Display System (KDS)
# =============================================================================

@router.get("/kds")
@router.get("/kds/{station_id}")
@htmx_view(module_id="commands", view_id="kds")
async def kitchen_display(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    station_id: uuid.UUID | None = None,
):
    stations = await _q(KitchenStation, db, hub_id).filter(
        KitchenStation.is_active == True,  # noqa: E712
    ).order_by(KitchenStation.sort_order, KitchenStation.name).all()

    station = None
    items = []
    if station_id:
        station = await _q(KitchenStation, db, hub_id).get(station_id)
        items_qs = await _q(OrderItem, db, hub_id).filter(
            OrderItem.station_id == station_id,
            OrderItem.status.in_(["pending", "preparing"]),
        ).options(
            selectinload(OrderItem.order),
        ).order_by(OrderItem.created_at).all()

        items = [{
            "id": str(item.id),
            "order_number": item.order.order_number,
            "table": item.order.table_display,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "modifiers": item.modifiers,
            "notes": item.notes,
            "status": item.status,
            "priority": item.order.priority,
            "elapsed_minutes": item.order.elapsed_minutes,
            "is_delayed": item.order.is_delayed,
        } for item in items_qs]

    return {
        "stations": stations,
        "current_station": station,
        "items": items,
    }


# =============================================================================
# Kitchen Stations
# =============================================================================

@router.get("/stations")
@htmx_view(module_id="commands", view_id="stations")
async def stations_list(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    stations = await _q(KitchenStation, db, hub_id).order_by(
        KitchenStation.sort_order, KitchenStation.name,
    ).all()
    return {"stations": stations}


@router.get("/stations/add")
@htmx_view(module_id="commands", view_id="station_add")
async def station_add(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    return {"is_new": True}


@router.post("/stations/add")
async def station_add_post(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    form = await request.form()
    data = KitchenStationCreate(
        name=form.get("name", ""),
        name_es=form.get("name_es", ""),
        description=form.get("description", ""),
        color=form.get("color", "#F97316"),
        icon=form.get("icon", "flame-outline"),
        printer_name=form.get("printer_name", ""),
        sort_order=int(form.get("sort_order", "0")),
        is_active=form.get("is_active") in ("on", "true", None),
    )
    async with atomic(db) as session:
        station = KitchenStation(hub_id=hub_id, **data.model_dump())
        session.add(station)
    add_message(request, "success", f"Station {data.name} created")
    return htmx_redirect("/m/commands/stations")


@router.get("/stations/{station_id}/edit")
@htmx_view(module_id="commands", view_id="station_edit")
async def station_edit(
    request: Request, station_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    station = await _q(KitchenStation, db, hub_id).get(station_id)
    if station is None:
        return JSONResponse({"error": "Station not found"}, status_code=404)
    return {"station": station, "is_new": False}


@router.post("/stations/{station_id}/edit")
async def station_edit_post(
    request: Request, station_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    station = await _q(KitchenStation, db, hub_id).get(station_id)
    if station is None:
        return JSONResponse({"error": "Station not found"}, status_code=404)

    form = await request.form()
    for f in ("name", "name_es", "description", "color", "icon", "printer_name"):
        v = form.get(f)
        if v is not None:
            setattr(station, f, v)

    sort_order = form.get("sort_order")
    if sort_order is not None:
        station.sort_order = int(sort_order)

    is_active = form.get("is_active")
    if is_active is not None:
        station.is_active = is_active in ("on", "true")

    await db.flush()
    add_message(request, "success", f"Station {station.name} updated")
    return htmx_redirect("/m/commands/stations")


@router.post("/stations/{station_id}/delete")
async def station_delete(
    request: Request, station_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    station = await _q(KitchenStation, db, hub_id).get(station_id)
    if station is None:
        return JSONResponse({"error": "Station not found"}, status_code=404)
    station.is_deleted = True
    station.deleted_at = datetime.now(UTC)
    await db.flush()
    return JSONResponse({"success": True, "message": "Station deleted"})


# =============================================================================
# Routing
# =============================================================================

@router.get("/routing")
@htmx_view(module_id="commands", view_id="routing")
async def routing(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    stations = await _q(KitchenStation, db, hub_id).filter(
        KitchenStation.is_active == True,  # noqa: E712
    ).order_by(KitchenStation.sort_order, KitchenStation.name).all()

    product_mappings = await _q(ProductStation, db, hub_id).options(
        selectinload(ProductStation.station),
    ).all()

    category_mappings = await _q(CategoryStation, db, hub_id).options(
        selectinload(CategoryStation.station),
    ).all()

    return {
        "stations": stations,
        "product_mappings": product_mappings,
        "category_mappings": category_mappings,
    }


@router.post("/routing/product/assign")
async def assign_product_station(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    body = await request.json()
    product_id = body.get("product_id")
    station_id = body.get("station_id")
    if not product_id or not station_id:
        return JSONResponse({"error": "product_id and station_id required"}, status_code=400)

    station = await _q(KitchenStation, db, hub_id).get(uuid.UUID(station_id))
    if station is None:
        return JSONResponse({"error": "Station not found"}, status_code=404)

    # Update or create
    existing = await _q(ProductStation, db, hub_id).filter(
        ProductStation.product_id == uuid.UUID(product_id),
    ).first()
    if existing:
        existing.station_id = station.id
    else:
        async with atomic(db) as session:
            mapping = ProductStation(
                hub_id=hub_id,
                product_id=uuid.UUID(product_id),
                station_id=station.id,
            )
            session.add(mapping)
    await db.flush()
    return JSONResponse({"success": True})


@router.post("/routing/category/assign")
async def assign_category_station(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    body = await request.json()
    category_id = body.get("category_id")
    station_id = body.get("station_id")
    if not category_id or not station_id:
        return JSONResponse({"error": "category_id and station_id required"}, status_code=400)

    station = await _q(KitchenStation, db, hub_id).get(uuid.UUID(station_id))
    if station is None:
        return JSONResponse({"error": "Station not found"}, status_code=404)

    existing = await _q(CategoryStation, db, hub_id).filter(
        CategoryStation.category_id == uuid.UUID(category_id),
    ).first()
    if existing:
        existing.station_id = station.id
    else:
        async with atomic(db) as session:
            mapping = CategoryStation(
                hub_id=hub_id,
                category_id=uuid.UUID(category_id),
                station_id=station.id,
            )
            session.add(mapping)
    await db.flush()
    return JSONResponse({"success": True})


@router.post("/routing/product/{product_id}/remove")
async def remove_product_routing(
    request: Request, product_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    mapping = await _q(ProductStation, db, hub_id).filter(
        ProductStation.product_id == product_id,
    ).first()
    if mapping:
        await _q(ProductStation, db, hub_id).hard_delete(mapping.id)
    return JSONResponse({"success": True})


@router.post("/routing/category/{category_id}/remove")
async def remove_category_routing(
    request: Request, category_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    mapping = await _q(CategoryStation, db, hub_id).filter(
        CategoryStation.category_id == category_id,
    ).first()
    if mapping:
        await _q(CategoryStation, db, hub_id).hard_delete(mapping.id)
    return JSONResponse({"success": True})


# =============================================================================
# History
# =============================================================================

@router.get("/history")
@htmx_view(module_id="commands", view_id="history")
async def history(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    search_query = request.query_params.get("q", "").strip()
    status_filter = request.query_params.get("status", "")
    order_type_filter = request.query_params.get("order_type", "")
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")

    query = _q(Order, db, hub_id)

    if search_query:
        query = query.filter(or_(
            Order.order_number.ilike(f"%{search_query}%"),
        ))
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if order_type_filter:
        query = query.filter(Order.order_type == order_type_filter)
    if date_from:
        query = query.filter(Order.created_at >= date_from)
    if date_to:
        query = query.filter(Order.created_at <= date_to + " 23:59:59")

    orders = await query.order_by(Order.created_at.desc()).limit(100).all()

    completed = [o for o in orders if o.status == "paid"]
    total_revenue = sum((o.total for o in completed), Decimal("0"))

    return {
        "orders": orders,
        "search_query": search_query,
        "status_filter": status_filter,
        "order_type_filter": order_type_filter,
        "date_from": date_from,
        "date_to": date_to,
        "total_revenue": total_revenue,
        "orders_count": len(completed),
        "status_choices": [(s, STATUS_LABELS[s]) for s in STATUS_CHOICES],
        "order_type_choices": _order_type_choices(),
    }


# =============================================================================
# API Endpoints (JSON)
# =============================================================================

@router.post("/api/orders/create")
async def api_create_order(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create order with items via JSON API."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    items_data = data.get("items", [])
    if not items_data:
        return JSONResponse({"error": "At least one item is required"}, status_code=400)

    async with atomic(db) as session:
        order_num = await generate_order_number(session, hub_id)
        order = Order(
            hub_id=hub_id,
            order_number=order_num,
            table_id=uuid.UUID(data["table_id"]) if data.get("table_id") else None,
            sale_id=uuid.UUID(data["sale_id"]) if data.get("sale_id") else None,
            order_type=data.get("order_type", "dine_in"),
            priority=data.get("priority", "normal"),
            round_number=data.get("round_number", 1),
            notes=data.get("notes", ""),
            waiter_id=user.id,
        )
        session.add(order)
        await session.flush()

        for item_data in items_data:
            product_id = uuid.UUID(item_data["product_id"]) if item_data.get("product_id") else None

            station = None
            if data.get("auto_route", True) and product_id:
                station = await get_station_for_product(session, hub_id, product_id)

            item = OrderItem(
                hub_id=hub_id,
                order_id=order.id,
                product_id=product_id,
                product_name=item_data.get("product_name", ""),
                unit_price=Decimal(str(item_data.get("unit_price", "0"))),
                quantity=item_data.get("quantity", 1),
                station_id=station.id if station else None,
                modifiers=item_data.get("modifiers", ""),
                notes=item_data.get("notes", ""),
                seat_number=item_data.get("seat_number"),
            )
            item.recalculate_total()
            session.add(item)

        await session.flush()

        all_items = await _q(OrderItem, session, hub_id).filter(
            OrderItem.order_id == order.id,
        ).all()
        order.calculate_totals(all_items)
        await session.flush()

    return JSONResponse({
        "success": True,
        "order_id": str(order.id),
        "order_number": order.order_number,
        "item_count": len(items_data),
    })


@router.get("/api/orders/{order_id}")
async def api_get_order(
    request: Request, order_id: uuid.UUID,
    db: DbSession, hub_id: HubId,
):
    order = await _q(Order, db, hub_id).options(
        selectinload(Order.items).selectinload(OrderItem.station),
    ).get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    items = [i for i in order.items if not i.is_deleted]
    return JSONResponse({
        "success": True,
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "table": order.table_display,
            "status": order.status,
            "priority": order.priority,
            "order_type": order.order_type,
            "round_number": order.round_number,
            "notes": order.notes,
            "subtotal": str(order.subtotal),
            "total": str(order.total),
            "elapsed_minutes": order.elapsed_minutes,
            "is_delayed": order.is_delayed,
            "items": [{
                "id": str(item.id),
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "total": str(item.total),
                "modifiers": item.modifiers,
                "notes": item.notes,
                "status": item.status,
                "station": item.station.name if item.station else None,
                "seat_number": item.seat_number,
            } for item in items],
        },
    })


@router.get("/api/orders/pending")
async def api_pending_orders(
    request: Request, db: DbSession, hub_id: HubId,
):
    orders = await _q(Order, db, hub_id).filter(
        Order.status.in_(["pending", "preparing"]),
    ).order_by(Order.created_at).all()

    return JSONResponse({
        "success": True,
        "orders": [{
            "id": str(o.id),
            "order_number": o.order_number,
            "table": o.table_display,
            "status": o.status,
            "priority": o.priority,
            "elapsed_minutes": o.elapsed_minutes,
            "is_delayed": o.is_delayed,
        } for o in orders],
    })


@router.get("/api/orders/table/{table_id}")
async def api_orders_by_table(
    request: Request, table_id: uuid.UUID,
    db: DbSession, hub_id: HubId,
):
    orders = await _q(Order, db, hub_id).filter(
        Order.table_id == table_id,
        Order.status.in_(["pending", "preparing", "ready"]),
    ).order_by(Order.round_number, Order.created_at).all()

    return JSONResponse({
        "success": True,
        "orders": [{
            "id": str(o.id),
            "order_number": o.order_number,
            "status": o.status,
            "round_number": o.round_number,
        } for o in orders],
    })


@router.get("/api/orders/stats")
async def api_order_stats(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    date_str = request.query_params.get("date")
    if date_str:
        from datetime import datetime as dt
        date = dt.strptime(date_str, "%Y-%m-%d").date()
    else:
        date = datetime.now(UTC).date()

    orders = await _q(Order, db, hub_id).filter(
        func.date(Order.created_at) == date,
    ).all()

    total = len(orders)
    completed = sum(1 for o in orders if o.status in ("served", "paid"))
    cancelled = sum(1 for o in orders if o.status == "cancelled")

    prep_times = [
        (o.ready_at - o.fired_at).total_seconds() / 60
        for o in orders
        if o.fired_at and o.ready_at
    ]
    avg_prep = int(sum(prep_times) / len(prep_times)) if prep_times else None

    return JSONResponse({
        "success": True,
        "date": date.isoformat(),
        "total_orders": total,
        "completed": completed,
        "cancelled": cancelled,
        "avg_prep_time_minutes": avg_prep,
    })


@router.get("/api/stations/summary")
async def api_station_summary(
    request: Request, db: DbSession, hub_id: HubId,
):
    stations = await _q(KitchenStation, db, hub_id).filter(
        KitchenStation.is_active == True,  # noqa: E712
    ).all()

    result = []
    for s in stations:
        pending_count = await _q(OrderItem, db, hub_id).filter(
            OrderItem.station_id == s.id,
            OrderItem.status.in_(["pending", "preparing"]),
        ).count()
        result.append({
            "id": str(s.id),
            "name": s.name,
            "color": s.color,
            "icon": s.icon,
            "pending_count": pending_count,
        })

    return JSONResponse({"success": True, "stations": result})


@router.get("/api/stations/{station_id}/items")
async def api_station_items(
    request: Request, station_id: uuid.UUID,
    db: DbSession, hub_id: HubId,
):
    items = await _q(OrderItem, db, hub_id).filter(
        OrderItem.station_id == station_id,
        OrderItem.status.in_(["pending", "preparing"]),
    ).options(
        selectinload(OrderItem.order),
    ).order_by(OrderItem.created_at).all()

    return JSONResponse({
        "success": True,
        "items": [{
            "id": str(item.id),
            "order_number": item.order.order_number,
            "table": item.order.table_display,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "modifiers": item.modifiers,
            "notes": item.notes,
            "status": item.status,
            "priority": item.order.priority,
            "elapsed_minutes": item.order.elapsed_minutes,
            "is_delayed": item.order.is_delayed,
        } for item in items],
    })


# =============================================================================
# Settings
# =============================================================================

@router.get("/settings")
@htmx_view(module_id="commands", view_id="settings")
async def settings_view(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    config = await _get_settings(db, hub_id)
    today = datetime.now(UTC).date()

    today_orders = await _q(Order, db, hub_id).filter(
        func.date(Order.created_at) == today,
    ).all()

    stations = await _q(KitchenStation, db, hub_id).order_by(
        KitchenStation.sort_order, KitchenStation.name,
    ).all()

    today_revenue = sum(
        (o.total for o in today_orders if o.status == "paid"),
        Decimal("0"),
    )

    return {
        "config": config,
        "stations": stations,
        "today_orders_count": len(today_orders),
        "today_revenue": today_revenue,
    }


@router.post("/settings/save")
async def settings_save(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    config = await _get_settings(db, hub_id)
    fields = [
        "auto_print_tickets", "show_prep_time", "alert_threshold_minutes",
        "use_rounds", "auto_fire_on_round", "sound_on_new_order",
        "default_order_type",
    ]
    for field in fields:
        if field in data:
            setattr(config, field, data[field])
    await db.flush()
    return JSONResponse({"success": True})


@router.post("/settings/toggle")
async def settings_toggle(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    config = await _get_settings(db, hub_id)
    form = await request.form()
    name = form.get("name")
    value = form.get("value") == "true"

    if hasattr(config, name) and isinstance(getattr(config, name), bool):
        setattr(config, name, value)
        await db.flush()

    return JSONResponse(status_code=204, content=None)


@router.post("/settings/input")
async def settings_input(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    config = await _get_settings(db, hub_id)
    form = await request.form()
    name = form.get("name")
    value = form.get("value")

    if hasattr(config, name):
        setattr(config, name, int(value))
        await db.flush()

    return JSONResponse(status_code=204, content=None)


@router.post("/settings/reset")
async def settings_reset(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    config = await _get_settings(db, hub_id)
    config.auto_print_tickets = True
    config.show_prep_time = True
    config.alert_threshold_minutes = 15
    config.use_rounds = True
    config.auto_fire_on_round = False
    config.sound_on_new_order = True
    config.default_order_type = "dine_in"
    await db.flush()
    return JSONResponse(status_code=204, content=None)


# =============================================================================
# WebSocket — real-time order/command push notifications
# =============================================================================

logger = logging.getLogger(__name__)

# In-memory connection manager: hub_id → list of connected WebSockets.
_commands_connections: dict[str, list[WebSocket]] = {}


async def notify_commands_clients(hub_id: str, event: dict) -> None:
    """Push event to all connected commands WebSocket clients for this hub.

    Safe to call from any module — silently skips disconnected clients.
    """
    dead: list[WebSocket] = []
    for ws in _commands_connections.get(hub_id, []):
        ok = await ws_send(ws, event)
        if not ok:
            dead.append(ws)
    # Prune dead connections
    if dead:
        conns = _commands_connections.get(hub_id, [])
        for ws in dead:
            try:
                conns.remove(ws)
            except ValueError:
                pass


@router.websocket("/ws/orders")
async def commands_ws(websocket: WebSocket):
    """WebSocket for real-time command/order updates.

    Protocol:
        Server → Client: {"type": "orders_updated", "orders": [...], "stats": {...}}
        Server → Client: {"type": "order_created", "order": {...}}
        Server → Client: {"type": "order_status_changed", "order_id": "...", "status": "..."}
        Server → Client: {"type": "pong"}
        Client → Server: {"type": "ping"}
    """
    from app.core.middleware.session import get_session_data

    # --- Authenticate via session cookie ---
    session_data = get_session_data(websocket)
    user_id = session_data.get("user_id")
    hub_id = session_data.get("hub_id")

    if not user_id or not hub_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    hub_id_str = str(hub_id)

    # --- Register connection ---
    if hub_id_str not in _commands_connections:
        _commands_connections[hub_id_str] = []
    _commands_connections[hub_id_str].append(websocket)

    logger.info("Commands WS connected: hub=%s user=%s", hub_id_str, user_id)

    async def _on_message(data: dict, ws: WebSocket) -> None:
        """Handle incoming client messages."""
        msg_type = data.get("type", "")
        if msg_type == "refresh":
            # Client requests a full refresh of active orders
            await _push_orders_snapshot(ws, hub_id_str)

    try:
        # --- Push initial order list on connect ---
        await websocket.accept()
        await _push_orders_snapshot(websocket, hub_id_str)

        # Run the message loop (handles ping/pong + keepalive).
        import asyncio
        import json
        from starlette.websockets import WebSocketDisconnect, WebSocketState
        from app.core.ws import WS_PING_INTERVAL, _ping_loop

        ping_task = asyncio.create_task(_ping_loop(websocket, WS_PING_INTERVAL))
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    await ws_send(websocket, {"type": "error", "message": "Invalid JSON"})
                    continue

                if msg.get("type") == "ping":
                    await ws_send(websocket, {"type": "pong"})
                    continue

                try:
                    await _on_message(msg, websocket)
                except Exception:
                    logger.exception("Error handling commands WS message")
                    await ws_send(websocket, {"type": "error", "message": "Internal server error"})

        except WebSocketDisconnect:
            logger.info("Commands WS disconnected: hub=%s user=%s", hub_id_str, user_id)
        except Exception:
            logger.exception("Commands WS error: hub=%s", hub_id_str)
        finally:
            ping_task.cancel()
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except Exception:
                    pass
    finally:
        # --- Unregister connection ---
        conns = _commands_connections.get(hub_id_str, [])
        try:
            conns.remove(websocket)
        except ValueError:
            pass
        if not conns:
            _commands_connections.pop(hub_id_str, None)


async def _push_orders_snapshot(ws: WebSocket, hub_id_str: str) -> None:
    """Send the current active orders + stats to a single WebSocket client."""
    from app.config.database import async_session_factory

    async with async_session_factory() as db:
        orders = await HubQuery(Order, db, hub_id_str).filter(
            Order.status.in_(["pending", "preparing", "ready", "served"]),
        ).order_by(Order.created_at.desc()).all()

        counts: dict[str, int] = {}
        for o in orders:
            counts[o.status] = counts.get(o.status, 0) + 1

        orders_data = [{
            "id": str(o.id),
            "order_number": o.order_number,
            "table": o.table_display,
            "status": o.status,
            "priority": o.priority,
            "order_type": o.order_type,
            "elapsed_minutes": o.elapsed_minutes,
            "is_delayed": o.is_delayed,
        } for o in orders]

    await ws_send(ws, {
        "type": "orders_updated",
        "orders": orders_data,
        "stats": {
            "pending": counts.get("pending", 0),
            "preparing": counts.get("preparing", 0),
            "ready": counts.get("ready", 0),
            "served": counts.get("served", 0),
        },
    })
