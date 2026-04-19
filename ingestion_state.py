"""Ingestion state — tracks the active dataset and import provenance.

Provides a session-scoped ``ActiveDataset`` that records *how* the
current data arrived (source type, label, row counts, timestamp) so
the sidebar can display provenance without re-querying the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import streamlit as st

from dataset_profile import ImportResult, ProfileType, SourceType

_ACTIVE_KEY = "_active_dataset"


@dataclass
class ActiveDataset:
    """Describes the dataset currently loaded in the dashboard."""

    profile_type: ProfileType
    source_type: SourceType
    source_label: str
    row_counts: dict[str, int] = field(default_factory=dict)
    imported_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds"),
    )

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())

    @property
    def source_badge(self) -> str:
        """Human-readable one-liner for the sidebar."""
        _ICONS = {
            SourceType.DEMO_SEED: "🌱",
            SourceType.CSV_BUNDLE: "📄",
            SourceType.EXCEL_WORKBOOK: "📗",
            SourceType.ADAPTED: "🔄",
            SourceType.ASSEMBLED: "🗂️",
        }
        icon = _ICONS.get(self.source_type, "📦")
        return f"{icon} {self.source_label}"


# ── Session helpers ─────────────────────────────────────────────

def get_active_dataset(profile_type: ProfileType) -> ActiveDataset | None:
    """Return the active dataset for a profile, or ``None``."""
    store: dict[str, ActiveDataset] = st.session_state.get(_ACTIVE_KEY, {})
    return store.get(profile_type.value)


def set_active_dataset(ds: ActiveDataset) -> None:
    """Store an active dataset (keyed by profile type)."""
    if _ACTIVE_KEY not in st.session_state:
        st.session_state[_ACTIVE_KEY] = {}
    st.session_state[_ACTIVE_KEY][ds.profile_type.value] = ds


def activate_from_result(result: ImportResult) -> ActiveDataset | None:
    """Create and store an ``ActiveDataset`` from a successful import result.

    Returns the new ``ActiveDataset``, or ``None`` if the import failed.
    """
    if not result.success:
        return None

    ds = ActiveDataset(
        profile_type=result.profile_type,
        source_type=result.source_type,
        source_label=result.source_label,
        row_counts=dict(result.row_counts),
    )
    set_active_dataset(ds)
    return ds


def clear_active_dataset(profile_type: ProfileType) -> None:
    """Remove the active dataset for a profile."""
    store: dict[str, ActiveDataset] = st.session_state.get(_ACTIVE_KEY, {})
    store.pop(profile_type.value, None)
