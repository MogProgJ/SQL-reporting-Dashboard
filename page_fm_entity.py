"""Flat Metric — Entity Detail deep-dive page.

Shows all metrics, trends, and raw data for a single entity.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import (
    fmt_number,
    col_text, col_value, col_year, col_score, col_count,
)
from flat_metric_queries import (
    get_fm_entities,
    get_fm_entity_comparison,
    get_fm_entity_metrics,
    get_fm_entity_summary,
    get_fm_entity_trend,
    get_fm_metric_names,
)
from nav_state import get_target, render_back_button, set_page, FlatMetricPage


# ── Public API ──────────────────────────────────────────────────


def render() -> None:
    """Render the entity detail page."""
    render_back_button(is_order=False)

    entities = get_fm_entities()
    if not entities:
        st.warning("No entity data available.")
        return

    # Entity selector — pre-select from nav target if set
    target = get_target()
    default_idx = 0
    if target and target in entities:
        default_idx = entities.index(target)

    selected = st.selectbox(
        "Select entity to inspect",
        entities,
        index=default_idx,
        key="fm_entity_detail_select",
    )
    if not selected:
        return

    st.markdown(f"## {selected}")

    # ── Header / summary KPIs ───────────────────────────────
    summary = get_fm_entity_summary(selected)
    if summary.empty or int(summary.iloc[0]["total_rows"]) == 0:
        st.info(f"No data found for entity **{selected}**.")
        return

    s = summary.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rows", fmt_number(s["total_rows"]))
    c2.metric("Metrics Tracked", fmt_number(s["metric_count"]))
    if pd.notna(s["min_year"]) and pd.notna(s["max_year"]):
        c3.metric("Year Span", f"{int(s['min_year'])}–{int(s['max_year'])}")
    else:
        c3.metric("Year Span", "—")
    if pd.notna(s["avg_score"]):
        c4.metric("Avg Score", f"{s['avg_score']:.1f}")
    else:
        c4.metric("Avg Score", "—")

    st.markdown("")

    # ── Tabs ────────────────────────────────────────────────
    tab_trend, tab_compare, tab_detail = st.tabs(
        ["📈 Time Trend", "📊 Metric Comparison", "📋 Detail & Export"]
    )

    with tab_trend:
        _render_trend(selected)

    with tab_compare:
        _render_comparison(selected, s)

    with tab_detail:
        _render_detail(selected)


# ── Tab renderers ───────────────────────────────────────────────


def _render_trend(entity: str) -> None:
    """Time trend for a selected metric."""
    metrics = get_fm_metric_names()
    if not metrics:
        st.info("No metrics available.")
        return

    metric = st.selectbox(
        "Metric to visualise",
        metrics,
        key="fm_entity_trend_metric",
    )

    trend = get_fm_entity_trend(entity, metric)
    if trend.empty:
        st.info(f"No year-over-year data for **{entity}** / {metric}.")
        return

    fig = px.line(
        trend,
        x="year",
        y="metric_value",
        markers=True,
        labels={"year": "Year", "metric_value": metric},
    )
    fig.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(dtick=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption(f"{metric} over time for {entity}.")

    # Show the data
    show = trend.copy()
    show_cols = ["year", "metric_value"]
    col_cfg = {
        "year": col_year(),
        "metric_value": col_value(metric),
    }
    if "score" in show.columns and show["score"].notna().any():
        show_cols.append("score")
        col_cfg["score"] = col_score()
    if "rank" in show.columns and show["rank"].notna().any():
        show_cols.append("rank")
        col_cfg["rank"] = col_count("Rank")

    st.dataframe(show[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True)


def _render_comparison(entity: str, summary_row) -> None:
    """Compare all metrics for the entity in a selected year."""
    min_yr = summary_row.get("min_year")
    max_yr = summary_row.get("max_year")

    year = None
    if pd.notna(min_yr) and pd.notna(max_yr):
        year = st.slider(
            "Year",
            min_value=int(min_yr),
            max_value=int(max_yr),
            value=int(max_yr),
            key="fm_entity_compare_year",
        )

    comp = get_fm_entity_comparison(entity, year=year)
    if comp.empty:
        st.info("No comparison data for this entity and year.")
        return

    st.subheader(f"Metrics for {entity}" + (f" ({year})" if year else " (latest year)"))

    fig = px.bar(
        comp.sort_values("metric_value"),
        x="metric_value",
        y="metric_name",
        orientation="h",
        labels={"metric_value": "Value", "metric_name": ""},
        text="metric_value",
    )
    fig.update_traces(texttemplate="%{x:,.1f}", textposition="outside")
    fig.update_layout(
        height=max(250, len(comp) * 45 + 60),
        margin=dict(l=0, r=100, t=10, b=0),
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # Table
    show_cols = ["metric_name", "metric_value"]
    col_cfg = {
        "metric_name": col_text("Metric"),
        "metric_value": col_value(),
    }
    if "score" in comp.columns and comp["score"].notna().any():
        show_cols.append("score")
        col_cfg["score"] = col_score()
    if "rank" in comp.columns and comp["rank"].notna().any():
        show_cols.append("rank")
        col_cfg["rank"] = col_count("Rank")

    st.dataframe(comp[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True)
    st.caption(f"Showing one value per metric — {'year ' + str(year) if year else 'latest available year per metric'}.")

    # Navigation to Metric Explorer
    metric_pick = st.selectbox(
        "Explore a metric across all entities",
        [""] + comp["metric_name"].tolist(),
        key="fm_entity_to_metric",
    )
    if metric_pick:
        set_page(FlatMetricPage.METRIC_EXPLORER.value, target=metric_pick)


def _render_detail(entity: str) -> None:
    """Full data table for the entity with export."""
    data = get_fm_entity_metrics(entity)
    if data.empty:
        st.info("No data for this entity.")
        return

    st.markdown(f"**{len(data):,} rows** for {entity}")

    show_cols = ["metric_name", "metric_value", "year"]
    col_cfg = {
        "metric_name": col_text("Metric"),
        "metric_value": col_value(),
        "year": col_year(),
    }
    if "score" in data.columns and data["score"].notna().any():
        show_cols.append("score")
        col_cfg["score"] = col_score()
    if "rank" in data.columns and data["rank"].notna().any():
        show_cols.append("rank")
        col_cfg["rank"] = col_count("Rank")

    st.dataframe(data[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True, height=400)

    csv = data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download CSV",
        data=csv,
        file_name=f"entity_{entity}.csv",
        mime="text/csv",
    )
