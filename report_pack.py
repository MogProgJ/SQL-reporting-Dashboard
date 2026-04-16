"""Report-pack builder — profile-aware bundles beyond CSV-only export.

A report pack is a downloadable JSON document containing metadata, KPIs,
summary tables, and the detail slice — everything needed to reproduce or
share a dashboard state offline.

Usage from the dashboard:
    from report_pack import build_order_pack, build_fm_pack
    pack_bytes = build_order_pack(filters, top_n)
    st.download_button("Download report pack", pack_bytes, ...)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd


# ── JSON encoder ────────────────────────────────────────────────

class _Encoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to JSON-safe records."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


# ── Order-profile pack ──────────────────────────────────────────

def build_order_pack(filters: dict, top_n: int = 10) -> bytes:
    """Build a JSON report pack for the Order Reporting profile."""
    from queries import (
        get_category_breakdown,
        get_kpis,
        get_order_detail,
        get_revenue_trend,
        get_top_customers,
        get_top_products,
    )

    pack: dict[str, Any] = {
        "report_type": "order_reporting",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filters": _serialise_filters(filters),
        "top_n": top_n,
    }

    # KPIs
    kpis = get_kpis(**filters)
    if not kpis.empty:
        pack["kpis"] = kpis.iloc[0].to_dict()

    # Revenue trend
    trend = get_revenue_trend(**filters)
    pack["revenue_trend"] = _df_to_records(trend)

    # Top customers & products
    pack["top_customers"] = _df_to_records(get_top_customers(limit=top_n, **filters))
    pack["top_products"] = _df_to_records(get_top_products(limit=top_n, **filters))

    # Category breakdown
    pack["category_breakdown"] = _df_to_records(get_category_breakdown(**filters))

    # Detail slice (capped)
    detail = get_order_detail(**filters)
    pack["detail_row_count"] = len(detail)
    pack["detail"] = _df_to_records(detail.head(500))

    return json.dumps(pack, cls=_Encoder, indent=2).encode("utf-8")


# ── Flat-metric pack ───────────────────────────────────────────

def build_fm_pack(filters: dict) -> bytes:
    """Build a JSON report pack for the Flat Metric profile."""
    from flat_metric_queries import (
        get_fm_detail,
        get_fm_kpis,
        get_fm_ranking,
        get_fm_trend,
    )

    pack: dict[str, Any] = {
        "report_type": "flat_metric",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filters": _serialise_filters(filters),
    }

    # KPIs
    kpis = get_fm_kpis(**filters)
    if not kpis.empty:
        pack["kpis"] = kpis.iloc[0].to_dict()

    # Ranking table
    primary = filters.get("_primary_metric", "")
    if primary:
        ranking = get_fm_ranking(primary, **filters)
        pack["ranking"] = _df_to_records(ranking)

    # Primary metric trend
    if primary:
        trend = get_fm_trend(primary, **filters)
        pack["trend"] = _df_to_records(trend)

    # Detail slice (capped)
    detail = get_fm_detail(**filters)
    pack["detail_row_count"] = len(detail)
    pack["detail"] = _df_to_records(detail.head(500))

    return json.dumps(pack, cls=_Encoder, indent=2).encode("utf-8")


# ── Helpers ─────────────────────────────────────────────────────

def _serialise_filters(filters: dict) -> dict:
    """Make a filter dict JSON-safe."""
    out: dict[str, Any] = {}
    for k, v in filters.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = list(v)
        else:
            out[k] = v
    return out
