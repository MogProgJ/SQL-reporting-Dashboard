"""Tests for saved_views, report_pack, and demo_presets modules.

All tests are pure-unit — no database or Streamlit runtime required.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# ═══════════════════════════════════════════════════════════════
#  saved_views
# ═══════════════════════════════════════════════════════════════

from saved_views import (
    SavedView,
    apply_view,
    capture_current_state,
    delete_view,
    list_views,
    load_view,
    save_view,
)


# ── Model ──────────────────────────────────────────────────────


class TestSavedViewModel:
    """SavedView dataclass serialisation & helpers."""

    def test_defaults(self):
        v = SavedView()
        assert v.profile == "order_reporting"
        assert v.page == "Summary"
        assert v.is_order is True
        assert v.target is None
        assert v.top_n == 10
        assert v.is_preset is False

    def test_to_dict_roundtrip(self):
        v = SavedView(title="test", profile="flat_metric", entities=["A"])
        d = v.to_dict()
        v2 = SavedView.from_dict(d)
        assert v2.title == "test"
        assert v2.profile == "flat_metric"
        assert v2.entities == ["A"]
        assert v2.is_order is False

    def test_from_dict_ignores_unknown_keys(self):
        d = {"title": "x", "unknown_field": 99}
        v = SavedView.from_dict(d)
        assert v.title == "x"

    def test_subtitle_order(self):
        v = SavedView(profile="order_reporting", page="Summary")
        assert "Order" in v.subtitle
        assert "Summary" in v.subtitle

    def test_subtitle_fm_with_target(self):
        v = SavedView(profile="flat_metric", page="Entity Detail", target="ACME")
        assert "FM" in v.subtitle
        assert "ACME" in v.subtitle

    def test_is_preset_flag(self):
        v = SavedView(is_preset=True)
        assert v.is_preset is True


# ── Persistence ────────────────────────────────────────────────


class TestPersistence:
    """JSON file save/load/list/delete."""

    @pytest.fixture(autouse=True)
    def _tmp_views_dir(self, tmp_path, monkeypatch):
        """Redirect saved views to a temp directory."""
        monkeypatch.setenv("SAVED_VIEWS_DIR", str(tmp_path / "views"))
        # Force the module to re-evaluate _views_dir
        self._dir = tmp_path / "views"

    def test_save_and_load(self):
        v = SavedView(title="my view", profile="order_reporting")
        save_view(v)
        loaded = load_view(v.id)
        assert loaded is not None
        assert loaded.title == "my view"
        assert loaded.id == v.id

    def test_load_nonexistent(self):
        assert load_view("nonexistent-id") is None

    def test_list_views_ordered_newest_first(self):
        v1 = SavedView(title="first", created_at="2024-01-01T00:00:00")
        v2 = SavedView(title="second", created_at="2024-06-01T00:00:00")
        save_view(v1)
        save_view(v2)
        views = list_views()
        assert len(views) == 2
        assert views[0].title == "second"
        assert views[1].title == "first"

    def test_delete_view(self):
        v = SavedView(title="to delete")
        save_view(v)
        assert delete_view(v.id) is True
        assert load_view(v.id) is None

    def test_delete_nonexistent(self):
        assert delete_view("nope") is False

    def test_corrupt_json_skipped(self):
        v = SavedView(title="good")
        save_view(v)
        # Write a corrupt file
        bad = Path(os.getenv("SAVED_VIEWS_DIR")) / "bad.json"
        bad.write_text("{invalid json", encoding="utf-8")
        views = list_views()
        assert len(views) == 1
        assert views[0].title == "good"


# ── Capture ────────────────────────────────────────────────────


class TestCaptureState:
    """capture_current_state() builder."""

    def test_capture_order(self):
        filters = dict(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 3, 31),
            customers=["Alice"],
            categories=[],
            products=["Widget"],
            statuses=["completed"],
        )
        v = capture_current_state(
            title="Q1",
            is_order=True,
            page="Summary",
            target=None,
            filters=filters,
            top_n=5,
        )
        assert v.is_order
        assert v.date_from == "2024-01-01"
        assert v.customers == ["Alice"]
        assert v.products == ["Widget"]
        assert v.top_n == 5

    def test_capture_fm(self):
        filters = dict(
            _primary_metric="Revenue",
            entities=["X"],
            metric_names=["Revenue", "Costs"],
            year_from=2020,
            year_to=2023,
        )
        v = capture_current_state(
            title="FM slice",
            is_order=False,
            page="Summary",
            target=None,
            filters=filters,
        )
        assert not v.is_order
        assert v.primary_metric == "Revenue"
        assert v.year_from == 2020


# ── Apply ──────────────────────────────────────────────────────


class TestApplyView:
    """apply_view() + flush_pending_view() deferred restoration."""

    @pytest.fixture()
    def fake_session(self):
        """Provide a dict that acts as st.session_state."""
        import streamlit as st
        state = {}
        with patch.object(st, "session_state", state):
            yield state

    def test_apply_order_view(self, fake_session):
        v = SavedView(
            profile="order_reporting",
            page="Summary",
            statuses=["completed"],
            customers=["Bob"],
        )
        warns = apply_view(v)
        assert warns == []
        # apply_view only schedules — keys are set after flush
        assert "_pending_view" in fake_session
        from saved_views import flush_pending_view
        with patch("streamlit.rerun"):
            flush_pending_view()
        assert fake_session["_profile_radio"].startswith("\U0001f6d2")
        assert fake_session["sel_statuses"] == ["completed"]
        assert fake_session["sel_customers"] == ["Bob"]

    def test_apply_fm_view(self, fake_session):
        v = SavedView(
            profile="flat_metric",
            page="Summary",
            primary_metric="Revenue",
            entities=["X"],
        )
        warns = apply_view(v)
        assert warns == []
        from saved_views import flush_pending_view
        with patch("streamlit.rerun"):
            flush_pending_view()
        assert fake_session["_profile_radio"].startswith("\U0001f4cf")
        assert fake_session["fm_primary_metric"] == "Revenue"

    def test_apply_invalid_page_warns(self, fake_session):
        v = SavedView(profile="order_reporting", page="NonexistentPage")
        apply_view(v)
        from saved_views import flush_pending_view
        with patch("streamlit.rerun"):
            flush_pending_view()
        warns = fake_session.get("_view_warnings", [])
        assert len(warns) == 1
        assert "NonexistentPage" in warns[0]
        assert fake_session["nav_page"] == "Summary"

    def test_apply_preserves_target(self, fake_session):
        v = SavedView(
            profile="order_reporting",
            page="Customer Detail",
            target="Alice Corp",
        )
        apply_view(v)
        from saved_views import flush_pending_view
        with patch("streamlit.rerun"):
            flush_pending_view()
        assert fake_session["nav_target"] == "Alice Corp"


# ═══════════════════════════════════════════════════════════════
#  report_pack
# ═══════════════════════════════════════════════════════════════

from report_pack import _serialise_filters


class TestReportPackHelpers:
    """Report pack serialisation helpers."""

    def test_serialise_filters_dates(self):
        result = _serialise_filters({"date_from": date(2024, 1, 1), "items": ["a"]})
        assert result["date_from"] == "2024-01-01"
        assert result["items"] == ["a"]

    def test_serialise_filters_empty(self):
        assert _serialise_filters({}) == {}


# ═══════════════════════════════════════════════════════════════
#  demo_presets
# ═══════════════════════════════════════════════════════════════

from demo_presets import get_presets


class TestDemoPresets:
    """Demo preset catalogue."""

    def test_order_presets_exist(self):
        presets = get_presets(is_order=True)
        assert len(presets) >= 1
        assert all(p.is_preset for p in presets)
        assert all(p.is_order for p in presets)

    def test_fm_presets_exist(self):
        presets = get_presets(is_order=False)
        assert len(presets) >= 1
        assert all(p.is_preset for p in presets)
        assert all(not p.is_order for p in presets)

    def test_presets_have_unique_ids(self):
        all_presets = get_presets(True) + get_presets(False)
        ids = [p.id for p in all_presets]
        assert len(ids) == len(set(ids))

    def test_presets_have_titles(self):
        for p in get_presets(True) + get_presets(False):
            assert p.title, f"Preset {p.id} has no title"

    def test_presets_have_valid_pages(self):
        from nav_state import FlatMetricPage, OrderPage

        order_pages = {p.value for p in OrderPage}
        fm_pages = {p.value for p in FlatMetricPage}
        for p in get_presets(True):
            assert p.page in order_pages, f"Invalid page {p.page} in {p.id}"
        for p in get_presets(False):
            assert p.page in fm_pages, f"Invalid page {p.page} in {p.id}"

    def test_presets_are_copies(self):
        """get_presets returns a copy, not the internal list."""
        p1 = get_presets(True)
        p2 = get_presets(True)
        assert p1 is not p2
