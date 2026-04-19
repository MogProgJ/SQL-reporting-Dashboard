"""Tests for profile readiness / state helpers.

Unit tests — mocks all DB calls so no real database is needed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from profile_state import (
    FLAT_METRIC_TABLES,
    ORDER_TABLES,
    ProfileReadiness,
    ReadinessStatus,
    check_flat_metric_readiness,
    check_order_readiness,
)


# ── ProfileReadiness dataclass ──────────────────────────────────


class TestProfileReadiness:
    def test_is_ready_when_status_ready(self):
        pr = ProfileReadiness(
            status=ReadinessStatus.READY,
            present_tables=("t",),
            missing_tables=(),
            row_counts={"t": 5},
        )
        assert pr.is_ready is True

    def test_not_ready_when_schema_missing(self):
        pr = ProfileReadiness(
            status=ReadinessStatus.SCHEMA_MISSING,
            present_tables=(),
            missing_tables=("t",),
            row_counts={},
        )
        assert pr.is_ready is False

    def test_not_ready_when_no_data(self):
        pr = ProfileReadiness(
            status=ReadinessStatus.NO_DATA,
            present_tables=("t",),
            missing_tables=(),
            row_counts={"t": 0},
        )
        assert pr.is_ready is False

    def test_total_rows(self):
        pr = ProfileReadiness(
            status=ReadinessStatus.READY,
            present_tables=("a", "b"),
            missing_tables=(),
            row_counts={"a": 10, "b": 20},
        )
        assert pr.total_rows == 30


# ── table_exists helper ─────────────────────────────────────────


class TestTableExists:
    def test_returns_true_for_existing_table(self):
        from db import table_exists

        with patch("db.fetch_scalar", return_value=True):
            assert table_exists("orders") is True

    def test_returns_false_for_missing_table(self):
        from db import table_exists

        with patch("db.fetch_scalar", return_value=False):
            assert table_exists("nonexistent") is False


# ── Order readiness ─────────────────────────────────────────────


class TestOrderReadiness:
    def test_all_tables_present_with_data(self):
        with (
            patch("profile_state.table_exists", return_value=True),
            patch("profile_state.fetch_scalar", return_value=10),
        ):
            r = check_order_readiness()
        assert r.status == ReadinessStatus.READY
        assert r.is_ready is True
        assert r.missing_tables == ()
        assert len(r.row_counts) == len(ORDER_TABLES)
        assert all(v == 10 for v in r.row_counts.values())

    def test_missing_one_table(self):
        def fake_exists(tbl):
            return tbl != "order_items"

        with patch("profile_state.table_exists", side_effect=fake_exists):
            r = check_order_readiness()
        assert r.status == ReadinessStatus.SCHEMA_MISSING
        assert "order_items" in r.missing_tables
        assert r.row_counts == {}

    def test_all_tables_present_but_empty(self):
        with (
            patch("profile_state.table_exists", return_value=True),
            patch("profile_state.fetch_scalar", return_value=0),
        ):
            r = check_order_readiness()
        assert r.status == ReadinessStatus.NO_DATA
        assert r.is_ready is False
        assert all(v == 0 for v in r.row_counts.values())

    def test_all_tables_missing(self):
        with patch("profile_state.table_exists", return_value=False):
            r = check_order_readiness()
        assert r.status == ReadinessStatus.SCHEMA_MISSING
        assert len(r.missing_tables) == len(ORDER_TABLES)


# ── Flat metric readiness ───────────────────────────────────────


class TestFlatMetricReadiness:
    def test_table_present_with_data(self):
        with (
            patch("profile_state.table_exists", return_value=True),
            patch("profile_state.fetch_scalar", return_value=90),
        ):
            r = check_flat_metric_readiness()
        assert r.status == ReadinessStatus.READY
        assert r.row_counts == {"flat_metrics": 90}

    def test_table_missing(self):
        with patch("profile_state.table_exists", return_value=False):
            r = check_flat_metric_readiness()
        assert r.status == ReadinessStatus.SCHEMA_MISSING
        assert "flat_metrics" in r.missing_tables
        assert r.row_counts == {}

    def test_table_present_but_empty(self):
        with (
            patch("profile_state.table_exists", return_value=True),
            patch("profile_state.fetch_scalar", return_value=0),
        ):
            r = check_flat_metric_readiness()
        assert r.status == ReadinessStatus.NO_DATA
        assert r.row_counts == {"flat_metrics": 0}


# ── Hardened row-count helpers ──────────────────────────────────


class TestHardenedRowCounts:
    def test_order_row_counts_missing_table(self):
        from importer import get_current_row_counts

        def fake_exists(tbl):
            return tbl != "products"

        with (
            patch("db.table_exists", side_effect=fake_exists),
            patch("db.fetch_scalar", return_value=5),
        ):
            counts = get_current_row_counts()
        assert counts["products"] == 0
        assert counts["customers"] == 5

    def test_fm_row_counts_missing_table(self):
        from importer import get_flat_metric_row_counts

        with patch("db.table_exists", return_value=False):
            counts = get_flat_metric_row_counts()
        assert counts == {"flat_metrics": 0}

    def test_fm_row_counts_table_exists(self):
        from importer import get_flat_metric_row_counts

        with (
            patch("db.table_exists", return_value=True),
            patch("db.fetch_scalar", return_value=42),
        ):
            counts = get_flat_metric_row_counts()
        assert counts == {"flat_metrics": 42}


# ── ReadinessStatus enum ────────────────────────────────────────


class TestReadinessStatusEnum:
    def test_values(self):
        assert ReadinessStatus.READY.value == "ready"
        assert ReadinessStatus.SCHEMA_MISSING.value == "schema_missing"
        assert ReadinessStatus.NO_DATA.value == "no_data"

    def test_table_tuples(self):
        assert len(ORDER_TABLES) == 5
        assert "flat_metrics" in FLAT_METRIC_TABLES
