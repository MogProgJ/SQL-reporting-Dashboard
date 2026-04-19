"""Canonical adapters — thin wrappers that route files through the existing
strict import pipeline.  These exist so the adapter registry can treat
canonical imports uniformly alongside adaptive imports.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from adapters import (
    AdapterPlan,
    AdapterResult,
    BaseAdapter,
    FieldMapping,
    register_adapter,
)
from file_profiler import FileProfile, Importability, ProfileFamily


class CanonicalOrderExcelAdapter(BaseAdapter):
    name = "canonical_order_excel"
    description = "Canonical Order Reporting Excel workbook (5 sheets)."
    profile_family = ProfileFamily.ORDER_REPORTING

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        return AdapterPlan(
            adapter_name=self.name,
            description=self.description,
            profile_family=self.profile_family,
            will_produce="Full Order Reporting dataset (strict canonical format).",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        from readers import read_excel_workbook
        try:
            frames = read_excel_workbook(buf)
            return AdapterResult(
                success=True,
                adapter_name=self.name,
                profile_family=self.profile_family,
                frames=frames,
            )
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=str(exc),
            )


class CanonicalOrderCsvBundleAdapter(BaseAdapter):
    name = "canonical_order_csv_bundle"
    description = "Canonical Order Reporting CSV bundle (5 files)."
    profile_family = ProfileFamily.ORDER_REPORTING

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        return AdapterPlan(
            adapter_name=self.name,
            description=self.description,
            profile_family=self.profile_family,
            will_produce="Full Order Reporting dataset (strict canonical format).",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        # This adapter handles ZIP-contained CSV bundles
        import zipfile
        from pathlib import Path

        from readers import read_csv_bundle
        try:
            buf.seek(0)
            file_map: dict[str, BytesIO] = {}
            with zipfile.ZipFile(buf) as zf:
                for entry in zf.namelist():
                    if entry.lower().endswith(".csv") and not entry.startswith("__MACOSX"):
                        with zf.open(entry) as f:
                            file_map[Path(entry).name] = BytesIO(f.read())
            frames = read_csv_bundle(file_map)
            return AdapterResult(
                success=True,
                adapter_name=self.name,
                profile_family=self.profile_family,
                frames=frames,
            )
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=str(exc),
            )


class CanonicalFlatMetricCsvAdapter(BaseAdapter):
    name = "canonical_flat_metric_csv"
    description = "Canonical long-format Flat Metric CSV."
    profile_family = ProfileFamily.FLAT_METRIC

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        return AdapterPlan(
            adapter_name=self.name,
            description=self.description,
            profile_family=self.profile_family,
            will_produce="Full Flat Metric dataset (strict canonical format).",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        from readers import read_flat_metric_csv
        try:
            frames = read_flat_metric_csv(buf)
            return AdapterResult(
                success=True,
                adapter_name=self.name,
                profile_family=self.profile_family,
                frames=frames,
            )
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=str(exc),
            )


class CanonicalFlatMetricExcelAdapter(BaseAdapter):
    name = "canonical_flat_metric_excel"
    description = "Canonical long-format Flat Metric Excel workbook."
    profile_family = ProfileFamily.FLAT_METRIC

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        return AdapterPlan(
            adapter_name=self.name,
            description=self.description,
            profile_family=self.profile_family,
            will_produce="Full Flat Metric dataset (strict canonical format).",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        from readers import read_flat_metric_excel
        try:
            frames = read_flat_metric_excel(buf)
            return AdapterResult(
                success=True,
                adapter_name=self.name,
                profile_family=self.profile_family,
                frames=frames,
            )
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=str(exc),
            )


# ── Auto-register ───────────────────────────────────────────────

register_adapter(CanonicalOrderExcelAdapter())
register_adapter(CanonicalOrderCsvBundleAdapter())
register_adapter(CanonicalFlatMetricCsvAdapter())
register_adapter(CanonicalFlatMetricExcelAdapter())
