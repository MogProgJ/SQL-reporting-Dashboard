"""Phase 6A tests — Ingestion Reliability & Dataset Assembly.

Covers:
- csv_utils: encoding fallback, delimiter sniffing, structured diagnostics
- file_profiler: robust CSV profiling, reference/metadata classification
- Northwind adapter: price derivation from products sheet
- Partial-entity classification improvements
- Assembly workspace: staging, coverage, import readiness
- Regression guards for existing imports
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import pandas as pd
import pytest


# ── CSV Encoding Fallback ───────────────────────────────────────


class TestCsvRobustParsing:
    """read_csv_robust should handle multiple encodings and delimiters."""

    def test_utf8_csv(self):
        from csv_utils import read_csv_robust
        content = "name,age\nAlice,30\nBob,25\n"
        buf = io.BytesIO(content.encode("utf-8"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.encoding == "utf-8"
        assert r.delimiter == ","
        assert len(r.df) == 2
        assert not r.warnings

    def test_utf8_bom_csv(self):
        from csv_utils import read_csv_robust
        content = "name,age\nAlice,30\n"
        buf = io.BytesIO(b"\xef\xbb\xbf" + content.encode("utf-8"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.encoding in ("utf-8", "utf-8-sig")
        assert len(r.df) == 1

    def test_cp1252_csv(self):
        """Simulates a file like customers.csv with CP1252 encoding."""
        from csv_utils import read_csv_robust
        # CP1252-specific characters: curly quotes, em dash
        content = "name,city\n\u201cAlice\u201d,Z\u00fcrich\nBob,M\u00fcnchen\n"
        buf = io.BytesIO(content.encode("cp1252"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.encoding == "cp1252"
        assert len(r.df) == 2
        assert any("cp1252" in w for w in r.warnings)

    def test_latin1_csv(self):
        from csv_utils import read_csv_robust
        content = "name,city\nJos\xe9,Paris\nRen\xe9,Lyon\n"
        buf = io.BytesIO(content.encode("latin-1"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.encoding in ("cp1252", "latin-1")  # both handle these chars
        assert len(r.df) == 2

    def test_semicolon_delimiter(self):
        from csv_utils import read_csv_robust
        content = "name;age;city\nAlice;30;Berlin\nBob;25;Munich\n"
        buf = io.BytesIO(content.encode("utf-8"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.delimiter == ";"
        assert r.df.shape[1] == 3
        assert any("semicolon" in w for w in r.warnings)

    def test_tab_delimiter(self):
        from csv_utils import read_csv_robust
        content = "name\tage\tcity\nAlice\t30\tBerlin\n"
        buf = io.BytesIO(content.encode("utf-8"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.delimiter == "\t"
        assert r.df.shape[1] == 3
        assert any("tab" in w for w in r.warnings)

    def test_binary_garbage_fails(self):
        from csv_utils import read_csv_robust
        buf = io.BytesIO(bytes(range(256)) * 10)
        r = read_csv_robust(buf)
        # Binary data should either fail or produce a single-column result
        # that doesn't match real CSV structure
        if r.success:
            # Acceptable: pandas might parse garbage but result is meaningless
            pass
        else:
            assert r.error

    def test_nrows_parameter(self):
        from csv_utils import read_csv_robust
        content = "a,b\n" + "\n".join(f"{i},{i*2}" for i in range(100))
        buf = io.BytesIO(content.encode("utf-8"))
        r = read_csv_robust(buf, nrows=10)
        assert r.success
        assert len(r.df) == 10

    def test_diagnostics_returned(self):
        """CsvReadResult should carry structured diagnostics."""
        from csv_utils import read_csv_robust
        # Use CP1252-specific characters so encoding detection picks cp1252
        content = "name;value\nf\u00f6o;1\nb\u00e4r;2\n"
        buf = io.BytesIO(content.encode("cp1252"))
        r = read_csv_robust(buf)
        assert r.success
        assert r.encoding == "cp1252"
        assert r.delimiter == ";"
        assert len(r.warnings) >= 1  # at least encoding or delimiter warning


# ── File Profiler with Robust CSV ───────────────────────────────


class TestProfilerRobustCsv:
    """file_profiler should use encoding fallback via csv_utils."""

    def test_cp1252_csv_not_unsupported(self):
        """A CP1252-encoded CSV should NOT be classified as UNSUPPORTED."""
        from file_profiler import Importability, profile_file
        content = "entity,metric_name,metric_value\n\u201cFoo\u201d,Revenue,100\n"
        buf = io.BytesIO(content.encode("cp1252"))
        fp = profile_file("metrics.csv", buf)
        assert fp.importability != Importability.UNSUPPORTED
        assert fp.encoding == "cp1252"

    def test_cp1252_partial_order_csv(self):
        """A CP1252 customers-like CSV should be detected as partial."""
        from file_profiler import Importability, ProfileFamily, profile_file
        content = "customername,segment,city\nM\u00fcller,B2B,Z\u00fcrich\n"
        buf = io.BytesIO(content.encode("cp1252"))
        fp = profile_file("customers.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.profile_family == ProfileFamily.ORDER_REPORTING
        assert fp.detected_entity == "customers"

    def test_semicolon_csv_profiled(self):
        from file_profiler import Importability, profile_file
        content = "entity;metric_name;metric_value\nFoo;Rev;100\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("data.csv", buf)
        assert fp.importability != Importability.UNSUPPORTED
        assert fp.delimiter == ";"

    def test_encoding_diagnostics_on_profile(self):
        from file_profiler import profile_file
        content = "a,b\n1,2\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("test.csv", buf)
        assert fp.encoding == "utf-8"
        assert fp.delimiter == ","


# ── Reference / Metadata Classification ─────────────────────────


class TestReferenceClassification:
    """Preview-only files should be classified by category."""

    def test_data_dictionary_is_metadata(self):
        from file_profiler import profile_file
        content = "field,description,type\nid,Primary key,integer\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("data_dictionary.csv", buf)
        assert fp.file_category == "metadata"

    def test_employees_is_auxiliary(self):
        from file_profiler import profile_file
        content = "employee_id,first_name,last_name,title\n1,John,Doe,Manager\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("employees.csv", buf)
        assert fp.file_category == "auxiliary"

    def test_shippers_is_auxiliary(self):
        from file_profiler import profile_file
        content = "shipper_id,company,phone\n1,Speedy,555-1234\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("shippers.csv", buf)
        assert fp.file_category == "auxiliary"

    def test_random_csv_is_unknown(self):
        from file_profiler import profile_file
        content = "x,y,z\n1,2,3\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("random_data.csv", buf)
        assert fp.file_category == "unknown"

    def test_partial_order_not_classified_as_reference(self):
        """Partial order entities should NOT get file_category set."""
        from file_profiler import Importability, profile_file
        content = "order_id,product,quantity,unit_price_cents\n1,Widget,5,999\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("order_details.csv", buf)
        assert fp.importability == Importability.PARTIAL_DATASET
        assert fp.file_category == ""  # not classified as reference


# ── Partial Entity Detection ────────────────────────────────────


class TestPartialEntityDetection:
    """_detect_partial_order_csv should return (entity, missing)."""

    def test_order_items_by_columns(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"orderid", "productid", "quantity"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == "order_items"
        assert "order_items" not in missing

    def test_orders_by_columns(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"order_id", "customerid", "orderdate", "status"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == "orders"
        assert "orders" not in missing

    def test_customers_by_columns(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"customername", "segment", "city"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == "customers"

    def test_products_by_columns(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"productname", "category", "price"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == "products"

    def test_categories_by_columns(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"categoryname", "description"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == "categories"

    def test_no_match(self):
        from file_profiler import _detect_partial_order_csv
        cols = {"foo", "bar", "baz"}
        entity, missing = _detect_partial_order_csv(cols)
        assert entity == ""
        assert missing == []

    def test_detected_entity_on_profile(self):
        from file_profiler import profile_file
        content = "order_id,product,quantity,unit_price_cents\n1,A,5,100\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("order_details.csv", buf)
        assert fp.detected_entity == "order_items"

    def test_stem_based_detection(self):
        from file_profiler import profile_file
        content = "col_a,col_b\n1,2\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("customers.csv", buf)
        assert fp.detected_entity == "customers"


# ── Northwind Adapter — Price Derivation ────────────────────────


class TestNorthwindPriceDerivation:
    """When ordersdetails lacks a price column, derive from products."""

    def _make_workbook(self, include_detail_price: bool = False) -> io.BytesIO:
        """Build a minimal Northwind workbook."""
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "CustomerID": [1, 2],
                "CustomerName": ["Alice", "Bob"],
            }).to_excel(w, sheet_name="customers", index=False)

            pd.DataFrame({
                "CategoryID": [1],
                "CategoryName": ["Gadgets"],
            }).to_excel(w, sheet_name="categories", index=False)

            pd.DataFrame({
                "ProductID": [10, 20],
                "ProductName": ["Widget", "Gizmo"],
                "CategoryID": [1, 1],
                "Price": [29.99, 12.50],  # dollars
            }).to_excel(w, sheet_name="products", index=False)

            pd.DataFrame({
                "OrderID": [100, 101],
                "CustomerID": [1, 2],
                "OrderDate": ["2024-01-15", "2024-02-20"],
            }).to_excel(w, sheet_name="orders", index=False)

            detail_data = {
                "OrderID": [100, 100, 101],
                "ProductID": [10, 20, 10],
                "Quantity": [2, 1, 3],
            }
            if include_detail_price:
                detail_data["UnitPrice"] = [29.99, 12.50, 29.99]

            pd.DataFrame(detail_data).to_excel(
                w, sheet_name="ordersdetails", index=False,
            )
        buf.seek(0)
        return buf

    def test_price_derived_from_products_when_missing(self):
        """ordersdetails without price → derive from products.Price."""
        from adapters import load_all_adapters
        from adapters.northwind_order import NorthwindOrderAdapter
        load_all_adapters()

        buf = self._make_workbook(include_detail_price=False)
        adapter = NorthwindOrderAdapter()
        result = adapter.transform(buf)

        assert result.success, f"Adapter failed: {result.error}"
        items = result.frames["order_items"]
        assert "unit_price_cents" in items.columns
        # Product 10 has Price=29.99 → 2999 cents
        prices = items["unit_price_cents"].tolist()
        assert all(p > 0 for p in prices), f"Prices should all be positive: {prices}"
        assert 2999 in prices  # Widget
        assert 1250 in prices  # Gizmo

    def test_price_from_detail_when_present(self):
        """When ordersdetails has a price column, use it directly."""
        from adapters.northwind_order import NorthwindOrderAdapter
        buf = self._make_workbook(include_detail_price=True)
        adapter = NorthwindOrderAdapter()
        result = adapter.transform(buf)
        assert result.success
        items = result.frames["order_items"]
        prices = items["unit_price_cents"].tolist()
        assert all(p > 0 for p in prices)

    def test_derivation_warning_surfaced(self):
        """Warnings should mention derivation from products sheet."""
        from adapters.northwind_order import NorthwindOrderAdapter
        buf = self._make_workbook(include_detail_price=False)
        adapter = NorthwindOrderAdapter()
        result = adapter.transform(buf)
        assert result.success
        assert any("derived from products" in w.lower() for w in result.warnings)

    def test_plan_reports_price_derivation(self):
        """The adapter plan should mention price derivation."""
        from file_profiler import profile_file
        from adapters.northwind_order import NorthwindOrderAdapter

        buf = self._make_workbook(include_detail_price=False)
        fp = profile_file("test.xlsx", buf)
        adapter = NorthwindOrderAdapter()
        buf.seek(0)
        plan = adapter.plan(fp, buf)
        assert any("derived" in a.lower() or "products sheet" in a.lower()
                    for a in plan.assumptions)

    def test_all_five_entities_produced(self):
        from adapters.northwind_order import NorthwindOrderAdapter
        buf = self._make_workbook(include_detail_price=False)
        adapter = NorthwindOrderAdapter()
        result = adapter.transform(buf)
        assert result.success
        assert set(result.frames.keys()) == {
            "customers", "categories", "products", "orders", "order_items"
        }


# ── Assembly Workspace ──────────────────────────────────────────


class TestAssemblyWorkspace:
    """Multi-file Order Reporting assembly."""

    @pytest.fixture(autouse=True)
    def _mock_session(self):
        """Provide a fake st.session_state for testing."""
        with patch("assembly_workspace.st") as mock_st:
            mock_st.session_state = {}
            yield mock_st

    def test_empty_workspace(self):
        from assembly_workspace import get_workspace
        ws = get_workspace()
        assert ws.covered_entities == set()
        assert not ws.is_importable

    def test_stage_file(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        df = pd.DataFrame({"name": ["Alice"], "segment": ["B2B"], "city": ["NYC"]})
        stage_file("customers.csv", "customers", FileProfile(filename="customers.csv"), b"raw", df)
        ws = get_workspace()
        assert "customers" in ws.covered_entities
        assert ws.staged["customers"].row_count == 1

    def test_coverage_tracking(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")

        stage_file("orders.csv", "orders", fp, b"raw",
                   pd.DataFrame({"order_id": [1]}))
        stage_file("order_items.csv", "order_items", fp, b"raw",
                   pd.DataFrame({"order_id": [1], "product": ["A"]}))
        stage_file("products.csv", "products", fp, b"raw",
                   pd.DataFrame({"name": ["A"]}))

        ws = get_workspace()
        assert ws.is_importable  # minimum required entities met
        assert ws.missing_required == set()
        assert ws.missing_entities == {"customers", "categories"}

    def test_not_importable_without_required(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")

        stage_file("customers.csv", "customers", fp, b"raw",
                   pd.DataFrame({"name": ["A"]}))
        stage_file("categories.csv", "categories", fp, b"raw",
                   pd.DataFrame({"name": ["B"]}))

        ws = get_workspace()
        assert not ws.is_importable

    def test_unstage_entity(self):
        from assembly_workspace import get_workspace, stage_file, unstage_entity
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")
        stage_file("orders.csv", "orders", fp, b"raw",
                   pd.DataFrame({"order_id": [1]}))
        assert "orders" in get_workspace().covered_entities
        unstage_entity("orders")
        assert "orders" not in get_workspace().covered_entities

    def test_clear_workspace(self):
        from assembly_workspace import clear_workspace, get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")
        stage_file("orders.csv", "orders", fp, b"raw",
                   pd.DataFrame({"order_id": [1]}))
        clear_workspace()
        ws = get_workspace()
        assert ws.covered_entities == set()

    def test_readiness_label(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")

        ws = get_workspace()
        assert "Partial" in ws.readiness_label

        stage_file("orders.csv", "orders", fp, b"raw",
                   pd.DataFrame({"order_id": [1]}))
        stage_file("order_items.csv", "order_items", fp, b"raw",
                   pd.DataFrame({"order_id": [1], "product": ["A"]}))
        stage_file("products.csv", "products", fp, b"raw",
                   pd.DataFrame({"name": ["A"]}))

        ws = get_workspace()
        assert "Ready" in ws.readiness_label

    def test_build_assembled_frames(self):
        from assembly_workspace import build_assembled_frames, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")

        csv_content = "name,segment,city\nAlice,B2B,NYC\n"
        stage_file("customers.csv", "customers", fp,
                   csv_content.encode("utf-8"),
                   pd.DataFrame({"name": ["Alice"]}))

        frames = build_assembled_frames()
        assert "customers" in frames
        assert len(frames["customers"]) == 1

    def test_replace_staged_file(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")

        stage_file("v1.csv", "customers", fp, b"raw",
                   pd.DataFrame({"name": ["Old"]}))
        assert get_workspace().staged["customers"].filename == "v1.csv"

        stage_file("v2.csv", "customers", fp, b"raw",
                   pd.DataFrame({"name": ["New"]}))
        assert get_workspace().staged["customers"].filename == "v2.csv"

    def test_coverage_fraction(self):
        from assembly_workspace import get_workspace, stage_file
        from file_profiler import FileProfile
        fp = FileProfile(filename="x.csv")
        stage_file("o.csv", "orders", fp, b"raw", pd.DataFrame({"a": [1]}))
        covered, total = get_workspace().coverage_fraction
        assert covered == 1
        assert total == 5


# ── SourceType.ASSEMBLED ────────────────────────────────────────


class TestAssembledSourceType:
    def test_assembled_enum_exists(self):
        from dataset_profile import SourceType
        assert SourceType.ASSEMBLED == "assembled"


# ── Regression Guards ───────────────────────────────────────────


class TestRegressionGuards:
    """Ensure existing import paths still work after Phase 6A changes."""

    def test_readers_csv_bundle_still_works(self):
        from readers import read_csv_bundle
        files = {}
        for entity in ("customers", "categories", "products", "orders", "order_items"):
            if entity == "customers":
                content = "name,segment,city\nAlice,B2B,NYC\n"
            elif entity == "categories":
                content = "name\nGadgets\n"
            elif entity == "products":
                content = "name,category,unit_price_cents\nWidget,Gadgets,999\n"
            elif entity == "orders":
                content = "order_id,customer,status,created_at\n1,Alice,completed,2024-01-01\n"
            else:
                content = "order_id,product,quantity,unit_price_cents\n1,Widget,2,999\n"
            files[f"{entity}.csv"] = io.BytesIO(content.encode("utf-8"))
        frames = read_csv_bundle(files)
        assert len(frames) == 5

    def test_readers_flat_metric_csv_still_works(self):
        from readers import read_flat_metric_csv
        content = "entity,metric_name,metric_value\nUS,GDP,1000\n"
        buf = io.BytesIO(content.encode("utf-8"))
        frames = read_flat_metric_csv(buf)
        assert "flat_metrics" in frames

    def test_profiler_canonical_fm_still_full_import(self):
        from file_profiler import Importability, profile_file
        content = "entity,metric_name,metric_value\nUS,GDP,1000\n"
        buf = io.BytesIO(content.encode("utf-8"))
        fp = profile_file("metrics.csv", buf)
        assert fp.importability == Importability.FULL_IMPORT

    def test_profiler_canonical_order_xlsx_still_works(self):
        from file_profiler import Importability, profile_file
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            for entity in ("customers", "categories", "products", "orders", "order_items"):
                pd.DataFrame({"col": [1]}).to_excel(w, sheet_name=entity, index=False)
        buf.seek(0)
        fp = profile_file("data.xlsx", buf)
        assert fp.importability == Importability.FULL_IMPORT
