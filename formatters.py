"""Display formatting helpers for the dashboard.

Pure functions with no side effects — easy to test.
"""

from __future__ import annotations

import pandas as pd


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
