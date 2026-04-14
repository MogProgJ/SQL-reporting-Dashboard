"""SQL Reporting Dashboard — Decision Support MVP."""

import streamlit as st

st.set_page_config(page_title="SQL Reporting Dashboard", layout="wide")

# ── Imports (after page config) ─────────────────────────────────
import pandas as pd

from db import DATABASE_URL
from queries import (
    find_outlier_days,
    find_outlier_orders,
    get_categories,
    get_category_breakdown,
    get_customer_drilldown,
    get_customers,
    get_date_range,
    get_kpis,
    get_order_detail,
    get_order_totals,
    get_product_share,
    get_products,
    get_revenue_trend,
    get_statuses,
    get_top_customers,
    get_top_products,
)

# ── Header ──────────────────────────────────────────────────────

st.title("SQL Reporting Dashboard")
st.caption("Simple UI. Serious SQL. Built as a portfolio project.")

if not DATABASE_URL:
    st.warning(
        "**DATABASE_URL is not set.** Copy `.env.example` to `.env` and fill it in.  \n"
        "See the [README](https://github.com/) quickstart for setup steps."
    )
    st.stop()


# ── Helpers ─────────────────────────────────────────────────────

def cents_to_dollars(c: int | float) -> str:
    return f"${c / 100:,.2f}"


def _empty_state(message: str = "No data matches the current filters.") -> None:
    st.info(
        f"{message}  \n"
        "**Try:** broaden the date range, clear customer/category/product filters, "
        "or include more statuses."
    )


# ── Sidebar filters ─────────────────────────────────────────────

try:
    min_date, max_date = get_date_range()
except Exception as exc:
    st.error(
        "**Cannot connect to the database.** Is Postgres running?  \n"
        f"`{exc}`  \n\n"
        "Run `docker compose up -d` and seed the database — see the README."
    )
    st.stop()

st.sidebar.header("Filters")

date_from, date_to = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

sel_statuses = st.sidebar.multiselect("Order status", get_statuses())
sel_customers = st.sidebar.multiselect("Customers", get_customers())
sel_categories = st.sidebar.multiselect("Categories", get_categories())
sel_products = st.sidebar.multiselect("Products", get_products())

st.sidebar.divider()
top_n = st.sidebar.slider("Top-N list size", min_value=5, max_value=25, value=10, step=5)

filters: dict = dict(
    date_from=date_from,
    date_to=date_to,
    customers=sel_customers or None,
    categories=sel_categories or None,
    products=sel_products or None,
    statuses=sel_statuses or None,
)

# ── Active-filter summary ───────────────────────────────────────

active: list[str] = []
active.append(f"**Dates:** {date_from} → {date_to}")
if sel_statuses:
    active.append(f"**Status:** {', '.join(sel_statuses)}")
if sel_customers:
    active.append(f"**Customers:** {', '.join(sel_customers)}")
if sel_categories:
    active.append(f"**Categories:** {', '.join(sel_categories)}")
if sel_products:
    active.append(f"**Products:** {', '.join(sel_products)}")

st.caption("Current slice: " + " · ".join(active))

# ── KPI row ─────────────────────────────────────────────────────

st.header("Key Metrics")
kpi = get_kpis(**filters)

if kpi.empty or int(kpi.iloc[0]["total_orders"]) == 0:
    _empty_state()
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
    _empty_state("No trend data for the selected filters.")

st.divider()

# ── Top lists ───────────────────────────────────────────────────

st.header("Top Lists")
col_left, col_right = st.columns(2)

with col_left:
    st.subheader(f"Top {top_n} Customers by Revenue")
    top_cust = get_top_customers(limit=top_n, **filters)
    if not top_cust.empty:
        top_cust["revenue"] = top_cust["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            top_cust[["customer", "revenue", "order_count"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        _empty_state("No customer data.")

with col_right:
    st.subheader(f"Top {top_n} Products by Revenue")
    top_prod = get_top_products(limit=top_n, **filters)
    if not top_prod.empty:
        top_prod["revenue"] = top_prod["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            top_prod[["product", "revenue", "units_sold"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        _empty_state("No product data.")

st.divider()

# ── Category breakdown (with share) ─────────────────────────────

st.header("Category Breakdown")
cat_df = get_category_breakdown(**filters)

if not cat_df.empty:
    total_rev = cat_df["revenue_cents"].sum()
    cat_df["revenue"] = cat_df["revenue_cents"] / 100
    cat_df["% of total"] = (cat_df["revenue_cents"] / total_rev * 100).round(1) if total_rev else 0

    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(cat_df, x="category", y="revenue", height=350)
    with col_table:
        display = cat_df.copy()
        display["revenue"] = display["revenue_cents"].apply(cents_to_dollars)
        st.dataframe(
            display[["category", "revenue", "% of total", "units_sold"]],
            use_container_width=True,
            hide_index=True,
        )
else:
    _empty_state("No category data.")

st.divider()

# ── Product share of revenue ────────────────────────────────────

st.header("Product Revenue Share")
prod_share = get_product_share(limit=top_n, **filters)

if not prod_share.empty:
    display_ps = prod_share.copy()
    display_ps["revenue"] = display_ps["revenue_cents"].apply(cents_to_dollars)
    display_ps.rename(columns={"pct_of_total": "% of total"}, inplace=True)
    st.dataframe(
        display_ps[["product", "revenue", "% of total", "units_sold"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    _empty_state("No product share data.")

st.divider()

# ── Customer drilldown ──────────────────────────────────────────

st.header("Customer Drilldown")
cust_drill = get_customer_drilldown(limit=top_n, **filters)

if not cust_drill.empty:
    display_cd = cust_drill.copy()
    display_cd["revenue"] = display_cd["revenue_cents"].apply(cents_to_dollars)
    display_cd["avg order"] = display_cd["avg_order_cents"].apply(cents_to_dollars)
    st.dataframe(
        display_cd[["customer", "segment", "city", "revenue", "order_count", "avg order"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    _empty_state("No customer drilldown data.")

st.divider()

# ── Anomaly / Outlier surfacing ─────────────────────────────────

st.header("Outliers")
st.caption(
    "Flagged using the **IQR rule** (values above Q3 + 1.5 × IQR). "
    "This is a transparent statistical threshold, not a black-box model."
)

tab_orders, tab_days = st.tabs(["Unusually Large Orders", "High-Revenue Days"])

with tab_orders:
    order_totals = get_order_totals(**filters)
    outlier_orders = find_outlier_orders(order_totals)
    if not outlier_orders.empty:
        display_oo = outlier_orders.copy()
        display_oo["order_total"] = display_oo["order_total_cents"].apply(cents_to_dollars)
        st.dataframe(
            display_oo[["order_id", "order_date", "customer", "order_total"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(outlier_orders)} order(s) flagged out of {len(order_totals)} total.")
    else:
        st.info("No unusually large orders detected in the current filter range.")

with tab_days:
    if not trend.empty:
        outlier_days = find_outlier_days(trend)
        if not outlier_days.empty:
            display_od = outlier_days.copy()
            display_od["revenue"] = display_od["revenue_cents"].apply(cents_to_dollars)
            display_od["order_date"] = pd.to_datetime(display_od["order_date"]).dt.date
            st.dataframe(
                display_od[["order_date", "revenue", "order_count"]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"{len(outlier_days)} day(s) flagged out of {len(trend)} total.")
        else:
            st.info("No unusually high-revenue days detected in the current filter range.")
    else:
        st.info("No trend data available for outlier detection.")

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

    csv = detail.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="order_detail.csv",
        mime="text/csv",
    )
else:
    _empty_state("No orders match the current filters.")
