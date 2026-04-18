"""Robust CSV reading with encoding fallback and delimiter sniffing.

Provides ``read_csv_robust`` — a drop-in replacement for ``pd.read_csv``
that tries multiple encodings and common delimiters before giving up.
Returns a ``CsvReadResult`` with the DataFrame, chosen encoding/delimiter,
and any diagnostic warnings.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

# Encoding fallback order — covers the vast majority of real-world CSVs.
_ENCODING_ORDER = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

# Delimiters to probe when comma fails or looks suspicious.
_DELIMITER_CANDIDATES = (",", ";", "\t")

# Minimum columns we'd expect for a "real" tabular file.
_MIN_COLS = 2


@dataclass
class CsvReadResult:
    """Outcome of a robust CSV read attempt."""

    df: pd.DataFrame | None = None
    success: bool = False
    encoding: str = ""
    delimiter: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""


def read_csv_robust(
    buf: BytesIO,
    *,
    nrows: int | None = None,
) -> CsvReadResult:
    """Read a CSV buffer with encoding fallback and delimiter sniffing.

    Strategy:
    1. Try each encoding in order.
    2. For each encoding, sniff the delimiter from the first few KB.
    3. If sniffing fails, try each common delimiter explicitly.
    4. Accept the first combination that produces ≥ 2 columns.
    5. Return structured diagnostics.
    """
    raw = buf.getvalue() if hasattr(buf, "getvalue") else buf.read()
    buf.seek(0)

    result = CsvReadResult()

    for enc in _ENCODING_ORDER:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

        # Try sniffing delimiter first
        sniffed_delim = _sniff_delimiter(text)
        delimiters_to_try = (
            [sniffed_delim] + [d for d in _DELIMITER_CANDIDATES if d != sniffed_delim]
            if sniffed_delim
            else list(_DELIMITER_CANDIDATES)
        )

        for delim in delimiters_to_try:
            try:
                df = pd.read_csv(
                    StringIO(text),
                    sep=delim,
                    nrows=nrows,
                    encoding_errors="strict",
                    on_bad_lines="warn",
                )
            except Exception:
                continue

            if df.shape[1] >= _MIN_COLS or (df.shape[1] == 1 and nrows is None):
                # Accept single-column if it's really a single-column file
                if df.shape[1] >= _MIN_COLS:
                    result.df = df
                    result.success = True
                    result.encoding = enc
                    result.delimiter = delim

                    if enc != "utf-8":
                        result.warnings.append(
                            f"File was read using '{enc}' encoding (not UTF-8)."
                        )
                    if delim != ",":
                        delim_name = {";": "semicolon", "\t": "tab"}.get(delim, repr(delim))
                        result.warnings.append(
                            f"Delimiter detected as {delim_name} (not comma)."
                        )
                    return result

        # If we decoded successfully but no delimiter worked well, try
        # comma with single-column acceptance (might be a legitimate
        # single-column CSV).
        try:
            df = pd.read_csv(StringIO(text), nrows=nrows, on_bad_lines="warn")
            if not df.empty:
                result.df = df
                result.success = True
                result.encoding = enc
                result.delimiter = ","
                if enc != "utf-8":
                    result.warnings.append(
                        f"File was read using '{enc}' encoding (not UTF-8)."
                    )
                return result
        except Exception:
            continue

    # All encodings/delimiters exhausted
    result.success = False
    result.error = (
        "Could not parse file as CSV with any supported encoding "
        f"({', '.join(_ENCODING_ORDER)}) or delimiter."
    )
    return result


def _sniff_delimiter(text: str, sample_size: int = 8192) -> str | None:
    """Use Python's csv.Sniffer to guess the delimiter."""
    sample = text[:sample_size]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return None
