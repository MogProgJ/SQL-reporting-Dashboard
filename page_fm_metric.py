"""Flat Metric — Metric Explorer deep-dive page.

Shows one metric across all entities and time: rankings, trends,
outliers, and raw data.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import (
    add_rank, fmt_number,
    col_rank, col_text, col_value, col_year, col_score, col_count,
)
from flat_metric_queries import (
    get_fm_metric_bottom_entities,
    get_fm_metric_detail,
    get_fm_metric_names,
    get_fm_metric_outliers,
    get_fm_metric_summary,
    get_fm_metric_top_entities,
    get_fm_metric_trend_avg,
    get_fm_year_range,
)
from nav_state import get_target, render_back_button, set_page, FlatMetricPage


def _find_outliers(df: pd.DataFrame, col: str = "metric_value") -> pd.DataFrame:
    """IQR-based outlier detection on a DataFrame column."""
    if df.empty or col not in df.columns or len(df) < 4:
        return df.head(0)
    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    return df[(df[col] < low) | (df[col] > high)].copy()


# ── Public API ──────────────────────────────────────────────────


def render() -> None:
    """Render the metric explorer page."""
    render_back_button(is_order=False)

    metrics = get_fm_metric_names()
    if not metrics:
        st.warning("No metric data available.")
        return

    target = get_target()
    default_idx = 0
    if target and target in metrics:
        default_idx = metrics.index(target)

    selected = st.selectbox(
        "Select metric to explore",
        metrics,
        index=default_idx,
        key="fm_metric_explorer_select",
    )
    if not selected:
        return

    st.markdown(f"## {selected}")

    # ── Header / summary KPIs ───────────────────────────────
    summary = get_fm_metric_summary(selected)
    if summary.empty or int(summary.iloc[0]["total_rows"]) == 0:
        st.info(f"No data found for metric **{selected}**.")
        return

    s = summary.iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Entities", fmt_number(s["entity_count"]))
    if pd.notna(s["min_year"]) and pd.notna(s["max_year"]):
        c2.metric("Year Span", f"{int(s['min_year'])}–{int(s['max_year'])}")
    else:
        c2.metric("Year Span", "—")
    c3.metric("Avg", f"{s['avg_value']:,.2f}")
    c4.metric("Min", f"{s['min_value']:,.2f}")
    c5.metric("Max", f"{s['max_value']:,.2f}")

    st.markdown("")

    # Optional year filter
    year_range = get_fm_year_range()
    sel_year = None
    if year_range:
        yr_min, yr_max = year_range
        use_year = st.checkbox("Filter by year", value=False, key="fm_metric_use_year")
        if use_year:
            sel_year = st.slider(
                "Year",
                min_value=yr_min,
                max_value=yr_max,
                value=yr_max,
                key="fm_metric_year_slider",
            )

    # ── Tabs ────────────────────────────────────────────────
    tab_rank, tab_trend, tab_outlier, tab_detail = st.tabs(
        ["🏆 Rankings", "📈 Trend", "⚠️ Outliers", "📋 Detail & Export"]
    )

    with tab_rank:
        _render_rankings(selected, sel_year)

    with tab_trend:
        _render_trend(selected)

    with tab_outlier:
        _render_outliers(selected, sel_year)

    with tab_detail:
        _render_detail(selected)


# ── Tab renderers ───────────────────────────────────────────────


def _render_rankings(metric_name: str, year: int | None) -> None:
    """Top and bottom entities for this metric."""
    year_label = str(year) if year else "latest year per entity"
    st.subheader(f"Top Entities ({year_label})")
    top = get_fm_metric_top_entities(metric_name, limit=10, year=year)
    if not top.empty:
        tbl = add_rank(top.copy())
        fig = px.bar(
            top.sort_values("metric_value"),
            x="metric_value",
            y="entity",
            orientation="h",
            labels={"metric_value": metric_name, "entity": ""},
            text="metric_value",
        )
        fig.update_traces(texttemplate="%{x:,.1f}", textposition="outside")
        fig.update_layout(
            height=max(250, len(top) * 35 + 60),
            margin=dict(l=0, r=100, t=10, b=0),
            yaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")

        show_cols = ["#", "entity", "metric_value"]
        col_cfg = {
            "#": col_rank(),
            "entity": col_text("Entity"),
            "metric_value": col_value(metric_name),
        }
        if "year" in tbl.columns and tbl["year"].notna().any():
            show_cols.append("year")
            col_cfg["year"] = col_year()
        st.dataframe(tbl[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True)
        st.caption(f"One row per entity — {year_label}.")

        # Navigation to Entity Detail
        entity_pick = st.selectbox(
            "Explore entity in detail",
            [""] + top["entity"].tolist(),
            key="fm_metric_to_entity",
        )
        if entity_pick:
            set_page(FlatMetricPage.ENTITY_DETAIL.value, target=entity_pick)
    else:
        st.info("No data for top entities.")

    st.divider()

    st.subheader(f"Bottom Entities ({year_label})")
    bottom = get_fm_metric_bottom_entities(metric_name, limit=10, year=year)
    if not bottom.empty:
        tbl_b = add_rank(bottom.copy())
        show_cols = ["#", "entity", "metric_value"]
        col_cfg = {
            "#": col_rank(),
            "entity": col_text("Entity"),
            "metric_value": col_value(metric_name),
        }
        if "year" in tbl_b.columns and tbl_b["year"].notna().any():
            show_cols.append("year")
            col_cfg["year"] = col_year()
        st.dataframe(tbl_b[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True)
        st.caption(f"One row per entity — {year_label}.")
    else:
        st.info("No data for bottom entities.")


def _render_trend(metric_name: str) -> None:
    """Average metric value per year across all entities."""
    st.subheader("Average Over Time")
    trend = get_fm_metric_trend_avg(metric_name)
    if trend.empty:
        st.info("No year-over-year trend data available.")
        return

    fig = px.line(
        trend,
        x="year",
        y="avg_value",
        markers=True,
        labels={"year": "Year", "avg_value": f"Avg {metric_name}"},
    )
    fig.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(dtick=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    st.dataframe(
        trend,
        column_config={
            "year": col_year(),
            "avg_value": col_value(f"Avg {metric_name}"),
            "entity_count": col_count("Entities"),
        },
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Average {metric_name} per year across all entities.")


def _render_outliers(metric_name: str, year: int | None) -> None:
    """Entities with unusually high or low values (IQR rule)."""
    st.subheader("Outlier Entities")
    st.markdown(
        "> Flagged using the **IQR rule** — values outside "
        "Q₁ − 1.5 × IQR or Q₃ + 1.5 × IQR. "
        "A transparent statistical threshold, not a black-box model."
    )

    raw = get_fm_metric_outliers(metric_name, year=year)
    outliers = _find_outliers(raw)
    if outliers.empty:
        st.info(f"No outlier entities detected for {metric_name}.")
        return

    st.markdown(f"**{len(outliers)} outlier(s)** out of {len(raw)} entities")

    show_cols = ["entity", "metric_value"]
    col_cfg = {
        "entity": col_text("Entity"),
        "metric_value": col_value(metric_name),
    }
    if "year" in outliers.columns and outliers["year"].notna().any():
        show_cols.append("year")
        col_cfg["year"] = col_year()

    st.dataframe(outliers[show_cols], column_config=col_cfg, use_container_width=True, hide_index=True)


def _render_detail(metric_name: str) -> None:
    """Full data table for this metric with export."""
    data = get_fm_metric_detail(metric_name)
    if data.empty:
        st.info("No data for this metric.")
        return

    st.markdown(f"**{len(data):,} rows** for {metric_name}")

    show_cols = ["entity", "metric_value", "year"]
    col_cfg = {
        "entity": col_text("Entity"),
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
        file_name=f"metric_{metric_name}.csv",
        mime="text/csv",
    )
