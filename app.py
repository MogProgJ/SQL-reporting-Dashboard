"""SQL Reporting Dashboard — Phase 3C: Multi-Profile Analytics."""

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

import dashboard_flat_metric
import dashboard_order
from db import DATABASE_URL, fetch_scalar
from importer import (
    generate_example_csv_zip,
    generate_example_excel,
    get_current_row_counts,
    get_flat_metric_row_counts,
    import_csv_bundle,
    import_excel_workbook,
    import_flat_metric_csv,
    import_flat_metric_excel,
)
from readers import EXPECTED_NAMES_SORTED

# ── Header ──────────────────────────────────────────────────────

st.markdown("## \U0001f4ca SQL Reporting Dashboard")
st.caption("Simple UI \u00b7 Serious SQL \u00b7 Built as a portfolio project")

if not DATABASE_URL:
    st.error(
        "**DATABASE_URL is not set.** Copy `.env.example` to `.env` and fill it in.  \n"
        "See the README quickstart for setup steps."
    )
    st.stop()

# Quick connectivity check
try:
    fetch_scalar("SELECT 1;")
except Exception as exc:
    st.error(
        "**Cannot connect to the database.**  \n"
        f"`{exc}`  \n\n"
        "Run `docker compose up -d` and seed the database \u2014 see the README."
    )
    st.stop()


# ── Helpers ─────────────────────────────────────────────────────

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

with st.sidebar:
    # ── Profile selector ────────────────────────────────────
    st.header("Analytics Profile")
    profile_choice = st.radio(
        "Profile",
        ["\U0001f6d2 Order Reporting", "\U0001f4cf Flat Metric"],
        index=0,
        label_visibility="collapsed",
    )
    is_order = profile_choice.startswith("\U0001f6d2")

    st.divider()

    # ── Data Source ──────────────────────────────────────────
    st.header("Data Source")

    if is_order:
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

        # Template / example downloads
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

    else:
        # Flat Metric data source
        fm_counts = get_flat_metric_row_counts()
        total_fm = sum(fm_counts.values())
        st.caption(f"**Current dataset:** {total_fm:,} rows")

        fm_source = st.radio(
            "Import data",
            ["Demo (seed)", "Upload CSV", "Upload Excel"],
            index=0,
            label_visibility="collapsed",
            key="fm_source",
        )

        _FM_COLS = "`entity`, `metric_name`, `metric_value` (required); `year`, `score`, `rank` (optional)"

        if fm_source == "Upload CSV":
            st.markdown(
                f"**Columns:** {_FM_COLS}",
                help="One CSV file with flat metric data.",
            )
            fm_csv = st.file_uploader(
                "Upload CSV file",
                type=["csv"],
                key="fm_csv_upload",
            )
            if fm_csv and st.button("Import CSV", use_container_width=True, key="fm_csv_btn"):
                with st.spinner("Importing flat metric CSV\u2026"):
                    result = import_flat_metric_csv(fm_csv, label=fm_csv.name)
                _show_import_result(result)

        elif fm_source == "Upload Excel":
            st.markdown(
                f"**Columns:** {_FM_COLS}",
                help="First sheet of the workbook will be read.",
            )
            fm_xls = st.file_uploader(
                "Upload .xlsx file",
                type=["xlsx"],
                key="fm_xls_upload",
            )
            if fm_xls and st.button("Import Excel", use_container_width=True, key="fm_xls_btn"):
                with st.spinner("Importing flat metric Excel\u2026"):
                    result = import_flat_metric_excel(fm_xls, label=fm_xls.name)
                _show_import_result(result)

        else:
            st.info("Using built-in demo dataset (seed.sql).")

        with st.expander("Table row counts"):
            for tbl, cnt in fm_counts.items():
                st.text(f"{tbl:15s} {cnt:>6,}")

    st.divider()

    # ── Filters ─────────────────────────────────────────────
    st.header("Filters")

    if is_order:
        filters, top_n = dashboard_order.render_filters()
    else:
        filters = dashboard_flat_metric.render_filters()

# ── Main content ────────────────────────────────────────────────

if is_order:
    dashboard_order.render(filters, top_n)
else:
    dashboard_flat_metric.render(filters)
