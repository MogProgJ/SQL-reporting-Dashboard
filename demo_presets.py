"""Built-in demo presets — reusable saved-view definitions for showcase flows.

Each preset is a ``SavedView`` with ``is_preset=True``.  The sidebar loads
presets alongside user-saved views so they are always available without
requiring any data import or manual filter tuning.
"""

from __future__ import annotations

from saved_views import SavedView


# ── Order presets ───────────────────────────────────────────────

_ORDER_PRESETS: list[SavedView] = [
    SavedView(
        id="preset-order-full-overview",
        title="Full overview (no filters)",
        description="All orders, default date range, top-10 charts.",
        profile="order_reporting",
        page="Summary",
        top_n=10,
        is_preset=True,
    ),
    SavedView(
        id="preset-order-top5-products",
        title="Top 5 products",
        description="Summary view narrowed to the top-5 product slice.",
        profile="order_reporting",
        page="Summary",
        top_n=5,
        is_preset=True,
    ),
    SavedView(
        id="preset-order-completed-only",
        title="Completed orders only",
        description="Filters to completed orders for revenue accuracy.",
        profile="order_reporting",
        page="Summary",
        statuses=["completed"],
        top_n=10,
        is_preset=True,
    ),
]


# ── Flat-metric presets ─────────────────────────────────────────

_FM_PRESETS: list[SavedView] = [
    SavedView(
        id="preset-fm-full-overview",
        title="All entities & metrics",
        description="Unfiltered view across every entity and metric.",
        profile="flat_metric",
        page="Summary",
        is_preset=True,
    ),
]


# ── Public API ──────────────────────────────────────────────────

def get_presets(is_order: bool) -> list[SavedView]:
    """Return presets for the active profile."""
    return list(_ORDER_PRESETS) if is_order else list(_FM_PRESETS)
