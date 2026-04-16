"""Order Reporting — Customer Detail deep-dive page.

Shows revenue, orders, product mix, trends, and raw data for a single customer.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from formatters import add_rank, cents_to_dollars, fmt_number
from queries import (
    get_customer_orders,
    get_customer_products,
    get_customer_summary,
    get_customer_trend,
    get_customers,
)
from nav_state import get_target, render_back_button


# ── Public API ──────────────────────────────────────────────────


def render() -> None:
    """Render the customer detail page."""
    render_back_button(is_order=True)

    customers = get_customers()
    if not customers:
        st.warning("No customer data available.")
        return

    target = get_target()
    default_idx = 0
    if target and target in customers:
        default_idx = customers.index(target)

    selected = st.selectbox(
        "Select customer to inspect",
        customers,
        index=default_idx,
        key="order_customer_detail_select",
    )
    if not selected:
        return

    # ── Summary header ──────────────────────────────────────
    summary = get_customer_summary(selected)
    if summary.empty:
        st.info(f"No data found for customer **{selected}**.")
        return

    s = summary.iloc[0]
    st.markdown(f"## {selected}")
    st.caption(f"{s['segment']} · {s['city']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", cents_to_dollars(s["revenue_cents"]))
    c2.metric("Orders", fmt_number(s["order_count"]))
    c3.metric("Avg Order", cents_to_dollars(s["avg_order_cents"]))
    if pd.notna(s["first_order"]) and pd.notna(s["last_order"]):
        c4.metric("Active", f"{s['first_order']} → {s['last_order']}")
    else:
        c4.metric("Active", "—")

    st.markdown("")

    # ── Tabs ────────────────────────────────────────────────
    tab_trend, tab_products, tab_detail = st.tabs(
        ["📈 Trend", "🛒 Product Mix", "📋 Orders & Export"]
    )

    with tab_trend:
        _render_trend(selected)

    with tab_products:
        _render_products(selected)

    with tab_detail:
        _render_detail(selected)


# ── Tab renderers ───────────────────────────────────────────────


def _render_trend(customer: str) -> None:
    """Revenue and order count over time for this customer."""
    trend = get_customer_trend(customer)
    if trend.empty:
        st.info("No trend data for this customer.")
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

    st.subheader("Order Volume")
    fig_vol = px.bar(
        trend,
        x="order_date",
        y="order_count",
        labels={"order_date": "Date", "order_count": "Orders"},
    )
    fig_vol.update_layout(
        height=250,
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_vol, use_container_width=True, theme="streamlit")


def _render_products(customer: str) -> None:
    """Top products purchased by this customer."""
    st.subheader("Top Products")
    products = get_customer_products(customer, limit=15)
    if products.empty:
        st.info("No product data for this customer.")
        return

    products["revenue"] = products["revenue_cents"] / 100
    tbl = add_rank(products.copy())

    fig = px.bar(
        products.sort_values("revenue"),
        x="revenue",
        y="product",
        orientation="h",
        labels={"revenue": "Revenue ($)", "product": ""},
        text="revenue",
    )
    fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(250, len(products) * 35 + 60),
        margin=dict(l=0, r=80, t=10, b=0),
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    st.dataframe(
        tbl[["#", "product", "category", "revenue", "units_bought"]],
        column_config={
            "#": st.column_config.NumberColumn("#", width="small"),
            "product": st.column_config.TextColumn("Product"),
            "category": st.column_config.TextColumn("Category"),
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "units_bought": st.column_config.NumberColumn("Units", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )


def _render_detail(customer: str) -> None:
    """Full order-item table for this customer with export."""
    detail = get_customer_orders(customer)
    if detail.empty:
        st.info("No order data for this customer.")
        return

    st.markdown(
        f"**{len(detail):,} line items** across "
        f"**{detail['order_id'].nunique():,} orders**"
    )

    dd = detail.copy()
    dd["unit_price"] = dd["unit_price_cents"] / 100
    dd["line_total"] = dd["line_total_cents"] / 100
    dd["order_total"] = dd["order_total_cents"] / 100

    st.dataframe(
        dd[["order_id", "order_date", "status", "product", "category",
            "quantity", "unit_price", "line_total", "order_total"]],
        column_config={
            "order_id": st.column_config.NumberColumn("Order #", format="%d"),
            "order_date": st.column_config.DateColumn("Date"),
            "status": st.column_config.TextColumn("Status"),
            "product": st.column_config.TextColumn("Product"),
            "category": st.column_config.TextColumn("Category"),
            "quantity": st.column_config.NumberColumn("Qty", format="%d"),
            "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
            "line_total": st.column_config.NumberColumn("Line Total", format="$%.2f"),
            "order_total": st.column_config.NumberColumn("Order Total", format="$%.2f"),
        },
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    csv = detail.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download CSV",
        data=csv,
        file_name=f"customer_{customer}.csv",
        mime="text/csv",
    )
    st.caption("Raw data — monetary values are in cents (integer).")
