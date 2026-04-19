"""Tests for Phase 4 Closeout — Semantic Hardening + Exploration Polish.

Covers:
- resolve_snapshot_year() logic — unit tests
- get_page() cross-profile validation — unit tests
- Snapshot ranking queries (one row per entity) — integration tests
- Snapshot comparison queries — integration tests
"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── resolve_snapshot_year unit tests ────────────────────────────


class TestResolveSnapshotYear:
    """Test resolve_snapshot_year helper logic."""

    @patch("flat_metric_queries.get_fm_year_range", return_value=(2021, 2023))
    def test_pinned_year(self, _mock):
        from flat_metric_queries import resolve_snapshot_year
        assert resolve_snapshot_year(year_from=2022, year_to=2022) == 2022

    @patch("flat_metric_queries.get_fm_year_range", return_value=(2021, 2023))
    def test_range_returns_latest(self, _mock):
        from flat_metric_queries import resolve_snapshot_year
        assert resolve_snapshot_year(year_from=2021, year_to=2023) == 2023

    @patch("flat_metric_queries.get_fm_year_range", return_value=(2021, 2023))
    def test_no_year_returns_latest(self, _mock):
        from flat_metric_queries import resolve_snapshot_year
        assert resolve_snapshot_year() == 2023

    @patch("flat_metric_queries.get_fm_year_range", return_value=None)
    def test_no_data_returns_none(self, _mock):
        from flat_metric_queries import resolve_snapshot_year
        assert resolve_snapshot_year() is None

    @patch("flat_metric_queries.get_fm_year_range", return_value=(2020, 2020))
    def test_single_year_dataset(self, _mock):
        from flat_metric_queries import resolve_snapshot_year
        assert resolve_snapshot_year() == 2020


# ── get_page cross-profile validation tests ─────────────────────


class TestGetPageValidation:
    """Test that get_page rejects stale cross-profile page values."""

    @pytest.fixture(autouse=True)
    def _clear_session(self):
        self._state: dict = {}
        with patch("nav_state.st") as mock_st:
            mock_st.session_state = self._state
            mock_st.rerun = MagicMock()
            mock_st.button = MagicMock(return_value=False)
            mock_st.selectbox = MagicMock()
            yield

    def test_stale_fm_page_in_order_context(self):
        from nav_state import get_page
        self._state["nav_page"] = "Entity Detail"
        result = get_page(is_order=True)
        assert result == "Summary"
        assert self._state["nav_page"] == "Summary"
        assert self._state["nav_target"] is None

    def test_stale_order_page_in_fm_context(self):
        from nav_state import get_page
        self._state["nav_page"] = "Customer Detail"
        result = get_page(is_order=False)
        assert result == "Summary"
        assert self._state["nav_page"] == "Summary"

    def test_valid_fm_page_preserved(self):
        from nav_state import get_page
        self._state["nav_page"] = "Entity Detail"
        result = get_page(is_order=False)
        assert result == "Entity Detail"

    def test_valid_order_page_preserved(self):
        from nav_state import get_page
        self._state["nav_page"] = "Customer Detail"
        result = get_page(is_order=True)
        assert result == "Customer Detail"

    def test_summary_shared_name_works_both_profiles(self):
        from nav_state import get_page
        self._state["nav_page"] = "Summary"
        assert get_page(is_order=True) == "Summary"
        assert get_page(is_order=False) == "Summary"


# ── Integration tests (require running DB) ───────────────────────

integration = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping integration tests",
)


@integration
class TestSnapshotRankingSemantics:
    """Integration tests for snapshot ranking — one row per entity."""

    def test_ranking_no_duplicate_entities(self):
        from flat_metric_queries import get_fm_ranking
        result = get_fm_ranking("GDP per Capita", limit=25)
        assert not result.empty
        assert result["entity"].is_unique, (
            "Ranking should have one row per entity"
        )

    def test_ranking_with_snapshot_year(self):
        from flat_metric_queries import get_fm_ranking
        result = get_fm_ranking("GDP per Capita", limit=25, snapshot_year=2023)
        assert not result.empty
        assert result["entity"].is_unique
        assert (result["year"] == 2023).all()

    def test_ranking_respects_limit(self):
        from flat_metric_queries import get_fm_ranking
        result = get_fm_ranking("GDP per Capita", limit=3)
        assert len(result) <= 3

    def test_ranking_sorted_descending(self):
        from flat_metric_queries import get_fm_ranking
        result = get_fm_ranking("GDP per Capita", limit=25)
        if len(result) > 1:
            vals = result["metric_value"].tolist()
            assert vals == sorted(vals, reverse=True)


@integration
class TestSnapshotComparisonSemantics:
    """Integration tests for snapshot comparison — one row per entity."""

    def test_comparison_no_duplicate_entities(self):
        from flat_metric_queries import get_fm_comparison
        result = get_fm_comparison("GDP per Capita")
        assert not result.empty
        assert result["entity"].is_unique, (
            "Comparison should have one row per entity"
        )

    def test_comparison_with_snapshot_year(self):
        from flat_metric_queries import get_fm_comparison
        result = get_fm_comparison("GDP per Capita", snapshot_year=2022)
        assert not result.empty
        assert result["entity"].is_unique
        assert (result["year"] == 2022).all()

    def test_comparison_sorted_descending(self):
        from flat_metric_queries import get_fm_comparison
        result = get_fm_comparison("GDP per Capita")
        if len(result) > 1:
            vals = result["metric_value"].tolist()
            assert vals == sorted(vals, reverse=True)
