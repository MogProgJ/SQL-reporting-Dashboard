"""Display formatting helpers for the dashboard.

Pure functions with no side effects — easy to test.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def cents_to_dollars(c: int | float) -> str:
    """Format a cents value as a dollar string: 12345 → '$123.45'."""
    return f"${c / 100:,.2f}"


def fmt_number(v: int | float) -> str:
    """Format an integer with thousands separators: 1234 → '1,234'."""
    return f"{int(v):,}"


def fmt_pct(v: float) -> str:
    """Format a float as a percentage string: 12.345 → '12.3%'."""
    return f"{v:.1f}%"


def add_rank(df: pd.DataFrame, col: str = "#") -> pd.DataFrame:
    """Return a copy with a 1-based rank column inserted at position 0."""
    out = df.copy()
    out.insert(0, col, range(1, len(out) + 1))
    return out


# ── Shared column-config builders ───────────────────────────────
# Consistent widths and formatting across all tables.
#
#  Column type     Width   Align    Format
#  ───────────     ─────   ─────    ──────
#  rank (#)         60     (default) %d
#  year             75     (default) %d
#  count / qty      85     (default) %d
#  money           110     (default) $%.2f
#  pct              80     (default) %.1f%%
#  score            80     (default) %.1f
#  text/name       None    (default) —
#  id (order#)      85     (default) %d


def col_rank(label: str = "#") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=60, format="%d")


def col_money(label: str = "Revenue") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=110, format="$%.2f")


def col_count(label: str = "Count", fmt: str = "%d") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=85, format=fmt)


def col_pct(label: str = "% Share") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=80, format="%.1f%%")


def col_year(label: str = "Year") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=75, format="%d")


def col_score(label: str = "Score") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=80, format="%.1f")


def col_id(label: str = "Order #") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=85, format="%d")


def col_text(label: str = "Name") -> st.column_config.TextColumn:
    return st.column_config.TextColumn(label)


def col_date(label: str = "Date") -> st.column_config.DateColumn:
    return st.column_config.DateColumn(label, width=100)


def col_value(label: str = "Value", fmt: str = "%.2f") -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, width=110, format=fmt)
