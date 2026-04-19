"""File profiler — inspect incoming files before import.

The profiler examines an uploaded file (or archive) and produces a
structured ``FileProfile`` describing what it contains, what it resembles,
and what the app can do with it.  This drives the preview/adapt/import UX.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from csv_utils import read_csv_robust


# ── Enums ───────────────────────────────────────────────────────

class FileType(str, Enum):
    """Detected file type."""
    CSV = "csv"
    XLSX = "xlsx"
    ZIP = "zip"
    UNKNOWN = "unknown"


class Importability(str, Enum):
    """What the app can do with this file."""
    FULL_IMPORT = "full_import"            # canonical strict match
    ADAPTER_IMPORT = "adapter_import"      # importable via a known adapter
    PREVIEW_ONLY = "preview_only"          # readable but not importable yet
    PARTIAL_DATASET = "partial_dataset"    # incomplete — needs companion data
    UNSUPPORTED = "unsupported"            # nothing useful we can do


class ProfileFamily(str, Enum):
    """Which analytics profile a file likely belongs to."""
    ORDER_REPORTING = "order_reporting"
    FLAT_METRIC = "flat_metric"
    UNKNOWN = "unknown"


# ── Result models ───────────────────────────────────────────────

@dataclass
class TabularAsset:
    """One readable table found in a file (a CSV, or a sheet in XLSX/ZIP)."""
    name: str
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    inferred_types: dict[str, str] = field(default_factory=dict)


@dataclass
class FileProfile:
    """Structured result of profiling an uploaded file."""
    filename: str
    file_type: FileType = FileType.UNKNOWN
    size_bytes: int = 0

    # Structure
    assets: list[TabularAsset] = field(default_factory=list)

    # Classification
    profile_family: ProfileFamily = ProfileFamily.UNKNOWN
    suggested_adapter: str | None = None
    importability: Importability = Importability.UNSUPPORTED
    confidence: str = ""          # brief reasoning

    # Partial-dataset info
    missing_entities: list[str] = field(default_factory=list)
    detected_entity: str = ""  # canonical entity this file maps to

    # Warnings / guidance
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    # Archive contents (for ZIP)
    archive_entries: list[str] = field(default_factory=list)

    # CSV parse diagnostics
    encoding: str = ""
    delimiter: str = ""

    # Reference classification (for preview-only files)
    file_category: str = ""  # "metadata" | "auxiliary" | "unknown" | ""


# ── Internal helpers ────────────────────────────────────────────

def _infer_dtype(series: pd.Series) -> str:
    """Return a human-friendly dtype label for a column."""
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "text"


def _build_asset(name: str, df: pd.DataFrame, sample_n: int = 5) -> TabularAsset:
    """Build a TabularAsset from a DataFrame."""
    cols = [str(c) for c in df.columns]
    inferred = {str(c): _infer_dtype(df[c]) for c in df.columns}
    sample = df.head(sample_n).to_dict(orient="records") if not df.empty else []
    return TabularAsset(
        name=name,
        columns=cols,
        row_count=len(df),
        sample_rows=sample,
        inferred_types=inferred,
    )


# ── Profile detection heuristics ────────────────────────────────

_ORDER_ENTITY_NAMES = {"customers", "categories", "products", "orders", "order_items"}

# Northwind-like sheet names that hint at order data
_NORTHWIND_HINTS = {"orders", "customers", "products", "categories"}
_NORTHWIND_DETAIL_HINTS = {"orderdetails", "ordersdetails", "order_details"}

# Flat-metric required columns
_FM_REQUIRED = {"entity", "metric_name", "metric_value"}

# Wide flat-metric heuristic: one text column + many numeric columns
_WIDE_FM_ENTITY_HINTS = {"country", "entity", "name", "region", "state", "company"}
_WIDE_FM_YEAR_HINTS = {"year", "yr"}


def _detect_canonical_order_sheets(sheet_names_lower: set[str]) -> bool:
    """True if sheet names match the canonical order model exactly."""
    return _ORDER_ENTITY_NAMES.issubset(sheet_names_lower)


def _detect_northwind_sheets(sheet_names_lower: set[str]) -> bool:
    """True if sheets resemble a Northwind-style order workbook."""
    core = _NORTHWIND_HINTS & sheet_names_lower
    detail = _NORTHWIND_DETAIL_HINTS & sheet_names_lower
    return len(core) >= 3 and len(detail) >= 1


def _detect_fm_long_columns(col_names_lower: set[str]) -> bool:
    """True if columns match canonical flat-metric long format."""
    return _FM_REQUIRED.issubset(col_names_lower)


def _detect_fm_wide_columns(col_names_lower: set[str], df: pd.DataFrame) -> bool:
    """True if the sheet looks like a wide flat-metric table."""
    entity_col = _WIDE_FM_ENTITY_HINTS & col_names_lower
    if not entity_col:
        return False
    # Need several numeric columns beyond entity/year
    numeric_cols = df.select_dtypes(include="number").columns
    return len(numeric_cols) >= 3


def _detect_partial_order_csv(col_names_lower: set[str]) -> tuple[str, list[str]]:
    """If columns resemble a single order entity, return (entity, missing_entities).

    Returns ("", []) if no match.
    """
    # order_items heuristic
    item_hints = {"order_id", "product", "quantity", "unit_price", "unitprice",
                  "unit_price_cents", "productid", "orderid"}
    if len(item_hints & col_names_lower) >= 2:
        return "order_items", sorted(_ORDER_ENTITY_NAMES - {"order_items"})

    # orders heuristic
    order_hints = {"order_id", "orderid", "customer", "customerid",
                   "status", "created_at", "orderdate", "order_date"}
    if len(order_hints & col_names_lower) >= 2:
        return "orders", sorted(_ORDER_ENTITY_NAMES - {"orders"})

    # customers heuristic
    cust_hints = {"customer", "customername", "customer_name", "segment",
                  "city", "companyname", "company_name", "contactname"}
    if len(cust_hints & col_names_lower) >= 2:
        return "customers", sorted(_ORDER_ENTITY_NAMES - {"customers"})

    # products heuristic
    prod_hints = {"product", "productname", "product_name", "category",
                  "unit_price", "unitprice", "unit_price_cents", "price",
                  "categoryname", "category_name", "categoryid"}
    if len(prod_hints & col_names_lower) >= 2:
        return "products", sorted(_ORDER_ENTITY_NAMES - {"products"})

    # categories heuristic
    cat_hints = {"categoryname", "category_name", "category",
                 "categoryid", "category_id", "description"}
    if len(cat_hints & col_names_lower) >= 2:
        return "categories", sorted(_ORDER_ENTITY_NAMES - {"categories"})

    return "", []


# ── Reference / metadata classification ─────────────────────────

# Known metadata/reference file stems (not useful for dashboards but readable)
_METADATA_STEMS = {"data_dictionary", "datadictionary", "metadata", "readme",
                   "changelog", "license", "notes"}
_AUXILIARY_STEMS = {"employees", "shippers", "suppliers", "regions",
                    "territories", "demographics"}


def _classify_reference_file(
    fp: FileProfile, stem: str, cols_lower: set[str],
) -> None:
    """Enrich a PREVIEW_ONLY profile with reference/metadata classification."""
    if stem in _METADATA_STEMS:
        fp.file_category = "metadata"
        fp.confidence = "Metadata or reference file — readable but not dashboard data."
        fp.suggestions.append(
            "This looks like metadata/documentation. It can be previewed but "
            "is not used by any analytics profile."
        )
    elif stem in _AUXILIARY_STEMS:
        fp.file_category = "auxiliary"
        fp.confidence = (
            f"Auxiliary business table ('{stem}') — readable but not required "
            "for current dashboards."
        )
        fp.suggestions.append(
            f"The '{stem}' table is not required by Order Reporting or Flat Metric profiles. "
            "It may be useful in future analytics expansions."
        )
    else:
        fp.file_category = "unknown"
        fp.confidence = "Readable CSV but does not match a known format."
        fp.suggestions.append("You can preview this file but it cannot be imported directly.")


# ── Public API ──────────────────────────────────────────────────

def profile_file(filename: str, buf: BytesIO) -> FileProfile:
    """Profile an uploaded file and return a structured result.

    Supports CSV, XLSX, and ZIP files.  Does not modify or import data —
    this is a read-only inspection.
    """
    buf.seek(0)
    size = buf.getbuffer().nbytes
    ext = Path(filename).suffix.lower()

    if ext == ".csv":
        return _profile_csv(filename, buf, size)
    elif ext in (".xlsx", ".xls"):
        return _profile_xlsx(filename, buf, size)
    elif ext == ".zip":
        return _profile_zip(filename, buf, size)
    else:
        return FileProfile(
            filename=filename,
            file_type=FileType.UNKNOWN,
            size_bytes=size,
            importability=Importability.UNSUPPORTED,
            confidence="Unrecognised file extension.",
            warnings=[f"File type '{ext}' is not supported."],
        )


def _profile_csv(filename: str, buf: BytesIO, size: int) -> FileProfile:
    """Profile a single CSV file."""
    fp = FileProfile(filename=filename, file_type=FileType.CSV, size_bytes=size)

    buf.seek(0)
    csv_result = read_csv_robust(buf, nrows=200)

    if not csv_result.success or csv_result.df is None:
        fp.warnings.append(csv_result.error or "Could not parse CSV.")
        fp.importability = Importability.UNSUPPORTED
        fp.confidence = "File could not be parsed as CSV with any supported encoding."
        return fp

    df = csv_result.df
    fp.warnings.extend(csv_result.warnings)

    # Store parse diagnostics on the profile
    fp.encoding = csv_result.encoding
    fp.delimiter = csv_result.delimiter

    cols_lower = {str(c).strip().lower() for c in df.columns}
    asset = _build_asset(Path(filename).stem, df)
    fp.assets.append(asset)

    # Canonical flat-metric long format?
    if _detect_fm_long_columns(cols_lower):
        fp.profile_family = ProfileFamily.FLAT_METRIC
        fp.suggested_adapter = "canonical_flat_metric_csv"
        fp.importability = Importability.FULL_IMPORT
        fp.confidence = "Columns match canonical flat-metric format."
        return fp

    # Canonical order entity by filename stem?
    stem = Path(filename).stem.lower()
    if stem in _ORDER_ENTITY_NAMES:
        fp.profile_family = ProfileFamily.ORDER_REPORTING
        fp.importability = Importability.PARTIAL_DATASET
        fp.detected_entity = stem
        fp.missing_entities = sorted(_ORDER_ENTITY_NAMES - {stem})
        fp.confidence = f"Matches order entity '{stem}' but a full import needs all 5 entities."
        fp.suggestions.append(
            f"Upload a CSV bundle with all 5 files: {', '.join(sorted(_ORDER_ENTITY_NAMES))}"
        )
        return fp

    # Partial order heuristic (column-based)?
    detected, missing = _detect_partial_order_csv(cols_lower)
    if detected:
        fp.profile_family = ProfileFamily.ORDER_REPORTING
        fp.importability = Importability.PARTIAL_DATASET
        fp.detected_entity = detected
        fp.missing_entities = missing
        fp.confidence = f"Columns resemble '{detected}' entity from Order Reporting."
        fp.suggestions.append(
            "A full Order Reporting dashboard also needs: " + ", ".join(missing)
        )
        return fp

    # Wide flat-metric heuristic?
    if _detect_fm_wide_columns(cols_lower, df):
        fp.profile_family = ProfileFamily.FLAT_METRIC
        fp.suggested_adapter = "wide_flat_metric"
        fp.importability = Importability.ADAPTER_IMPORT
        fp.confidence = "Looks like a wide flat-metric table with entity column and numeric metrics."
        return fp

    # Fallback: classify reference/metadata vs truly unknown
    fp.importability = Importability.PREVIEW_ONLY
    _classify_reference_file(fp, stem, cols_lower)
    return fp


def _profile_xlsx(filename: str, buf: BytesIO, size: int) -> FileProfile:
    """Profile an Excel workbook."""
    fp = FileProfile(filename=filename, file_type=FileType.XLSX, size_bytes=size)

    try:
        buf.seek(0)
        xls = pd.ExcelFile(buf, engine="openpyxl")
    except Exception as exc:
        fp.warnings.append(f"Could not open workbook: {exc}")
        fp.importability = Importability.UNSUPPORTED
        fp.confidence = "File could not be opened as an Excel workbook."
        return fp

    sheet_names_lower = {s.lower() for s in xls.sheet_names}
    fp.confidence = f"Excel workbook with {len(xls.sheet_names)} sheet(s)."

    # Read up to 200 rows from each sheet for profiling
    for sheet in xls.sheet_names:
        try:
            df = xls.parse(sheet, nrows=200)
            fp.assets.append(_build_asset(sheet, df))
        except Exception:
            fp.warnings.append(f"Could not read sheet '{sheet}'.")

    # Canonical order workbook?
    if _detect_canonical_order_sheets(sheet_names_lower):
        fp.profile_family = ProfileFamily.ORDER_REPORTING
        fp.suggested_adapter = "canonical_order_excel"
        fp.importability = Importability.FULL_IMPORT
        fp.confidence = "All 5 canonical order sheets present."
        return fp

    # Northwind-style order workbook?
    if _detect_northwind_sheets(sheet_names_lower):
        fp.profile_family = ProfileFamily.ORDER_REPORTING
        fp.suggested_adapter = "northwind_order_excel"
        fp.importability = Importability.ADAPTER_IMPORT
        fp.confidence = "Sheets resemble a Northwind-style order workbook."
        return fp

    # Single-sheet workbook: check first sheet
    if len(xls.sheet_names) >= 1 and fp.assets:
        first = fp.assets[0]
        cols_lower = {c.strip().lower() for c in first.columns}

        # Flat-metric long?
        if _detect_fm_long_columns(cols_lower):
            fp.profile_family = ProfileFamily.FLAT_METRIC
            fp.suggested_adapter = "canonical_flat_metric_excel"
            fp.importability = Importability.FULL_IMPORT
            fp.confidence = "First sheet has canonical flat-metric columns."
            return fp

        # Wide flat-metric?  Need full df for numeric detection
        try:
            buf.seek(0)
            xls2 = pd.ExcelFile(buf, engine="openpyxl")
            df_first = xls2.parse(xls.sheet_names[0], nrows=200)
            if _detect_fm_wide_columns(cols_lower, df_first):
                fp.profile_family = ProfileFamily.FLAT_METRIC
                fp.suggested_adapter = "wide_flat_metric"
                fp.importability = Importability.ADAPTER_IMPORT
                fp.confidence = "First sheet looks like a wide flat-metric table."
                return fp
        except Exception:
            pass

    # Fallback
    fp.importability = Importability.PREVIEW_ONLY
    fp.suggestions.append("Workbook does not match a known import format. Preview available.")
    return fp


def _profile_zip(filename: str, buf: BytesIO, size: int) -> FileProfile:
    """Profile a ZIP archive by listing and inspecting contained files."""
    fp = FileProfile(filename=filename, file_type=FileType.ZIP, size_bytes=size)

    try:
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            fp.archive_entries = zf.namelist()
    except Exception as exc:
        fp.warnings.append(f"Could not read ZIP archive: {exc}")
        fp.importability = Importability.UNSUPPORTED
        fp.confidence = "File could not be opened as a ZIP archive."
        return fp

    # Classify contained files
    csv_files = [e for e in fp.archive_entries
                 if e.lower().endswith(".csv") and not e.startswith("__MACOSX")]
    xlsx_files = [e for e in fp.archive_entries
                  if e.lower().endswith(".xlsx") and not e.startswith("__MACOSX")]

    usable = csv_files + xlsx_files
    if not usable:
        fp.importability = Importability.PREVIEW_ONLY
        fp.confidence = "ZIP archive has no CSV or Excel files inside."
        fp.suggestions.append(
            f"Archive contains {len(fp.archive_entries)} entries but none are CSV/XLSX."
        )
        return fp

    # Try to inspect contained assets
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        # Check for canonical CSV bundle
        csv_stems = {Path(f).stem.lower() for f in csv_files}
        if _ORDER_ENTITY_NAMES.issubset(csv_stems):
            fp.profile_family = ProfileFamily.ORDER_REPORTING
            fp.suggested_adapter = "canonical_order_csv_bundle"
            fp.importability = Importability.FULL_IMPORT
            fp.confidence = "ZIP contains a canonical Order Reporting CSV bundle."
            # Profile each CSV briefly
            for cf in csv_files:
                try:
                    with zf.open(cf) as inner:
                        inner_buf = BytesIO(inner.read())
                        csv_r = read_csv_robust(inner_buf, nrows=50)
                        if csv_r.success and csv_r.df is not None:
                            fp.assets.append(_build_asset(Path(cf).stem, csv_r.df))
                except Exception:
                    pass
            return fp

        # Profile each readable file
        for entry in usable[:10]:  # cap inspection at 10 files
            try:
                with zf.open(entry) as inner:
                    inner_buf = BytesIO(inner.read())
                    if entry.lower().endswith(".csv"):
                        csv_r = read_csv_robust(inner_buf, nrows=200)
                        if csv_r.success and csv_r.df is not None:
                            fp.assets.append(_build_asset(entry, csv_r.df))
                        else:
                            fp.warnings.append(f"Could not read '{entry}' from archive.")
                    else:
                        df = pd.read_excel(inner_buf, engine="openpyxl", nrows=200)
                        fp.assets.append(_build_asset(entry, df))
            except Exception:
                fp.warnings.append(f"Could not read '{entry}' from archive.")

    # Summarise
    fp.confidence = (
        f"ZIP archive with {len(csv_files)} CSV(s) and {len(xlsx_files)} Excel file(s)."
    )
    fp.importability = Importability.PREVIEW_ONLY
    fp.suggestions.append(
        "Extract and upload individual files for import, or use an "
        "Excel/CSV file directly."
    )
    return fp
