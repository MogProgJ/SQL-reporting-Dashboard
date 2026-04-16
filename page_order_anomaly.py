"""Order Reporting — Anomaly Explorer deep-dive page.

Surfaces large orders and high-revenue days using transparent IQR rules.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import add_rank, cents_to_dollars, fmt_number
from queries import (
    find_outlier_days,
    find_outlier_orders,
    get_order_detail,
    get_revenue_trend,
    get_order_totals,
)
from nav_state import render_back_button


# ── Public API ──────────────────────────────────────────────────


def render(filters: dict) -> None:
    """Render the anomaly explorer page.

    Parameters
    ----------
    filters : dict
        The same filter dict used elsewhere (date_from, date_to, etc.).
    """
    render_back_button(is_order=True)

    st.markdown("## Anomaly Explorer")
    st.markdown(
        "> All anomaly flags use the **IQR rule** — values outside "
        "Q₁ − 1.5 × IQR or Q₃ + 1.5 × IQR. "
        "A simple, transparent statistical threshold."
    )

    tab_orders, tab_days, tab_raw = st.tabs(
        ["💰 Large Orders", "📆 High-Revenue Days", "📋 Detail & Export"]
    )

    with tab_orders:
        _render_outlier_orders(filters)

    with tab_days:
        _render_outlier_days(filters)

    with tab_raw:
        _render_raw(filters)


# ── Tab renderers ───────────────────────────────────────────────


def _render_outlier_orders(filters: dict) -> None:
    """Orders with unusually high totals."""
    st.subheader("Orders Above IQR Threshold")
    totals = get_order_totals(**filters)
    outliers = find_outlier_orders(totals)

    if outliers.empty:
        st.info("No outlier orders detected with current filters.")
        return

    outliers["revenue"] = outliers["revenue_cents"] / 100
    tbl = add_rank(outliers.sort_values("revenue", ascending=False).copy())

    st.markdown(f"**{len(outliers):,} outlier order(s)** out of {len(totals):,} total")

    # Chart top 15
    top = outliers.nlargest(15, "revenue")
    top["order_label"] = "Order #" + top["order_id"].astype(str)

    fig = px.bar(
        top.sort_values("revenue"),
        x="revenue",
        y="order_label",
        orientation="h",
        labels={"revenue": "Revenue ($)", "order_label": ""},
        text="revenue",
    )
    fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(250, len(top) * 35 + 60),
        margin=dict(l=0, r=80, t=10, b=0),
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # Full table
    show_cols = ["#", "order_id", "revenue"]
    col_cfg = {
        "#": st.column_config.NumberColumn("#", width="small"),
        "order_id": st.column_config.NumberColumn("Order #", format="%d"),
        "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
    }
    if "customer" in tbl.columns:
        show_cols.insert(2, "customer")
        col_cfg["customer"] = st.column_config.TextColumn("Customer")
    if "order_date" in tbl.columns:
        show_cols.insert(2, "order_date")
        col_cfg["order_date"] = st.column_config.DateColumn("Date")

    st.dataframe(
        tbl[show_cols].head(50),
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
    )

    # IQR threshold info
    if not totals.empty:
        q1 = totals["revenue_cents"].quantile(0.25) / 100
        q3 = totals["revenue_cents"].quantile(0.75) / 100
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr
        st.caption(
            f"Q₁ = ${q1:,.0f} · Q₃ = ${q3:,.0f} · "
            f"IQR = ${iqr:,.0f} · Threshold = ${threshold:,.0f}"
        )


def _render_outlier_days(filters: dict) -> None:
    """Days with unusually high revenue."""
    st.subheader("High-Revenue Days")
    daily = get_revenue_trend(**filters)
    outliers = find_outlier_days(daily)

    if outliers.empty:
        st.info("No outlier days detected with current filters.")
        return

    outliers["revenue"] = outliers["revenue_cents"] / 100
    outliers["order_date"] = pd.to_datetime(outliers["order_date"])

    st.markdown(f"**{len(outliers):,} outlier day(s)** out of {len(daily):,} total days")

    fig = px.bar(
        outliers.sort_values("order_date"),
        x="order_date",
        y="revenue",
        labels={"order_date": "Date", "revenue": "Revenue ($)"},
        text="revenue",
    )
    fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
    fig.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    st.dataframe(
        outliers[["order_date", "revenue"]].sort_values("order_date"),
        column_config={
            "order_date": st.column_config.DateColumn("Date"),
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
        },
        use_container_width=True,
        hide_index=True,
    )

    # IQR info
    if not daily.empty:
        q1 = daily["revenue_cents"].quantile(0.25) / 100
        q3 = daily["revenue_cents"].quantile(0.75) / 100
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr
        st.caption(
            f"Q₁ = ${q1:,.0f} · Q₃ = ${q3:,.0f} · "
            f"IQR = ${iqr:,.0f} · Threshold = ${threshold:,.0f}"
        )


def _render_raw(filters: dict) -> None:
    """Full detail table with export for inspection."""
    detail = get_order_detail(**filters)
    if detail.empty:
        st.info("No order data with current filters.")
        return

    st.markdown(f"**{len(detail):,} line items** (all orders within filters)")

    dd = detail.copy()
    for c in ("unit_price_cents", "line_total_cents"):
        if c in dd.columns:
            dd[c.replace("_cents", "")] = dd[c] / 100

    show_cols = [c for c in ["order_id", "order_date", "customer", "product",
                              "quantity", "unit_price", "line_total"] if c in dd.columns]

    st.dataframe(
        dd[show_cols].head(500),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    csv = detail.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download CSV",
        data=csv,
        file_name="anomaly_orders.csv",
        mime="text/csv",
    )
    st.caption("Raw data — monetary values are in cents (integer).")
