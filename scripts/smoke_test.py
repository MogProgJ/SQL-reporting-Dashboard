#!/usr/bin/env python3
"""Smoke-test helper — verify DB connectivity, schema, and data readiness.

Usage:
    python scripts/smoke_test.py              # from repo root
    python -m scripts.smoke_test              # alternative

Exit codes:
    0  All checks passed
    1  One or more checks failed
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path so we can import app modules.
_repo = Path(__file__).resolve().parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from db import get_connection  # noqa: E402
from profile_state import (  # noqa: E402
    ReadinessStatus,
    check_flat_metric_readiness,
    check_order_readiness,
)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    failures = 0

    # ── 1. DB connectivity ──────────────────────────────────────────
    print("Checking database connectivity ...")
    try:
        conn = get_connection()
        conn.close()
        _ok("Connected to database")
    except Exception as exc:
        _fail(f"Cannot connect: {exc}")
        # Everything else depends on the DB — bail early.
        return 1

    # ── 2. Order profile readiness ──────────────────────────────────
    print("Checking Order Reporting profile ...")
    order = check_order_readiness()
    if order.status == ReadinessStatus.READY:
        _ok(f"Order tables present, {order.total_rows:,} total rows")
    else:
        _fail(f"Order profile: {order.status.value} (missing={order.missing_tables})")
        failures += 1

    # ── 3. Flat Metric profile readiness ────────────────────────────
    print("Checking Flat Metric profile ...")
    fm = check_flat_metric_readiness()
    if fm.status == ReadinessStatus.READY:
        _ok(f"Flat Metric tables present, {fm.total_rows:,} total rows")
    else:
        _fail(f"Flat Metric profile: {fm.status.value} (missing={fm.missing_tables})")
        failures += 1

    # ── Summary ─────────────────────────────────────────────────────
    print()
    if failures:
        print(f"Smoke test: {failures} check(s) failed.")
        return 1
    print("Smoke test: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
