"""Read CSV bundles and Excel workbooks into canonical DataFrames.

Each reader returns a dict[str, pd.DataFrame] keyed by canonical entity name.
Raises ``ReaderError`` for user-facing failures (missing dependency, bad shape).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from canonical_model import CANONICAL_ENTITIES

# Entity names the readers look for (order-reporting profile).
_ENTITY_NAMES = {e.name for e in CANONICAL_ENTITIES}
EXPECTED_NAMES_SORTED: list[str] = sorted(_ENTITY_NAMES)

# Flat-metric profile expected columns.
_FM_REQUIRED_COLS = {"entity", "metric_name", "metric_value"}
_FM_ALL_COLS = _FM_REQUIRED_COLS | {"year", "score", "rank"}


class ReaderError(Exception):
    """A user-facing import reader failure.

    Attributes:
        summary: one-line description of the problem.
        detail: longer explanation or resolution hint.
    """

    def __init__(self, summary: str, detail: str = "") -> None:
        self.summary = summary
        self.detail = detail
        super().__init__(summary)


# ── CSV bundle reader ───────────────────────────────────────────


def read_csv_bundle(
    files: dict[str, BytesIO],
) -> dict[str, pd.DataFrame]:
    """Read uploaded CSV files into DataFrames.

    *files* maps filename (e.g. ``"customers.csv"``) → file-like object.
    Only files whose stem matches a canonical entity name are returned.
    Raises ``ReaderError`` if no recognised files are found.
    """
    frames: dict[str, pd.DataFrame] = {}
    for filename, buf in files.items():
        stem = Path(filename).stem.lower()
        if stem in _ENTITY_NAMES:
            buf.seek(0)
            frames[stem] = pd.read_csv(buf)

    if not frames:
        provided = sorted(Path(f).stem.lower() for f in files)
        raise ReaderError(
            summary="No recognised CSV files in the uploaded bundle.",
            detail=(
                f"Expected files named after the canonical entities: "
                f"{', '.join(EXPECTED_NAMES_SORTED)}.\n"
                f"Files provided: {', '.join(provided) or '(none)'}."
            ),
        )
    return frames


# ── Excel workbook reader ───────────────────────────────────────


def _check_openpyxl() -> None:
    """Raise ``ReaderError`` if the openpyxl engine is not installed."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise ReaderError(
            summary="Excel import requires the openpyxl package.",
            detail=(
                "Install it with:  pip install openpyxl\n"
                "Then restart the app and try again.\n"
                "Alternatively, export your data as CSV files and use "
                "the CSV bundle import instead."
            ),
        )


def read_excel_workbook(
    buf: BytesIO,
) -> dict[str, pd.DataFrame]:
    """Read an Excel workbook with one sheet per canonical entity.

    Sheet names are matched case-insensitively against canonical entity names.
    Raises ``ReaderError`` if openpyxl is missing or the workbook shape is
    incompatible with the canonical model.
    """
    _check_openpyxl()

    try:
        xls = pd.ExcelFile(buf, engine="openpyxl")
    except Exception as exc:
        raise ReaderError(
            summary="Could not open the uploaded file as an Excel workbook.",
            detail=f"pandas/openpyxl error: {exc}",
        )

    sheet_map = {s.lower(): s for s in xls.sheet_names}
    found = set(sheet_map.keys())
    expected = _ENTITY_NAMES
    matched = found & expected
    missing = expected - found

    if not matched:
        raise ReaderError(
            summary="This workbook is not compatible with the current reporting model.",
            detail=(
                f"Expected sheets: {', '.join(EXPECTED_NAMES_SORTED)}.\n"
                f"Found sheets: {', '.join(sorted(found)) or '(none)'}.\n\n"
                "The current import path requires a workbook with one sheet "
                "per canonical entity. Single-sheet or arbitrary spreadsheets "
                "are not yet supported."
            ),
        )

    if missing:
        raise ReaderError(
            summary="Workbook is missing required sheets.",
            detail=(
                f"Missing: {', '.join(sorted(missing))}.\n"
                f"Found: {', '.join(sorted(found))}.\n"
                f"All required sheets: {', '.join(EXPECTED_NAMES_SORTED)}."
            ),
        )

    frames: dict[str, pd.DataFrame] = {}
    for entity_name in _ENTITY_NAMES:
        if entity_name in sheet_map:
            frames[entity_name] = xls.parse(sheet_map[entity_name])
    return frames


# ── Flat-metric readers (single CSV / single Excel sheet) ───────


def _validate_fm_columns(df: pd.DataFrame) -> None:
    """Raise ``ReaderError`` if the DataFrame lacks required flat-metric columns."""
    cols = {c.strip().lower() for c in df.columns}
    missing = _FM_REQUIRED_COLS - cols
    if missing:
        raise ReaderError(
            summary="File is missing required flat-metric columns.",
            detail=(
                f"Missing: {', '.join(sorted(missing))}.\n"
                f"Required: {', '.join(sorted(_FM_REQUIRED_COLS))}.\n"
                f"Optional: {', '.join(sorted(_FM_ALL_COLS - _FM_REQUIRED_COLS))}.\n"
                f"Found: {', '.join(sorted(cols))}."
            ),
        )


def read_flat_metric_csv(buf: BytesIO) -> dict[str, pd.DataFrame]:
    """Read a single CSV file into a ``flat_metrics`` DataFrame.

    Raises ``ReaderError`` if required columns are missing.
    """
    try:
        buf.seek(0)
        df = pd.read_csv(buf)
    except Exception as exc:
        raise ReaderError(
            summary="Could not parse the uploaded CSV file.",
            detail=f"pandas error: {exc}",
        )
    if df.empty:
        raise ReaderError(
            summary="The uploaded CSV file has no data rows.",
            detail="Add at least one row of flat-metric data and try again.",
        )
    _validate_fm_columns(df)
    return {"flat_metrics": df}


def read_flat_metric_excel(buf: BytesIO) -> dict[str, pd.DataFrame]:
    """Read the first sheet of an Excel workbook into a ``flat_metrics`` DataFrame.

    Raises ``ReaderError`` if openpyxl is missing or columns are wrong.
    """
    _check_openpyxl()
    try:
        df = pd.read_excel(buf, engine="openpyxl")
    except Exception as exc:
        raise ReaderError(
            summary="Could not open the uploaded file as an Excel workbook.",
            detail=f"pandas/openpyxl error: {exc}",
        )
    if df.empty:
        raise ReaderError(
            summary="The uploaded Excel sheet has no data rows.",
            detail="Add at least one row of flat-metric data and try again.",
        )
    _validate_fm_columns(df)
    return {"flat_metrics": df}
