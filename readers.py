"""Read CSV bundles and Excel workbooks into canonical DataFrames.

Each reader returns a dict[str, pd.DataFrame] keyed by canonical entity name.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from canonical_model import CANONICAL_ENTITIES

# Entity names the readers look for.
_ENTITY_NAMES = {e.name for e in CANONICAL_ENTITIES}


# ── CSV bundle reader ───────────────────────────────────────────


def read_csv_bundle(
    files: dict[str, BytesIO],
) -> dict[str, pd.DataFrame]:
    """Read uploaded CSV files into DataFrames.

    *files* maps filename (e.g. ``"customers.csv"``) → file-like object.
    Only files whose stem matches a canonical entity name are returned.
    """
    frames: dict[str, pd.DataFrame] = {}
    for filename, buf in files.items():
        stem = Path(filename).stem.lower()
        if stem in _ENTITY_NAMES:
            buf.seek(0)
            frames[stem] = pd.read_csv(buf)
    return frames


# ── Excel workbook reader ───────────────────────────────────────


def read_excel_workbook(
    buf: BytesIO,
) -> dict[str, pd.DataFrame]:
    """Read an Excel workbook with one sheet per canonical entity.

    Sheet names are matched case-insensitively against canonical entity names.
    """
    xls = pd.ExcelFile(buf)
    sheet_map = {s.lower(): s for s in xls.sheet_names}

    frames: dict[str, pd.DataFrame] = {}
    for entity_name in _ENTITY_NAMES:
        if entity_name in sheet_map:
            frames[entity_name] = xls.parse(sheet_map[entity_name])
    return frames
