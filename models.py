"""
Commands module models — SQLAlchemy 2.0.

Models: OrdersSettings, KitchenStation, Order, OrderItem, OrderModifier,
        ProductStation, CategoryStation.

NOTE: Table names use the 'orders_' prefix for DB compatibility with the
original Django module (app_label = 'orders'). The module_id is 'commands'.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import HubBaseModel

if TYPE_CHECKING:
    pass


# =============================================================================
# Settings
# =============================================================================

class OrdersSettings(HubBaseModel):
    """Per-hub configuration for commands module."""
    __tablename__ = "commands_settings"
    __table_args__ = (
        UniqueConstraint("hub_id", name="uq_commands_settings_hub"),
    )

    # Kitchen display settings
    auto_print_tickets: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    show_prep_time: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    alert_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, server_default="15",
    )

    # Order behavior
    use_rounds: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    auto_fire_on_round: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    default_order_type: Mapped[str] = mapped_column(
        String(20), default="dine_in", server_default="dine_in",
    )

    # Sound notifications
    sound_on_new_order: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )

    def __repr__(self) -> str:
        return f"<OrdersSettings hub={self.hub_id}>"


# =============================================================================
# Kitchen Stations
# =============================================================================

class KitchenStation(HubBaseModel):
    """
    Kitchen station for routing orders.
    Examples: Bar, Grill, Fryer, Dessert, Cold Kitchen.
    """
    __tablename__ = "orders_kitchen_station"
    __table_args__ = (
        UniqueConstraint("hub_id", "name", name="uq_kitchen_station_hub_name"),
        Index("ix_kitchen_station_hub_active", "hub_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_es: Mapped[str] = mapped_column(String(100), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Visual
    color: Mapped[str] = mapped_column(String(7), default="#F97316", server_default="#F97316")
    icon: Mapped[str] = mapped_column(String(50), default="flame-outline", server_default="flame-outline")

    # Printing
    printer_name: Mapped[str] = mapped_column(String(100), default="", server_default="")

    # Display
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Relationships
    order_items: Mapped[list[OrderItem]] = relationship(
        "OrderItem", back_populates="station",
    )
    product_mappings: Mapped[list[ProductStation]] = relationship(
        "ProductStation", back_populates="station", cascade="all, delete-orphan",
    )
    category_mappings: Mapped[list[CategoryStation]] = relationship(
        "CategoryStation", back_populates="station", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KitchenStation {self.name!r}>"


# =============================================================================
# Orders
# =============================================================================

STATUS_CHOICES = ("pending", "preparing", "ready", "served", "paid", "cancelled")
ORDER_TYPE_CHOICES = ("dine_in", "takeaway", "delivery")
PRIORITY_CHOICES = ("normal", "rush", "vip")

STATUS_LABELS = {
    "pending": "Pending",
    "preparing": "Preparing",
    "ready": "Ready",
    "served": "Served",
    "paid": "Paid",
    "cancelled": "Cancelled",
}

ORDER_TYPE_LABELS = {
    "dine_in": "Dine In",
    "takeaway": "Takeaway",
    "delivery": "Delivery",
}

PRIORITY_LABELS = {
    "normal": "Normal",
    "rush": "Rush",
    "vip": "VIP",
}


class Order(HubBaseModel):
    """Restaurant/retail order ticket."""
    __tablename__ = "orders_order"
    __table_args__ = (
        Index("ix_orders_order_hub_status", "hub_id", "status"),
        Index("ix_orders_order_hub_created", "hub_id", "created_at"),
        Index("ix_orders_order_hub_type", "hub_id", "order_type"),
    )

    # Identification
    order_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )

    # Links (FKs to other modules — nullable for cross-module safety)
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tables_table.id", ondelete="SET NULL"), nullable=True,
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sales_sale.id", ondelete="SET NULL"), nullable=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers_customer.id", ondelete="SET NULL"), nullable=True,
    )
    waiter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )

    # Order info
    order_type: Mapped[str] = mapped_column(
        String(20), default="dine_in", server_default="dine_in",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending",
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal",
    )

    # Round/course
    round_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1",
    )

    # Notes
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Financial
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Timing
    fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    served_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    items: Mapped[list[OrderItem]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order #{self.order_number}>"

    # ---- Display helpers ----

    @property
    def status_display(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def order_type_display(self) -> str:
        return ORDER_TYPE_LABELS.get(self.order_type, self.order_type)

    @property
    def priority_display(self) -> str:
        return PRIORITY_LABELS.get(self.priority, self.priority)

    @property
    def table_display(self) -> str:
        return "-"

    @property
    def elapsed_minutes(self) -> int:
        if not self.fired_at:
            return 0
        delta = datetime.now(UTC) - self.fired_at
        return int(delta.total_seconds() / 60)

    @property
    def prep_time_minutes(self) -> int | None:
        if not self.fired_at or not self.ready_at:
            return None
        delta = self.ready_at - self.fired_at
        return int(delta.total_seconds() / 60)

    @property
    def is_delayed(self) -> bool:
        return (
            self.status in ("pending", "preparing")
            and self.elapsed_minutes > 15
        )

    @property
    def can_be_edited(self) -> bool:
        return self.status in ("pending", "preparing")

    # ---- Financial ----

    def calculate_totals(self, items: list[OrderItem] | None = None) -> Decimal:
        """Recalculate subtotal and total from items."""
        if items is None:
            items = [i for i in self.items if not i.is_deleted]
        self.subtotal = sum((item.total for item in items), Decimal("0.00"))
        self.total = self.subtotal - self.discount + self.tax
        return self.total

    # ---- Number generation ----

    @staticmethod
    def generate_order_number_sync(hub_id: uuid.UUID) -> str:
        """Generate a fallback order number using timestamp."""
        now = datetime.now(UTC)
        prefix = now.strftime("%Y%m%d")
        # In the async version, the caller should query last order
        return f"{prefix}-0001"


# =============================================================================
# Order Items
# =============================================================================

ITEM_STATUS_CHOICES = ("pending", "preparing", "ready", "served", "cancelled")


class OrderItem(HubBaseModel):
    """Individual item in an order, routed to a kitchen station."""
    __tablename__ = "orders_order_item"
    __table_args__ = (
        Index("ix_order_item_status", "hub_id", "status"),
        Index("ix_order_item_station_status", "hub_id", "station_id", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders_order.id", ondelete="CASCADE"), nullable=False,
    )
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("orders_kitchen_station.id", ondelete="SET NULL"), nullable=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )

    # Snapshot
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Quantity & total
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Modifiers/notes
    modifiers: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending",
    )

    # Seat number (for splitting bills)
    seat_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timing
    fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="items")
    station: Mapped[KitchenStation | None] = relationship(
        "KitchenStation", back_populates="order_items",
    )
    modifier_details: Mapped[list[OrderModifier]] = relationship(
        "OrderModifier", back_populates="order_item", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<OrderItem {self.quantity}x {self.product_name!r}>"

    @property
    def display_name(self) -> str:
        if self.modifiers:
            return f"{self.product_name} ({self.modifiers})"
        return self.product_name

    @property
    def status_display(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def prep_time_minutes(self) -> int | None:
        if not self.started_at or not self.completed_at:
            return None
        return int((self.completed_at - self.started_at).total_seconds() / 60)

    def recalculate_total(self) -> None:
        """Recalculate item total from unit_price * quantity."""
        self.total = self.unit_price * self.quantity


# =============================================================================
# Order Modifier
# =============================================================================

class OrderModifier(HubBaseModel):
    """Modifier applied to an order item (extra toppings, cooking preferences)."""
    __tablename__ = "orders_order_modifier"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders_order_item.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Relationships
    order_item: Mapped[OrderItem] = relationship("OrderItem", back_populates="modifier_details")

    def __repr__(self) -> str:
        if self.price > 0:
            return f"<OrderModifier {self.name} (+{self.price})>"
        return f"<OrderModifier {self.name}>"


# =============================================================================
# Station Routing
# =============================================================================

class ProductStation(HubBaseModel):
    """Maps a product to a kitchen station for automatic routing."""
    __tablename__ = "orders_product_station"
    __table_args__ = (
        UniqueConstraint("hub_id", "product_id", name="uq_product_station_hub_product"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders_kitchen_station.id", ondelete="CASCADE"), nullable=False,
    )

    # Relationships
    station: Mapped[KitchenStation] = relationship("KitchenStation", back_populates="product_mappings")

    def __repr__(self) -> str:
        return f"<ProductStation product={self.product_id} -> station={self.station_id}>"


class CategoryStation(HubBaseModel):
    """Maps a product category to a kitchen station for automatic routing."""
    __tablename__ = "orders_category_station"
    __table_args__ = (
        UniqueConstraint("hub_id", "category_id", name="uq_category_station_hub_category"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders_kitchen_station.id", ondelete="CASCADE"), nullable=False,
    )

    # Relationships
    station: Mapped[KitchenStation] = relationship("KitchenStation", back_populates="category_mappings")

    def __repr__(self) -> str:
        return f"<CategoryStation category={self.category_id} -> station={self.station_id}>"


# =============================================================================
# Helper: get_station_for_product
# =============================================================================

async def get_station_for_product(
    session: Any,
    hub_id: uuid.UUID,
    product_id: uuid.UUID,
) -> KitchenStation | None:
    """
    Resolve the kitchen station for a product.
    Priority: direct product mapping > category mapping > None.
    """
    from app.core.db.query import HubQuery

    # Check direct product mapping
    mapping = await HubQuery(ProductStation, session, hub_id).filter(
        ProductStation.product_id == product_id,
    ).first()
    if mapping:
        station = await HubQuery(KitchenStation, session, hub_id).filter(
            KitchenStation.id == mapping.station_id,
            KitchenStation.is_active == True,  # noqa: E712
        ).first()
        if station:
            return station

    # Check category mapping
    try:
        from sqlalchemy import select
        # Try to get product's category from inventory module
        from importlib import import_module
        inv_models = import_module("inventory.models")
        Product = inv_models.Product
        result = await session.execute(
            select(Product.category_id).where(Product.id == product_id)
        )
        row = result.first()
        if row and row[0]:
            cat_mapping = await HubQuery(CategoryStation, session, hub_id).filter(
                CategoryStation.category_id == row[0],
            ).first()
            if cat_mapping:
                station = await HubQuery(KitchenStation, session, hub_id).filter(
                    KitchenStation.id == cat_mapping.station_id,
                    KitchenStation.is_active == True,  # noqa: E712
                ).first()
                if station:
                    return station
    except Exception:
        pass

    return None


async def generate_order_number(session: Any, hub_id: uuid.UUID) -> str:
    """Generate an order number in YYYYMMDD-XXXX format."""
    from app.core.db.query import HubQuery

    now = datetime.now(UTC)
    prefix = now.strftime("%Y%m%d")
    last = await HubQuery(Order, session, hub_id).filter(
        Order.order_number.startswith(prefix),
    ).order_by(Order.order_number.desc()).first()
    if last:
        try:
            num = int(last.order_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f"{prefix}-{num:04d}"
