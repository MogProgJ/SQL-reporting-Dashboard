"""Normalize raw DataFrames into canonical shape before loading.

Handles column renaming, type coercion, date parsing, and money
normalization.  Pure functions — no I/O.
"""

from __future__ import annotations

import pandas as pd

from canonical_model import CANONICAL_ENTITIES, EntitySpec


def normalize_frames(
    frames: dict[str, pd.DataFrame],
    entity_specs: tuple | None = None,
) -> dict[str, pd.DataFrame]:
    """Return a copy of *frames* with each entity normalized to canonical types.

    *entity_specs* defaults to ``CANONICAL_ENTITIES`` (order reporting model).
    """
    specs = entity_specs or CANONICAL_ENTITIES
    out: dict[str, pd.DataFrame] = {}
    for spec in specs:
        if spec.name not in frames:
            continue
        out[spec.name] = _normalize_entity(spec, frames[spec.name].copy())
    return out


def _normalize_entity(spec: EntitySpec, df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a single entity DataFrame in-place and return it."""
    # Strip whitespace from column names
    df.columns = [c.strip().lower() for c in df.columns]

    for col in spec.columns:
        if col.name not in df.columns:
            continue

        if col.dtype == "int":
            df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
            # Round and convert to nullable int (handles NaN gracefully)
            df[col.name] = df[col.name].round(0).astype("Int64")

        elif col.dtype == "float":
            df[col.name] = pd.to_numeric(df[col.name], errors="coerce").astype("float64")

        elif col.dtype == "date":
            df[col.name] = pd.to_datetime(
                df[col.name], errors="coerce", format="mixed"
            )

        elif col.dtype == "text":
            df[col.name] = df[col.name].astype(str).str.strip()

    return df
