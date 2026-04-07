"""
AI tools for the Commands module.

Uses @register_tool + AssistantTool class pattern.
All tools are async and use HubQuery for DB access.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import selectinload

from app.ai.registry import AssistantTool, register_tool
from app.core.db.query import HubQuery

from .models import (
    CategoryStation,
    KitchenStation,
    Order,
    OrderItem,
    OrdersSettings,
    ProductStation,
    generate_order_number,
)
from datetime import UTC


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@register_tool
class ListOrders(AssistantTool):
    name = "list_orders"
    description = (
        "Use this to browse or monitor active and recent orders. "
        "Returns order number, status, type, priority, table, waiter, item count, total, "
        "elapsed time in minutes, and whether the order is delayed. "
        "Read-only — no side effects. "
        "For full details including all line items, use get_order. "
        "Example triggers: 'what orders are pending?', 'show delayed orders', 'list takeaway orders'"
    )
    module_id = "commands"
    required_permission = "orders.view_order"
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": (
                    "Filter by order status. Options: 'pending' (just created), "
                    "'preparing' (sent to kitchen), 'ready' (kitchen done), "
                    "'served' (delivered to table), 'paid' (closed), 'cancelled'. "
                    "Omit to return all statuses."
                ),
            },
            "order_type": {
                "type": "string",
                "description": "Filter by order type. Options: 'dine_in', 'takeaway', 'delivery'. Omit for all types.",
            },
            "priority": {
                "type": "string",
                "description": "Filter by priority level. Options: 'normal', 'rush', 'vip'. Omit for all priorities.",
            },
            "table_id": {
                "type": "string",
                "description": "Filter orders for a specific table by its UUID. Use list_tables to find table IDs.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of orders to return. Default is 20.",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        query = _q(Order, session, hub_id)
        if args.get("status"):
            query = query.filter(Order.status == args["status"])
        if args.get("order_type"):
            query = query.filter(Order.order_type == args["order_type"])
        if args.get("priority"):
            query = query.filter(Order.priority == args["priority"])
        if args.get("table_id"):
            query = query.filter(Order.table_id == args["table_id"])

        limit = args.get("limit", 20)
        total = await query.count()
        orders = await query.order_by(Order.created_at.desc()).limit(limit).all()

        return {
            "orders": [
                {
                    "id": str(o.id),
                    "order_number": o.order_number,
                    "status": o.status,
                    "order_type": o.order_type,
                    "priority": o.priority,
                    "total": str(o.total),
                    "elapsed_minutes": o.elapsed_minutes,
                    "is_delayed": o.is_delayed,
                }
                for o in orders
            ],
            "total": total,
        }


@register_tool
class GetOrder(AssistantTool):
    name = "get_order"
    description = (
        "Use this to get the complete details of a specific order, including every line item "
        "(product name, quantity, price, status, kitchen station, seat number, modifiers, and notes), "
        "plus financial totals (subtotal, tax, discount, total), waiter, table, and elapsed time. "
        "Read-only — no side effects. "
        "Provide either order_id (UUID) or order_number (e.g., '20260301-0001'). "
        "Use list_orders first if you need to find an ID or order number."
    )
    module_id = "commands"
    required_permission = "orders.view_order"
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Internal UUID of the order.",
            },
            "order_number": {
                "type": "string",
                "description": "Human-readable order number (e.g., '20260301-0001').",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        query = _q(Order, session, hub_id).options(
            selectinload(Order.items).selectinload(OrderItem.station),
        )
        if args.get("order_id"):
            o = await query.get(args["order_id"])
        elif args.get("order_number"):
            o = await query.filter(Order.order_number == args["order_number"]).first()
        else:
            return {"error": "Provide order_id or order_number"}

        if o is None:
            return {"error": "Order not found"}

        items = [i for i in o.items if not i.is_deleted]
        return {
            "id": str(o.id),
            "order_number": o.order_number,
            "status": o.status,
            "order_type": o.order_type,
            "priority": o.priority,
            "notes": o.notes,
            "subtotal": str(o.subtotal),
            "tax": str(o.tax),
            "discount": str(o.discount),
            "total": str(o.total),
            "elapsed_minutes": o.elapsed_minutes,
            "items": [
                {
                    "id": str(i.id),
                    "product_name": i.product_name,
                    "quantity": i.quantity,
                    "unit_price": str(i.unit_price),
                    "total": str(i.total),
                    "status": i.status,
                    "station": i.station.name if i.station else None,
                    "notes": i.notes,
                    "modifiers": i.modifiers,
                    "seat_number": i.seat_number,
                }
                for i in items
            ],
        }


@register_tool
class CreateOrder(AssistantTool):
    name = "create_order"
    description = (
        "Use this to open a new order with one or more items. "
        "SIDE EFFECT: creates an Order and OrderItem records. Requires confirmation. "
        "For dine_in orders, provide table_id. For takeaway/delivery, table_id is optional. "
        "Product IDs must come from the inventory (use list_products to find them). "
        "After creation, use update_order_status with action='fire' to send it to the kitchen. "
        "Example triggers: 'create an order for table 5', 'open a takeaway order with 2 coffees'"
    )
    module_id = "commands"
    required_permission = "orders.add_order"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "order_type": {
                "type": "string",
                "description": "Type of order. Options: 'dine_in' (at a table, default), 'takeaway' (pick up), 'delivery' (delivered).",
            },
            "table_id": {
                "type": "string",
                "description": "UUID of the table (required for dine_in orders). Use list_tables to find table IDs.",
            },
            "customer_id": {
                "type": "string",
                "description": "UUID of the linked customer (optional).",
            },
            "waiter_id": {
                "type": "string",
                "description": "UUID of the staff member taking the order (optional).",
            },
            "priority": {
                "type": "string",
                "description": "Order urgency. Options: 'normal' (default), 'rush' (urgent), 'vip' (VIP guest).",
            },
            "notes": {
                "type": "string",
                "description": "General order notes (e.g., allergies, special requests).",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "UUID of the product from inventory.",
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "Number of units ordered.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Per-item notes (e.g., 'sin sal', 'muy hecho').",
                        },
                        "modifiers": {
                            "type": "string",
                            "description": "Modifier text for the item (e.g., 'extra cheese').",
                        },
                    },
                    "required": ["product_id", "quantity"],
                },
                "description": "List of products and quantities for this order.",
            },
        },
        "required": ["order_type"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        order_num = await generate_order_number(session, hub_id)
        order = Order(
            hub_id=hub_id,
            order_number=order_num,
            order_type=args["order_type"],
            table_id=args.get("table_id"),
            customer_id=args.get("customer_id"),
            waiter_id=args.get("waiter_id"),
            priority=args.get("priority", "normal"),
            notes=args.get("notes", ""),
        )
        session.add(order)
        await session.flush()

        items_created = []
        for item_data in args.get("items", []):
            product_id = item_data["product_id"]

            # Get product info from inventory — product must exist
            product_name = ""
            unit_price = Decimal("0.00")
            try:
                from importlib import import_module
                inv = import_module("inventory.models")
                product = await _q(inv.Product, session, hub_id).get(product_id)
                if product:
                    product_name = product.name
                    unit_price = getattr(product, "price", Decimal("0.00"))
                else:
                    return {"error": f"Product not found: {product_id}. Use list_products to find valid product IDs."}
            except ImportError:
                return {"error": "Inventory module is not installed. Cannot resolve product IDs."}

            item = OrderItem(
                hub_id=hub_id,
                order_id=order.id,
                product_id=product_id,
                product_name=product_name,
                unit_price=unit_price,
                quantity=item_data["quantity"],
                notes=item_data.get("notes", ""),
                modifiers=item_data.get("modifiers", ""),
            )
            item.recalculate_total()
            session.add(item)
            items_created.append({"product": item.product_name, "quantity": item.quantity})

        await session.flush()

        all_items = await _q(OrderItem, session, hub_id).filter(
            OrderItem.order_id == order.id,
        ).all()
        order.calculate_totals(all_items)
        await session.flush()

        return {
            "id": str(order.id),
            "order_number": order.order_number,
            "items": items_created,
            "total": str(order.total),
            "created": True,
        }


@register_tool
class UpdateOrderStatus(AssistantTool):
    name = "update_order_status"
    description = (
        "Use this to advance or change the status of an order through its lifecycle. "
        "SIDE EFFECT: changes order status and may trigger kitchen notifications. Requires confirmation. "
        "Actions and their effects: "
        "'fire' — sends order to kitchen (status: pending -> preparing); "
        "'mark_ready' — marks order as ready for pickup/serving (preparing -> ready); "
        "'mark_served' — marks order as delivered to the table (ready -> served); "
        "'cancel' — cancels the order (requires a reason); "
        "'recall' — re-sends a ready order back to the kitchen. "
        "Use get_order or list_orders to find the order_id."
    )
    module_id = "commands"
    required_permission = "orders.change_order"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "UUID of the order to update.",
            },
            "action": {
                "type": "string",
                "description": (
                    "Action to perform. Options: "
                    "'fire' (send to kitchen), "
                    "'mark_ready' (kitchen finished), "
                    "'mark_served' (delivered to guest), "
                    "'cancel' (cancel order — provide reason), "
                    "'recall' (send back to kitchen)."
                ),
            },
            "reason": {
                "type": "string",
                "description": "Cancellation reason. Required when action is 'cancel'.",
            },
        },
        "required": ["order_id", "action"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        from datetime import datetime

        o = await _q(Order, session, hub_id).options(
            selectinload(Order.items),
        ).get(args["order_id"])
        if o is None:
            return {"error": "Order not found"}

        action = args["action"]
        now = datetime.now(UTC)

        if action == "fire":
            o.fired_at = now
            o.status = "preparing"
            for item in o.items:
                if not item.is_deleted and item.status == "pending":
                    item.status = "preparing"
                    item.fired_at = now
        elif action == "mark_ready":
            o.status = "ready"
            o.ready_at = now
        elif action == "mark_served":
            o.status = "served"
            o.served_at = now
        elif action == "cancel":
            o.status = "cancelled"
            reason = args.get("reason", "")
            if reason:
                o.notes = f"{o.notes}\nCancelled: {reason}".strip()
            for item in o.items:
                if not item.is_deleted:
                    item.status = "cancelled"
        elif action == "recall":
            if o.status == "ready":
                o.status = "preparing"
                o.ready_at = None
                for item in o.items:
                    if not item.is_deleted and item.status == "ready":
                        item.status = "preparing"
                        item.completed_at = None
        else:
            return {"error": f"Unknown action: {action}"}

        await session.flush()
        return {"id": str(o.id), "order_number": o.order_number, "status": o.status, "updated": True}


@register_tool
class ListKitchenStations(AssistantTool):
    name = "list_kitchen_stations"
    description = (
        "Use this to see all kitchen stations configured for order routing "
        "(e.g., 'Plancha', 'Frios', 'Bebidas', 'Horno'). "
        "Returns name, color, icon, associated printer, active status, and current pending order count. "
        "Read-only — no side effects. "
        "Call this before set_station_routing to find station IDs."
    )
    module_id = "commands"
    required_permission = "orders.view_order"
    parameters = {
        "type": "object",
        "properties": {
            "is_active": {
                "type": "boolean",
                "description": "Set to true to return only active stations, false for inactive only. Omit for all stations.",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        query = _q(KitchenStation, session, hub_id)
        if "is_active" in args:
            query = query.filter(KitchenStation.is_active == args["is_active"])
        stations = await query.order_by(KitchenStation.sort_order).all()

        result = []
        for s in stations:
            pending_count = await _q(OrderItem, session, hub_id).filter(
                OrderItem.station_id == s.id,
                OrderItem.status.in_(["pending", "preparing"]),
            ).count()
            result.append({
                "id": str(s.id),
                "name": s.name,
                "color": s.color,
                "icon": s.icon,
                "printer_name": s.printer_name,
                "is_active": s.is_active,
                "pending_count": pending_count,
            })

        return {"stations": result}


@register_tool
class CreateKitchenStation(AssistantTool):
    name = "create_kitchen_station"
    description = (
        "Use this to create a new kitchen station that orders can be routed to "
        "(e.g., 'Plancha', 'Horno', 'Barra', 'Postres'). "
        "SIDE EFFECT: creates a new KitchenStation record. Requires confirmation. "
        "After creating the station, use set_station_routing to assign products or categories to it. "
        "Call list_kitchen_stations first to avoid duplicates."
    )
    module_id = "commands"
    required_permission = "orders.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Station name shown in the kitchen display."},
            "color": {"type": "string", "description": "Hex color code (e.g., '#FF5733')."},
            "icon": {"type": "string", "description": "Ionicon name (e.g., 'flame-outline')."},
            "printer_name": {"type": "string", "description": "Printer name for auto-print."},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        s = KitchenStation(
            hub_id=hub_id,
            name=args["name"],
            color=args.get("color", "#F97316"),
            icon=args.get("icon", "flame-outline"),
            printer_name=args.get("printer_name", ""),
        )
        session.add(s)
        await session.flush()
        return {"id": str(s.id), "name": s.name, "created": True}


@register_tool
class SetStationRouting(AssistantTool):
    name = "set_station_routing"
    description = (
        "Use this to route a product or product category to a specific kitchen station. "
        "When an order is fired, each item is automatically sent to its designated station. "
        "SIDE EFFECT: creates or updates a routing rule. Requires confirmation. "
        "Product-level routing takes priority over category-level routing."
    )
    module_id = "commands"
    required_permission = "orders.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "station_id": {"type": "string", "description": "UUID of the kitchen station."},
            "product_id": {"type": "string", "description": "UUID of the product to route."},
            "category_id": {"type": "string", "description": "UUID of the category to route."},
        },
        "required": ["station_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        station_id = args["station_id"]
        result = {}

        if args.get("product_id"):
            existing = await _q(ProductStation, session, hub_id).filter(
                ProductStation.product_id == args["product_id"],
            ).first()
            if existing:
                existing.station_id = station_id
                result["product_routing"] = {"product_id": args["product_id"], "created": False}
            else:
                ps = ProductStation(
                    hub_id=hub_id,
                    product_id=args["product_id"],
                    station_id=station_id,
                )
                session.add(ps)
                result["product_routing"] = {"product_id": args["product_id"], "created": True}

        if args.get("category_id"):
            existing = await _q(CategoryStation, session, hub_id).filter(
                CategoryStation.category_id == args["category_id"],
            ).first()
            if existing:
                existing.station_id = station_id
                result["category_routing"] = {"category_id": args["category_id"], "created": False}
            else:
                cs = CategoryStation(
                    hub_id=hub_id,
                    category_id=args["category_id"],
                    station_id=station_id,
                )
                session.add(cs)
                result["category_routing"] = {"category_id": args["category_id"], "created": True}

        await session.flush()
        return result


@register_tool
class GetOrdersSettings(AssistantTool):
    name = "get_orders_settings"
    description = (
        "Use this to read the current orders module configuration. "
        "Read-only — no side effects."
    )
    module_id = "commands"
    required_permission = "orders.view_settings"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        s = await _q(OrdersSettings, session, hub_id).first()
        if s is None:
            return {"error": "Settings not found"}
        return {
            "auto_print_tickets": s.auto_print_tickets,
            "show_prep_time": s.show_prep_time,
            "alert_threshold_minutes": s.alert_threshold_minutes,
            "use_rounds": s.use_rounds,
            "auto_fire_on_round": s.auto_fire_on_round,
            "default_order_type": s.default_order_type,
            "sound_on_new_order": s.sound_on_new_order,
        }


@register_tool
class UpdateOrdersSettings(AssistantTool):
    name = "update_orders_settings"
    description = (
        "Use this to change the orders module configuration. "
        "SIDE EFFECT: updates settings. Requires confirmation. "
        "Only the fields you provide are updated."
    )
    module_id = "commands"
    required_permission = "orders.change_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "auto_print_tickets": {"type": "boolean"},
            "show_prep_time": {"type": "boolean"},
            "alert_threshold_minutes": {"type": "integer"},
            "use_rounds": {"type": "boolean"},
            "auto_fire_on_round": {"type": "boolean"},
            "default_order_type": {"type": "string"},
            "sound_on_new_order": {"type": "boolean"},
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        s = await _q(OrdersSettings, session, hub_id).first()
        if s is None:
            return {"error": "Settings not found"}
        updated = []
        for field in [
            "auto_print_tickets", "show_prep_time", "alert_threshold_minutes",
            "use_rounds", "auto_fire_on_round", "default_order_type", "sound_on_new_order",
        ]:
            if field in args:
                setattr(s, field, args[field])
                updated.append(field)
        if updated:
            await session.flush()
        return {"updated_fields": updated, "success": True}


@register_tool
class UpdateOrder(AssistantTool):
    name = "update_order"
    description = (
        "Update an order's editable fields: notes, priority, order_type, table, waiter, customer. "
        "Only provided fields are changed. For status changes use update_order_status instead."
    )
    module_id = "commands"
    required_permission = "orders.change_order"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Order UUID"},
            "notes": {"type": "string"},
            "priority": {"type": "string", "description": "normal, rush, vip"},
            "order_type": {"type": "string", "description": "dine_in, takeaway, delivery"},
            "table_id": {"type": "string"},
            "waiter_id": {"type": "string"},
            "customer_id": {"type": "string"},
        },
        "required": ["order_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        o = await _q(Order, session, hub_id).get(args["order_id"])
        if o is None:
            return {"error": "Order not found"}
        for field in ["notes", "priority", "order_type", "table_id", "waiter_id", "customer_id"]:
            if field in args:
                setattr(o, field, args[field])
        await session.flush()
        return {"id": str(o.id), "order_number": o.order_number, "updated": True}


@register_tool
class DeleteOrder(AssistantTool):
    name = "delete_order"
    description = "Soft-delete an order (marks as deleted). Only pending or cancelled orders without linked sales can be deleted."
    module_id = "commands"
    required_permission = "orders.delete_order"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Order UUID"},
        },
        "required": ["order_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        from datetime import datetime

        o = await _q(Order, session, hub_id).get(args["order_id"])
        if o is None:
            return {"error": "Order not found"}
        if o.status not in ("pending", "cancelled"):
            return {"error": f"Cannot delete order in status '{o.status}'. Only pending or cancelled orders can be deleted."}

        # Check if order is linked to a Sale (paid)
        if o.sale_id is not None:
            return {"error": "Cannot delete order linked to a sale. Void or refund the sale first."}

        order_number = o.order_number
        o.is_deleted = True
        o.deleted_at = datetime.now(UTC)
        await session.flush()
        return {"deleted": True, "order_number": order_number}


@register_tool
class DeleteKitchenStation(AssistantTool):
    name = "delete_kitchen_station"
    description = "Delete a kitchen station."
    module_id = "commands"
    required_permission = "orders.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "station_id": {"type": "string", "description": "KitchenStation UUID"},
        },
        "required": ["station_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        s = await _q(KitchenStation, session, hub_id).get(args["station_id"])
        if s is None:
            return {"error": "Station not found"}

        # Check for active product/category routing mappings
        product_mappings = await _q(ProductStation, session, hub_id).filter(
            ProductStation.station_id == s.id,
        ).count()
        category_mappings = await _q(CategoryStation, session, hub_id).filter(
            CategoryStation.station_id == s.id,
        ).count()
        total_mappings = product_mappings + category_mappings
        if total_mappings > 0:
            return {
                "error": (
                    f"Cannot delete station '{s.name}' with {total_mappings} active routing mapping(s) "
                    f"({product_mappings} product, {category_mappings} category). "
                    "Reassign or remove the routings first using set_station_routing."
                ),
            }

        # Check for active orders routed to this station
        active_items = await _q(OrderItem, session, hub_id).filter(
            OrderItem.station_id == s.id,
            OrderItem.status.in_(["pending", "preparing"]),
        ).count()
        if active_items > 0:
            return {"error": f"Cannot delete station '{s.name}' with {active_items} active order item(s) in progress."}

        name = s.name
        await _q(KitchenStation, session, hub_id).hard_delete(s.id)
        return {"deleted": True, "name": name}


@register_tool
class UpdateKitchenStation(AssistantTool):
    name = "update_kitchen_station"
    description = "Update a kitchen station's name, color, icon, printer, or active status."
    module_id = "commands"
    required_permission = "orders.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "station_id": {"type": "string", "description": "KitchenStation UUID"},
            "name": {"type": "string"},
            "color": {"type": "string"},
            "icon": {"type": "string"},
            "printer_name": {"type": "string"},
            "is_active": {"type": "boolean"},
        },
        "required": ["station_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any, session: Any, hub_id: Any) -> dict:
        s = await _q(KitchenStation, session, hub_id).get(args["station_id"])
        if s is None:
            return {"error": "Station not found"}
        for field in ["name", "color", "icon", "printer_name", "is_active"]:
            if field in args:
                setattr(s, field, args[field])
        await session.flush()
        return {"id": str(s.id), "name": s.name, "updated": True}
