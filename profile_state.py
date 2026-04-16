"""Profile readiness and dataset-state helpers.

Provides explicit checks so the UI can determine whether a profile's
backing tables exist and contain data — without crashing on missing
schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from db import fetch_scalar, table_exists


class ReadinessStatus(str, Enum):
    """Possible states for an analytics profile."""

    READY = "ready"
    SCHEMA_MISSING = "schema_missing"
    NO_DATA = "no_data"


@dataclass(frozen=True)
class ProfileReadiness:
    """Result of a profile readiness check."""

    status: ReadinessStatus
    present_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]
    row_counts: dict[str, int]

    @property
    def is_ready(self) -> bool:
        return self.status == ReadinessStatus.READY

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())


# ── Required tables per profile ─────────────────────────────────

ORDER_TABLES: tuple[str, ...] = (
    "customers",
    "categories",
    "products",
    "orders",
    "order_items",
)

FLAT_METRIC_TABLES: tuple[str, ...] = ("flat_metrics",)


# ── Public helpers ──────────────────────────────────────────────

def check_order_readiness() -> ProfileReadiness:
    """Check whether the Order Reporting profile is ready to render."""
    return _check_tables(ORDER_TABLES)


def check_flat_metric_readiness() -> ProfileReadiness:
    """Check whether the Flat Metric profile is ready to render."""
    return _check_tables(FLAT_METRIC_TABLES)


# ── Internal ────────────────────────────────────────────────────

def _check_tables(required: tuple[str, ...]) -> ProfileReadiness:
    """Generic readiness check for a set of required tables."""
    present: list[str] = []
    missing: list[str] = []

    for tbl in required:
        if table_exists(tbl):
            present.append(tbl)
        else:
            missing.append(tbl)

    if missing:
        return ProfileReadiness(
            status=ReadinessStatus.SCHEMA_MISSING,
            present_tables=tuple(present),
            missing_tables=tuple(missing),
            row_counts={},
        )

    # All tables exist — get row counts
    counts: dict[str, int] = {}
    for tbl in required:
        val = fetch_scalar(f"SELECT COUNT(*) FROM {tbl};")  # noqa: S608
        counts[tbl] = int(val) if val else 0

    if all(v == 0 for v in counts.values()):
        status = ReadinessStatus.NO_DATA
    else:
        status = ReadinessStatus.READY

    return ProfileReadiness(
        status=status,
        present_tables=tuple(present),
        missing_tables=(),
        row_counts=counts,
    )
