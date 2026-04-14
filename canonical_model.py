"""Canonical reporting model for the SQL Reporting Dashboard.

Defines the five entities the dashboard depends on, their required columns,
types, and semantic rules.  Every import source must produce data that
satisfies this contract before it can be loaded into the reporting tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Column spec ─────────────────────────────────────────────────


@dataclass(frozen=True)
class ColumnSpec:
    """One required column inside a canonical entity."""

    name: str
    dtype: str  # "text", "int", "date", "timestamp"
    description: str
    nullable: bool = False


# ── Entity specs ────────────────────────────────────────────────


@dataclass(frozen=True)
class EntitySpec:
    """A canonical entity (table) the dashboard requires."""

    name: str
    description: str
    columns: tuple[ColumnSpec, ...]
    natural_key: tuple[str, ...] = ()  # columns that uniquely identify a row

    @property
    def required_column_names(self) -> set[str]:
        return {c.name for c in self.columns}


# ── The five canonical entities ─────────────────────────────────

CUSTOMERS = EntitySpec(
    name="customers",
    description="People or organisations that place orders.",
    natural_key=("name",),
    columns=(
        ColumnSpec("name", "text", "Customer display name"),
        ColumnSpec("segment", "text", "Business segment (e.g. SMB, Enterprise)"),
        ColumnSpec("city", "text", "City where the customer is located"),
    ),
)

CATEGORIES = EntitySpec(
    name="categories",
    description="Product groupings used for breakdown reporting.",
    natural_key=("name",),
    columns=(
        ColumnSpec("name", "text", "Unique category name"),
    ),
)

PRODUCTS = EntitySpec(
    name="products",
    description="Items that can appear on order lines.",
    natural_key=("name",),
    columns=(
        ColumnSpec("name", "text", "Product display name"),
        ColumnSpec("category", "text", "Category name (must match a categories row)"),
        ColumnSpec(
            "unit_price_cents",
            "int",
            "Default/catalog unit price in cents (> 0)",
        ),
    ),
)

ORDERS = EntitySpec(
    name="orders",
    description="Individual purchase transactions.",
    natural_key=("order_id",),
    columns=(
        ColumnSpec("order_id", "text", "Unique order identifier"),
        ColumnSpec("customer", "text", "Customer name (must match a customers row)"),
        ColumnSpec(
            "status",
            "text",
            "Order status (e.g. completed, pending, cancelled)",
        ),
        ColumnSpec("created_at", "date", "Date the order was placed"),
    ),
)

ORDER_ITEMS = EntitySpec(
    name="order_items",
    description="Line items belonging to an order.",
    columns=(
        ColumnSpec("order_id", "text", "Parent order identifier (must match an orders row)"),
        ColumnSpec("product", "text", "Product name (must match a products row)"),
        ColumnSpec("quantity", "int", "Number of units (> 0)"),
        ColumnSpec(
            "unit_price_cents",
            "int",
            "Price per unit in cents at time of sale (> 0)",
        ),
    ),
)

# Ordered list — import/load order respects FK dependencies.
CANONICAL_ENTITIES: tuple[EntitySpec, ...] = (
    CUSTOMERS,
    CATEGORIES,
    PRODUCTS,
    ORDERS,
    ORDER_ITEMS,
)

ENTITY_MAP: dict[str, EntitySpec] = {e.name: e for e in CANONICAL_ENTITIES}


# ── Semantic notes (consumed by docs and validators) ────────────

REVENUE_RULE = (
    "Revenue is derived as SUM(order_items.quantity * order_items.unit_price_cents). "
    "All monetary values are stored in integer cents to avoid floating-point issues."
)

AOV_RULE = (
    "Average order value = total revenue / COUNT(DISTINCT orders.order_id)."
)

MONEY_CONVENTION = (
    "All prices and revenue figures are in integer cents. "
    "The dashboard converts to dollars for display only."
)
