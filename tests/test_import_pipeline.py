"""Tests for the Phase 3B import pipeline.

Unit tests only — no database required.  Covers:
  - canonical_model definitions
  - validators (missing entities, columns, types, refs)
  - normalizers (type coercion, column stripping)
  - readers (CSV bundle, Excel workbook)
  - dataset_profile types
  - importer orchestration (mocked DB)
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest


# ── Canonical model ─────────────────────────────────────────────


class TestCanonicalModel:
    def test_five_entities_defined(self):
        from canonical_model import CANONICAL_ENTITIES

        assert len(CANONICAL_ENTITIES) == 5
        names = [e.name for e in CANONICAL_ENTITIES]
        assert names == ["customers", "categories", "products", "orders", "order_items"]

    def test_entity_map_keys(self):
        from canonical_model import ENTITY_MAP

        assert set(ENTITY_MAP.keys()) == {
            "customers", "categories", "products", "orders", "order_items",
        }

    def test_required_column_names(self):
        from canonical_model import CUSTOMERS

        assert CUSTOMERS.required_column_names == {"name", "segment", "city"}

    def test_products_has_unit_price(self):
        from canonical_model import PRODUCTS

        col_names = {c.name for c in PRODUCTS.columns}
        assert "unit_price_cents" in col_names

    def test_order_items_no_natural_key(self):
        from canonical_model import ORDER_ITEMS

        assert ORDER_ITEMS.natural_key == ()


# ── Dataset profile types ───────────────────────────────────────


class TestDatasetProfile:
    def test_source_type_values(self):
        from dataset_profile import SourceType

        assert SourceType.DEMO_SEED.value == "demo_seed"
        assert SourceType.CSV_BUNDLE.value == "csv_bundle"

    def test_import_result_errors_warnings(self):
        from dataset_profile import ImportResult, SourceType, ValidationIssue

        issues = [
            ValidationIssue("a", "", "bad", severity="error"),
            ValidationIssue("b", "", "meh", severity="warning"),
            ValidationIssue("c", "", "also bad", severity="error"),
        ]
        result = ImportResult(
            success=False,
            source_type=SourceType.CSV_BUNDLE,
            source_label="test",
            issues=issues,
        )
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_validation_issue_str(self):
        from dataset_profile import ValidationIssue

        iss = ValidationIssue("orders", "customer", "not found")
        assert "[ERROR] orders.customer" in str(iss)


# ── Validators ──────────────────────────────────────────────────


def _make_valid_frames() -> dict[str, pd.DataFrame]:
    """Return a minimal valid set of entity DataFrames."""
    return {
        "customers": pd.DataFrame(
            {"name": ["Alice"], "segment": ["SMB"], "city": ["Portland"]}
        ),
        "categories": pd.DataFrame({"name": ["Widgets"]}),
        "products": pd.DataFrame(
            {"name": ["Gizmo"], "category": ["Widgets"], "unit_price_cents": [1500]}
        ),
        "orders": pd.DataFrame(
            {
                "order_id": ["1001"],
                "customer": ["Alice"],
                "status": ["completed"],
                "created_at": ["2026-01-15"],
            }
        ),
        "order_items": pd.DataFrame(
            {
                "order_id": ["1001"],
                "product": ["Gizmo"],
                "quantity": [3],
                "unit_price_cents": [1500],
            }
        ),
    }


class TestValidators:
    def test_valid_frames_no_errors(self):
        from validators import validate_dataframes

        issues = validate_dataframes(_make_valid_frames())
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_missing_entity(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        del frames["categories"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("Missing required entity" in e.message for e in errors)

    def test_empty_entity(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["customers"] = pd.DataFrame(columns=["name", "segment", "city"])
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("zero rows" in e.message for e in errors)

    def test_missing_column(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["customers"] = pd.DataFrame({"name": ["Alice"], "segment": ["SMB"]})
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("city" in e.message for e in errors)

    def test_null_in_non_nullable(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["customers"] = pd.DataFrame(
            {"name": [None], "segment": ["SMB"], "city": ["Portland"]}
        )
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("null" in e.message for e in errors)

    def test_non_numeric_int_column(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["products"]["unit_price_cents"] = ["abc"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("integer" in e.message.lower() for e in errors)

    def test_negative_price_error(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["products"]["unit_price_cents"] = [-100]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("<= 0" in e.message for e in errors)

    def test_orphan_category_reference(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["products"]["category"] = ["NonExistent"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("category" in e.column for e in errors)

    def test_orphan_customer_reference(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["orders"]["customer"] = ["Ghost"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("customer" in e.column for e in errors)

    def test_orphan_order_id_reference(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["order_items"]["order_id"] = ["9999"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("order_id" in e.column for e in errors)

    def test_orphan_product_reference(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["order_items"]["product"] = ["Ghost"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("product" in e.column for e in errors)

    def test_blank_text_warning(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["customers"]["city"] = ["  "]
        issues = validate_dataframes(frames)
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("blank" in w.message.lower() for w in warnings)

    def test_bad_date_value(self):
        from validators import validate_dataframes

        frames = _make_valid_frames()
        frames["orders"]["created_at"] = ["not-a-date"]
        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert any("date" in e.message.lower() for e in errors)


# ── Normalizers ─────────────────────────────────────────────────


class TestNormalizers:
    def test_int_coercion(self):
        from normalizers import normalize_frames

        frames = _make_valid_frames()
        frames["products"]["unit_price_cents"] = ["1500"]
        out = normalize_frames(frames)
        assert out["products"]["unit_price_cents"].dtype.name == "Int64"
        assert out["products"]["unit_price_cents"].iloc[0] == 1500

    def test_date_coercion(self):
        from normalizers import normalize_frames

        frames = _make_valid_frames()
        out = normalize_frames(frames)
        assert pd.api.types.is_datetime64_any_dtype(out["orders"]["created_at"])

    def test_text_stripping(self):
        from normalizers import normalize_frames

        frames = _make_valid_frames()
        frames["customers"]["city"] = ["  Portland  "]
        out = normalize_frames(frames)
        assert out["customers"]["city"].iloc[0] == "Portland"

    def test_column_name_lowercased(self):
        from normalizers import normalize_frames

        frames = _make_valid_frames()
        frames["customers"].columns = ["Name", "Segment", "City"]
        out = normalize_frames(frames)
        assert list(out["customers"].columns) == ["name", "segment", "city"]

    def test_missing_entity_skipped(self):
        from normalizers import normalize_frames

        frames = {"customers": _make_valid_frames()["customers"]}
        out = normalize_frames(frames)
        assert "orders" not in out
        assert "customers" in out


# ── Readers ─────────────────────────────────────────────────────


class TestCSVReader:
    def _csv_buf(self, text: str) -> BytesIO:
        return BytesIO(text.encode("utf-8"))

    def test_reads_matching_filenames(self):
        from readers import read_csv_bundle

        files = {
            "customers.csv": self._csv_buf("name,segment,city\nAlice,SMB,PDX"),
            "categories.csv": self._csv_buf("name\nWidgets"),
        }
        frames = read_csv_bundle(files)
        assert "customers" in frames
        assert "categories" in frames
        assert len(frames["customers"]) == 1

    def test_ignores_unknown_filenames(self):
        from readers import read_csv_bundle

        files = {
            "readme.csv": self._csv_buf("a,b\n1,2"),
        }
        frames = read_csv_bundle(files)
        assert frames == {}

    def test_case_insensitive_stem(self):
        from readers import read_csv_bundle

        files = {
            "Customers.CSV": self._csv_buf("name,segment,city\nBob,Ent,NYC"),
        }
        frames = read_csv_bundle(files)
        assert "customers" in frames


class TestExcelReader:
    def _make_workbook(self, sheets: dict[str, pd.DataFrame]) -> BytesIO:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        buf.seek(0)
        return buf

    def test_reads_matching_sheets(self):
        from readers import read_excel_workbook

        buf = self._make_workbook(
            {
                "customers": pd.DataFrame(
                    {"name": ["Alice"], "segment": ["SMB"], "city": ["PDX"]}
                ),
                "SomeOther": pd.DataFrame({"x": [1]}),
            }
        )
        frames = read_excel_workbook(buf)
        assert "customers" in frames
        assert "someother" not in frames

    def test_case_insensitive_sheet_names(self):
        from readers import read_excel_workbook

        buf = self._make_workbook(
            {
                "CATEGORIES": pd.DataFrame({"name": ["Widgets"]}),
            }
        )
        frames = read_excel_workbook(buf)
        assert "categories" in frames


# ── Importer orchestration (mocked DB) ──────────────────────────


class TestImporter:
    def test_csv_import_with_valid_data(self):
        from importer import import_csv_bundle

        def _csv(text: str) -> BytesIO:
            return BytesIO(text.encode("utf-8"))

        files = {
            "customers.csv": _csv("name,segment,city\nAlice,SMB,PDX"),
            "categories.csv": _csv("name\nWidgets"),
            "products.csv": _csv("name,category,unit_price_cents\nGizmo,Widgets,1500"),
            "orders.csv": _csv("order_id,customer,status,created_at\n1001,Alice,completed,2026-01-15"),
            "order_items.csv": _csv(
                "order_id,product,quantity,unit_price_cents\n1001,Gizmo,3,1500"
            ),
        }

        mock_counts = {
            "customers": 1, "categories": 1, "products": 1,
            "orders": 1, "order_items": 1,
        }

        with patch("importer.load_into_db", return_value=mock_counts):
            result = import_csv_bundle(files, label="test")

        assert result.success is True
        assert result.row_counts == mock_counts
        assert result.errors == []

    def test_csv_import_with_validation_errors(self):
        from importer import import_csv_bundle

        def _csv(text: str) -> BytesIO:
            return BytesIO(text.encode("utf-8"))

        # Missing categories entity entirely
        files = {
            "customers.csv": _csv("name,segment,city\nAlice,SMB,PDX"),
            "products.csv": _csv("name,category,unit_price_cents\nGizmo,Widgets,1500"),
            "orders.csv": _csv("order_id,customer,status,created_at\n1001,Alice,completed,2026-01-15"),
            "order_items.csv": _csv(
                "order_id,product,quantity,unit_price_cents\n1001,Gizmo,3,1500"
            ),
        }

        with patch("importer.load_into_db") as mock_load:
            result = import_csv_bundle(files, label="test")

        assert result.success is False
        assert len(result.errors) > 0
        mock_load.assert_not_called()

    def test_csv_import_db_failure(self):
        from importer import import_csv_bundle

        def _csv(text: str) -> BytesIO:
            return BytesIO(text.encode("utf-8"))

        files = {
            "customers.csv": _csv("name,segment,city\nAlice,SMB,PDX"),
            "categories.csv": _csv("name\nWidgets"),
            "products.csv": _csv("name,category,unit_price_cents\nGizmo,Widgets,1500"),
            "orders.csv": _csv("order_id,customer,status,created_at\n1001,Alice,completed,2026-01-15"),
            "order_items.csv": _csv(
                "order_id,product,quantity,unit_price_cents\n1001,Gizmo,3,1500"
            ),
        }

        with patch("importer.load_into_db", side_effect=RuntimeError("connection failed")):
            result = import_csv_bundle(files, label="test")

        assert result.success is False
        assert any("Database load failed" in e.message for e in result.errors)

    def test_get_demo_profile(self):
        from dataset_profile import SourceType
        from importer import get_demo_profile

        profile = get_demo_profile()
        assert profile.source_type == SourceType.DEMO_SEED
        assert "seed" in profile.label.lower()
