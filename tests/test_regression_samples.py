"""Regression tests using synthetic sample files.

These tests exercise the full profiler → classification → staging → assembly
pipeline using in-memory fixtures that replicate the structure of real files
previously tested (customers.csv, order_details.csv, Northwind workbooks,
Northwind ZIP archives).  No real sample files are required.
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import pandas as pd
import pytest


# ── Fixture helpers ─────────────────────────────────────────────


def _csv_bytes(content: str, encoding: str = "utf-8") -> io.BytesIO:
    return io.BytesIO(content.encode(encoding))


def _xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    buf.seek(0)
    return buf


def _zip_of_csvs(files: dict[str, str], encoding: str = "utf-8") -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content.encode(encoding))
    buf.seek(0)
    return buf


# ── Fixture data ────────────────────────────────────────────────

CUSTOMERS_CSV = (
    "customerID,companyName,contactName,city,country\n"
    "ALFKI,Alfreds Futterkiste,Maria Anders,Berlin,Germany\n"
    "ANATR,Ana Trujillo,Ana Trujillo,México D.F.,Mexico\n"
)

ORDERS_CSV = (
    "orderID,customerID,orderDate,shipCity,status\n"
    "10248,ALFKI,2024-01-15,Berlin,shipped\n"
    "10249,ANATR,2024-01-16,México D.F.,delivered\n"
)

ORDER_ITEMS_CSV = (
    "orderID,productID,unitPrice,quantity,discount\n"
    "10248,11,14.00,12,0.0\n"
    "10248,42,9.80,10,0.0\n"
    "10249,72,34.80,5,0.15\n"
)

PRODUCTS_CSV = (
    "productID,productName,categoryID,unitPrice\n"
    "11,Queso Cabrales,4,21.00\n"
    "42,Singaporean Hokkien,5,14.00\n"
    "72,Mozzarella di Giovanni,4,34.80\n"
)

CATEGORIES_CSV = (
    "categoryID,categoryName,description\n"
    "4,Dairy Products,Cheeses\n"
    "5,Grains/Cereals,Breads and pasta\n"
)

# CP1252-encoded customers (non-ASCII city names)
CUSTOMERS_CP1252_CSV = (
    "customerID,companyName,contactName,city,country\n"
    "ALFKI,Alfreds Futterkiste,Maria Anders,Berl\xedn,Germany\n"
    "ANATR,Ana Trujillo,Ana Trujillo,M\xe9xico D.F.,Mexico\n"
)

# Semicolon-delimited variant
ORDERS_SEMICOLON_CSV = (
    "orderID;customerID;orderDate;shipCity;status\n"
    "10248;ALFKI;2024-01-15;Berlin;shipped\n"
)

METADATA_CSV = "field_name,description,data_type\norderID,Unique order identifier,integer\n"

EMPLOYEES_CSV = "employeeID,firstName,lastName\n1,Nancy,Davolio\n2,Andrew,Fuller\n"

FLAT_METRIC_CSV = (
    "entity,metric_name,metric_value,year\n"
    "USA,GDP,21400000,2023\n"
    "Germany,GDP,4200000,2023\n"
)


# ── 1. Partial-entity CSV detection ────────────────────────────


class TestPartialEntityDetection:
    """Profiler correctly classifies single-entity CSVs."""

    def test_orders_csv_by_filename(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = _csv_bytes(ORDERS_CSV)
        fp = profile_file("orders.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.profile_family == ProfileFamily.ORDER_REPORTING
        assert fp.detected_entity == "orders"
        assert "order_items" in fp.missing_entities

    def test_order_items_by_columns(self):
        """order_details.csv style — detected by columns not filename."""
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = _csv_bytes(ORDER_ITEMS_CSV)
        fp = profile_file("order_details.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.detected_entity == "order_items"

    def test_customers_csv(self):
        from file_profiler import Importability, profile_file

        buf = _csv_bytes(CUSTOMERS_CSV)
        fp = profile_file("customers.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.detected_entity == "customers"

    def test_products_csv(self):
        from file_profiler import Importability, profile_file

        buf = _csv_bytes(PRODUCTS_CSV)
        fp = profile_file("products.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.detected_entity == "products"

    def test_categories_csv(self):
        from file_profiler import Importability, profile_file

        buf = _csv_bytes(CATEGORIES_CSV)
        fp = profile_file("categories.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.detected_entity == "categories"


# ── 2. Encoding and delimiter resilience ───────────────────────


class TestEncodingResilience:
    """Files with non-UTF-8 encoding or non-comma delimiters are handled."""

    def test_cp1252_customers(self):
        from file_profiler import profile_file

        buf = io.BytesIO(CUSTOMERS_CP1252_CSV.encode("cp1252"))
        fp = profile_file("customers.csv", buf)
        assert fp.encoding in ("cp1252", "latin-1", "ISO-8859-1", "Windows-1252")
        assert fp.detected_entity == "customers"

    def test_semicolon_delimited_orders(self):
        from file_profiler import profile_file

        buf = _csv_bytes(ORDERS_SEMICOLON_CSV)
        fp = profile_file("orders.csv", buf)
        assert fp.delimiter == ";"
        assert fp.detected_entity == "orders"


# ── 3. Reference / metadata classification ─────────────────────


class TestReferenceClassification:
    """Non-importable files are classified correctly."""

    def test_metadata_csv(self):
        from file_profiler import Importability, profile_file

        buf = _csv_bytes(METADATA_CSV)
        fp = profile_file("data_dictionary.csv", buf)
        assert fp.importability == Importability.PREVIEW_ONLY
        assert fp.file_category == "metadata"

    def test_auxiliary_employees(self):
        from file_profiler import Importability, profile_file

        buf = _csv_bytes(EMPLOYEES_CSV)
        fp = profile_file("employees.csv", buf)
        assert fp.importability == Importability.PREVIEW_ONLY
        assert fp.file_category == "auxiliary"

    def test_unknown_random_csv(self):
        from file_profiler import Importability, profile_file

        content = "x,y,z\n1,2,3\n4,5,6\n"
        buf = _csv_bytes(content)
        fp = profile_file("random_data.csv", buf)
        assert fp.importability == Importability.PREVIEW_ONLY
        assert fp.file_category == "unknown"


# ── 4. Flat-metric CSV detection ───────────────────────────────


class TestFlatMetricDetection:
    """Flat metric CSVs are classified as FULL_IMPORT."""

    def test_canonical_flat_metric(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = _csv_bytes(FLAT_METRIC_CSV)
        fp = profile_file("metrics.csv", buf)
        assert fp.importability == Importability.FULL_IMPORT
        assert fp.profile_family == ProfileFamily.FLAT_METRIC


# ── 5. Northwind-style XLSX detection ──────────────────────────


class TestNorthwindXlsxDetection:
    """Multi-sheet Excel files resembling Northwind are detected."""

    @pytest.fixture()
    def northwind_xlsx(self):
        """Minimal Northwind-like workbook with key sheets."""
        sheets = {
            "orders": pd.DataFrame({
                "orderID": [10248], "customerID": ["ALFKI"],
                "orderDate": ["2024-01-15"],
            }),
            "orderdetails": pd.DataFrame({
                "orderID": [10248], "productID": [11],
                "unitPrice": [14.0], "quantity": [12], "discount": [0.0],
            }),
            "products": pd.DataFrame({
                "productID": [11], "productName": ["Queso Cabrales"],
                "unitPrice": [21.0], "categoryID": [4],
            }),
            "customers": pd.DataFrame({
                "customerID": ["ALFKI"],
                "companyName": ["Alfreds Futterkiste"],
                "city": ["Berlin"],
            }),
            "categories": pd.DataFrame({
                "categoryID": [4], "categoryName": ["Dairy Products"],
            }),
            "employees": pd.DataFrame({
                "employeeID": [1], "firstName": ["Nancy"],
            }),
            "shippers": pd.DataFrame({
                "shipperID": [1], "companyName": ["Speedy Express"],
            }),
        }
        return _xlsx_bytes(sheets)

    def test_northwind_detected_as_adapter(self, northwind_xlsx):
        from file_profiler import Importability, profile_file

        fp = profile_file("orders_frostonline.xlsx", northwind_xlsx)
        assert fp.importability in (
            Importability.ADAPTER_IMPORT, Importability.FULL_IMPORT,
        )
        assert fp.suggested_adapter is not None

    def test_northwind_has_assets(self, northwind_xlsx):
        from file_profiler import profile_file

        fp = profile_file("Northwind.xlsx", northwind_xlsx)
        assert len(fp.assets) >= 5


# ── 6. ZIP archive inspection ──────────────────────────────────


class TestZipProfiling:
    """ZIP files containing CSVs are inspected and classified."""

    def test_zip_with_order_csvs(self):
        from file_profiler import Importability, profile_file

        files = {
            "customers.csv": CUSTOMERS_CSV,
            "orders.csv": ORDERS_CSV,
            "order_items.csv": ORDER_ITEMS_CSV,
            "products.csv": PRODUCTS_CSV,
            "categories.csv": CATEGORIES_CSV,
        }
        buf = _zip_of_csvs(files)
        fp = profile_file("Northwind+Traders.zip", buf)
        assert fp.importability in (
            Importability.FULL_IMPORT,
            Importability.ADAPTER_IMPORT,
            Importability.PARTIAL_DATASET,
        )
        assert len(fp.archive_entries) == 5

    def test_zip_archive_entries_listed(self):
        from file_profiler import profile_file

        files = {"a.csv": "x,y\n1,2\n", "b.csv": "a,b\n3,4\n"}
        buf = _zip_of_csvs(files)
        fp = profile_file("data.zip", buf)
        assert set(fp.archive_entries) == {"a.csv", "b.csv"}


# ── 7. Assembly workspace full cycle ───────────────────────────


class TestAssemblyFullCycle:
    """Stage individual CSVs and build a complete dataset."""

    @pytest.fixture(autouse=True)
    def _mock_session(self):
        """Provide a mock Streamlit session_state."""
        with patch("streamlit.session_state", {}):
            yield

    def test_stage_three_minimum_entities(self):
        from assembly_workspace import get_workspace, stage_file
        from csv_utils import read_csv_robust
        from file_profiler import profile_file

        files = [
            ("orders.csv", ORDERS_CSV),
            ("order_items.csv", ORDER_ITEMS_CSV),
            ("products.csv", PRODUCTS_CSV),
        ]

        ws = get_workspace()
        for fname, content in files:
            buf = _csv_bytes(content)
            fp = profile_file(fname, buf)
            buf.seek(0)
            csv_r = read_csv_robust(buf)
            stage_file(fname, fp.detected_entity, fp, content.encode(), csv_r.df)

        assert ws.is_importable
        assert ws.missing_required == set()

    def test_assembly_build_frames(self):
        from assembly_workspace import build_assembled_frames, get_workspace, stage_file
        from csv_utils import read_csv_robust
        from file_profiler import profile_file

        for fname, content in [
            ("orders.csv", ORDERS_CSV),
            ("order_items.csv", ORDER_ITEMS_CSV),
            ("products.csv", PRODUCTS_CSV),
        ]:
            buf = _csv_bytes(content)
            fp = profile_file(fname, buf)
            buf.seek(0)
            csv_r = read_csv_robust(buf)
            stage_file(fname, fp.detected_entity, fp, content.encode(), csv_r.df)

        frames = build_assembled_frames()
        assert "orders" in frames
        assert "order_items" in frames
        assert "products" in frames
        assert len(frames["orders"]) == 2

    def test_coverage_increases_as_files_staged(self):
        from assembly_workspace import get_workspace, stage_file
        from csv_utils import read_csv_robust
        from file_profiler import profile_file

        ws = get_workspace()
        covered, total = ws.coverage_fraction
        assert covered == 0

        buf = _csv_bytes(ORDERS_CSV)
        fp = profile_file("orders.csv", buf)
        buf.seek(0)
        csv_r = read_csv_robust(buf)
        stage_file("orders.csv", "orders", fp, ORDERS_CSV.encode(), csv_r.df)

        covered, _ = ws.coverage_fraction
        assert covered == 1
        assert not ws.is_importable  # still missing order_items, products

    def test_optional_entity_not_required(self):
        """categories and customers are optional — not blocking import."""
        from assembly_workspace import get_workspace, stage_file
        from csv_utils import read_csv_robust
        from file_profiler import profile_file

        for fname, content in [
            ("orders.csv", ORDERS_CSV),
            ("order_items.csv", ORDER_ITEMS_CSV),
            ("products.csv", PRODUCTS_CSV),
        ]:
            buf = _csv_bytes(content)
            fp = profile_file(fname, buf)
            buf.seek(0)
            csv_r = read_csv_robust(buf)
            stage_file(fname, fp.detected_entity, fp, content.encode(), csv_r.df)

        ws = get_workspace()
        assert ws.is_importable
        assert "customers" in ws.missing_entities
        assert "categories" in ws.missing_entities
        assert "customers" not in ws.missing_required

    def test_unstage_removes_entity(self):
        from assembly_workspace import get_workspace, stage_file, unstage_entity
        from csv_utils import read_csv_robust
        from file_profiler import profile_file

        buf = _csv_bytes(ORDERS_CSV)
        fp = profile_file("orders.csv", buf)
        buf.seek(0)
        csv_r = read_csv_robust(buf)
        stage_file("orders.csv", "orders", fp, ORDERS_CSV.encode(), csv_r.df)

        ws = get_workspace()
        assert "orders" in ws.staged

        unstage_entity("orders")
        assert "orders" not in ws.staged


# ── 8. ActiveDataset model ──────────────────────────────────────


class TestActiveDatasetModel:
    """ActiveDataset tracks import provenance."""

    def test_source_badge_csv(self):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset

        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.CSV_BUNDLE,
            source_label="CSV upload",
            row_counts={"orders": 50, "products": 50},
        )
        assert "CSV" in ds.source_badge or "csv" in ds.source_badge.lower()

    def test_source_badge_adapter(self):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset

        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.ADAPTED,
            source_label="Northwind.xlsx",
            row_counts={"orders": 200, "products": 300},
        )
        assert "Northwind" in ds.source_badge or "🔄" in ds.source_badge

    def test_source_badge_assembly(self):
        from dataset_profile import ProfileType, SourceType
        from ingestion_state import ActiveDataset

        ds = ActiveDataset(
            profile_type=ProfileType.ORDER_REPORTING,
            source_type=SourceType.ASSEMBLED,
            source_label="Assembled dataset",
            row_counts={"orders": 100, "products": 100, "order_items": 50},
        )
        badge = ds.source_badge.lower()
        assert "assembl" in badge or "multi" in badge or "🗂️" in ds.source_badge
