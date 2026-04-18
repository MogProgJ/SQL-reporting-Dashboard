"""SQL Reporting Dashboard — Phase 3C Closeout: Multi-Profile Hardening."""

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
    import_adapted_frames,
    import_csv_bundle,
    import_excel_workbook,
    import_flat_metric_csv,
    import_flat_metric_excel,
)
from nav_state import (
    FlatMetricPage,
    OrderPage,
    get_page,
    render_nav,
)
import page_fm_entity
import page_fm_metric
import page_order_anomaly
import page_order_customer
import page_order_product
from profile_state import (
    ReadinessStatus,
    check_flat_metric_readiness,
    check_order_readiness,
)
from readers import EXPECTED_NAMES_SORTED
from saved_views import (
    apply_view,
    capture_current_state,
    delete_view,
    list_views,
    save_view,
)
import demo_presets

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


def _render_smart_upload() -> None:
    """Smart Upload — profile, preview, and adapt uploaded files."""
    from io import BytesIO

    from adapters import find_adapter, load_all_adapters
    from file_profiler import Importability, profile_file

    load_all_adapters()

    uploaded = st.file_uploader(
        "Upload any CSV, Excel, or ZIP file",
        type=["csv", "xlsx", "xls", "zip"],
        key="smart_upload",
    )
    if not uploaded:
        st.caption(
            "Drop a file to inspect its structure, preview data, "
            "and optionally import via an adapter."
        )
        return

    buf = BytesIO(uploaded.getvalue())
    profile = profile_file(uploaded.name, buf)

    # Store in session for the preview panel
    st.session_state["_smart_profile"] = profile

    # Status badge
    _BADGE = {
        Importability.FULL_IMPORT: ("✅", "Fully importable"),
        Importability.ADAPTER_IMPORT: ("🔄", "Importable via adapter"),
        Importability.PREVIEW_ONLY: ("👁️", "Preview only"),
        Importability.PARTIAL_DATASET: ("⚠️", "Partial dataset"),
        Importability.UNSUPPORTED: ("❌", "Not supported"),
    }
    icon, label = _BADGE.get(profile.importability, ("❓", "Unknown"))
    st.markdown(f"**{icon} {label}**")
    st.caption(profile.confidence)

    # Warnings
    for w in profile.warnings:
        st.warning(w, icon="⚠️")

    # Suggestions
    for s in profile.suggestions:
        st.info(s, icon="💡")

    # Missing entities (partial dataset)
    if profile.missing_entities:
        st.caption(f"Missing entities: {', '.join(profile.missing_entities)}")

    # Asset preview
    if profile.assets:
        with st.expander(f"📋 Structure ({len(profile.assets)} table(s))"):
            for asset in profile.assets:
                st.markdown(f"**{asset.name}** — {asset.row_count} rows, {len(asset.columns)} columns")
                st.caption(", ".join(asset.columns[:15]))

    # Archive contents
    if profile.archive_entries:
        with st.expander(f"📦 Archive contents ({len(profile.archive_entries)} entries)"):
            for entry in profile.archive_entries[:30]:
                st.text(entry)

    # Adapter plan + import
    if profile.suggested_adapter:
        adapter = find_adapter(profile)
        if adapter:
            buf.seek(0)
            plan = adapter.plan(profile, buf)

            with st.expander(f"🔧 Adapter: {adapter.description}"):
                if plan.field_mappings:
                    st.markdown("**Field mappings:**")
                    for m in plan.field_mappings:
                        note = f" ({m.transform})" if m.transform else ""
                        st.caption(f"{m.source} → {m.target}{note}")
                if plan.assumptions:
                    st.markdown("**Assumptions:**")
                    for a in plan.assumptions:
                        st.caption(f"• {a}")
                if plan.ignored_sheets:
                    st.caption(f"Ignored: {', '.join(plan.ignored_sheets)}")
                if plan.will_produce:
                    st.caption(f"Will produce: {plan.will_produce}")

            if profile.importability in (Importability.FULL_IMPORT, Importability.ADAPTER_IMPORT):
                if st.button("⬆️ Import via adapter", use_container_width=True, key="smart_import_btn"):
                    buf.seek(0)
                    with st.spinner(f"Transforming via {adapter.name}…"):
                        adapter_result = adapter.transform(buf)
                    if not adapter_result.success:
                        st.error(f"Adapter failed: {adapter_result.error}")
                    else:
                        for w in adapter_result.warnings:
                            st.caption(f"⚠️ {w}")
                        with st.spinner("Importing into database…"):
                            result = import_adapted_frames(
                                frames=adapter_result.frames,
                                profile_family=adapter_result.profile_family.value,
                                adapter_name=adapter_result.adapter_name,
                                label=uploaded.name,
                            )
                        _show_import_result(result)


# ── Profile-not-ready UI helpers ────────────────────────────────

def _render_profile_not_ready(profile_label: str, readiness) -> None:
    """Show a clean message when a profile cannot render."""
    if readiness.status == ReadinessStatus.SCHEMA_MISSING:
        missing = ", ".join(f"`{t}`" for t in readiness.missing_tables)
        st.warning(
            f"**{profile_label} profile is not initialised.**\n\n"
            f"Missing table(s): {missing}\n\n"
            "Run the bootstrap script or reseed the database to create the schema:\n"
            "```\n.\\scripts\\dev-up.ps1\n```\n"
            "Or seed manually:\n"
            "```\nGet-Content seed\\seed.sql -Raw | docker exec -i reporting_db psql -U postgres -d reporting\n```"
        )
    elif readiness.status == ReadinessStatus.NO_DATA:
        st.info(
            f"**{profile_label} profile has no data loaded.**\n\n"
            "Import a dataset using the sidebar, or reseed the demo data:\n"
            "```\nGet-Content seed\\seed.sql -Raw | docker exec -i reporting_db psql -U postgres -d reporting\n```"
        )
    st.stop()


# ── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    # ── Profile selector ────────────────────────────────────
    st.header("Analytics Profile")
    profile_choice = st.radio(
        "Profile",
        ["\U0001f6d2 Order Reporting", "\U0001f4cf Flat Metric"],
        index=0,
        label_visibility="collapsed",
        key="_profile_radio",
    )
    is_order = profile_choice.startswith("\U0001f6d2")

    # ── Page navigation ─────────────────────────────────────
    render_nav(is_order)

    st.divider()

    # ── Readiness check ─────────────────────────────────────
    readiness = check_order_readiness() if is_order else check_flat_metric_readiness()

    # ── Data Source ──────────────────────────────────────────
    st.header("Data Source")

    if is_order:
        row_counts = readiness.row_counts if readiness.is_ready else get_current_row_counts()
        total_rows = sum(row_counts.values())
        st.caption(
            f"**Current dataset:** {total_rows:,} rows across "
            f"{len([v for v in row_counts.values() if v]):,} tables"
        )

        source_choice = st.radio(
            "Import data",
            ["Demo (seed)", "Upload CSV bundle", "Upload Excel workbook", "Smart Upload"],
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

        elif source_choice == "Smart Upload":
            st.caption(
                "Upload any CSV, Excel, or ZIP file. The app will detect "
                "its format and suggest the best import path."
            )
            _render_smart_upload()

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
        fm_counts = readiness.row_counts if readiness.is_ready else get_flat_metric_row_counts()
        total_fm = sum(fm_counts.values())
        st.caption(f"**Current dataset:** {total_fm:,} rows")

        fm_source = st.radio(
            "Import data",
            ["Demo (seed)", "Upload CSV", "Upload Excel", "Smart Upload"],
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

        elif fm_source == "Smart Upload":
            st.caption(
                "Upload any CSV, Excel, or ZIP file. The app will detect "
                "its format and suggest the best import path."
            )
            _render_smart_upload()

        else:
            st.info("Using built-in demo dataset (seed.sql).")

        with st.expander("Table row counts"):
            for tbl, cnt in fm_counts.items():
                st.text(f"{tbl:15s} {cnt:>6,}")

    st.divider()

    # ── Filters ─────────────────────────────────────────────
    st.header("Filters")

    if not readiness.is_ready:
        st.caption("Filters unavailable — profile not ready.")
        filters = {}
        top_n = 10
    elif is_order:
        filters, top_n = dashboard_order.render_filters()
    else:
        filters = dashboard_flat_metric.render_filters()
        top_n = 10

    st.divider()

    # ── Saved Views ─────────────────────────────────────────
    st.header("Views")

    # Save current view
    with st.expander("\U0001f4be Save current view"):
        view_title = st.text_input("Title", key="_save_view_title",
                                    placeholder="e.g. Q1 revenue overview")
        view_desc = st.text_input("Note (optional)", key="_save_view_desc",
                                   placeholder="Short description")
        if st.button("Save", use_container_width=True, key="_save_view_btn"):
            if view_title.strip():
                current_page = get_page(is_order)
                from nav_state import get_target
                current_target = get_target()
                sv = capture_current_state(
                    title=view_title.strip(),
                    is_order=is_order,
                    page=current_page,
                    target=current_target,
                    filters=filters,
                    top_n=top_n,
                    description=view_desc.strip(),
                )
                save_view(sv)
                st.success(f"Saved: **{sv.title}**")
            else:
                st.warning("Enter a title to save.")

    # Load / manage saved views
    all_views = list_views()
    user_views = [v for v in all_views if not v.is_preset]
    if user_views:
        with st.expander(f"\U0001f4c2 Saved views ({len(user_views)})"):
            view_labels = [f"{v.title} ({v.subtitle})" for v in user_views]
            sel_idx = st.selectbox("Select a view", range(len(view_labels)),
                                   format_func=lambda i: view_labels[i],
                                   key="_load_view_sel")
            sel_view = user_views[sel_idx]
            st.caption(f"\U0001f552 {sel_view.created_at[:16]}")
            if sel_view.description:
                st.caption(sel_view.description)

            col_load, col_del = st.columns(2)
            with col_load:
                if st.button("Load", use_container_width=True, key="_load_view_btn"):
                    warns = apply_view(sel_view)
                    if warns:
                        for w in warns:
                            st.warning(w)
                    st.rerun()
            with col_del:
                if st.button("Delete", use_container_width=True, key="_del_view_btn"):
                    delete_view(sel_view.id)
                    st.rerun()

    # Demo presets
    presets = demo_presets.get_presets(is_order)
    if presets:
        with st.expander("\U0001f680 Demo presets"):
            preset_labels = [p.title for p in presets]
            sel_p_idx = st.selectbox("Preset", range(len(preset_labels)),
                                      format_func=lambda i: preset_labels[i],
                                      key="_preset_sel")
            sel_preset = presets[sel_p_idx]
            if sel_preset.description:
                st.caption(sel_preset.description)
            if st.button("Load preset", use_container_width=True, key="_load_preset_btn"):
                apply_view(sel_preset)
                st.rerun()

# ── Main content ────────────────────────────────────────────────

if not readiness.is_ready:
    profile_label = "Order Reporting" if is_order else "Flat Metric"
    _render_profile_not_ready(profile_label, readiness)
elif is_order:
    page = get_page(is_order=True)
    if page == OrderPage.CUSTOMER_DETAIL.value:
        page_order_customer.render()
    elif page == OrderPage.PRODUCT_DETAIL.value:
        page_order_product.render()
    elif page == OrderPage.ANOMALY_EXPLORER.value:
        page_order_anomaly.render(filters)
    else:
        dashboard_order.render(filters, top_n)
else:
    page = get_page(is_order=False)
    if page == FlatMetricPage.ENTITY_DETAIL.value:
        page_fm_entity.render()
    elif page == FlatMetricPage.METRIC_EXPLORER.value:
        page_fm_metric.render()
    else:
        dashboard_flat_metric.render(filters)
