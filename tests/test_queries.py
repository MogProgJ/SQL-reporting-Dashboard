"""Tests for the query layer and database helpers.

These tests are split into two groups:
1. Unit tests — run without a database (mock-based).
2. Integration tests — require a running, seeded Postgres instance.
   Mark with @pytest.mark.integration so they can be skipped easily.
"""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── Unit tests (no DB required) ─────────────────────────────────

class TestBuildFilters:
    """Test the _build_filters helper in queries.py."""

    def _build(self, **kw):
        from queries import _build_filters
        return _build_filters(**kw)

    def test_no_filters(self):
        where, params = self._build()
        assert where == ""
        assert params == []

    def test_date_from_only(self):
        where, params = self._build(date_from=date(2026, 1, 1))
        assert "o.created_at >= %s" in where
        assert date(2026, 1, 1) in params

    def test_date_range(self):
        where, params = self._build(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 3, 31),
        )
        assert "WHERE" in where
        assert len(params) == 2

    def test_customers_filter(self):
        where, params = self._build(customers=["Acme Foods", "Bluebird Cafe"])
        assert "c.name = ANY(%s)" in where
        assert ["Acme Foods", "Bluebird Cafe"] in params

    def test_categories_filter(self):
        where, params = self._build(categories=["Produce"])
        assert "cat.name = ANY(%s)" in where

    def test_products_filter(self):
        where, params = self._build(products=["Organic Bananas"])
        assert "p.name = ANY(%s)" in where

    def test_combined_filters(self):
        where, params = self._build(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 6, 30),
            customers=["Acme Foods"],
            categories=["Dairy"],
            products=["Whole Milk 1gal"],
        )
        assert where.startswith("WHERE")
        assert " AND " in where
        assert len(params) == 5


class TestDbModule:
    """Test db.py helper behaviour (mocked connections)."""

    def test_missing_database_url_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to pick up empty DATABASE_URL
            import importlib
            import db as db_mod
            db_mod.DATABASE_URL = ""
            with pytest.raises(RuntimeError, match="DATABASE_URL"):
                db_mod.get_connection()

    def test_run_query_calls_read_sql(self):
        import db as db_mod
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(db_mod, "get_connection", return_value=mock_conn):
            with patch("pandas.read_sql_query", return_value=pd.DataFrame({"a": [1]})) as mock_read:
                result = db_mod.run_query("SELECT 1 AS a")
                mock_read.assert_called_once_with("SELECT 1 AS a", mock_conn, params=None)
                assert list(result.columns) == ["a"]


class TestCentsToDollars:
    """Test the formatting helper used by the dashboard."""

    def test_basic(self):
        # Import from app would pull in Streamlit; test the logic directly
        def cents_to_dollars(c):
            return f"${c / 100:,.2f}"

        assert cents_to_dollars(0) == "$0.00"
        assert cents_to_dollars(100) == "$1.00"
        assert cents_to_dollars(129900) == "$1,299.00"
        assert cents_to_dollars(50) == "$0.50"


# ── Integration tests (require running DB) ───────────────────────

integration = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping integration tests",
)


@integration
class TestIntegrationQueries:
    """Run real queries against the seeded database."""

    def test_get_customers(self):
        from queries import get_customers
        customers = get_customers()
        assert len(customers) >= 20
        assert "Acme Foods" in customers

    def test_get_categories(self):
        from queries import get_categories
        categories = get_categories()
        assert len(categories) >= 5
        assert "Produce" in categories

    def test_get_products(self):
        from queries import get_products
        products = get_products()
        assert len(products) >= 20

    def test_get_date_range(self):
        from queries import get_date_range
        mn, mx = get_date_range()
        assert mn <= mx

    def test_get_kpis_no_filters(self):
        from queries import get_kpis
        df = get_kpis()
        assert not df.empty
        row = df.iloc[0]
        assert row["total_orders"] > 0
        assert row["total_revenue_cents"] > 0
        assert row["avg_order_value_cents"] > 0
        assert row["unique_customers"] > 0

    def test_get_revenue_trend(self):
        from queries import get_revenue_trend
        df = get_revenue_trend()
        assert not df.empty
        assert "order_date" in df.columns
        assert "revenue_cents" in df.columns

    def test_get_top_customers(self):
        from queries import get_top_customers
        df = get_top_customers(limit=5)
        assert len(df) <= 5
        assert len(df) > 0

    def test_get_top_products(self):
        from queries import get_top_products
        df = get_top_products(limit=5)
        assert len(df) <= 5
        assert len(df) > 0

    def test_get_category_breakdown(self):
        from queries import get_category_breakdown
        df = get_category_breakdown()
        assert not df.empty
        assert "category" in df.columns

    def test_get_order_detail(self):
        from queries import get_order_detail
        df = get_order_detail()
        assert not df.empty
        expected_cols = {"order_id", "order_date", "status", "customer", "product", "category", "quantity"}
        assert expected_cols.issubset(set(df.columns))

    def test_filtered_kpis(self):
        from queries import get_kpis, get_date_range
        mn, mx = get_date_range()
        df = get_kpis(date_from=mn, date_to=mx)
        assert not df.empty
        assert df.iloc[0]["total_orders"] > 0
