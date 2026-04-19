"""Order Reporting — Product Detail deep-dive page.

Shows revenue, customers, trends, and raw data for a single product.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import (
    add_rank, cents_to_dollars, fmt_number,
    col_rank, col_money, col_count, col_text, col_date, col_id,
)
from queries import (
    get_product_customers,
    get_product_orders,
    get_product_summary,
    get_product_trend,
    get_products,
)
from nav_state import get_target, render_back_button


# ── Public API ──────────────────────────────────────────────────


def render() -> None:
    """Render the product detail page."""
    render_back_button(is_order=True)

    products = get_products()
    if not products:
        st.warning("No product data available.")
        return

    target = get_target()
    default_idx = 0
    if target and target in products:
        default_idx = products.index(target)

    selected = st.selectbox(
        "Select product to inspect",
        products,
        index=default_idx,
        key="order_product_detail_select",
    )
    if not selected:
        return

    # ── Summary header ──────────────────────────────────────
    summary = get_product_summary(selected)
    if summary.empty:
        st.info(f"No data found for product **{selected}**.")
        return

    s = summary.iloc[0]
    st.markdown(f"## {selected}")
    st.caption(f"Category: {s['category']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", cents_to_dollars(s["revenue_cents"]))
    c2.metric("Units Sold", fmt_number(s["units_sold"]))
    c3.metric("Customers", fmt_number(s["customer_count"]))
    c4.metric("Orders", fmt_number(s["order_count"]))

    st.markdown("")

    # ── Tabs ────────────────────────────────────────────────
    tab_trend, tab_customers, tab_detail = st.tabs(
        ["📈 Trend", "👥 Top Customers", "📋 Orders & Export"]
    )

    with tab_trend:
        _render_trend(selected)

    with tab_customers:
        _render_customers(selected)

    with tab_detail:
        _render_detail(selected)


# ── Tab renderers ───────────────────────────────────────────────


def _render_trend(product: str) -> None:
    """Revenue and units sold over time."""
    trend = get_product_trend(product)
    if trend.empty:
        st.info("No trend data for this product.")
        return

    trend["revenue"] = trend["revenue_cents"] / 100
    trend["order_date"] = pd.to_datetime(trend["order_date"])

    st.subheader("Revenue Over Time")
    fig = px.area(
        trend,
        x="order_date",
        y="revenue",
        labels={"order_date": "Date", "revenue": "Revenue ($)"},
    )
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    st.subheader("Units Sold")
    fig_u = px.bar(
        trend,
        x="order_date",
        y="units_sold",
        labels={"order_date": "Date", "units_sold": "Units"},
    )
    fig_u.update_layout(
        height=250,
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_u, use_container_width=True, theme="streamlit")


def _render_customers(product: str) -> None:
    """Top customers who bought this product."""
    st.subheader("Top Customers")
    customers = get_product_customers(product, limit=15)
    if customers.empty:
        st.info("No customer data for this product.")
        return

    customers["revenue"] = customers["revenue_cents"] / 100
    tbl = add_rank(customers.copy())

    fig = px.bar(
        customers.sort_values("revenue"),
        x="revenue",
        y="customer",
        orientation="h",
        labels={"revenue": "Revenue ($)", "customer": ""},
        text="revenue",
    )
    fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(250, len(customers) * 35 + 60),
        margin=dict(l=0, r=80, t=10, b=0),
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    st.dataframe(
        tbl[["#", "customer", "segment", "city", "revenue", "units_bought"]],
        column_config={
            "#": col_rank(),
            "customer": col_text("Customer"),
            "segment": col_text("Segment"),
            "city": col_text("City"),
            "revenue": col_money(),
            "units_bought": col_count("Units"),
        },
        use_container_width=True,
        hide_index=True,
    )


def _render_detail(product: str) -> None:
    """Full order-item table for this product with export."""
    detail = get_product_orders(product)
    if detail.empty:
        st.info("No order data for this product.")
        return

    st.markdown(
        f"**{len(detail):,} line items** across "
        f"**{detail['order_id'].nunique():,} orders**"
    )

    dd = detail.copy()
    dd["unit_price"] = dd["unit_price_cents"] / 100
    dd["line_total"] = dd["line_total_cents"] / 100

    st.dataframe(
        dd[["order_id", "order_date", "status", "customer",
            "quantity", "unit_price", "line_total"]],
        column_config={
            "order_id": col_id(),
            "order_date": col_date(),
            "status": col_text("Status"),
            "customer": col_text("Customer"),
            "quantity": col_count("Qty"),
            "unit_price": col_money("Unit Price"),
            "line_total": col_money("Line Total"),
        },
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    csv = detail.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download CSV",
        data=csv,
        file_name=f"product_{product}.csv",
        mime="text/csv",
    )
    st.caption("Raw data — monetary values are in cents (integer).")
