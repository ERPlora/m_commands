# Kitchen Orders (module: `commands`)

This module provides real-time production order management for kitchens, workshops, bakeries, and factories. Orders are routed to kitchen stations and tracked through preparation stages.

## Naming history

The module was originally named **Commands** after the Spanish/French culinary term *comanda* (kitchen ticket). In 2026, the public display name was updated to **Kitchen Orders** for clarity in English-speaking markets.

To avoid breaking existing installations, the following identifiers are **intentionally preserved**:

| Identifier | Value | Reason |
|---|---|---|
| `MODULE_ID` | `commands` | Stored in `hub_module.module_id` in every production DB |
| Python package | `commands` | All imports use `from commands.models import ...` |
| DB table prefix | `orders_*` | Tables pre-date the module rename; changing requires a data migration |

## Python aliases

`commands/__init__.py` exports the following aliases so new code can use the preferred names:

```python
from commands import KitchenOrder       # = commands.models.Order
from commands import KitchenOrderItem   # = commands.models.OrderItem
```

Both aliases point to the same class objects; no data is duplicated.

## Usage

```python
# Preferred (new code)
from commands import KitchenOrder, KitchenOrderItem

# Legacy (still valid, never remove)
from commands.models import Order, OrderItem
```
