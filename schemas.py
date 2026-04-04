"""
Pydantic schemas for commands module.

Replaces Django forms — used for request validation and form rendering.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


# ============================================================================
# Order
# ============================================================================

class OrderCreate(BaseModel):
    order_type: str = Field(default="dine_in", max_length=20)
    table_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    priority: str = Field(default="normal", max_length=20)
    round_number: int = Field(default=1, ge=1)
    notes: str = ""


class OrderUpdate(BaseModel):
    order_type: str | None = None
    table_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    priority: str | None = None
    round_number: int | None = None
    notes: str | None = None


# ============================================================================
# Order Item
# ============================================================================

class OrderItemCreate(BaseModel):
    product_id: uuid.UUID | None = None
    product_name: str = Field(default="", max_length=255)
    unit_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    quantity: int = Field(default=1, ge=1)
    modifiers: str = ""
    notes: str = ""
    seat_number: int | None = None


# ============================================================================
# Kitchen Station
# ============================================================================

class KitchenStationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    name_es: str = Field(default="", max_length=100)
    description: str = ""
    color: str = Field(default="#F97316", max_length=7)
    icon: str = Field(default="flame-outline", max_length=50)
    printer_name: str = Field(default="", max_length=100)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class KitchenStationUpdate(BaseModel):
    name: str | None = None
    name_es: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    printer_name: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ============================================================================
# Settings
# ============================================================================

class OrdersSettingsUpdate(BaseModel):
    auto_print_tickets: bool | None = None
    show_prep_time: bool | None = None
    alert_threshold_minutes: int | None = None
    use_rounds: bool | None = None
    auto_fire_on_round: bool | None = None
    default_order_type: str | None = None
    sound_on_new_order: bool | None = None


# ============================================================================
# Order Modifier
# ============================================================================

class OrderModifierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(default=Decimal("0.00"), ge=0)


# ============================================================================
# Filter
# ============================================================================

class OrderFilter(BaseModel):
    q: str = ""
    status: str = ""
    order_type: str = ""
    date_from: str = ""
    date_to: str = ""
