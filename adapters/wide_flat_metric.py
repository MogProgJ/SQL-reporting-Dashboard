"""Wide flat-metric adapter — transforms wide-format metric spreadsheets
into the canonical long-format Flat Metric model.

Handles workbooks like ``FSI-2023-DOWNLOAD.xlsx`` where:
- One column is the entity (e.g. Country)
- One optional column is the year (e.g. Year)
- Optional columns for rank/total/score
- Remaining numeric columns are individual metrics (wide format)

The adapter melts the wide columns into long-format rows with
``entity``, ``metric_name``, ``metric_value``, ``year``, ``score``, ``rank``.
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
from file_profiler import FileProfile, ProfileFamily


# ── Column detection heuristics ─────────────────────────────────

_ENTITY_CANDIDATES = ("country", "entity", "name", "region", "state",
                      "company", "organization", "org")
_YEAR_CANDIDATES = ("year", "yr", "period")
_RANK_CANDIDATES = ("rank", "ranking", "position")
_SCORE_CANDIDATES = ("total", "score", "overall", "index", "composite")


def _pick_col(col_map: dict[str, str], *candidates: str) -> str | None:
    """Return the original column name for the first matching candidate."""
    for c in candidates:
        if c in col_map:
            return col_map[c]
    return None


class WideFlatMetricAdapter(BaseAdapter):
    name = "wide_flat_metric"
    description = "Wide flat-metric workbook → canonical long format via melt."
    profile_family = ProfileFamily.FLAT_METRIC

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        buf.seek(0)
        try:
            df = self._read_first_sheet(buf, nrows=5)
        except Exception:
            return AdapterPlan(
                adapter_name=self.name,
                description=self.description,
                profile_family=self.profile_family,
                warnings=["Could not read workbook to build plan."],
            )

        col_map = {str(c).strip().lower(): str(c) for c in df.columns}
        entity_col = _pick_col(col_map, *_ENTITY_CANDIDATES)
        year_col = _pick_col(col_map, *_YEAR_CANDIDATES)
        rank_col = _pick_col(col_map, *_RANK_CANDIDATES)
        score_col = _pick_col(col_map, *_SCORE_CANDIDATES)

        # Metric columns = numeric columns minus known special ones
        special = {c.lower().strip() for c in [entity_col, year_col, rank_col, score_col] if c}
        numeric_cols = [str(c) for c in df.select_dtypes(include="number").columns
                        if str(c).strip().lower() not in special]

        mappings = []
        if entity_col:
            mappings.append(FieldMapping(entity_col, "entity"))
        if year_col:
            mappings.append(FieldMapping(year_col, "year"))
        if score_col:
            mappings.append(FieldMapping(score_col, "score", "used as composite score"))
        if rank_col:
            mappings.append(FieldMapping(rank_col, "rank"))

        assumptions = []
        if not year_col:
            assumptions.append("No year column detected; year will be left empty.")
        if not rank_col:
            assumptions.append("No rank column detected; rank will be left empty.")

        return AdapterPlan(
            adapter_name=self.name,
            description=f"Melt {len(numeric_cols)} metric columns into long format.",
            profile_family=self.profile_family,
            field_mappings=mappings,
            assumptions=assumptions,
            will_produce=f"Flat Metric dataset with {len(numeric_cols)} metrics per entity.",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        buf.seek(0)
        warnings: list[str] = []

        try:
            df = self._read_first_sheet(buf)
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=f"Could not read workbook: {exc}",
            )

        col_map = {str(c).strip().lower(): str(c) for c in df.columns}

        # Detect columns
        entity_col = _pick_col(col_map, *_ENTITY_CANDIDATES)
        year_col = _pick_col(col_map, *_YEAR_CANDIDATES)
        rank_col = _pick_col(col_map, *_RANK_CANDIDATES)
        score_col = _pick_col(col_map, *_SCORE_CANDIDATES)

        if not entity_col:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error="No entity column detected (expected: country, entity, name, etc.).",
            )

        # Identify metric columns (numeric, not entity/year/rank/score)
        special = {c.lower().strip() for c in [entity_col, year_col, rank_col, score_col] if c}
        metric_cols = [str(c) for c in df.select_dtypes(include="number").columns
                       if str(c).strip().lower() not in special]

        if not metric_cols:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error="No numeric metric columns found to melt.",
            )

        # Build long-format DataFrame via melt
        id_vars = [entity_col]
        if year_col:
            id_vars.append(year_col)

        melted = df.melt(
            id_vars=id_vars,
            value_vars=metric_cols,
            var_name="metric_name",
            value_name="metric_value",
        )

        # Build canonical columns
        result = pd.DataFrame()
        result["entity"] = melted[entity_col].astype(str).str.strip()
        result["metric_name"] = melted["metric_name"].astype(str).str.strip()
        result["metric_value"] = pd.to_numeric(melted["metric_value"], errors="coerce").fillna(0.0)

        if year_col:
            result["year"] = pd.to_numeric(melted[year_col], errors="coerce").astype("Int64")
        else:
            result["year"] = pd.NA
            warnings.append("No year column detected; year left empty.")

        # Score: map from the original score column per entity+year
        if score_col:
            score_map = df.set_index(
                [entity_col] + ([year_col] if year_col else [])
            )[score_col]
            merge_keys = ["entity"] + (["year"] if year_col else [])
            # Build a mapping df
            score_df = df[[entity_col] + ([year_col] if year_col else []) + [score_col]].copy()
            score_df.columns = merge_keys + ["score"]
            score_df["entity"] = score_df["entity"].astype(str).str.strip()
            if year_col:
                score_df["year"] = pd.to_numeric(score_df["year"], errors="coerce").astype("Int64")
            result = result.merge(score_df.drop_duplicates(), on=merge_keys, how="left")
            result["score"] = pd.to_numeric(result["score"], errors="coerce")
        else:
            result["score"] = pd.NA
            warnings.append("No score/total column detected; score left empty.")

        # Rank: map from original rank column
        if rank_col:
            rank_df = df[[entity_col] + ([year_col] if year_col else []) + [rank_col]].copy()
            merge_keys = ["entity"] + (["year"] if year_col else [])
            rank_df.columns = merge_keys + ["rank"]
            rank_df["entity"] = rank_df["entity"].astype(str).str.strip()
            if year_col:
                rank_df["year"] = pd.to_numeric(rank_df["year"], errors="coerce").astype("Int64")
            result = result.merge(rank_df.drop_duplicates(), on=merge_keys, how="left")
            result["rank"] = pd.to_numeric(result["rank"], errors="coerce").astype("Int64")
        else:
            result["rank"] = pd.NA

        # Drop rows where metric_value is NaN (from melt of sparse data)
        result = result.dropna(subset=["metric_value"]).reset_index(drop=True)

        warnings.append(f"Melted {len(metric_cols)} metric columns into {len(result)} long-format rows.")

        plan = self.plan(None, buf)  # type: ignore[arg-type]

        return AdapterResult(
            success=True,
            adapter_name=self.name,
            profile_family=self.profile_family,
            frames={"flat_metrics": result},
            plan=plan,
            warnings=warnings,
        )

    def _read_first_sheet(self, buf: BytesIO, nrows: int | None = None) -> pd.DataFrame:
        """Read the first sheet of an Excel workbook."""
        buf.seek(0)
        xls = pd.ExcelFile(buf, engine="openpyxl")
        if nrows:
            return xls.parse(xls.sheet_names[0], nrows=nrows)
        return xls.parse(xls.sheet_names[0])


# ── Auto-register ───────────────────────────────────────────────

register_adapter(WideFlatMetricAdapter())
