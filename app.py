"""SQL Reporting Dashboard — Streamlit MVP."""

import streamlit as st

st.set_page_config(page_title="SQL Reporting Dashboard", layout="wide")

# ── Imports (after page config) ─────────────────────────────────
import pandas as pd

from db import DATABASE_URL
from queries import (
    get_categories,
    get_category_breakdown,
    get_customers,
    get_date_range,
    get_kpis,
    get_order_detail,
    get_products,
    get_revenue_trend,
    get_top_customers,
    get_top_products,
)

# ── Header ──────────────────────────────────────────────────────

st.title("SQL Reporting Dashboard")
st.caption("Simple UI. Serious SQL. Built as a portfolio project.")

if not DATABASE_URL:
    st.warning("DATABASE_URL is not set. Copy `.env.example` to `.env` and fill it in.")
    st.stop()


# ── Helpers ─────────────────────────────────────────────────────

def cents_to_dollars(c: int | float) -> str:
    return f"${c / 100:,.2f}"


# ── Sidebar filters ─────────────────────────────────────────────

try:
    min_date, max_date = get_date_range()
except Exception as exc:
    st.error(f"Cannot connect to the database. Is Postgres running?\n\n`{exc}`")
    st.stop()

st.sidebar.header("Filters")

date_from, date_to = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

sel_customers = st.sidebar.multiselect("Customers", get_customers())
sel_categories = st.sidebar.multiselect("Categories", get_categories())
sel_products = st.sidebar.multiselect("Products", get_products())

filters: dict = dict(
    date_from=date_from,
    date_to=date_to,
    customers=sel_customers or None,
    categories=sel_categories or None,
    products=sel_products or None,
)

# ── KPI row ─────────────────────────────────────────────────────

st.header("Key Metrics")
kpi = get_kpis(**filters)

if kpi.empty or int(kpi.iloc[0]["total_orders"]) == 0:
    st.info("No data matches the current filters.")
    st.stop()

k = kpi.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", cents_to_dollars(k["total_revenue_cents"]))
c2.metric("Total Orders", f"{int(k['total_orders']):,}")
c3.metric("Avg Order Value", cents_to_dollars(k["avg_order_value_cents"]))
c4.metric("Unique Customers", f"{int(k['unique_customers']):,}")

st.divider()

# ── Trend charts ────────────────────────────────────────────────

st.header("Trends")
trend = get_revenue_trend(**filters)

if not trend.empty:
    trend["revenue"] = trend["revenue_cents"] / 100
    trend["order_date"] = pd.to_datetime(trend["order_date"])

    tab_rev, tab_vol = st.tabs(["Revenue", "Order Volume"])

    with tab_rev:
        st.line_chart(trend, x="order_date", y="revenue", height=350)
    with tab_vol:
        st.bar_chart(trend, x="order_date", y="order_count", height=350)
else:
    st.info("No trend data for the selected filters.")

st.divider()

# ── Top lists ───────────────────────────────────────────────────

st.header("Top Lists")
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Top Customers by Revenue")
    top_cust = get_top_customers(limit=10, **filters)
    if not top_cust.empty:
        top_cust["revenue"] = top_cust["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            top_cust[["customer", "revenue", "order_count"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No customer data.")

with col_right:
    st.subheader("Top Products by Revenue")
    top_prod = get_top_products(limit=10, **filters)
    if not top_prod.empty:
        top_prod["revenue"] = top_prod["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            top_prod[["product", "revenue", "units_sold"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No product data.")

st.divider()

# ── Category breakdown ──────────────────────────────────────────

st.header("Category Breakdown")
cat_df = get_category_breakdown(**filters)

if not cat_df.empty:
    cat_df["revenue"] = cat_df["revenue_cents"] / 100
    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(cat_df, x="category", y="revenue", height=350)
    with col_table:
        display = cat_df.copy()
        display["revenue"] = display["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            display[["category", "revenue", "units_sold"]],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("No category data.")

st.divider()

# ── Detail table + CSV export ───────────────────────────────────

st.header("Order Detail")
detail = get_order_detail(**filters)

if not detail.empty:
    display_detail = detail.copy()
    display_detail["line_total"] = display_detail["line_total_cents"].apply(cents_to_dollars)
    display_detail["unit_price"] = display_detail["unit_price_cents"].apply(cents_to_dollars)
    show_cols = [
        "order_id", "order_date", "status", "customer", "segment", "city",
        "product", "category", "quantity", "unit_price", "line_total",
    ]
    st.dataframe(display_detail[show_cols], use_container_width=True, hide_index=True)

    # CSV export
    csv = detail.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="order_detail.csv",
        mime="text/csv",
    )
else:
    st.info("No orders match the current filters.")
