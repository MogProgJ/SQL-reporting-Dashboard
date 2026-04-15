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

    def test_no_recognised_files_raises_reader_error(self):
        from readers import ReaderError, read_csv_bundle

        files = {
            "readme.csv": self._csv_buf("a,b\n1,2"),
        }
        with pytest.raises(ReaderError, match="No recognised CSV files"):
            read_csv_bundle(files)

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
        from readers import ReaderError, read_excel_workbook

        buf = self._make_workbook(
            {
                "customers": pd.DataFrame(
                    {"name": ["Alice"], "segment": ["SMB"], "city": ["PDX"]}
                ),
                "SomeOther": pd.DataFrame({"x": [1]}),
            }
        )
        # Only one canonical sheet present → missing sheets error
        with pytest.raises(ReaderError, match="missing required sheets"):
            read_excel_workbook(buf)

    def test_case_insensitive_sheet_names(self):
        from readers import ReaderError, read_excel_workbook

        buf = self._make_workbook(
            {
                "CATEGORIES": pd.DataFrame({"name": ["Widgets"]}),
            }
        )
        # Only one canonical sheet present → missing sheets error
        with pytest.raises(ReaderError, match="missing required sheets"):
            read_excel_workbook(buf)

    def test_all_sheets_present_reads_successfully(self):
        from readers import read_excel_workbook

        buf = self._make_workbook(
            {
                "customers": pd.DataFrame(
                    {"name": ["Alice"], "segment": ["SMB"], "city": ["PDX"]}
                ),
                "categories": pd.DataFrame({"name": ["Widgets"]}),
                "products": pd.DataFrame(
                    {"name": ["Gizmo"], "category": ["Widgets"], "unit_price_cents": [1500]}
                ),
                "orders": pd.DataFrame(
                    {"order_id": ["1001"], "customer": ["Alice"], "status": ["completed"], "created_at": ["2026-01-15"]}
                ),
                "order_items": pd.DataFrame(
                    {"order_id": ["1001"], "product": ["Gizmo"], "quantity": [3], "unit_price_cents": [1500]}
                ),
            }
        )
        frames = read_excel_workbook(buf)
        assert set(frames.keys()) == {"customers", "categories", "products", "orders", "order_items"}

    def test_incompatible_workbook_no_matching_sheets(self):
        from readers import ReaderError, read_excel_workbook

        buf = self._make_workbook(
            {"Sheet1": pd.DataFrame({"x": [1, 2]})}
        )
        with pytest.raises(ReaderError, match="not compatible"):
            read_excel_workbook(buf)


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


# ── Import UX hardening ─────────────────────────────────────────


class TestReaderErrorHandling:
    """Tests for graceful error handling in the import pipeline."""

    def test_openpyxl_missing_produces_reader_error(self):
        """Simulate openpyxl not being installed."""
        from readers import ReaderError, _check_openpyxl

        with patch.dict("sys.modules", {"openpyxl": None}):
            with pytest.raises(ReaderError, match="openpyxl"):
                _check_openpyxl()

    def test_excel_import_missing_openpyxl_returns_structured_result(self):
        """Importer should return a clean ImportResult, not a traceback."""
        from importer import import_excel_workbook
        from readers import ReaderError

        buf = BytesIO(b"not a real workbook")
        with patch("readers._check_openpyxl", side_effect=ReaderError(
            summary="Excel import requires the openpyxl package.",
            detail="Install it with:  pip install openpyxl",
        )):
            result = import_excel_workbook(buf, label="test.xlsx")

        assert result.success is False
        assert any("openpyxl" in e.message for e in result.errors)

    def test_incompatible_workbook_returns_structured_result(self):
        """A workbook with no matching sheets should produce a clear result."""
        from importer import import_excel_workbook

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
        buf.seek(0)

        result = import_excel_workbook(buf, label="bad.xlsx")
        assert result.success is False
        assert any("not compatible" in e.message for e in result.errors)

    def test_workbook_missing_some_sheets_returns_structured_result(self):
        """A workbook with only some canonical sheets should list what's missing."""
        from importer import import_excel_workbook

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame({"name": ["Alice"], "segment": ["SMB"], "city": ["PDX"]}).to_excel(
                writer, sheet_name="customers", index=False
            )
        buf.seek(0)

        result = import_excel_workbook(buf, label="partial.xlsx")
        assert result.success is False
        assert any("missing" in e.message.lower() for e in result.errors)

    def test_csv_no_matching_files_returns_structured_result(self):
        """CSV bundle with only unrecognised file names should fail cleanly."""
        from importer import import_csv_bundle

        files = {"report.csv": BytesIO(b"a,b\n1,2")}
        result = import_csv_bundle(files, label="bad bundle")
        assert result.success is False
        assert any("No recognised CSV" in e.message for e in result.errors)

    def test_unexpected_reader_exception_returns_structured_result(self):
        """Truly unexpected errors should still produce a result, not a traceback."""
        from importer import import_excel_workbook

        with patch(
            "importer.read_excel_workbook",
            side_effect=RuntimeError("disk on fire"),
        ):
            result = import_excel_workbook(BytesIO(b""), label="boom.xlsx")

        assert result.success is False
        assert any("Unexpected error" in e.message for e in result.errors)


class TestTemplateGeneration:
    """Tests that generated templates are valid and match the contract."""

    def test_csv_zip_contains_all_entities(self):
        import zipfile

        from importer import generate_example_csv_zip

        data = generate_example_csv_zip()
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = {n.replace(".csv", "") for n in zf.namelist()}
        assert names == {"customers", "categories", "products", "orders", "order_items"}

    def test_csv_zip_files_are_valid_csv(self):
        import zipfile

        from importer import generate_example_csv_zip

        data = generate_example_csv_zip()
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for name in zf.namelist():
                df = pd.read_csv(BytesIO(zf.read(name)))
                assert len(df) > 0, f"{name} should have sample rows"

    def test_csv_template_passes_validation(self):
        """Generated CSV template must pass the app's own validator."""
        import zipfile

        from importer import generate_example_csv_zip
        from validators import validate_dataframes

        data = generate_example_csv_zip()
        frames: dict[str, pd.DataFrame] = {}
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for name in zf.namelist():
                entity = name.replace(".csv", "")
                frames[entity] = pd.read_csv(BytesIO(zf.read(name)))

        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == [], f"Template should not have validation errors: {errors}"

    def test_excel_template_contains_all_sheets(self):
        from importer import generate_example_excel

        data = generate_example_excel()
        xls = pd.ExcelFile(BytesIO(data), engine="openpyxl")
        sheets = {s.lower() for s in xls.sheet_names}
        assert sheets == {"customers", "categories", "products", "orders", "order_items"}

    def test_excel_template_passes_validation(self):
        """Generated Excel template must pass the app's own validator."""
        from importer import generate_example_excel
        from validators import validate_dataframes

        data = generate_example_excel()
        xls = pd.ExcelFile(BytesIO(data), engine="openpyxl")
        frames = {s.lower(): xls.parse(s) for s in xls.sheet_names}

        issues = validate_dataframes(frames)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == [], f"Template should not have validation errors: {errors}"


# ── Flat metric model ───────────────────────────────────────────


class TestFlatMetricModel:
    def test_single_entity_defined(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES

        assert len(FLAT_METRIC_ENTITIES) == 1
        assert FLAT_METRIC_ENTITIES[0].name == "flat_metrics"

    def test_required_columns(self):
        from flat_metric_model import FLAT_METRICS

        col_names = FLAT_METRICS.required_column_names
        assert "entity" in col_names
        assert "metric_name" in col_names
        assert "metric_value" in col_names

    def test_optional_columns_nullable(self):
        from flat_metric_model import FLAT_METRICS

        col_map = {c.name: c for c in FLAT_METRICS.columns}
        assert col_map["year"].nullable is True
        assert col_map["score"].nullable is True
        assert col_map["rank"].nullable is True
        assert col_map["entity"].nullable is False

    def test_natural_key(self):
        from flat_metric_model import FLAT_METRICS

        assert FLAT_METRICS.natural_key == ("entity", "metric_name")

    def test_entity_map(self):
        from flat_metric_model import FLAT_METRIC_ENTITY_MAP

        assert "flat_metrics" in FLAT_METRIC_ENTITY_MAP


# ── Profile type ────────────────────────────────────────────────


class TestProfileType:
    def test_profile_type_values(self):
        from dataset_profile import ProfileType

        assert ProfileType.ORDER_REPORTING.value == "order_reporting"
        assert ProfileType.FLAT_METRIC.value == "flat_metric"

    def test_import_result_has_profile_type(self):
        from dataset_profile import ImportResult, ProfileType, SourceType

        result = ImportResult(
            success=True,
            source_type=SourceType.CSV_BUNDLE,
            source_label="test",
            profile_type=ProfileType.FLAT_METRIC,
        )
        assert result.profile_type == ProfileType.FLAT_METRIC

    def test_import_result_default_profile(self):
        from dataset_profile import ImportResult, ProfileType, SourceType

        result = ImportResult(
            success=True,
            source_type=SourceType.CSV_BUNDLE,
            source_label="test",
        )
        assert result.profile_type == ProfileType.ORDER_REPORTING

    def test_dataset_profile_has_profile_type(self):
        from dataset_profile import DatasetProfile, ProfileType, SourceType

        profile = DatasetProfile(
            source_type=SourceType.DEMO_SEED,
            label="demo",
            profile_type=ProfileType.FLAT_METRIC,
        )
        assert profile.profile_type == ProfileType.FLAT_METRIC


# ── Flat metric validators ──────────────────────────────────────


def _make_valid_fm_frame() -> dict[str, pd.DataFrame]:
    """Return a minimal valid flat-metric DataFrame."""
    return {
        "flat_metrics": pd.DataFrame({
            "entity": ["USA", "China"],
            "metric_name": ["GDP", "GDP"],
            "metric_value": [65000.0, 13000.0],
            "year": [2023, 2023],
            "score": [95.0, 78.0],
            "rank": [1, 2],
        })
    }


class TestFlatMetricValidators:
    def test_valid_frame_no_errors(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from validators import validate_dataframes

        frames = _make_valid_fm_frame()
        issues = validate_dataframes(frames, entity_specs=FLAT_METRIC_ENTITIES)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_missing_entity_column(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from validators import validate_dataframes

        frames = {
            "flat_metrics": pd.DataFrame({
                "metric_name": ["GDP"],
                "metric_value": [65000.0],
            })
        }
        issues = validate_dataframes(frames, entity_specs=FLAT_METRIC_ENTITIES)
        errors = [i for i in issues if i.severity == "error"]
        assert any("entity" in e.message for e in errors)

    def test_null_metric_value(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from validators import validate_dataframes

        frames = {
            "flat_metrics": pd.DataFrame({
                "entity": ["USA"],
                "metric_name": ["GDP"],
                "metric_value": [None],
            })
        }
        issues = validate_dataframes(frames, entity_specs=FLAT_METRIC_ENTITIES)
        errors = [i for i in issues if i.severity == "error"]
        assert any("null" in e.message.lower() for e in errors)

    def test_nullable_year_allowed(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from validators import validate_dataframes

        frames = {
            "flat_metrics": pd.DataFrame({
                "entity": ["USA"],
                "metric_name": ["GDP"],
                "metric_value": [65000.0],
                "year": [None],
                "score": [None],
                "rank": [None],
            })
        }
        issues = validate_dataframes(frames, entity_specs=FLAT_METRIC_ENTITIES)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_non_numeric_metric_value(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from validators import validate_dataframes

        frames = {
            "flat_metrics": pd.DataFrame({
                "entity": ["USA"],
                "metric_name": ["GDP"],
                "metric_value": ["not a number"],
            })
        }
        issues = validate_dataframes(frames, entity_specs=FLAT_METRIC_ENTITIES)
        errors = [i for i in issues if i.severity == "error"]
        assert any("number" in e.message.lower() for e in errors)


# ── Flat metric normalizers ─────────────────────────────────────


class TestFlatMetricNormalizers:
    def test_float_coercion(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from normalizers import normalize_frames

        frames = {
            "flat_metrics": pd.DataFrame({
                "entity": ["USA"],
                "metric_name": ["GDP"],
                "metric_value": ["65000"],
                "year": ["2023"],
                "score": ["95.2"],
                "rank": ["1"],
            })
        }
        result = normalize_frames(frames, entity_specs=FLAT_METRIC_ENTITIES)
        df = result["flat_metrics"]
        assert df["metric_value"].dtype == "float64"
        assert df["year"].dtype == "Int64"

    def test_column_name_lowercased(self):
        from flat_metric_model import FLAT_METRIC_ENTITIES
        from normalizers import normalize_frames

        frames = {
            "flat_metrics": pd.DataFrame({
                "Entity": ["USA"],
                "METRIC_NAME": ["GDP"],
                "Metric_Value": [65000.0],
            })
        }
        result = normalize_frames(frames, entity_specs=FLAT_METRIC_ENTITIES)
        df = result["flat_metrics"]
        assert "entity" in df.columns
        assert "metric_name" in df.columns
        assert "metric_value" in df.columns


# ── Flat metric readers ─────────────────────────────────────────


class TestFlatMetricCSVReader:
    def test_reads_valid_csv(self):
        from readers import read_flat_metric_csv

        csv_data = "entity,metric_name,metric_value\nUSA,GDP,65000\n"
        buf = BytesIO(csv_data.encode("utf-8"))
        frames = read_flat_metric_csv(buf)
        assert "flat_metrics" in frames
        assert len(frames["flat_metrics"]) == 1

    def test_missing_column_raises(self):
        from readers import ReaderError, read_flat_metric_csv

        csv_data = "entity,some_other\nUSA,123\n"
        buf = BytesIO(csv_data.encode("utf-8"))
        with pytest.raises(ReaderError, match="missing required"):
            read_flat_metric_csv(buf)

    def test_empty_csv_raises(self):
        from readers import ReaderError, read_flat_metric_csv

        csv_data = "entity,metric_name,metric_value\n"
        buf = BytesIO(csv_data.encode("utf-8"))
        with pytest.raises(ReaderError, match="no data rows"):
            read_flat_metric_csv(buf)


class TestFlatMetricExcelReader:
    def test_reads_valid_excel(self):
        from readers import read_flat_metric_excel

        buf = BytesIO()
        df = pd.DataFrame({
            "entity": ["USA"],
            "metric_name": ["GDP"],
            "metric_value": [65000.0],
        })
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        frames = read_flat_metric_excel(buf)
        assert "flat_metrics" in frames
        assert len(frames["flat_metrics"]) == 1

    def test_missing_column_raises(self):
        from readers import ReaderError, read_flat_metric_excel

        buf = BytesIO()
        df = pd.DataFrame({"entity": ["USA"], "some_other": [123]})
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        with pytest.raises(ReaderError, match="missing required"):
            read_flat_metric_excel(buf)


# ── Flat metric importer ────────────────────────────────────────


class TestFlatMetricImporter:
    def test_csv_import_success(self):
        from importer import import_flat_metric_csv

        csv_data = "entity,metric_name,metric_value,year\nUSA,GDP,65000,2023\n"
        buf = BytesIO(csv_data.encode("utf-8"))

        with patch("importer.load_flat_metrics", return_value={"flat_metrics": 1}):
            result = import_flat_metric_csv(buf, label="test")

        assert result.success is True
        assert result.row_counts == {"flat_metrics": 1}

    def test_csv_import_validation_failure(self):
        from importer import import_flat_metric_csv

        csv_data = "entity,metric_name,metric_value\n"
        buf = BytesIO(csv_data.encode("utf-8"))

        # Empty CSV raises ReaderError
        result = import_flat_metric_csv(buf, label="test")
        assert result.success is False

    def test_excel_import_success(self):
        from importer import import_flat_metric_excel

        buf = BytesIO()
        df = pd.DataFrame({
            "entity": ["USA"],
            "metric_name": ["GDP"],
            "metric_value": [65000.0],
        })
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        with patch("importer.load_flat_metrics", return_value={"flat_metrics": 1}):
            result = import_flat_metric_excel(buf, label="test")

        assert result.success is True

    def test_csv_import_db_failure(self):
        from importer import import_flat_metric_csv

        csv_data = "entity,metric_name,metric_value\nUSA,GDP,65000\n"
        buf = BytesIO(csv_data.encode("utf-8"))

        with patch("importer.load_flat_metrics", side_effect=RuntimeError("db down")):
            result = import_flat_metric_csv(buf, label="test")

        assert result.success is False
        assert any("Database load failed" in e.message for e in result.errors)


# ── Flat metric query filter builder ────────────────────────────


class TestFlatMetricFilters:
    def test_no_filters(self):
        from flat_metric_queries import _build_fm_filters

        where, params = _build_fm_filters()
        assert where == ""
        assert params == []

    def test_entities_filter(self):
        from flat_metric_queries import _build_fm_filters

        where, params = _build_fm_filters(entities=["USA", "China"])
        assert "entity = ANY(%s)" in where
        assert params == [["USA", "China"]]

    def test_metric_names_filter(self):
        from flat_metric_queries import _build_fm_filters

        where, params = _build_fm_filters(metric_names=["GDP"])
        assert "metric_name = ANY(%s)" in where
        assert params == [["GDP"]]

    def test_year_range_filter(self):
        from flat_metric_queries import _build_fm_filters

        where, params = _build_fm_filters(year_from=2021, year_to=2023)
        assert "year >= %s" in where
        assert "year <= %s" in where
        assert params == [2021, 2023]

    def test_combined_filters(self):
        from flat_metric_queries import _build_fm_filters

        where, params = _build_fm_filters(
            entities=["USA"],
            metric_names=["GDP"],
            year_from=2021,
            year_to=2023,
        )
        assert where.startswith("WHERE")
        assert len(params) == 4
