"""Assembly workspace for multi-file Order Reporting dataset construction.

Manages a lightweight session-state-backed workspace where users can
stage individual CSV files as order entities, track coverage, and import
the assembled dataset once enough entities are present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from file_profiler import (
    FileProfile,
    Importability,
    ProfileFamily,
    _ORDER_ENTITY_NAMES,
    profile_file,
)

# Minimum entities required for an importable Order Reporting dataset.
# At minimum we need orders + order_items + products.  Customers and
# categories can be synthesised from references in orders/order_items.
_REQUIRED_ENTITIES = {"orders", "order_items", "products"}
_ALL_ENTITIES = _ORDER_ENTITY_NAMES  # {"customers", "categories", "products", "orders", "order_items"}

_SESSION_KEY = "_assembly_workspace"


@dataclass
class StagedFile:
    """One file staged in the assembly workspace."""

    filename: str
    entity: str  # canonical entity name this file maps to
    profile: FileProfile
    data: bytes  # raw file bytes for later reading
    row_count: int = 0
    columns: list[str] = field(default_factory=list)


@dataclass
class AssemblyWorkspace:
    """Session-scoped workspace for assembling a multi-file order dataset."""

    staged: dict[str, StagedFile] = field(default_factory=dict)  # entity → StagedFile

    @property
    def covered_entities(self) -> set[str]:
        return set(self.staged.keys())

    @property
    def missing_entities(self) -> set[str]:
        return _ALL_ENTITIES - self.covered_entities

    @property
    def missing_required(self) -> set[str]:
        return _REQUIRED_ENTITIES - self.covered_entities

    @property
    def is_importable(self) -> bool:
        """True when the minimum required entities are staged."""
        return not self.missing_required

    @property
    def coverage_fraction(self) -> tuple[int, int]:
        """(covered, total) entity count."""
        return len(self.covered_entities), len(_ALL_ENTITIES)

    @property
    def readiness_label(self) -> str:
        covered, total = self.coverage_fraction
        if self.is_importable:
            return f"✅ Ready to import ({covered}/{total} entities)"
        return f"⚠️ Partial ({covered}/{total} entities — need more files)"


def get_workspace() -> AssemblyWorkspace:
    """Return (or create) the session-scoped assembly workspace."""
    if _SESSION_KEY not in st.session_state:
        st.session_state[_SESSION_KEY] = AssemblyWorkspace()
    return st.session_state[_SESSION_KEY]


def clear_workspace() -> None:
    """Reset the assembly workspace."""
    st.session_state[_SESSION_KEY] = AssemblyWorkspace()


def stage_file(
    filename: str,
    entity: str,
    profile: FileProfile,
    raw_bytes: bytes,
    df: pd.DataFrame,
) -> None:
    """Stage a file as a specific entity in the workspace.

    Replaces any previously staged file for the same entity.
    """
    ws = get_workspace()
    ws.staged[entity] = StagedFile(
        filename=filename,
        entity=entity,
        profile=profile,
        data=raw_bytes,
        row_count=len(df),
        columns=[str(c) for c in df.columns],
    )


def unstage_entity(entity: str) -> None:
    """Remove a staged entity from the workspace."""
    ws = get_workspace()
    ws.staged.pop(entity, None)


def build_assembled_frames() -> dict[str, pd.DataFrame]:
    """Read all staged files and return a dict of entity → DataFrame.

    Uses ``read_csv_robust`` for CSV files to maintain encoding resilience.
    """
    from csv_utils import read_csv_robust

    ws = get_workspace()
    frames: dict[str, pd.DataFrame] = {}

    for entity, sf in ws.staged.items():
        buf = BytesIO(sf.data)
        ext = sf.filename.rsplit(".", 1)[-1].lower() if "." in sf.filename else ""

        if ext == "csv":
            result = read_csv_robust(buf)
            if result.success and result.df is not None:
                frames[entity] = result.df
            else:
                raise ValueError(
                    f"Could not re-read staged file '{sf.filename}' for entity '{entity}': "
                    f"{result.error}"
                )
        elif ext in ("xlsx", "xls"):
            frames[entity] = pd.read_excel(buf, engine="openpyxl")
        else:
            raise ValueError(f"Unsupported file type for staged file '{sf.filename}'.")

    return frames
