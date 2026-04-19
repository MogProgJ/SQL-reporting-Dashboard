"""Tests for Phase 6 — Adaptive Ingestion & Smart Preview.

Unit tests only — no database required.  Covers:
  - file_profiler (CSV, XLSX, ZIP, partial detection)
  - adapter registry (register, find, load_all)
  - Northwind order adapter (detection, plan, transform)
  - wide flat-metric adapter (detection, plan, melt)
  - canonical adapters (passthrough)
  - dataset_profile ADAPTED source type
  - importer import_adapted_frames (mocked DB)
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest


# ── File Profiler ───────────────────────────────────────────────


class TestFileProfilerCSV:
    """Profile single CSV files."""

    def test_canonical_fm_csv_detected(self):
        from file_profiler import FileType, Importability, ProfileFamily, profile_file

        df = pd.DataFrame({
            "entity": ["USA", "UK"],
            "metric_name": ["GDP", "GDP"],
            "metric_value": [21.0, 3.0],
        })
        buf = BytesIO(df.to_csv(index=False).encode())
        p = profile_file("metrics.csv", buf)

        assert p.file_type == FileType.CSV
        assert p.profile_family == ProfileFamily.FLAT_METRIC
        assert p.importability == Importability.FULL_IMPORT
        assert p.suggested_adapter == "canonical_flat_metric_csv"
        assert len(p.assets) == 1
        assert p.assets[0].row_count == 2

    def test_partial_order_csv_by_stem(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        df = pd.DataFrame({"name": ["Alice"], "segment": ["SMB"], "city": ["PDX"]})
        buf = BytesIO(df.to_csv(index=False).encode())
        p = profile_file("customers.csv", buf)

        assert p.profile_family == ProfileFamily.ORDER_REPORTING
        assert p.importability == Importability.PARTIAL_DATASET
        assert "customers" not in p.missing_entities
        assert len(p.missing_entities) == 4

    def test_partial_order_csv_by_columns(self):
        from file_profiler import Importability, profile_file

        df = pd.DataFrame({
            "order_id": ["1001"],
            "product": ["Widget"],
            "quantity": [5],
            "unit_price_cents": [1999],
        })
        buf = BytesIO(df.to_csv(index=False).encode())
        p = profile_file("line_items.csv", buf)

        assert p.importability == Importability.PARTIAL_DATASET
        assert "order_items" not in p.missing_entities

    def test_wide_fm_csv_detected(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        df = pd.DataFrame({
            "Country": ["USA", "UK"],
            "Year": [2023, 2023],
            "GDP": [21.0, 3.0],
            "Population": [330, 67],
            "Inflation": [3.7, 6.7],
        })
        buf = BytesIO(df.to_csv(index=False).encode())
        p = profile_file("world_stats.csv", buf)

        assert p.profile_family == ProfileFamily.FLAT_METRIC
        assert p.importability == Importability.ADAPTER_IMPORT
        assert p.suggested_adapter == "wide_flat_metric"

    def test_unknown_csv_is_preview_only(self):
        from file_profiler import Importability, profile_file

        df = pd.DataFrame({"foo": [1], "bar": [2]})
        buf = BytesIO(df.to_csv(index=False).encode())
        p = profile_file("random.csv", buf)

        assert p.importability == Importability.PREVIEW_ONLY

    def test_unparseable_csv(self):
        from file_profiler import Importability, profile_file

        buf = BytesIO(b"\x00\x01\x02\x03")
        p = profile_file("bad.csv", buf)
        # Should not crash; may be UNSUPPORTED or PREVIEW_ONLY
        assert p.importability in (Importability.UNSUPPORTED, Importability.PREVIEW_ONLY)


class TestFileProfilerXLSX:
    """Profile Excel workbooks."""

    def _make_canonical_order_xlsx(self) -> BytesIO:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"name": ["A"], "segment": ["S"], "city": ["C"]}).to_excel(w, sheet_name="customers", index=False)
            pd.DataFrame({"name": ["Cat1"]}).to_excel(w, sheet_name="categories", index=False)
            pd.DataFrame({"name": ["P"], "category": ["Cat1"], "unit_price_cents": [100]}).to_excel(w, sheet_name="products", index=False)
            pd.DataFrame({"order_id": ["1"], "customer": ["A"], "status": ["completed"], "created_at": ["2024-01-01"]}).to_excel(w, sheet_name="orders", index=False)
            pd.DataFrame({"order_id": ["1"], "product": ["P"], "quantity": [1], "unit_price_cents": [100]}).to_excel(w, sheet_name="order_items", index=False)
        return BytesIO(buf.getvalue())

    def test_canonical_order_xlsx(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = self._make_canonical_order_xlsx()
        p = profile_file("orders.xlsx", buf)

        assert p.profile_family == ProfileFamily.ORDER_REPORTING
        assert p.importability == Importability.FULL_IMPORT
        assert p.suggested_adapter == "canonical_order_excel"

    def test_northwind_xlsx_detected(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"CustomerID": [1], "CustomerName": ["A"]}).to_excel(w, sheet_name="customers", index=False)
            pd.DataFrame({"CategoryID": [1], "CategoryName": ["C"]}).to_excel(w, sheet_name="categories", index=False)
            pd.DataFrame({"ProductID": [1], "ProductName": ["P"]}).to_excel(w, sheet_name="products", index=False)
            pd.DataFrame({"OrderID": [1], "CustomerID": [1], "OrderDate": ["2024-01-01"]}).to_excel(w, sheet_name="orders", index=False)
            pd.DataFrame({"OrderID": [1], "ProductID": [1], "Quantity": [5]}).to_excel(w, sheet_name="ordersdetails", index=False)
            pd.DataFrame({"EmployeeID": [1]}).to_excel(w, sheet_name="employees", index=False)
        buf = BytesIO(buf.getvalue())
        p = profile_file("northwind.xlsx", buf)

        assert p.profile_family == ProfileFamily.ORDER_REPORTING
        assert p.importability == Importability.ADAPTER_IMPORT
        assert p.suggested_adapter == "northwind_order_excel"

    def test_fm_long_xlsx_detected(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "entity": ["US"], "metric_name": ["GDP"], "metric_value": [21.0]
            }).to_excel(w, sheet_name="data", index=False)
        buf = BytesIO(buf.getvalue())
        p = profile_file("fm.xlsx", buf)

        assert p.profile_family == ProfileFamily.FLAT_METRIC
        assert p.importability == Importability.FULL_IMPORT

    def test_wide_fm_xlsx_detected(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "Country": ["US", "UK"],
                "GDP": [21.0, 3.0],
                "Pop": [330, 67],
                "HDI": [0.92, 0.93],
            }).to_excel(w, sheet_name="Sheet1", index=False)
        buf = BytesIO(buf.getvalue())
        p = profile_file("wide.xlsx", buf)

        assert p.profile_family == ProfileFamily.FLAT_METRIC
        assert p.suggested_adapter == "wide_flat_metric"


class TestFileProfilerZIP:
    """Profile ZIP archives."""

    def test_canonical_csv_bundle_zip(self):
        from file_profiler import Importability, ProfileFamily, profile_file

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name in ("customers", "categories", "products", "orders", "order_items"):
                df = pd.DataFrame({"col": [1]})
                zf.writestr(f"{name}.csv", df.to_csv(index=False))
        buf = BytesIO(buf.getvalue())
        p = profile_file("bundle.zip", buf)

        assert p.profile_family == ProfileFamily.ORDER_REPORTING
        assert p.importability == Importability.FULL_IMPORT
        assert p.suggested_adapter == "canonical_order_csv_bundle"

    def test_zip_with_no_useful_files(self):
        from file_profiler import Importability, profile_file

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
        buf = BytesIO(buf.getvalue())
        p = profile_file("archive.zip", buf)

        assert p.importability == Importability.PREVIEW_ONLY

    def test_unknown_extension(self):
        from file_profiler import Importability, profile_file

        buf = BytesIO(b"not a real file")
        p = profile_file("data.json", buf)
        assert p.importability == Importability.UNSUPPORTED


class TestFileProfilerModels:
    """FileProfile and related dataclass basics."""

    def test_file_profile_defaults(self):
        from file_profiler import FileProfile, FileType, Importability

        fp = FileProfile(filename="test.csv")
        assert fp.file_type == FileType.UNKNOWN
        assert fp.importability == Importability.UNSUPPORTED
        assert fp.assets == []
        assert fp.warnings == []

    def test_tabular_asset_dataclass(self):
        from file_profiler import TabularAsset

        a = TabularAsset(name="sheet1", columns=["a", "b"], row_count=10)
        assert a.name == "sheet1"
        assert a.row_count == 10
        assert a.sample_rows == []


# ── Adapter Registry ────────────────────────────────────────────


class TestAdapterRegistry:
    def test_load_all_adapters_populates_registry(self):
        from adapters import _ADAPTERS, get_adapters, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapters = get_adapters()
        assert len(adapters) >= 5  # 4 canonical + northwind + wide_fm
        names = {a.name for a in adapters}
        assert "canonical_order_excel" in names
        assert "northwind_order_excel" in names
        assert "wide_flat_metric" in names

    def test_find_adapter_by_name(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        a = find_adapter_by_name("northwind_order_excel")
        assert a is not None
        assert a.name == "northwind_order_excel"

    def test_find_adapter_unknown(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        assert find_adapter_by_name("does_not_exist") is None

    def test_find_adapter_from_profile(self):
        from adapters import _ADAPTERS, find_adapter, load_all_adapters
        from file_profiler import FileProfile, Importability

        _ADAPTERS.clear()
        load_all_adapters()
        fp = FileProfile(filename="test.xlsx", suggested_adapter="northwind_order_excel",
                         importability=Importability.ADAPTER_IMPORT)
        adapter = find_adapter(fp)
        assert adapter is not None
        assert adapter.name == "northwind_order_excel"


# ── Northwind Adapter ──────────────────────────────────────────


class TestNorthwindAdapter:
    def _make_northwind_xlsx(self) -> BytesIO:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "CustomerID": [1, 2],
                "CustomerName": ["Alice", "Bob"],
                "City": ["Portland", "Seattle"],
            }).to_excel(w, sheet_name="customers", index=False)

            pd.DataFrame({
                "CategoryID": [1, 2],
                "CategoryName": ["Electronics", "Food"],
            }).to_excel(w, sheet_name="categories", index=False)

            pd.DataFrame({
                "ProductID": [1, 2],
                "ProductName": ["Widget", "Gadget"],
                "CategoryID": [1, 2],
                "UnitPrice": [29.99, 12.50],
            }).to_excel(w, sheet_name="products", index=False)

            pd.DataFrame({
                "OrderID": [100, 101],
                "CustomerID": [1, 2],
                "OrderDate": ["2024-01-15", "2024-02-20"],
            }).to_excel(w, sheet_name="orders", index=False)

            pd.DataFrame({
                "OrderID": [100, 100, 101],
                "ProductID": [1, 2, 1],
                "Quantity": [3, 1, 5],
                "UnitPrice": [29.99, 12.50, 29.99],
            }).to_excel(w, sheet_name="ordersdetails", index=False)

            pd.DataFrame({"EmployeeID": [1]}).to_excel(w, sheet_name="employees", index=False)
            pd.DataFrame({"ShipperID": [1]}).to_excel(w, sheet_name="shippers", index=False)
        return BytesIO(buf.getvalue())

    def test_can_handle_with_matching_profile(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters
        from file_profiler import FileProfile, Importability

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        fp = FileProfile(filename="nw.xlsx", suggested_adapter="northwind_order_excel",
                         importability=Importability.ADAPTER_IMPORT)
        assert adapter.can_handle(fp)

    def test_plan_has_field_mappings(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        plan = adapter.plan(None, buf)
        assert plan.adapter_name == "northwind_order_excel"
        assert len(plan.field_mappings) > 0

    def test_plan_detects_no_status_assumption(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        plan = adapter.plan(None, buf)
        status_assumptions = [a for a in plan.assumptions if "status" in a.lower()]
        assert len(status_assumptions) > 0

    def test_transform_produces_five_entities(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        assert result.success
        assert set(result.frames.keys()) == {"customers", "categories", "products", "orders", "order_items"}

    def test_transform_customers_mapped(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        cust = result.frames["customers"]
        assert "name" in cust.columns
        assert list(cust["name"]) == ["Alice", "Bob"]

    def test_transform_prices_converted_to_cents(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        prods = result.frames["products"]
        assert "unit_price_cents" in prods.columns
        # 29.99 * 100 = 2999
        assert 2999 in prods["unit_price_cents"].values

    def test_transform_orders_default_status(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        orders = result.frames["orders"]
        assert "status" in orders.columns
        assert all(orders["status"] == "completed")

    def test_transform_order_items_resolves_product_names(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        items = result.frames["order_items"]
        assert "product" in items.columns
        assert "Widget" in items["product"].values

    def test_transform_warns_about_conversions(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("northwind_order_excel")
        buf = self._make_northwind_xlsx()
        result = adapter.transform(buf)

        assert len(result.warnings) > 0


# ── Wide Flat Metric Adapter ───────────────────────────────────


class TestWideFlatMetricAdapter:
    def _make_wide_xlsx(self, with_year=True, with_rank=True) -> BytesIO:
        data = {
            "Country": ["USA", "UK", "Germany"],
            "GDP": [21.0, 3.0, 4.2],
            "Population": [330, 67, 83],
            "HDI": [0.92, 0.93, 0.94],
        }
        if with_year:
            data["Year"] = [2023, 2023, 2023]
        if with_rank:
            data["Rank"] = [1, 5, 4]
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame(data).to_excel(w, sheet_name="Sheet1", index=False)
        return BytesIO(buf.getvalue())

    def test_can_handle_with_matching_profile(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters
        from file_profiler import FileProfile, Importability

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        fp = FileProfile(filename="wide.xlsx", suggested_adapter="wide_flat_metric",
                         importability=Importability.ADAPTER_IMPORT)
        assert adapter.can_handle(fp)

    def test_plan_describes_melt(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx()
        plan = adapter.plan(None, buf)
        assert "melt" in plan.description.lower() or "metric" in plan.description.lower()
        assert len(plan.field_mappings) > 0

    def test_transform_produces_flat_metrics(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx()
        result = adapter.transform(buf)

        assert result.success
        assert "flat_metrics" in result.frames
        fm = result.frames["flat_metrics"]
        assert "entity" in fm.columns
        assert "metric_name" in fm.columns
        assert "metric_value" in fm.columns

    def test_transform_melts_correct_count(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx()
        result = adapter.transform(buf)

        fm = result.frames["flat_metrics"]
        # 3 countries × 3 metrics (GDP, Population, HDI) = 9 rows
        assert len(fm) == 9

    def test_transform_preserves_year(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx()
        result = adapter.transform(buf)

        fm = result.frames["flat_metrics"]
        assert "year" in fm.columns
        assert fm["year"].dropna().iloc[0] == 2023

    def test_transform_preserves_rank(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx()
        result = adapter.transform(buf)

        fm = result.frames["flat_metrics"]
        assert "rank" in fm.columns

    def test_transform_without_year(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = self._make_wide_xlsx(with_year=False, with_rank=False)
        result = adapter.transform(buf)

        assert result.success
        fm = result.frames["flat_metrics"]
        assert len(fm) == 9  # 3 countries × 3 metrics

    def test_transform_no_entity_column_fails(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("wide_flat_metric")
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"A": [1], "B": [2], "C": [3]}).to_excel(w, sheet_name="Sheet1", index=False)
        buf = BytesIO(buf.getvalue())
        result = adapter.transform(buf)
        assert not result.success


# ── Canonical Adapters ─────────────────────────────────────────


class TestCanonicalAdapters:
    """Ensure canonical adapters pass through to existing readers."""

    def test_canonical_fm_csv_transform(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("canonical_flat_metric_csv")
        df = pd.DataFrame({
            "entity": ["X"], "metric_name": ["Y"], "metric_value": [1.0],
        })
        buf = BytesIO(df.to_csv(index=False).encode())
        result = adapter.transform(buf)
        assert result.success
        assert "flat_metrics" in result.frames

    def test_canonical_fm_excel_transform(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("canonical_flat_metric_excel")
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "entity": ["X"], "metric_name": ["Y"], "metric_value": [1.0],
            }).to_excel(w, sheet_name="data", index=False)
        buf = BytesIO(buf.getvalue())
        result = adapter.transform(buf)
        assert result.success
        assert "flat_metrics" in result.frames

    def test_canonical_order_excel_transform(self):
        from adapters import _ADAPTERS, find_adapter_by_name, load_all_adapters

        _ADAPTERS.clear()
        load_all_adapters()
        adapter = find_adapter_by_name("canonical_order_excel")
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"name": ["A"], "segment": ["S"], "city": ["C"]}).to_excel(w, sheet_name="customers", index=False)
            pd.DataFrame({"name": ["Cat"]}).to_excel(w, sheet_name="categories", index=False)
            pd.DataFrame({"name": ["P"], "category": ["Cat"], "unit_price_cents": [100]}).to_excel(w, sheet_name="products", index=False)
            pd.DataFrame({"order_id": ["1"], "customer": ["A"], "status": ["ok"], "created_at": ["2024-01-01"]}).to_excel(w, sheet_name="orders", index=False)
            pd.DataFrame({"order_id": ["1"], "product": ["P"], "quantity": [1], "unit_price_cents": [100]}).to_excel(w, sheet_name="order_items", index=False)
        buf = BytesIO(buf.getvalue())
        result = adapter.transform(buf)
        assert result.success
        assert set(result.frames.keys()) == {"customers", "categories", "products", "orders", "order_items"}


# ── Dataset Profile ─────────────────────────────────────────────


class TestAdaptedSourceType:
    def test_adapted_source_type_exists(self):
        from dataset_profile import SourceType

        assert hasattr(SourceType, "ADAPTED")
        assert SourceType.ADAPTED.value == "adapted"


# ── Importer — import_adapted_frames ────────────────────────────


class TestImportAdaptedFrames:
    @patch("importer.load_into_db")
    def test_adapted_order_frames_flow_through_pipeline(self, mock_load):
        from importer import import_adapted_frames

        mock_load.return_value = {"customers": 1, "categories": 1, "products": 1, "orders": 1, "order_items": 1}

        frames = {
            "customers": pd.DataFrame({"name": ["A"], "segment": ["S"], "city": ["C"]}),
            "categories": pd.DataFrame({"name": ["Cat"]}),
            "products": pd.DataFrame({"name": ["P"], "category": ["Cat"], "unit_price_cents": [100]}),
            "orders": pd.DataFrame({"order_id": ["1"], "customer": ["A"], "status": ["ok"], "created_at": ["2024-01-01"]}),
            "order_items": pd.DataFrame({"order_id": ["1"], "product": ["P"], "quantity": [1], "unit_price_cents": [100]}),
        }

        result = import_adapted_frames(
            frames=frames,
            profile_family="order_reporting",
            adapter_name="northwind_order_excel",
            label="test.xlsx",
        )
        assert result.success
        assert mock_load.called

    @patch("importer.load_flat_metrics")
    def test_adapted_fm_frames_flow_through_pipeline(self, mock_load):
        from importer import import_adapted_frames

        mock_load.return_value = {"flat_metrics": 3}

        frames = {
            "flat_metrics": pd.DataFrame({
                "entity": ["US", "UK", "DE"],
                "metric_name": ["GDP", "GDP", "GDP"],
                "metric_value": [21.0, 3.0, 4.2],
            }),
        }

        result = import_adapted_frames(
            frames=frames,
            profile_family="flat_metric",
            adapter_name="wide_flat_metric",
            label="wide.xlsx",
        )
        assert result.success
        assert mock_load.called


# ── Integration-style: profiler → adapter → result ──────────────


class TestProfileToAdapterFlow:
    """End-to-end flow: profile a file → find adapter → transform."""

    def test_northwind_e2e(self):
        from adapters import _ADAPTERS, find_adapter, load_all_adapters
        from file_profiler import Importability, profile_file

        _ADAPTERS.clear()
        load_all_adapters()

        # Build a Northwind workbook
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"CustomerID": [1], "CustomerName": ["Acme"]}).to_excel(w, sheet_name="customers", index=False)
            pd.DataFrame({"CategoryID": [1], "CategoryName": ["Stuff"]}).to_excel(w, sheet_name="categories", index=False)
            pd.DataFrame({"ProductID": [1], "ProductName": ["Thing"], "CategoryID": [1], "UnitPrice": [10.0]}).to_excel(w, sheet_name="products", index=False)
            pd.DataFrame({"OrderID": [1], "CustomerID": [1], "OrderDate": ["2024-06-01"]}).to_excel(w, sheet_name="orders", index=False)
            pd.DataFrame({"OrderID": [1], "ProductID": [1], "Quantity": [2], "UnitPrice": [10.0]}).to_excel(w, sheet_name="ordersdetails", index=False)
        buf = BytesIO(buf.getvalue())

        # Profile
        profile = profile_file("northwind.xlsx", buf)
        assert profile.importability == Importability.ADAPTER_IMPORT
        assert profile.suggested_adapter == "northwind_order_excel"

        # Find adapter
        adapter = find_adapter(profile)
        assert adapter is not None

        # Transform
        buf.seek(0)
        result = adapter.transform(buf)
        assert result.success
        assert "customers" in result.frames
        assert result.frames["customers"]["name"].iloc[0] == "Acme"

    def test_wide_fm_e2e(self):
        from adapters import _ADAPTERS, find_adapter, load_all_adapters
        from file_profiler import Importability, profile_file

        _ADAPTERS.clear()
        load_all_adapters()

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({
                "Country": ["US", "UK"],
                "Year": [2023, 2023],
                "GDP": [21.0, 3.0],
                "HDI": [0.92, 0.93],
                "CPI": [3.7, 6.7],
            }).to_excel(w, sheet_name="Sheet1", index=False)
        buf = BytesIO(buf.getvalue())

        profile = profile_file("world_data.xlsx", buf)
        assert profile.importability == Importability.ADAPTER_IMPORT
        assert profile.suggested_adapter == "wide_flat_metric"

        adapter = find_adapter(profile)
        buf.seek(0)
        result = adapter.transform(buf)
        assert result.success
        fm = result.frames["flat_metrics"]
        assert len(fm) == 6  # 2 countries × 3 metrics
        assert set(fm["metric_name"].unique()) == {"GDP", "HDI", "CPI"}
