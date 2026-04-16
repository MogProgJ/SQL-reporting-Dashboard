"""Lightweight navigation state for profile-aware deep-dive pages.

Stores current page selection in ``st.session_state``.
Each profile has its own set of valid pages.
"""

from __future__ import annotations

from enum import Enum

import streamlit as st

# ── Page enums ──────────────────────────────────────────────────


class OrderPage(str, Enum):
    SUMMARY = "Summary"
    CUSTOMER_DETAIL = "Customer Detail"
    PRODUCT_DETAIL = "Product Detail"
    ANOMALY_EXPLORER = "Anomaly Explorer"


class FlatMetricPage(str, Enum):
    SUMMARY = "Summary"
    ENTITY_DETAIL = "Entity Detail"
    METRIC_EXPLORER = "Metric Explorer"


# ── State keys ──────────────────────────────────────────────────

_PAGE_KEY = "nav_page"
_TARGET_KEY = "nav_target"  # e.g. a customer name or entity name


# ── Public API ──────────────────────────────────────────────────


def get_page(is_order: bool) -> str:
    """Return the current page name for the active profile.

    If the stored page belongs to a different profile it is treated as
    Summary so that stale state from the other profile is ignored.
    """
    default = OrderPage.SUMMARY.value if is_order else FlatMetricPage.SUMMARY.value
    valid = {p.value for p in (OrderPage if is_order else FlatMetricPage)}
    current = st.session_state.get(_PAGE_KEY, default)
    if current not in valid:
        st.session_state[_PAGE_KEY] = default
        st.session_state[_TARGET_KEY] = None
        return default
    return current


def set_page(page: str, target: str | None = None) -> None:
    """Set the current page and optional target, then rerun."""
    st.session_state[_PAGE_KEY] = page
    st.session_state[_TARGET_KEY] = target
    st.rerun()


def get_target() -> str | None:
    """Return the current deep-dive target (entity, customer, etc.)."""
    return st.session_state.get(_TARGET_KEY)


def go_back(is_order: bool) -> None:
    """Navigate back to the profile summary."""
    default = OrderPage.SUMMARY.value if is_order else FlatMetricPage.SUMMARY.value
    st.session_state[_PAGE_KEY] = default
    st.session_state[_TARGET_KEY] = None
    st.rerun()


def render_nav(is_order: bool) -> None:
    """Render the page navigation selector in the sidebar."""
    if is_order:
        pages = [p.value for p in OrderPage]
    else:
        pages = [p.value for p in FlatMetricPage]

    current = get_page(is_order)
    if current not in pages:
        current = pages[0]

    st.selectbox(
        "Page",
        pages,
        index=pages.index(current),
        key="_nav_select",
        on_change=_on_nav_change,
        kwargs={"is_order": is_order},
    )


def _on_nav_change(is_order: bool) -> None:
    """Callback when the nav selector changes."""
    new_page = st.session_state.get("_nav_select", "Summary")
    st.session_state[_PAGE_KEY] = new_page
    # Clear target when switching pages (unless user navigated explicitly)
    if new_page == (OrderPage.SUMMARY.value if is_order else FlatMetricPage.SUMMARY.value):
        st.session_state[_TARGET_KEY] = None


def render_back_button(is_order: bool) -> None:
    """Render a back-to-summary button on deep-dive pages."""
    label = "← Back to Summary"
    if st.button(label, key="nav_back"):
        go_back(is_order)
