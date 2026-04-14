"""SQL Reporting Dashboard - Phase 3B: Data Flexibility."""

import streamlit as st

st.set_page_config(
    page_title="SQL Reporting Dashboard",
    page_icon="\U0001f4ca",
    layout="wide",
)

# ── CSS injection ───────────────────────────────────────────────

_CSS = """<style>
/* KPI metric cards */
[data-testid="stMetric"] {
    background: rgba(28, 131, 225, 0.08);
    border: 1px solid rgba(28, 131, 225, 0.15);
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricLabel"] {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
/* Download button */
[data-testid="stDownloadButton"] > button {
    border: 1px solid rgba(28, 131, 225, 0.4);
}
</style>"""

st.markdown(_CSS, unsafe_allow_html=True)

# ── Imports (after page config + CSS) ───────────────────────────

import pandas as pd
import plotly.express as px

from db import DATABASE_URL
from formatters import add_rank, cents_to_dollars, fmt_number
from importer import (
    generate_example_csv_zip,
    generate_example_excel,
    get_current_row_counts,
    get_demo_profile,
    import_csv_bundle,
    import_excel_workbook,
)
from readers import EXPECTED_NAMES_SORTED
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

st.markdown("## \U0001f4ca SQL Reporting Dashboard")
st.caption("Simple UI \u00b7 Serious SQL \u00b7 Built as a portfolio project")

if not DATABASE_URL:
    st.error(
        "**DATABASE_URL is not set.** Copy `.env.example` to `.env` and fill it in.  \n"
        "See the README quickstart for setup steps."
    )
    st.stop()


# ── Helpers ─────────────────────────────────────────────────────

def _empty_state(message: str = "No data matches the current filters.") -> None:
    st.warning(
        f"**{message}**  \n"
        "Try broadening the date range, removing customer/category/product "
        "filters, or including more statuses."
    )


def _show_import_result(result) -> None:
    """Display an import result cleanly in the sidebar."""
    if result.success:
        total = sum(result.row_counts.values())
        summary_lines = "  \n".join(
            f"  \u2022 {name}: {cnt:,} rows"
            for name, cnt in result.row_counts.items()
            if cnt
        )
        st.success(
            f"**Imported {total:,} rows successfully.**  \n{summary_lines}"
        )
        if result.warnings:
            with st.expander(f"\u26a0\ufe0f {len(result.warnings)} warning(s)"):
                for w in result.warnings:
                    st.caption(f"{w.entity}.{w.column}: {w.message}")
        st.rerun()
    else:
        st.error(
            f"**Import failed** ({len(result.errors)} error(s)).  \n"
            "Review the issues below and fix your data."
        )
        for iss in result.errors:
            label = iss.entity or "general"
            # Show multi-line messages with preformatted detail
            if "\n" in iss.message:
                lines = iss.message.split("\n", 1)
                st.warning(f"**{label}:** {lines[0]}")
                st.caption(lines[1])
            else:
                st.warning(f"**{label}:** {iss.message}")
        if result.warnings:
            with st.expander(f"{len(result.warnings)} warning(s)"):
                for w in result.warnings:
                    st.caption(f"{w.entity}.{w.column}: {w.message}")


# ── Sidebar ─────────────────────────────────────────────────────

try:
    min_date, max_date = get_date_range()
except Exception as exc:
    st.error(
        "**Cannot connect to the database.**  \n"
        f"`{exc}`  \n\n"
        "Run `docker compose up -d` and seed the database \u2014 see the README."
    )
    st.stop()


def _clear_filters():
    for key in ("sel_statuses", "sel_customers", "sel_categories", "sel_products"):
        st.session_state[key] = []


with st.sidebar:
    # ── Data Source ──────────────────────────────────────────
    st.header("Data Source")

    row_counts = get_current_row_counts()
    total_rows = sum(row_counts.values())
    st.caption(
        f"**Current dataset:** {total_rows:,} rows across "
        f"{len([v for v in row_counts.values() if v]):,} tables"
    )

    source_choice = st.radio(
        "Import data",
        ["Demo (seed)", "Upload CSV bundle", "Upload Excel workbook"],
        index=0,
        label_visibility="collapsed",
    )

    _ENTITY_LIST = ", ".join(f"`{n}`" for n in EXPECTED_NAMES_SORTED)

    if source_choice == "Upload CSV bundle":
        st.markdown(
            f"**Required CSV files:** {_ENTITY_LIST}  \n"
            "One file per entity, column headers in the first row.",
            help="File names must match the entity names (e.g. customers.csv).",
        )
        csv_files = st.file_uploader(
            "Upload CSV files",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_upload",
        )
        if csv_files and st.button("Import CSVs", use_container_width=True):
            file_map = {f.name: f for f in csv_files}
            with st.spinner("Importing CSV bundle\u2026"):
                result = import_csv_bundle(file_map, label="CSV upload")
            _show_import_result(result)

    elif source_choice == "Upload Excel workbook":
        st.markdown(
            f"**Required sheets:** {_ENTITY_LIST}  \n"
            "One sheet per entity, column headers in the first row.",
            help="Sheet names are matched case-insensitively.",
        )
        xls_file = st.file_uploader(
            "Upload .xlsx workbook",
            type=["xlsx"],
            key="xls_upload",
        )
        if xls_file and st.button("Import Excel", use_container_width=True):
            with st.spinner("Importing Excel workbook\u2026"):
                result = import_excel_workbook(xls_file, label=xls_file.name)
            _show_import_result(result)

    else:
        st.info("Using built-in demo dataset (seed.sql).")

    with st.expander("Table row counts"):
        for tbl, cnt in row_counts.items():
            st.text(f"{tbl:15s} {cnt:>6,}")

    # ── Template / example downloads ────────────────────────
    with st.expander("\u2b07 Download example templates"):
        st.caption(
            "These contain sample data that the import pipeline accepts. "
            "Replace the rows with your own data, keeping the structure."
        )
        st.download_button(
            label="CSV bundle (.zip)",
            data=generate_example_csv_zip(),
            file_name="reporting_template_csv.zip",
            mime="application/zip",
        )
        try:
            xls_bytes = generate_example_excel()
            st.download_button(
                label="Excel workbook (.xlsx)",
                data=xls_bytes,
                file_name="reporting_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            st.caption(
                "Excel template unavailable (openpyxl not installed). "
                "Use the CSV template instead."
            )

    st.divider()
    st.header("Filters")

    date_from, date_to = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    st.divider()

    sel_statuses = st.multiselect(
        "Status", get_statuses(), key="sel_statuses", placeholder="All statuses"
    )
    sel_customers = st.multiselect(
        "Customer", get_customers(), key="sel_customers", placeholder="All customers"
    )
    sel_categories = st.multiselect(
        "Category", get_categories(), key="sel_categories", placeholder="All categories"
    )
    sel_products = st.multiselect(
        "Product", get_products(), key="sel_products", placeholder="All products"
    )

    st.divider()

    top_n = st.slider("Top-N list size", min_value=5, max_value=25, value=10, step=5)

    st.divider()

    st.button("Clear all filters", on_click=_clear_filters, use_container_width=True)


filters: dict = dict(
    date_from=date_from,
    date_to=date_to,
    customers=sel_customers or None,
    categories=sel_categories or None,
    products=sel_products or None,
    statuses=sel_statuses or None,
)

# ── Active-filter summary ───────────────────────────────────────

active_parts: list[str] = []
active_parts.append(f"\U0001f4c5 {date_from} \u2192 {date_to}")
if sel_statuses:
    active_parts.append(f"Status: {', '.join(sel_statuses)}")
if sel_customers:
    active_parts.append(f"Customers: {', '.join(sel_customers)}")
if sel_categories:
    active_parts.append(f"Categories: {', '.join(sel_categories)}")
if sel_products:
    active_parts.append(f"Products: {', '.join(sel_products)}")

with st.container(border=True):
    st.caption("**Active slice:** " + " \u00b7 ".join(active_parts))

# ── KPI row (always visible) ───────────────────────────────────

kpi = get_kpis(**filters)

if kpi.empty or int(kpi.iloc[0]["total_orders"]) == 0:
    _empty_state()
    st.stop()

k = kpi.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", cents_to_dollars(k["total_revenue_cents"]))
c2.metric("Total Orders", fmt_number(k["total_orders"]))
c3.metric("Avg Order Value", cents_to_dollars(k["avg_order_value_cents"]))
c4.metric("Unique Customers", fmt_number(k["unique_customers"]))

st.markdown("")  # spacing

# ── Load shared data (used across tabs) ─────────────────────────

trend = get_revenue_trend(**filters)
if not trend.empty:
    trend["revenue"] = trend["revenue_cents"] / 100
    trend["order_date"] = pd.to_datetime(trend["order_date"])

# ── Main content tabs ───────────────────────────────────────────

tab_overview, tab_breakdown, tab_outliers, tab_detail = st.tabs(
    ["\U0001f4c8 Overview", "\U0001f4ca Breakdown", "\u26a0\ufe0f Outliers", "\U0001f4cb Detail & Export"]
)

# ── TAB: Overview ───────────────────────────────────────────────

with tab_overview:
    if not trend.empty:
        st.subheader("Revenue Trend")
        fig_rev = px.area(
            trend,
            x="order_date",
            y="revenue",
            labels={"order_date": "Date", "revenue": "Revenue ($)"},
        )
        fig_rev.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title=None,
            yaxis_title="Revenue ($)",
            hovermode="x unified",
        )
        st.plotly_chart(fig_rev, use_container_width=True, theme="streamlit")
        st.caption("Daily revenue for the selected date range and filters.")

        st.subheader("Order Volume")
        fig_vol = px.bar(
            trend,
            x="order_date",
            y="order_count",
            labels={"order_date": "Date", "order_count": "Orders"},
        )
        fig_vol.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title=None,
            yaxis_title="Order Count",
            hovermode="x unified",
        )
        st.plotly_chart(fig_vol, use_container_width=True, theme="streamlit")
        st.caption("Number of distinct orders per day.")
    else:
        _empty_state("No trend data for the selected filters.")

    st.divider()

    # Top lists
    st.subheader("Top Lists")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"**Top {top_n} Customers by Revenue**")
        top_cust = get_top_customers(limit=top_n, **filters)
        if not top_cust.empty:
            tc = add_rank(top_cust)
            tc["revenue"] = tc["revenue_cents"] / 100
            st.dataframe(
                tc[["#", "customer", "revenue", "order_count"]],
                column_config={
                    "#": st.column_config.NumberColumn("#", width="small"),
                    "customer": st.column_config.TextColumn("Customer"),
                    "revenue": st.column_config.NumberColumn(
                        "Revenue", format="$%.2f"
                    ),
                    "order_count": st.column_config.NumberColumn(
                        "Orders", format="%d"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            _empty_state("No customer data.")

    with col_right:
        st.markdown(f"**Top {top_n} Products by Revenue**")
        top_prod = get_top_products(limit=top_n, **filters)
        if not top_prod.empty:
            tp = add_rank(top_prod)
            tp["revenue"] = tp["revenue_cents"] / 100
            st.dataframe(
                tp[["#", "product", "revenue", "units_sold"]],
                column_config={
                    "#": st.column_config.NumberColumn("#", width="small"),
                    "product": st.column_config.TextColumn("Product"),
                    "revenue": st.column_config.NumberColumn(
                        "Revenue", format="$%.2f"
                    ),
                    "units_sold": st.column_config.NumberColumn(
                        "Units Sold", format="%d"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            _empty_state("No product data.")

# ── TAB: Breakdown ──────────────────────────────────────────────

with tab_breakdown:
    # Category breakdown
    st.subheader("Category Breakdown")
    cat_df = get_category_breakdown(**filters)

    if not cat_df.empty:
        total_rev = cat_df["revenue_cents"].sum()
        cat_df["revenue"] = cat_df["revenue_cents"] / 100
        cat_df["pct"] = (
            (cat_df["revenue_cents"] / total_rev * 100).round(1) if total_rev else 0
        )

        col_chart, col_table = st.columns([3, 2])

        with col_chart:
            fig_cat = px.bar(
                cat_df.sort_values("revenue"),
                x="revenue",
                y="category",
                orientation="h",
                labels={"revenue": "Revenue ($)", "category": ""},
                text="revenue",
            )
            fig_cat.update_traces(
                texttemplate="$%{x:,.0f}", textposition="outside"
            )
            fig_cat.update_layout(
                height=max(250, len(cat_df) * 45 + 60),
                margin=dict(l=0, r=80, t=10, b=0),
                yaxis_title=None,
                xaxis_title="Revenue ($)",
            )
            st.plotly_chart(fig_cat, use_container_width=True, theme="streamlit")

        with col_table:
            st.dataframe(
                cat_df[["category", "revenue", "pct", "units_sold"]],
                column_config={
                    "category": st.column_config.TextColumn("Category"),
                    "revenue": st.column_config.NumberColumn(
                        "Revenue", format="$%.2f"
                    ),
                    "pct": st.column_config.NumberColumn(
                        "% Share", format="%.1f%%"
                    ),
                    "units_sold": st.column_config.NumberColumn(
                        "Units", format="%d"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

        st.caption("Revenue and unit share by product category.")
    else:
        _empty_state("No category data.")

    st.divider()

    # Product revenue share
    st.subheader(f"Product Revenue Share (Top {top_n})")
    prod_share = get_product_share(limit=top_n, **filters)

    if not prod_share.empty:
        col_donut, col_tbl = st.columns([2, 3])

        with col_donut:
            ps_chart = prod_share.copy()
            ps_chart["revenue"] = ps_chart["revenue_cents"] / 100
            fig_donut = px.pie(
                ps_chart,
                values="revenue",
                names="product",
                hole=0.45,
            )
            fig_donut.update_traces(textinfo="percent", textposition="outside")
            fig_donut.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(
                fig_donut, use_container_width=True, theme="streamlit"
            )

        with col_tbl:
            ps_tbl = add_rank(prod_share.copy())
            ps_tbl["revenue"] = ps_tbl["revenue_cents"] / 100
            st.dataframe(
                ps_tbl[["#", "product", "revenue", "pct_of_total", "units_sold"]],
                column_config={
                    "#": st.column_config.NumberColumn("#", width="small"),
                    "product": st.column_config.TextColumn("Product"),
                    "revenue": st.column_config.NumberColumn(
                        "Revenue", format="$%.2f"
                    ),
                    "pct_of_total": st.column_config.NumberColumn(
                        "% Share", format="%.1f%%"
                    ),
                    "units_sold": st.column_config.NumberColumn(
                        "Units", format="%d"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

        st.caption("Each product's share of total filtered revenue.")
    else:
        _empty_state("No product share data.")

    st.divider()

    # Customer drilldown
    st.subheader(f"Customer Drilldown (Top {top_n})")
    cust_drill = get_customer_drilldown(limit=top_n, **filters)

    if not cust_drill.empty:
        cd = add_rank(cust_drill.copy())
        cd["revenue"] = cd["revenue_cents"] / 100
        cd["avg_order"] = cd["avg_order_cents"] / 100
        st.dataframe(
            cd[
                [
                    "#",
                    "customer",
                    "segment",
                    "city",
                    "revenue",
                    "order_count",
                    "avg_order",
                ]
            ],
            column_config={
                "#": st.column_config.NumberColumn("#", width="small"),
                "customer": st.column_config.TextColumn("Customer"),
                "segment": st.column_config.TextColumn("Segment"),
                "city": st.column_config.TextColumn("City"),
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="$%.2f"
                ),
                "order_count": st.column_config.NumberColumn(
                    "Orders", format="%d"
                ),
                "avg_order": st.column_config.NumberColumn(
                    "Avg Order", format="$%.2f"
                ),
            },
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Revenue, order frequency, and average order value per customer."
        )
    else:
        _empty_state("No customer drilldown data.")

# ── TAB: Outliers ───────────────────────────────────────────────

with tab_outliers:
    st.markdown(
        "> Flagged using the **IQR rule** \u2014 values above Q\u2083 + 1.5 \u00d7 IQR. "
        "A transparent statistical threshold, not a black-box model."
    )

    tab_lg_orders, tab_hi_days = st.tabs(["Large Orders", "High-Revenue Days"])

    with tab_lg_orders:
        order_totals = get_order_totals(**filters)
        outlier_orders = find_outlier_orders(order_totals)
        if not outlier_orders.empty:
            oo = outlier_orders.copy()
            oo["order_total"] = oo["order_total_cents"] / 100
            st.dataframe(
                oo[["order_id", "order_date", "customer", "order_total"]],
                column_config={
                    "order_id": st.column_config.NumberColumn(
                        "Order #", format="%d"
                    ),
                    "order_date": st.column_config.DateColumn("Date"),
                    "customer": st.column_config.TextColumn("Customer"),
                    "order_total": st.column_config.NumberColumn(
                        "Total", format="$%.2f"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"{len(outlier_orders)} order(s) flagged out of "
                f"{len(order_totals)} total."
            )
        else:
            st.info("No unusually large orders detected in this slice.")

    with tab_hi_days:
        if not trend.empty:
            outlier_days = find_outlier_days(trend)
            if not outlier_days.empty:
                od = outlier_days.copy()
                od["revenue_display"] = od["revenue_cents"] / 100
                od["order_date"] = pd.to_datetime(od["order_date"]).dt.date
                st.dataframe(
                    od[["order_date", "revenue_display", "order_count"]],
                    column_config={
                        "order_date": st.column_config.DateColumn("Date"),
                        "revenue_display": st.column_config.NumberColumn(
                            "Revenue", format="$%.2f"
                        ),
                        "order_count": st.column_config.NumberColumn(
                            "Orders", format="%d"
                        ),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    f"{len(outlier_days)} day(s) flagged out of "
                    f"{len(trend)} total."
                )
            else:
                st.info(
                    "No unusually high-revenue days detected in this slice."
                )
        else:
            st.info("No trend data available for outlier detection.")

# ── TAB: Detail & Export ────────────────────────────────────────

with tab_detail:
    detail = get_order_detail(**filters)

    if not detail.empty:
        st.markdown(
            f"**{len(detail):,} line items** across "
            f"**{detail['order_id'].nunique():,} orders**"
        )

        dd = detail.copy()
        dd["unit_price"] = dd["unit_price_cents"] / 100
        dd["line_total"] = dd["line_total_cents"] / 100
        dd["order_total"] = dd["order_total_cents"] / 100

        show_cols = [
            "order_id",
            "order_date",
            "status",
            "customer",
            "product",
            "category",
            "quantity",
            "unit_price",
            "line_total",
            "order_total",
        ]

        st.dataframe(
            dd[show_cols],
            column_config={
                "order_id": st.column_config.NumberColumn(
                    "Order #", format="%d"
                ),
                "order_date": st.column_config.DateColumn("Date"),
                "status": st.column_config.TextColumn("Status"),
                "customer": st.column_config.TextColumn("Customer"),
                "product": st.column_config.TextColumn("Product"),
                "category": st.column_config.TextColumn("Category"),
                "quantity": st.column_config.NumberColumn("Qty", format="%d"),
                "unit_price": st.column_config.NumberColumn(
                    "Unit Price", format="$%.2f"
                ),
                "line_total": st.column_config.NumberColumn(
                    "Line Total", format="$%.2f"
                ),
                "order_total": st.column_config.NumberColumn(
                    "Order Total", format="$%.2f"
                ),
            },
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        csv = detail.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="\u2b07 Download CSV",
            data=csv,
            file_name="order_detail.csv",
            mime="text/csv",
        )
        st.caption(
            "CSV contains raw data (cents, not formatted dollars) for "
            "downstream analysis."
        )
    else:
        _empty_state("No orders match the current filters.")
