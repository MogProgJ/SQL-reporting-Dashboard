"""Tests for Phase 4 — Multi-Page Expansion.

Covers:
- Navigation state (nav_state.py) — unit tests
- Natural key duplicate validation — unit tests
- Flat metric deep-dive queries — integration tests
- Order deep-dive queries — integration tests
"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── nav_state unit tests ────────────────────────────────────────


class TestNavState:
    """Test navigation state helpers."""

    @pytest.fixture(autouse=True)
    def _clear_session(self):
        """Patch st.session_state with a plain dict for each test."""
        self._state: dict = {}
        with patch("nav_state.st") as mock_st:
            mock_st.session_state = self._state
            mock_st.rerun = MagicMock()
            mock_st.button = MagicMock(return_value=False)
            mock_st.selectbox = MagicMock()
            yield

    def test_get_page_default_order(self):
        from nav_state import get_page
        assert get_page(is_order=True) == "Summary"

    def test_get_page_default_flat_metric(self):
        from nav_state import get_page
        assert get_page(is_order=False) == "Summary"

    def test_set_page_stores_state(self):
        from nav_state import set_page, get_page, get_target
        set_page("Customer Detail", target="Acme Foods")
        assert self._state["nav_page"] == "Customer Detail"
        assert self._state["nav_target"] == "Acme Foods"

    def test_go_back_resets(self):
        from nav_state import go_back
        self._state["nav_page"] = "Entity Detail"
        self._state["nav_target"] = "Germany"
        go_back(is_order=False)
        assert self._state["nav_page"] == "Summary"
        assert self._state["nav_target"] is None

    def test_go_back_order_resets(self):
        from nav_state import go_back
        self._state["nav_page"] = "Customer Detail"
        self._state["nav_target"] = "Acme"
        go_back(is_order=True)
        assert self._state["nav_page"] == "Summary"
        assert self._state["nav_target"] is None

    def test_get_target_none_by_default(self):
        from nav_state import get_target
        assert get_target() is None

    def test_page_enums(self):
        from nav_state import OrderPage, FlatMetricPage
        assert OrderPage.SUMMARY.value == "Summary"
        assert OrderPage.CUSTOMER_DETAIL.value == "Customer Detail"
        assert OrderPage.PRODUCT_DETAIL.value == "Product Detail"
        assert OrderPage.ANOMALY_EXPLORER.value == "Anomaly Explorer"
        assert FlatMetricPage.SUMMARY.value == "Summary"
        assert FlatMetricPage.ENTITY_DETAIL.value == "Entity Detail"
        assert FlatMetricPage.METRIC_EXPLORER.value == "Metric Explorer"


# ── Natural key duplicate validation ────────────────────────────


class TestNaturalKeyValidation:
    """Test that natural key duplicate detection works correctly."""

    def test_no_duplicates(self):
        from validators import _validate_entity
        from flat_metric_model import FLAT_METRICS

        df = pd.DataFrame({
            "entity": ["A", "A", "B"],
            "metric_name": ["GDP", "HDI", "GDP"],
            "metric_value": [1.0, 2.0, 3.0],
            "year": [2021, 2021, 2021],
        })
        result = _validate_entity(FLAT_METRICS, df)
        errors = [i for i in result if i.severity == "error"]
        warnings = [i for i in result if i.severity == "warning"]
        assert len(errors) == 0
        # No duplicates, so no natural key warnings
        nk_warnings = [w for w in warnings if "duplicate" in w.message.lower()]
        assert len(nk_warnings) == 0

    def test_with_duplicates(self):
        from validators import _validate_entity
        from flat_metric_model import FLAT_METRICS

        df = pd.DataFrame({
            "entity": ["A", "A", "A"],
            "metric_name": ["GDP", "GDP", "HDI"],
            "metric_value": [1.0, 2.0, 3.0],
            "year": [2021, 2021, 2021],
        })
        result = _validate_entity(FLAT_METRICS, df)
        warnings = [i for i in result if i.severity == "warning"]
        nk_warnings = [w for w in warnings if "duplicate" in w.message.lower()]
        assert len(nk_warnings) >= 1


# ── IQR outlier detection in page_fm_metric ─────────────────────


class TestFmOutlierDetection:
    """Test the _find_outliers helper in page_fm_metric.py."""

    def test_empty(self):
        from page_fm_metric import _find_outliers
        df = pd.DataFrame(columns=["metric_value"])
        assert _find_outliers(df).empty

    def test_no_outliers(self):
        from page_fm_metric import _find_outliers
        df = pd.DataFrame({"metric_value": [100, 102, 98, 101, 99, 103, 97, 100]})
        assert _find_outliers(df).empty

    def test_with_outlier(self):
        from page_fm_metric import _find_outliers
        df = pd.DataFrame({
            "metric_value": [100, 102, 98, 101, 99, 103, 97, 100, 101, 500],
        })
        result = _find_outliers(df)
        assert len(result) >= 1
        assert result["metric_value"].min() > 200

    def test_too_few_rows(self):
        from page_fm_metric import _find_outliers
        df = pd.DataFrame({"metric_value": [1, 2, 3]})
        assert _find_outliers(df).empty


# ── Integration tests (require running DB) ───────────────────────

integration = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping integration tests",
)


@integration
class TestFlatMetricDeepDiveQueries:
    """Integration tests for flat metric entity + metric explorer queries."""

    def test_entity_summary(self):
        from flat_metric_queries import get_fm_entity_summary
        result = get_fm_entity_summary("Germany")
        assert not result.empty
        assert int(result.iloc[0]["total_rows"]) > 0

    def test_entity_metrics(self):
        from flat_metric_queries import get_fm_entity_metrics
        result = get_fm_entity_metrics("Germany")
        assert not result.empty
        assert "metric_name" in result.columns
        assert "metric_value" in result.columns

    def test_entity_trend(self):
        from flat_metric_queries import get_fm_entity_trend
        result = get_fm_entity_trend("Germany", "GDP per Capita")
        assert not result.empty
        assert "year" in result.columns

    def test_entity_comparison(self):
        from flat_metric_queries import get_fm_entity_comparison
        result = get_fm_entity_comparison("Germany", year=2023)
        assert not result.empty

    def test_metric_summary(self):
        from flat_metric_queries import get_fm_metric_summary
        result = get_fm_metric_summary("GDP per Capita")
        assert not result.empty
        assert int(result.iloc[0]["entity_count"]) > 0

    def test_metric_top_entities(self):
        from flat_metric_queries import get_fm_metric_top_entities
        result = get_fm_metric_top_entities("GDP per Capita", limit=5)
        assert len(result) <= 5
        assert not result.empty

    def test_metric_bottom_entities(self):
        from flat_metric_queries import get_fm_metric_bottom_entities
        result = get_fm_metric_bottom_entities("GDP per Capita", limit=5)
        assert len(result) <= 5
        assert not result.empty

    def test_metric_trend_avg(self):
        from flat_metric_queries import get_fm_metric_trend_avg
        result = get_fm_metric_trend_avg("GDP per Capita")
        assert not result.empty
        assert "avg_value" in result.columns

    def test_metric_outliers(self):
        from flat_metric_queries import get_fm_metric_outliers
        result = get_fm_metric_outliers("GDP per Capita")
        assert not result.empty
        assert "entity" in result.columns


@integration
class TestOrderDeepDiveQueries:
    """Integration tests for order customer + product detail queries."""

    def test_customer_summary(self):
        from queries import get_customer_summary
        result = get_customer_summary("Acme Foods")
        assert not result.empty
        assert result.iloc[0]["revenue_cents"] > 0

    def test_customer_trend(self):
        from queries import get_customer_trend
        result = get_customer_trend("Acme Foods")
        assert not result.empty
        assert "revenue_cents" in result.columns

    def test_customer_products(self):
        from queries import get_customer_products
        result = get_customer_products("Acme Foods", limit=5)
        assert not result.empty
        assert len(result) <= 5

    def test_customer_orders(self):
        from queries import get_customer_orders
        result = get_customer_orders("Acme Foods")
        assert not result.empty
        assert "order_id" in result.columns

    def test_product_summary(self):
        from queries import get_product_summary, get_products
        products = get_products()
        assert len(products) > 0
        result = get_product_summary(products[0])
        assert not result.empty
        assert result.iloc[0]["revenue_cents"] > 0

    def test_product_trend(self):
        from queries import get_product_trend, get_products
        products = get_products()
        result = get_product_trend(products[0])
        assert not result.empty

    def test_product_customers(self):
        from queries import get_product_customers, get_products
        products = get_products()
        result = get_product_customers(products[0], limit=5)
        assert not result.empty
        assert len(result) <= 5

    def test_product_orders(self):
        from queries import get_product_orders, get_products
        products = get_products()
        result = get_product_orders(products[0])
        assert not result.empty
