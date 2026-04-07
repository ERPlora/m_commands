"""
AI context for the Commands module.
Loaded into the assistant system prompt when this module's tools are active.
"""

CONTEXT = """
## Module Knowledge: Commands

### Models
**KitchenStation** — Where items are prepared (Bar, Cocina Caliente, Cocina Fria, etc.).
- `name`, `color`, `icon`, `printer_name`, `sort_order`, `is_active`
- Items auto-routed to stations via ProductStation or CategoryStation mappings

**Order** — Restaurant ticket (command/comanda).
- `order_number`: auto-generated (YYYYMMDD-XXXX)
- `status`: pending | preparing | ready | served | paid | cancelled
- `order_type`: dine_in | takeaway | delivery
- `priority`: normal | rush | vip
- `table_id` -> tables.Table (optional FK)
- `sale_id` -> sales.Sale (linked when paid)
- `customer_id` -> customers.Customer (optional)
- `waiter_id` -> accounts.LocalUser
- `round_number`: course/round number for multi-course meals
- Financial: `subtotal`, `tax`, `discount`, `total`
- Timing: `fired_at` (sent to kitchen), `ready_at`, `served_at`

**OrderItem** — Individual item in an order.
- `order` -> Order (FK, related_name='items')
- `station` -> KitchenStation (routed automatically)
- `product_id` -> inventory.Product (snapshot in `product_name`, `unit_price`)
- `quantity`, `total`
- `status`: pending | preparing | ready | served | cancelled
- `modifiers` (text), `notes` (special instructions)
- `seat_number`: for bill splitting
- Timing: `fired_at`, `started_at`, `completed_at`

**ProductStation** — Routes a product to a specific station.
- `product_id` -> Product, `station` -> KitchenStation
- Priority: product mapping > category mapping

**CategoryStation** — Routes all products in a category to a station.
- `category_id` -> inventory.Category, `station` -> KitchenStation

**OrderModifier** — Extra modifier on an item (topping, cooking preference).
- `order_item` -> OrderItem, `name`, `price`

### Order workflow (fire/bump/serve)
1. Create order -> status=pending, items=pending
2. fire() -> status=preparing, fired_at=now, items=preparing (sent to KDS)
3. Kitchen: item.start_preparing() -> item.status=preparing
4. Kitchen: item.mark_ready() -> item.status=ready -> if all ready: order.mark_ready()
5. Waiter: order.mark_served() -> status=served
6. Payment: order links to Sale, status=paid
7. Recall: order.recall() -> status=preparing (if marked ready by mistake)

### Station routing (auto)
- get_station_for_product(session, hub_id, product_id): checks ProductStation first, then CategoryStation
- Used when creating OrderItems to assign the correct kitchen station

### Settings (OrdersSettings)
- `use_rounds`: enable round/course support
- `auto_fire_on_round`: automatically fire when round is set
- `alert_threshold_minutes`: minutes before order is marked delayed (default 15)
- `auto_print_tickets`

### Relationships
- Order -> Table (tables_table.orders)
- Order -> Sale (sales_sale.orders) — linked on payment
- OrderItem -> KitchenStation (kitchen display routing)
- Order -> kitchen.KitchenOrderLog (audit trail)

## Restrictions
- Cannot delete an order that is linked to a Sale (sale_id is set). Void or refund the sale first.
- Order delete is a soft-delete (is_deleted=True), not a hard delete.
- Only pending or cancelled orders can be deleted.
- Cannot create order items with invalid product IDs — product must exist in inventory.
- Cannot delete a kitchen station that has active routing mappings (ProductStation/CategoryStation).
- Cannot delete a kitchen station with active order items in progress (pending/preparing).
"""

SOPS = [
    {
        "id": "new_order",
        "triggers": {
            "es": ["nueva comanda", "crear pedido", "tomar pedido", "nuevo pedido"],
            "en": ["new order", "create order", "take order"],
        },
        "description": {"es": "Crear un nuevo pedido", "en": "Create a new order"},
        "steps": [
            {"tool": "list_tables", "description": "Show available tables"},
            {"tool": "create_order", "description": "Create order for table with items"},
        ],
        "modules_required": ["orders"],
    },
    {
        "id": "pending_orders",
        "triggers": {
            "es": ["pedidos pendientes", "comandas pendientes", "ver pedidos"],
            "en": ["pending orders", "view orders", "open orders"],
        },
        "description": {"es": "Ver pedidos pendientes", "en": "View pending orders"},
        "steps": [
            {"tool": "list_orders", "args": {"status": "pending"}, "description": "List pending orders"},
        ],
        "modules_required": ["orders"],
    },
]
