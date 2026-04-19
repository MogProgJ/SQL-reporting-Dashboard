"""SQL Reporting Dashboard — Release Candidate."""

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
/* ── Table polish ─────────────────────────────────── */
/* Header cells — uppercase, tighter, subtle weight */
[data-testid="stDataFrame"] th {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 600;
}
/* Body rows — slightly more breathing room */
[data-testid="stDataFrame"] td {
    font-size: 0.84rem;
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
from ingestion_state import activate_from_result, get_active_dataset
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
    flush_pending_view,
    list_views,
    save_view,
)
import demo_presets

# ── Flush any pending saved-view BEFORE widgets are instantiated ─
flush_pending_view()

# Show view-load warnings if any
_view_warnings = st.session_state.pop("_view_warnings", None)
if _view_warnings:
    for _w in _view_warnings:
        st.warning(_w)

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
    """Display an import result and activate the dataset on success."""
    if result.success:
        # Activate the dataset in session state
        active = activate_from_result(result)

        total = sum(result.row_counts.values())
        summary_lines = "  \n".join(
            f"  \u2022 {name}: {cnt:,} rows"
            for name, cnt in result.row_counts.items()
            if cnt
        )
        profile_label = (
            "Order Reporting" if result.profile_type.value == "order_reporting"
            else "Flat Metric"
        )
        source_desc = _source_type_label(result.source_type)
        st.success(
            f"**\u2705 {profile_label} dataset is now active**  \n"
            f"Source: {source_desc} · *{result.source_label}*  \n"
            f"Loaded **{total:,} rows** into the database.  \n"
            f"{summary_lines}"
        )
        if result.warnings:
            with st.expander(f"\u26a0\ufe0f {len(result.warnings)} warning(s)"):
                for w in result.warnings:
                    st.caption(f"{w.entity}.{w.column}: {w.message}")
        st.rerun()
    else:
        st.error(
            f"**Import failed** — {len(result.errors)} error(s).  \n"
            "Fix the issues below and try again."
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


def _source_type_label(source_type) -> str:
    """Human-readable label for a SourceType."""
    from dataset_profile import SourceType
    _LABELS = {
        SourceType.DEMO_SEED: "Demo seed",
        SourceType.CSV_BUNDLE: "CSV bundle",
        SourceType.EXCEL_WORKBOOK: "Excel workbook",
        SourceType.ADAPTED: "Adapted import",
        SourceType.ASSEMBLED: "Assembled dataset",
    }
    return _LABELS.get(source_type, str(source_type))


def _render_smart_upload() -> None:
    """Smart Upload — guided file inspection, staging, adaptation, and import."""
    from io import BytesIO

    from adapters import find_adapter, load_all_adapters
    from assembly_workspace import (
        build_assembled_frames,
        clear_workspace,
        get_workspace,
        stage_file,
        unstage_entity,
    )
    from csv_utils import read_csv_robust
    from file_profiler import Importability, ProfileFamily, profile_file

    load_all_adapters()

    # ── Assembly workspace (always visible when files are staged) ─
    ws = get_workspace()
    if ws.staged:
        _render_assembly_workspace(ws)

    uploaded = st.file_uploader(
        "Upload a data file",
        type=["csv", "xlsx", "xls", "zip"],
        key="smart_upload",
        help="CSV, Excel, or ZIP. The app inspects the file and guides you.",
    )
    if not uploaded:
        if not ws.staged:
            st.caption(
                "Drop a file to get started. The app identifies it and "
                "shows what you can do with it."
            )
        return

    raw_bytes = uploaded.getvalue()
    buf = BytesIO(raw_bytes)
    profile = profile_file(uploaded.name, buf)

    st.session_state["_smart_profile"] = profile

    # ── Step 1: What is this file? ───────────────────────────
    _BADGE = {
        Importability.FULL_IMPORT: ("✅", "Ready to import"),
        Importability.ADAPTER_IMPORT: ("🔄", "Importable via adapter"),
        Importability.PREVIEW_ONLY: ("👁️", "Preview only"),
        Importability.PARTIAL_DATASET: ("🧩", "Partial dataset — can be staged"),
        Importability.UNSUPPORTED: ("❌", "Not supported"),
    }
    icon, label = _BADGE.get(profile.importability, ("❓", "Unknown"))
    st.markdown(f"### {icon} {label}")

    # Encoding/delimiter info
    diag_parts = []
    if profile.encoding and profile.encoding != "utf-8":
        diag_parts.append(f"encoding: {profile.encoding}")
    if profile.delimiter and profile.delimiter != ",":
        delim_name = {";": "semicolon", "\t": "tab"}.get(profile.delimiter, repr(profile.delimiter))
        diag_parts.append(f"delimiter: {delim_name}")
    if diag_parts:
        st.caption(f"📝 Detected {', '.join(diag_parts)}")

    # File category for preview-only files
    if profile.importability == Importability.PREVIEW_ONLY and profile.file_category:
        cat_labels = {
            "metadata": "📋 This is a metadata / reference file — not dashboard data.",
            "auxiliary": "📦 Auxiliary business table — not used by current profiles.",
            "unknown": "❓ Unrecognised format — preview available below.",
        }
        st.info(cat_labels.get(profile.file_category, profile.file_category))

    # Confidence note
    if profile.confidence:
        st.caption(profile.confidence)

    # Warnings and suggestions
    for w in profile.warnings:
        st.warning(w, icon="⚠️")
    for s in profile.suggestions:
        st.info(s, icon="💡")

    # ── Step 2: Structure preview ────────────────────────────
    if profile.assets:
        with st.expander(f"📋 Structure preview ({len(profile.assets)} table(s))", expanded=False):
            for asset in profile.assets:
                st.markdown(f"**{asset.name}** — {asset.row_count:,} rows, {len(asset.columns)} columns")
                st.caption(", ".join(asset.columns[:15]))

    if profile.archive_entries:
        with st.expander(f"📦 Archive contents ({len(profile.archive_entries)} entries)"):
            for entry in profile.archive_entries[:30]:
                st.text(entry)

    # ── Step 3: What can you do? ─────────────────────────────

    # Partial dataset → stage for assembly
    if (
        profile.importability == Importability.PARTIAL_DATASET
        and profile.profile_family == ProfileFamily.ORDER_REPORTING
        and profile.detected_entity
    ):
        entity = profile.detected_entity
        missing = profile.missing_entities

        st.markdown(f"**Detected entity:** `{entity}`")
        if missing:
            st.caption(f"Still needed for a full dataset: {', '.join(missing)}")

        if entity in ws.staged:
            st.caption(f"ℹ️ '{entity}' is already staged — staging again replaces it.")

        if st.button(
            f"📌 Stage as '{entity}'",
            use_container_width=True,
            key="stage_partial_btn",
            type="primary",
        ):
            buf.seek(0)
            csv_result = read_csv_robust(buf)
            if csv_result.success and csv_result.df is not None:
                stage_file(uploaded.name, entity, profile, raw_bytes, csv_result.df)
                st.success(f"✅ Staged **{uploaded.name}** as `{entity}`.")
                st.rerun()
            else:
                st.error(f"Could not read file: {csv_result.error}")

    # Adapter plan + import
    if profile.suggested_adapter:
        adapter = find_adapter(profile)
        if adapter:
            buf.seek(0)
            plan = adapter.plan(profile, buf)

            with st.expander(f"🔧 Adapter: {adapter.description}", expanded=False):
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
                    st.caption(f"Ignored sheets: {', '.join(plan.ignored_sheets)}")
                if plan.will_produce:
                    st.caption(f"Will produce: {plan.will_produce}")

            if profile.importability in (Importability.FULL_IMPORT, Importability.ADAPTER_IMPORT):
                if st.button(
                    "⬆️ Import into database",
                    use_container_width=True,
                    key="smart_import_btn",
                    type="primary",
                ):
                    buf.seek(0)
                    with st.spinner(f"Transforming via {adapter.name}…"):
                        adapter_result = adapter.transform(buf)
                    if not adapter_result.success:
                        st.error(f"Adapter failed: {adapter_result.error}")
                    else:
                        for w in adapter_result.warnings:
                            st.caption(f"⚠️ {w}")
                        with st.spinner("Loading into database…"):
                            result = import_adapted_frames(
                                frames=adapter_result.frames,
                                profile_family=adapter_result.profile_family.value,
                                adapter_name=adapter_result.adapter_name,
                                label=uploaded.name,
                            )
                        _show_import_result(result)


def _render_assembly_workspace(ws) -> None:
    """Render the assembly workspace with entity checklist and guided flow."""
    from assembly_workspace import clear_workspace, unstage_entity, _ALL_ENTITIES, _REQUIRED_ENTITIES

    st.markdown("---")
    st.markdown("### 🗂️ Assembly Workspace")

    covered, total = ws.coverage_fraction
    st.progress(covered / total if total else 0)

    # Entity checklist — every entity shown, staged ones checked
    for entity in sorted(_ALL_ENTITIES):
        is_required = entity in _REQUIRED_ENTITIES
        req_tag = "" if is_required else " *(optional)*"
        if entity in ws.staged:
            sf = ws.staged[entity]
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"✅ **{entity}**{req_tag} ← _{sf.filename}_ ({sf.row_count:,} rows)")
            with col2:
                if st.button("✕", key=f"unstage_{entity}", help=f"Remove {entity}"):
                    unstage_entity(entity)
                    st.rerun()
        else:
            marker = "⬜" if is_required else "◻️"
            st.markdown(f"{marker} **{entity}**{req_tag}")

    st.caption(ws.readiness_label)

    # Next-step guidance
    if ws.missing_required:
        needed = sorted(ws.missing_required)
        next_hint = f"**Next:** upload a file for **{needed[0]}**"
        if len(needed) > 1:
            next_hint += f" (then {', '.join(needed[1:])})"
        st.info(next_hint, icon="👉")

    # Import button — prominent when ready
    if ws.is_importable:
        if st.button(
            "⬆️ Import assembled dataset",
            use_container_width=True,
            key="assembly_import_btn",
            type="primary",
        ):
            from assembly_workspace import build_assembled_frames

            try:
                with st.spinner("Reading staged files…"):
                    frames = build_assembled_frames()
                with st.spinner("Loading into database…"):
                    result = import_adapted_frames(
                        frames=frames,
                        profile_family="order_reporting",
                        adapter_name="multi_file_assembly",
                        label="Assembled dataset",
                    )
                _show_import_result(result)
                if result.success:
                    clear_workspace()
            except Exception as exc:
                st.error(f"Assembly import failed: {exc}")

    # Clear workspace
    if ws.staged:
        if st.button("🗑️ Clear workspace", use_container_width=True, key="clear_ws_btn"):
            clear_workspace()
            st.rerun()

    st.markdown("---")


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

    # ── 1. Active Dataset ───────────────────────────────────
    st.divider()
    st.header("📊 Active Dataset")

    readiness = check_order_readiness() if is_order else check_flat_metric_readiness()

    if is_order:
        from dataset_profile import ProfileType

        active_ds = get_active_dataset(ProfileType.ORDER_REPORTING)
        row_counts = readiness.row_counts if readiness.is_ready else get_current_row_counts()
        total_rows = sum(row_counts.values())

        if active_ds:
            st.markdown(f"**{active_ds.source_badge}**")
            st.caption(
                f"{active_ds.total_rows:,} rows · "
                f"imported {active_ds.imported_at[:16]}"
            )
        elif readiness.is_ready:
            st.markdown("**🌱 Demo seed**")
            st.caption(f"{total_rows:,} rows across {len([v for v in row_counts.values() if v]):,} tables")
        else:
            st.caption("No dataset loaded.")

        with st.expander("Table row counts"):
            for tbl, cnt in row_counts.items():
                st.text(f"{tbl:15s} {cnt:>6,}")
    else:
        from dataset_profile import ProfileType as _PT

        active_fm = get_active_dataset(_PT.FLAT_METRIC)
        fm_counts = readiness.row_counts if readiness.is_ready else get_flat_metric_row_counts()
        total_fm = sum(fm_counts.values())

        if active_fm:
            st.markdown(f"**{active_fm.source_badge}**")
            st.caption(
                f"{active_fm.total_rows:,} rows · "
                f"imported {active_fm.imported_at[:16]}"
            )
        elif readiness.is_ready:
            st.markdown("**🌱 Demo seed**")
            st.caption(f"{total_fm:,} rows")
        else:
            st.caption("No dataset loaded.")

        with st.expander("Table row counts"):
            for tbl, cnt in fm_counts.items():
                st.text(f"{tbl:15s} {cnt:>6,}")

    # ── 2. Import Data ──────────────────────────────────────
    st.divider()
    st.header("⬆️ Import Data")

    if is_order:
        source_choice = st.radio(
            "How to import",
            ["Smart Upload", "CSV bundle", "Excel workbook"],
            index=0,
            label_visibility="collapsed",
        )

        _ENTITY_LIST = ", ".join(f"`{n}`" for n in EXPECTED_NAMES_SORTED)

        if source_choice == "CSV bundle":
            st.caption(f"Required files: {_ENTITY_LIST}")
            csv_files = st.file_uploader(
                "Upload CSV files",
                type=["csv"],
                accept_multiple_files=True,
                key="csv_upload",
            )
            if csv_files and st.button("Import CSVs", use_container_width=True, type="primary"):
                file_map = {f.name: f for f in csv_files}
                with st.spinner("Importing CSV bundle\u2026"):
                    result = import_csv_bundle(file_map, label="CSV upload")
                _show_import_result(result)

        elif source_choice == "Excel workbook":
            st.caption(f"Required sheets: {_ENTITY_LIST}")
            xls_file = st.file_uploader(
                "Upload .xlsx workbook",
                type=["xlsx"],
                key="xls_upload",
            )
            if xls_file and st.button("Import Excel", use_container_width=True, type="primary"):
                with st.spinner("Importing Excel workbook\u2026"):
                    result = import_excel_workbook(xls_file, label=xls_file.name)
                _show_import_result(result)

        else:  # Smart Upload
            st.caption("Upload any file — the app identifies it and guides you.")
            _render_smart_upload()

        # Template downloads
        with st.expander("📥 Example templates"):
            st.caption("Sample data matching the required format.")
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
                st.caption("Excel template unavailable (openpyxl not installed).")

    else:
        fm_source = st.radio(
            "How to import",
            ["Smart Upload", "CSV", "Excel"],
            index=0,
            label_visibility="collapsed",
            key="fm_source",
        )

        _FM_COLS = "`entity`, `metric_name`, `metric_value` (required); `year`, `score`, `rank` (optional)"

        if fm_source == "CSV":
            st.caption(f"Columns: {_FM_COLS}")
            fm_csv = st.file_uploader("Upload CSV file", type=["csv"], key="fm_csv_upload")
            if fm_csv and st.button("Import CSV", use_container_width=True, key="fm_csv_btn", type="primary"):
                with st.spinner("Importing flat metric CSV\u2026"):
                    result = import_flat_metric_csv(fm_csv, label=fm_csv.name)
                _show_import_result(result)

        elif fm_source == "Excel":
            st.caption(f"Columns: {_FM_COLS}")
            fm_xls = st.file_uploader("Upload .xlsx file", type=["xlsx"], key="fm_xls_upload")
            if fm_xls and st.button("Import Excel", use_container_width=True, key="fm_xls_btn", type="primary"):
                with st.spinner("Importing flat metric Excel\u2026"):
                    result = import_flat_metric_excel(fm_xls, label=fm_xls.name)
                _show_import_result(result)

        else:  # Smart Upload
            st.caption("Upload any file — the app identifies it and guides you.")
            _render_smart_upload()

    # ── 3. Filters ──────────────────────────────────────────
    st.divider()
    st.header("🔍 Filters")

    if not readiness.is_ready:
        st.caption("Filters unavailable — no data loaded.")
        filters = {}
        top_n = 10
    elif is_order:
        filters, top_n = dashboard_order.render_filters()
    else:
        filters = dashboard_flat_metric.render_filters()
        top_n = 10

    # ── 4. Saved Views & Presets ────────────────────────────
    st.divider()
    st.header("📑 Saved Views")
    st.caption("Save and restore dashboard states (filters, page, profile).")

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
        with st.expander(f"\U0001f4c2 Your views ({len(user_views)})"):
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
                    apply_view(sel_view)
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
