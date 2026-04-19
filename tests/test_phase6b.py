"""Phase 6B tests — Ingestion State Clarity & Guided Import Flow.

Covers:
- saved_views: apply_view / flush_pending_view deferred pattern
- ingestion_state: ActiveDataset creation, activation, retrieval
- Assembly workspace: improved UX helpers
- Preset loading: no crash on profile switch
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Saved-view deferred apply ───────────────────────────────────


class TestApplyViewDeferred:
    """apply_view should schedule, not immediately mutate widget keys."""

    def _make_view(self, **kwargs):
        from saved_views import SavedView
        return SavedView(**kwargs)

    @patch("streamlit.session_state", new_callable=dict)
    def test_apply_view_stores_pending(self, mock_state):
        """apply_view should write _pending_view, not widget keys."""
        from saved_views import apply_view

        view = self._make_view(
            title="Test", profile="order_reporting", page="Summary",
        )
        warnings = apply_view(view)
        assert warnings == []
        assert "_pending_view" in mock_state
        assert mock_state["_pending_view"] is view
        # Must NOT write _profile_radio directly
        assert "_profile_radio" not in mock_state

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_apply_view_does_not_rerun(self, mock_state, mock_rerun):
        """apply_view should not trigger st.rerun — caller does that."""
        from saved_views import apply_view

        view = self._make_view(title="Test", profile="flat_metric", page="Summary")
        apply_view(view)
        mock_rerun.assert_not_called()


class TestFlushPendingView:
    """flush_pending_view applies scheduled state before widgets."""

    def _make_view(self, **kwargs):
        from saved_views import SavedView
        return SavedView(**kwargs)

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_noop_when_no_pending(self, mock_state, mock_rerun):
        """No pending view → no-op, no rerun."""
        from saved_views import flush_pending_view

        warnings = flush_pending_view()
        assert warnings == []
        mock_rerun.assert_not_called()

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_sets_profile_radio_order(self, mock_state, mock_rerun):
        """Flushing an order view sets _profile_radio before widgets."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="Order View", profile="order_reporting", page="Summary",
            statuses=["completed"], customers=["Acme"],
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("_profile_radio") == "\U0001f6d2 Order Reporting"
        assert mock_state.get("sel_statuses") == ["completed"]
        assert mock_state.get("sel_customers") == ["Acme"]
        mock_rerun.assert_called_once()

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_sets_profile_radio_fm(self, mock_state, mock_rerun):
        """Flushing an FM view sets _profile_radio to Flat Metric."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="FM View", profile="flat_metric", page="Summary",
            primary_metric="revenue", entities=["store_a"],
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("_profile_radio") == "\U0001f4cf Flat Metric"
        assert mock_state.get("fm_primary_metric") == "revenue"
        assert mock_state.get("sel_fm_entities") == ["store_a"]
        mock_rerun.assert_called_once()

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_warns_on_invalid_page(self, mock_state, mock_rerun):
        """Flushing with an unknown page should store a warning."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="Bad Page", profile="order_reporting", page="NonExistent",
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("nav_page") == "Summary"
        assert "_view_warnings" in mock_state
        assert any("NonExistent" in w for w in mock_state["_view_warnings"])

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_restores_top_n(self, mock_state, mock_rerun):
        """flush should restore top_n from saved view."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="Top5", profile="order_reporting", page="Summary", top_n=5,
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("top_n") == 5

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_restores_date_range(self, mock_state, mock_rerun):
        """flush should restore date_from/date_to from saved view."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="Dated", profile="order_reporting", page="Summary",
            date_from="2024-01-01", date_to="2024-06-30",
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("date_from") == "2024-01-01"
        assert mock_state.get("date_to") == "2024-06-30"

    @patch("streamlit.rerun")
    @patch("streamlit.session_state", new_callable=dict)
    def test_flush_restores_fm_year_range(self, mock_state, mock_rerun):
        """flush should restore year_from/year_to for FM views."""
        from saved_views import flush_pending_view

        view = self._make_view(
            title="Year", profile="flat_metric", page="Summary",
            year_from=2020, year_to=2023,
        )
        mock_state["_pending_view"] = view

        flush_pending_view()

        assert mock_state.get("year_from") == 2020
        assert mock_state.get("year_to") == 2023


# ── Ingestion State ─────────────────────────────────────────────


class TestActiveDataset:
    """ActiveDataset model and session helpers."""

    def test_active_dataset_badge(self):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset

        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.CSV_BUNDLE,
            source_label="my_data.zip",
            row_counts={"orders": 100, "order_items": 500},
        )
        assert ds.total_rows == 600
        assert "📄" in ds.source_badge
        assert "my_data.zip" in ds.source_badge

    def test_active_dataset_assembled_badge(self):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset

        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.ASSEMBLED,
            source_label="Assembled dataset",
        )
        assert "🗂️" in ds.source_badge

    @patch("ingestion_state.st")
    def test_set_and_get_active_dataset(self, mock_st):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset, get_active_dataset, set_active_dataset

        mock_st.session_state = {}
        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.ADAPTED,
            source_label="test.xlsx",
            row_counts={"orders": 10},
        )
        set_active_dataset(ds)
        result = get_active_dataset(ProfileType.ORDER_REPORTING)
        assert result is ds
        assert result.total_rows == 10

    @patch("ingestion_state.st")
    def test_get_active_dataset_none(self, mock_st):
        from dataset_profile import ProfileType
        from ingestion_state import get_active_dataset

        mock_st.session_state = {}
        assert get_active_dataset(ProfileType.FLAT_METRIC) is None

    @patch("ingestion_state.st")
    def test_activate_from_result_success(self, mock_st):
        from dataset_profile import ImportResult, ProfileType, SourceType
        from ingestion_state import activate_from_result, get_active_dataset

        mock_st.session_state = {}
        result = ImportResult(
            success=True,
            source_type=SourceType.EXCEL_WORKBOOK,
            source_label="northwind.xlsx",
            profile_type=ProfileType.ORDER_REPORTING,
            row_counts={"orders": 50, "order_items": 200},
        )
        ds = activate_from_result(result)
        assert ds is not None
        assert ds.total_rows == 250
        assert ds.source_label == "northwind.xlsx"

        # Should be retrievable
        stored = get_active_dataset(ProfileType.ORDER_REPORTING)
        assert stored is ds

    @patch("ingestion_state.st")
    def test_activate_from_result_failure(self, mock_st):
        from dataset_profile import ImportResult, SourceType
        from ingestion_state import activate_from_result

        mock_st.session_state = {}
        result = ImportResult(
            success=False,
            source_type=SourceType.CSV_BUNDLE,
            source_label="bad.zip",
        )
        assert activate_from_result(result) is None

    @patch("ingestion_state.st")
    def test_clear_active_dataset(self, mock_st):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import (
            ActiveDataset,
            clear_active_dataset,
            get_active_dataset,
            set_active_dataset,
        )

        mock_st.session_state = {}
        ds = ActiveDataset(
            profile_type=ProfileType.FLAT_METRIC,
            source_type=SourceType.DEMO_SEED,
            source_label="demo",
        )
        set_active_dataset(ds)
        assert get_active_dataset(ProfileType.FLAT_METRIC) is not None

        clear_active_dataset(ProfileType.FLAT_METRIC)
        assert get_active_dataset(ProfileType.FLAT_METRIC) is None


# ── Importer: assembled source type ────────────────────────────


class TestAssembledSourceType:
    """import_adapted_frames should use ASSEMBLED for multi-file assembly."""

    @patch("importer._import_frames")
    def test_assembly_uses_assembled_source_type(self, mock_import):
        from dataset_profile import SourceType
        from importer import import_adapted_frames

        mock_import.return_value = MagicMock(success=True)
        import_adapted_frames(
            frames={"orders": MagicMock()},
            profile_family="order_reporting",
            adapter_name="multi_file_assembly",
            label="Assembled dataset",
        )
        _, kwargs = mock_import.call_args
        # Positional args: frames, source_type, label
        args = mock_import.call_args[0]
        assert args[1] == SourceType.ASSEMBLED

    @patch("importer._import_frames")
    def test_adapter_uses_adapted_source_type(self, mock_import):
        from dataset_profile import SourceType
        from importer import import_adapted_frames

        mock_import.return_value = MagicMock(success=True)
        import_adapted_frames(
            frames={"orders": MagicMock()},
            profile_family="order_reporting",
            adapter_name="northwind_excel",
            label="test.xlsx",
        )
        args = mock_import.call_args[0]
        assert args[1] == SourceType.ADAPTED


# ── SavedView model ────────────────────────────────────────────


class TestSavedViewModel:
    """SavedView model sanity checks."""

    def test_is_order_property(self):
        from saved_views import SavedView

        v = SavedView(profile="order_reporting")
        assert v.is_order is True

        v2 = SavedView(profile="flat_metric")
        assert v2.is_order is False

    def test_subtitle_property(self):
        from saved_views import SavedView

        v = SavedView(profile="order_reporting", page="Summary")
        assert "Order" in v.subtitle

    def test_round_trip_dict(self):
        from saved_views import SavedView

        v = SavedView(title="Test", profile="order_reporting", page="Summary", top_n=5)
        d = v.to_dict()
        v2 = SavedView.from_dict(d)
        assert v2.title == "Test"
        assert v2.top_n == 5
        assert v2.profile == "order_reporting"

    def test_from_dict_ignores_unknown_keys(self):
        from saved_views import SavedView

        data = {"title": "X", "unknown_field": 42, "profile": "flat_metric"}
        v = SavedView.from_dict(data)
        assert v.title == "X"
        assert v.profile == "flat_metric"


# ── Assembly workspace helpers ──────────────────────────────────


class TestAssemblyWorkspaceModel:
    """AssemblyWorkspace dataclass properties."""

    def test_coverage_empty(self):
        from assembly_workspace import AssemblyWorkspace
        ws = AssemblyWorkspace()
        assert ws.coverage_fraction == (0, 5)
        assert not ws.is_importable
        assert ws.missing_required == {"orders", "order_items", "products"}

    def test_coverage_partial(self):
        from assembly_workspace import AssemblyWorkspace, StagedFile
        ws = AssemblyWorkspace()
        ws.staged["orders"] = StagedFile(
            filename="orders.csv", entity="orders",
            profile=MagicMock(), data=b"", row_count=10,
        )
        covered, total = ws.coverage_fraction
        assert covered == 1
        assert total == 5
        assert not ws.is_importable

    def test_coverage_importable(self):
        from assembly_workspace import AssemblyWorkspace, StagedFile

        ws = AssemblyWorkspace()
        for entity in ("orders", "order_items", "products"):
            ws.staged[entity] = StagedFile(
                filename=f"{entity}.csv", entity=entity,
                profile=MagicMock(), data=b"", row_count=10,
            )
        assert ws.is_importable
        assert ws.missing_required == set()
        assert "Ready" in ws.readiness_label

    def test_readiness_label_partial(self):
        from assembly_workspace import AssemblyWorkspace
        ws = AssemblyWorkspace()
        assert "Partial" in ws.readiness_label
        assert "0/5" in ws.readiness_label
