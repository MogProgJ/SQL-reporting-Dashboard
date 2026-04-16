"""Flat Metric analytics dashboard — filters and visualisations.

Provides KPI row, ranking table, comparison bar chart, year-over-year
trends, and a full detail/export table for the flat-metric profile.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import add_rank, fmt_number
from flat_metric_queries import (
    get_fm_comparison,
    get_fm_detail,
    get_fm_entities,
    get_fm_kpis,
    get_fm_metric_names,
    get_fm_ranking,
    get_fm_trend,
    get_fm_year_range,
)
from nav_state import FlatMetricPage, set_page


# ── Helpers ─────────────────────────────────────────────────────

def _empty_state(message: str = "No data matches the current filters.") -> None:
    st.warning(
        f"**{message}**  \n"
        "Try broadening the entity or metric filters."
    )


def _clear_fm_filters():
    for key in ("sel_fm_entities", "sel_fm_metrics"):
        st.session_state[key] = []


# ── Sidebar filters ─────────────────────────────────────────────

def render_filters() -> dict:
    """Render flat-metric filter widgets in the sidebar.

    Returns a dict of filter kwargs for the query functions.
    """
    metric_names = get_fm_metric_names()
    if not metric_names:
        st.warning("No flat-metric data found.")
        st.stop()

    primary_metric = st.selectbox(
        "Primary metric",
        metric_names,
        key="fm_primary_metric",
        help="Metric used for rankings and comparison charts.",
    )

    st.divider()

    sel_entities = st.multiselect(
        "Entity", get_fm_entities(), key="sel_fm_entities", placeholder="All entities"
    )
    sel_metrics = st.multiselect(
        "Metric", metric_names, key="sel_fm_metrics", placeholder="All metrics"
    )

    year_range = get_fm_year_range()
    year_from = year_to = None
    if year_range:
        yr_min, yr_max = year_range
        year_from, year_to = st.slider(
            "Year range",
            min_value=yr_min,
            max_value=yr_max,
            value=(yr_min, yr_max),
        )

    st.divider()
    st.button("Clear all filters", on_click=_clear_fm_filters, use_container_width=True)

    return dict(
        entities=sel_entities or None,
        metric_names=sel_metrics or None,
        year_from=year_from,
        year_to=year_to,
        _primary_metric=primary_metric,
    )


# ── Active-filter summary ───────────────────────────────────────

def _render_filter_summary(filters: dict) -> None:
    parts: list[str] = []
    parts.append(f"\U0001f4cf {filters.get('_primary_metric', '—')}")
    if filters.get("entities"):
        parts.append(f"Entities: {', '.join(filters['entities'])}")
    if filters.get("metric_names"):
        parts.append(f"Metrics: {', '.join(filters['metric_names'])}")
    if filters.get("year_from") is not None:
        parts.append(f"Years: {filters['year_from']}–{filters['year_to']}")

    with st.container(border=True):
        st.caption("**Active slice:** " + " \u00b7 ".join(parts))


# ── Main dashboard ──────────────────────────────────────────────

def render(filters: dict) -> None:
    """Render the full flat-metric analytics dashboard."""
    _render_filter_summary(filters)

    # Extract internal key
    primary_metric = filters.pop("_primary_metric")
    query_filters = {k: v for k, v in filters.items() if not k.startswith("_")}

    # ── KPI row ─────────────────────────────────────────────
    kpi = get_fm_kpis(**query_filters)
    if kpi.empty or int(kpi.iloc[0]["total_rows"]) == 0:
        _empty_state()
        st.stop()

    k = kpi.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rows", fmt_number(k["total_rows"]))
    c2.metric("Unique Entities", fmt_number(k["unique_entities"]))
    c3.metric("Metrics Tracked", fmt_number(k["metric_count"]))
    if pd.notna(k["min_year"]) and pd.notna(k["max_year"]):
        c4.metric("Year Span", f"{int(k['min_year'])}–{int(k['max_year'])}")
    else:
        c4.metric("Year Span", "—")

    st.markdown("")

    # ── Tabs ────────────────────────────────────────────────
    tab_rank, tab_trend, tab_detail = st.tabs(
        ["\U0001f3c6 Rankings", "\U0001f4c8 Trends", "\U0001f4cb Detail & Export"]
    )

    with tab_rank:
        _render_rankings(primary_metric, query_filters)

    with tab_trend:
        _render_trends(primary_metric, query_filters)

    with tab_detail:
        _render_detail(query_filters)


# ── Tab renderers ───────────────────────────────────────────────

def _render_rankings(primary_metric: str, filters: dict) -> None:
    st.subheader(f"Rankings — {primary_metric}")

    ranking = get_fm_ranking(primary_metric, limit=25, **filters)
    if ranking.empty:
        _empty_state(f"No data for metric '{primary_metric}'.")
        return

    # Bar chart
    fig = px.bar(
        ranking.sort_values("metric_value"),
        x="metric_value",
        y="entity",
        orientation="h",
        labels={"metric_value": primary_metric, "entity": ""},
        text="metric_value",
    )
    fig.update_traces(texttemplate="%{x:,.1f}", textposition="outside")
    fig.update_layout(
        height=max(250, len(ranking) * 35 + 60),
        margin=dict(l=0, r=100, t=10, b=0),
        yaxis_title=None,
        xaxis_title=primary_metric,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # Table
    tbl = add_rank(ranking.copy())
    show_cols = ["#", "entity", "metric_value"]
    col_config = {
        "#": st.column_config.NumberColumn("#", width="small"),
        "entity": st.column_config.TextColumn("Entity"),
        "metric_value": st.column_config.NumberColumn(primary_metric, format="%.2f"),
    }
    if "year" in tbl.columns and tbl["year"].notna().any():
        show_cols.append("year")
        col_config["year"] = st.column_config.NumberColumn("Year", format="%d")
    if "score" in tbl.columns and tbl["score"].notna().any():
        show_cols.append("score")
        col_config["score"] = st.column_config.NumberColumn("Score", format="%.1f")

    st.dataframe(
        tbl[show_cols],
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Entities ranked by {primary_metric} (descending).")

    # Navigation hooks
    col_a, col_b = st.columns(2)
    with col_a:
        entities_list = ranking["entity"].tolist()
        entity_pick = st.selectbox(
            "Explore entity in detail",
            [""] + entities_list,
            key="fm_rank_entity_pick",
        )
        if entity_pick:
            set_page(FlatMetricPage.ENTITY_DETAIL.value, target=entity_pick)
    with col_b:
        if st.button(f"Explore {primary_metric} across all entities", key="fm_rank_metric_btn"):
            set_page(FlatMetricPage.METRIC_EXPLORER.value, target=primary_metric)


def _render_trends(primary_metric: str, filters: dict) -> None:
    st.subheader(f"Trend — {primary_metric}")

    trend = get_fm_trend(primary_metric, **filters)
    if trend.empty:
        st.info("No year-over-year data available for this metric and filters.")
        return

    fig = px.line(
        trend,
        x="year",
        y="metric_value",
        color="entity",
        markers=True,
        labels={"year": "Year", "metric_value": primary_metric, "entity": "Entity"},
    )
    fig.update_layout(
        height=400,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Year",
        yaxis_title=primary_metric,
        hovermode="x unified",
        xaxis=dict(dtick=1),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption(f"{primary_metric} over time for each entity.")

    # Comparison table (latest year)
    comparison = get_fm_comparison(primary_metric, **filters)
    if not comparison.empty:
        st.subheader("Entity Comparison")
        comp_tbl = add_rank(comparison.copy())
        st.dataframe(
            comp_tbl[["#", "entity", "metric_value", "year"]],
            column_config={
                "#": st.column_config.NumberColumn("#", width="small"),
                "entity": st.column_config.TextColumn("Entity"),
                "metric_value": st.column_config.NumberColumn(
                    primary_metric, format="%.2f"
                ),
                "year": st.column_config.NumberColumn("Year", format="%d"),
            },
            use_container_width=True,
            hide_index=True,
        )


def _render_detail(filters: dict) -> None:
    detail = get_fm_detail(**filters)

    if not detail.empty:
        st.markdown(
            f"**{len(detail):,} rows** across "
            f"**{detail['entity'].nunique():,} entities**"
        )

        col_config = {
            "entity": st.column_config.TextColumn("Entity"),
            "metric_name": st.column_config.TextColumn("Metric"),
            "metric_value": st.column_config.NumberColumn("Value", format="%.2f"),
        }
        show_cols = ["entity", "metric_name", "metric_value"]

        if "year" in detail.columns and detail["year"].notna().any():
            show_cols.append("year")
            col_config["year"] = st.column_config.NumberColumn("Year", format="%d")
        if "score" in detail.columns and detail["score"].notna().any():
            show_cols.append("score")
            col_config["score"] = st.column_config.NumberColumn("Score", format="%.1f")
        if "rank" in detail.columns and detail["rank"].notna().any():
            show_cols.append("rank")
            col_config["rank"] = st.column_config.NumberColumn("Rank", format="%d")

        st.dataframe(
            detail[show_cols],
            column_config=col_config,
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        csv = detail.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="\u2b07 Download CSV",
            data=csv,
            file_name="flat_metric_detail.csv",
            mime="text/csv",
        )
        st.caption("Raw flat-metric data export.")
    else:
        _empty_state("No detail data for the current filters.")
