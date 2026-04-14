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
from readers import ReaderError, read_csv_bundle, read_excel_workbook
from validators import validate_dataframes


def import_csv_bundle(
    files: dict[str, BytesIO],
    label: str = "CSV upload",
) -> ImportResult:
    """Import a set of CSV files into the reporting database."""
    try:
        frames = read_csv_bundle(files)
    except ReaderError as exc:
        return _reader_error_result(exc, SourceType.CSV_BUNDLE, label)
    except Exception as exc:
        return _unexpected_error_result(exc, SourceType.CSV_BUNDLE, label)
    return _import_frames(frames, SourceType.CSV_BUNDLE, label)


def import_excel_workbook(
    buf: BytesIO,
    label: str = "Excel upload",
) -> ImportResult:
    """Import an Excel workbook into the reporting database."""
    try:
        frames = read_excel_workbook(buf)
    except ReaderError as exc:
        return _reader_error_result(exc, SourceType.EXCEL_WORKBOOK, label)
    except Exception as exc:
        return _unexpected_error_result(exc, SourceType.EXCEL_WORKBOOK, label)
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


def _reader_error_result(
    exc: ReaderError, source_type: SourceType, label: str,
) -> ImportResult:
    """Convert a ReaderError into a structured ImportResult."""
    msg = exc.summary
    if exc.detail:
        msg = f"{exc.summary}\n{exc.detail}"
    return ImportResult(
        success=False,
        source_type=source_type,
        source_label=label,
        issues=[ValidationIssue(entity="", column="", message=msg)],
    )


def _unexpected_error_result(
    exc: Exception, source_type: SourceType, label: str,
) -> ImportResult:
    """Convert an unexpected exception into a structured ImportResult."""
    return ImportResult(
        success=False,
        source_type=source_type,
        source_label=label,
        issues=[
            ValidationIssue(
                entity="",
                column="",
                message=(
                    f"Unexpected error reading the file: {type(exc).__name__}: {exc}\n"
                    "If this persists, check that the file is a valid CSV or "
                    "Excel workbook and try again."
                ),
            )
        ],
    )


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


# ── Template / example generators ───────────────────────────────

# Minimal sample rows for each entity — small, valid, and self-consistent.
_SAMPLE_DATA: dict[str, dict[str, list]] = {
    "customers": {
        "name": ["Alice Johnson", "Bob Smith"],
        "segment": ["SMB", "Enterprise"],
        "city": ["Portland", "Seattle"],
    },
    "categories": {
        "name": ["Electronics", "Office Supplies"],
    },
    "products": {
        "name": ["Wireless Mouse", "Notebook Pack"],
        "category": ["Electronics", "Office Supplies"],
        "unit_price_cents": [2999, 1250],
    },
    "orders": {
        "order_id": ["1001", "1002"],
        "customer": ["Alice Johnson", "Bob Smith"],
        "status": ["completed", "pending"],
        "created_at": ["2026-01-15", "2026-02-20"],
    },
    "order_items": {
        "order_id": ["1001", "1001", "1002"],
        "product": ["Wireless Mouse", "Notebook Pack", "Wireless Mouse"],
        "quantity": [2, 5, 1],
        "unit_price_cents": [2999, 1250, 2999],
    },
}


def generate_example_csv_zip() -> bytes:
    """Return a ZIP archive containing example CSV files for all entities."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entity_name in ("customers", "categories", "products", "orders", "order_items"):
            df = pd.DataFrame(_SAMPLE_DATA[entity_name])
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            zf.writestr(f"{entity_name}.csv", csv_bytes)
    return buf.getvalue()


def generate_example_excel() -> bytes:
    """Return an Excel workbook with one sheet per canonical entity."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for entity_name in ("customers", "categories", "products", "orders", "order_items"):
            df = pd.DataFrame(_SAMPLE_DATA[entity_name])
            df.to_excel(writer, sheet_name=entity_name, index=False)
    return buf.getvalue()
