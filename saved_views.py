"""Saved-view model and JSON-file persistence.

A *saved view* captures enough analytical state to restore a meaningful
dashboard session: profile, page, filters, deep-dive target, and metadata.

Views are stored as individual JSON files under a configurable directory
(default ``saved_views/`` in the repo root).  Each file is named by the
view's UUID and is fully self-contained.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


# ── Configuration ───────────────────────────────────────────────

def _views_dir() -> Path:
    """Return the directory where saved views are persisted."""
    root = Path(os.getenv("SAVED_VIEWS_DIR", "saved_views"))
    root.mkdir(parents=True, exist_ok=True)
    return root


# ── Model ───────────────────────────────────────────────────────

@dataclass
class SavedView:
    """Serialisable snapshot of the current analytical state."""

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # Profile / page
    profile: str = "order_reporting"  # "order_reporting" | "flat_metric"
    page: str = "Summary"
    target: str | None = None  # deep-dive entity name

    # Order-profile filters
    date_from: str | None = None  # ISO date string
    date_to: str | None = None
    statuses: list[str] = field(default_factory=list)
    customers: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    top_n: int = 10

    # Flat-metric filters
    primary_metric: str | None = None
    entities: list[str] = field(default_factory=list)
    metric_names: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None

    # Optional flags
    is_preset: bool = False

    # ── Derived helpers ─────────────────────────────────────

    @property
    def is_order(self) -> bool:
        return self.profile == "order_reporting"

    @property
    def subtitle(self) -> str:
        """One-line summary for the view list."""
        profile_label = "Order" if self.is_order else "FM"
        parts = [profile_label, self.page]
        if self.target:
            parts.append(self.target)
        return " · ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SavedView":
        """Construct from a dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ── JSON encoder for date objects ───────────────────────────────

class _DateEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


# ── Persistence ─────────────────────────────────────────────────

def save_view(view: SavedView) -> Path:
    """Persist a saved view as a JSON file.  Returns the file path."""
    path = _views_dir() / f"{view.id}.json"
    path.write_text(json.dumps(view.to_dict(), cls=_DateEncoder, indent=2), encoding="utf-8")
    return path


def load_view(view_id: str) -> SavedView | None:
    """Load a single saved view by ID.  Returns ``None`` if not found."""
    path = _views_dir() / f"{view_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SavedView.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return None


def list_views() -> list[SavedView]:
    """Return all saved views, newest first."""
    views: list[SavedView] = []
    for p in _views_dir().glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            views.append(SavedView.from_dict(data))
        except (json.JSONDecodeError, TypeError):
            continue
    views.sort(key=lambda v: v.created_at, reverse=True)
    return views


def delete_view(view_id: str) -> bool:
    """Delete a saved view.  Returns True if it existed."""
    path = _views_dir() / f"{view_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# ── Capture / apply ─────────────────────────────────────────────

def capture_current_state(
    title: str,
    is_order: bool,
    page: str,
    target: str | None,
    filters: dict,
    top_n: int = 10,
    description: str = "",
) -> SavedView:
    """Build a SavedView from the current session state."""
    view = SavedView(
        title=title,
        description=description,
        profile="order_reporting" if is_order else "flat_metric",
        page=page,
        target=target,
        top_n=top_n,
    )
    if is_order:
        if filters.get("date_from"):
            view.date_from = str(filters["date_from"])
        if filters.get("date_to"):
            view.date_to = str(filters["date_to"])
        view.statuses = filters.get("statuses") or []
        view.customers = filters.get("customers") or []
        view.categories = filters.get("categories") or []
        view.products = filters.get("products") or []
    else:
        view.primary_metric = filters.get("_primary_metric")
        view.entities = filters.get("entities") or []
        view.metric_names = filters.get("metric_names") or []
        view.year_from = filters.get("year_from")
        view.year_to = filters.get("year_to")
    return view


def apply_view(view: SavedView) -> list[str]:
    """Write a saved view's state into ``st.session_state``.

    Validates page names and deep-dive targets before restoring.
    Returns a list of warnings for any state that could not be restored.
    """
    import streamlit as st
    from nav_state import FlatMetricPage, OrderPage, _PAGE_KEY, _TARGET_KEY

    warnings: list[str] = []

    # Profile — set the radio index
    if view.is_order:
        st.session_state["_profile_radio"] = "\U0001f6d2 Order Reporting"
    else:
        st.session_state["_profile_radio"] = "\U0001f4cf Flat Metric"

    # Page validation
    valid_pages = (
        {p.value for p in OrderPage} if view.is_order
        else {p.value for p in FlatMetricPage}
    )
    if view.page in valid_pages:
        st.session_state[_PAGE_KEY] = view.page
    else:
        warnings.append(f"Page '{view.page}' not found — falling back to Summary.")
        st.session_state[_PAGE_KEY] = "Summary"

    # Target — set even if stale (deep-dive pages show their own "not found")
    if view.target:
        st.session_state[_TARGET_KEY] = view.target
    else:
        st.session_state[_TARGET_KEY] = None

    # Filters
    if view.is_order:
        st.session_state["sel_statuses"] = view.statuses
        st.session_state["sel_customers"] = view.customers
        st.session_state["sel_categories"] = view.categories
        st.session_state["sel_products"] = view.products
    else:
        if view.primary_metric:
            st.session_state["fm_primary_metric"] = view.primary_metric
        st.session_state["sel_fm_entities"] = view.entities
        st.session_state["sel_fm_metrics"] = view.metric_names

    return warnings

    return warnings
