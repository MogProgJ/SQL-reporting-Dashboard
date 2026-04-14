"""High-level import orchestrator.

Ties together readers → validators → normalizers → loader into a
single ``run_import`` entry point consumed by the UI.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from dataset_profile import DatasetProfile, ImportResult, SourceType, ValidationIssue
from loader import load_into_db
from normalizers import normalize_frames
from readers import read_csv_bundle, read_excel_workbook
from validators import validate_dataframes


def import_csv_bundle(
    files: dict[str, BytesIO],
    label: str = "CSV upload",
) -> ImportResult:
    """Import a set of CSV files into the reporting database."""
    frames = read_csv_bundle(files)
    return _import_frames(frames, SourceType.CSV_BUNDLE, label)


def import_excel_workbook(
    buf: BytesIO,
    label: str = "Excel upload",
) -> ImportResult:
    """Import an Excel workbook into the reporting database."""
    frames = read_excel_workbook(buf)
    return _import_frames(frames, SourceType.EXCEL_WORKBOOK, label)


def get_demo_profile() -> DatasetProfile:
    """Return a profile describing the built-in seed dataset."""
    return DatasetProfile(
        source_type=SourceType.DEMO_SEED,
        label="Built-in demo (seed.sql)",
    )


def get_current_row_counts() -> dict[str, int]:
    """Query current row counts from the reporting tables."""
    from db import fetch_scalar

    counts: dict[str, int] = {}
    for table in ("customers", "categories", "products", "orders", "order_items"):
        val = fetch_scalar(f"SELECT COUNT(*) FROM {table};")  # noqa: S608
        counts[table] = int(val) if val else 0
    return counts


# ── Internal ────────────────────────────────────────────────────


def _import_frames(
    frames: dict[str, pd.DataFrame],
    source_type: SourceType,
    label: str,
) -> ImportResult:
    """Validate, normalize, and load a dict of entity DataFrames."""
    # Normalize column names before validation
    for key in list(frames.keys()):
        frames[key].columns = [c.strip().lower() for c in frames[key].columns]

    issues = validate_dataframes(frames)
    errors = [i for i in issues if i.severity == "error"]

    if errors:
        return ImportResult(
            success=False,
            source_type=source_type,
            source_label=label,
            issues=issues,
        )

    # Normalize types
    normalized = normalize_frames(frames)

    # Load into database
    try:
        row_counts = load_into_db(normalized)
    except Exception as exc:
        issues.append(
            ValidationIssue(
                entity="",
                column="",
                message=f"Database load failed: {exc}",
            )
        )
        return ImportResult(
            success=False,
            source_type=source_type,
            source_label=label,
            issues=issues,
        )

    return ImportResult(
        success=True,
        source_type=source_type,
        source_label=label,
        issues=issues,  # may contain warnings
        row_counts=row_counts,
    )
