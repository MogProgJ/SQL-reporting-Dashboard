# Architecture Decision Records

> Public build started on 2026-03-01.

## ADR 001: Postgres + simple seed script

**Context:** The project needs a relational database with realistic-looking data
for local development and demos.

**Decision:** Use PostgreSQL (via Docker) with a hand-written seed script
(`seed/seed.sql`) that creates tables and inserts a small number of rows.

**Consequences:**
- Anyone with Docker can spin up the database in seconds.
- The seed script is easy to read and extend.
- No ORM or migration tool is required at this stage.

## ADR 002: Streamlit for fast reporting UI

**Context:** The dashboard needs a web UI that can render KPIs, tables, and
charts with minimal front-end code.

**Decision:** Use Streamlit as the presentation layer. SQL stays in plain `.sql`
files or inline strings; Streamlit renders the results.

**Consequences:**
- Very fast to iterate on new reports.
- No REST API or SPA framework needed for the MVP.
- Streamlit's caching (`@st.cache_data`) keeps page loads snappy.

## ADR 003: Normalised reporting schema (customers, categories, products, orders, order_items)

**Context:** The original single `orders` table was too flat for meaningful
reporting — no product breakdown, no category mix, no real customer dimension.

**Decision:** Replace the single table with five normalised tables:
`customers`, `categories`, `products`, `orders`, `order_items`.
Money stays in cents. The seed script is idempotent (DROP + CREATE).

**Consequences:**
- Enables top-product, category-mix, customer-revenue, and trend reporting.
- Seed script is re-runnable for local dev.
- Schema is still simple — no migration tool needed yet.

## ADR 004: Query layer separated from UI

**Context:** Inline SQL in `app.py` would become hard to maintain as the
dashboard grows.

**Decision:** Extract a thin query layer (`db.py` + `queries.py`). `db.py`
handles connections; `queries.py` contains parameterized functions that return
DataFrames. No ORM.

**Consequences:**
- SQL is testable independently of Streamlit.
- Filters use parameterized queries (safe from injection).
- Easy to add new queries without touching UI code.

## ADR 005: IQR-based anomaly surfacing (no ML)

**Context:** The dashboard should help users spot unusual orders or revenue
days, but adding ML/AI would be overkill and dishonest for this project's scope.

**Decision:** Use the classic IQR (interquartile range) box-plot rule to flag
outliers: any value above Q3 + 1.5 × IQR. The rule is applied in Python
(`find_outlier_orders`, `find_outlier_days` in `queries.py`) and the dashboard
explains the method transparently in the UI.

**Consequences:**
- Simple, deterministic, and explainable.
- No external dependencies or model training.
- Users see exactly what rule is being applied.
- Can be replaced with more sophisticated methods later if needed.

## ADR 006: Plotly charts + tab layout (Phase 3A)

**Context:** The dashboard was functional but visually flat — default Streamlit
charts, long single-page scroll, no visual hierarchy. The presentation layer
was the weakest link for portfolio credibility.

**Decision:** Migrate charts to Plotly Express (area, bar, horizontal bar,
donut) and reorganise the page into four content tabs (Overview, Breakdown,
Outliers, Detail & Export). Extract display helpers into `formatters.py`.
Use `st.column_config` for table formatting.

**Consequences:**
- Charts are more readable with proper axis labels, hover tooltips, and
  appropriate chart types (e.g. horizontal bar for categories).
- Tab structure reduces cognitive load without hiding functionality.
- `plotly` becomes a new dependency (~15 MB).
- Formatting helpers are testable independently of Streamlit.
- Single-page architecture preserved — no multi-page routing complexity.

## ADR 007: Import pipeline with canonical model (Phase 3B)

**Context:** The dashboard was locked to a single data source (seed.sql).
To demonstrate that the reporting model is reusable, users need a way to
import their own data — but not from arbitrary flat files. The schema must
stay fixed; only the rows change.

**Decision:** Define a canonical reporting model (`canonical_model.py`) that
specifies the five required entities, their columns, types, and referential
relationships. Build an import pipeline (readers → validators → normalizers →
loader) that accepts CSV bundles or Excel workbooks and atomically replaces
the database contents via TRUNCATE + reload inside a single transaction.

**Consequences:**
- Any conforming dataset can be loaded without code changes.
- Validation catches errors (missing entities, bad types, broken references)
  before touching the database.
- TRUNCATE + reload is simpler than merge/upsert and sufficient for the
  dashboard's reporting-only use case.
- `openpyxl` becomes a new dependency (~4 MB).
- Dashboard queries remain completely unchanged — they still read the same
  five tables with the same columns.
- No auth or multi-tenancy: one dataset at a time, visible to all users.

## ADR 008: Multi-profile analytics with profile selector (Phase 3C)

**Context:** The dashboard was locked to a single analytics profile — five
normalised order-reporting tables with FK relationships. To demonstrate that the
architecture can support different analytical domains (e.g. country statistics,
university rankings), the system needs a second profile family with its own
semantics, filters, KPIs, and charts — without breaking the existing order profile.

**Decision:** Introduce a `ProfileType` enum (`ORDER_REPORTING`, `FLAT_METRIC`)
and a second canonical model (`flat_metric_model.py`) with a single flat table.
Parameterise validators and normalizers to accept any entity spec tuple.
Extract per-profile dashboard rendering into separate modules
(`dashboard_order.py`, `dashboard_flat_metric.py`). Rewrite `app.py` as a thin
orchestrator with a sidebar profile selector that routes to the correct module.

**Consequences:**
- Two fully independent analytics profiles coexist in the same database.
- Adding a third profile requires: one model file, one query module, one
  dashboard module, and a new `ProfileType` value — no changes to the pipeline
  infrastructure.
- `app.py` dropped from ~680 to ~240 lines; each dashboard module is
  independently testable.
- The "float" dtype is now supported across validators and normalizers.
- Nullable columns may be absent from import files without triggering errors.
- `scripts/dev-up.ps1` seeding was fixed (pipe instead of redirect) as part
  of this phase.

## ADR 009: Profile readiness checks and stale-schema recovery (Phase 3C Closeout)

**Context:** After adding the flat-metric profile in Phase 3C, switching to a
profile whose backing tables don't exist crashes the app with a raw
`psycopg2.errors.UndefinedTable` traceback. This can happen when:
- A developer starts the app before seeding the database.
- The seed script is only partially applied.
- A table is dropped during debugging or maintenance.

**Decision:** Introduce a three-layer defence:
1. `db.table_exists()` — queries `information_schema.tables` (parameterized,
   safe) to check if a table exists without touching it.
2. `profile_state.py` — structured readiness checks that return a
   `ProfileReadiness` result with status (`READY`, `SCHEMA_MISSING`, `NO_DATA`),
   present/missing tables, and row counts. Never throws for expected conditions.
3. `app.py` readiness guards — check readiness before rendering; display clean
   messages with reseed/import guidance for non-ready profiles.

Additionally, harden `importer.get_current_row_counts()` and
`get_flat_metric_row_counts()` to return zeros for missing tables, and rewrite
`dev-up.ps1` with `ON_ERROR_STOP=1` so seed failures are not silently swallowed.

**Consequences:**
- Switching to an unseeded profile shows a helpful message instead of a crash.
- Row-count sidebar displays zeros instead of crashing when tables are absent.
- Seed failures are reported immediately by the bootstrap script.
- The readiness check adds one extra `information_schema` query per table per
  page load — negligible overhead for the small table counts involved.

## ADR 010: Session-state navigation for deep-dive pages (Phase 4)

**Context:** The dashboard showed breadth (KPIs, rankings, trends, outliers)
but offered no way to explore a single entity, customer, product, or metric
in depth. Users could only see aggregates — not drill down.

**Decision:** Add `nav_state.py` — a lightweight session-state navigation layer
using `st.session_state` with per-profile page enums (`OrderPage`,
`FlatMetricPage`). Each profile has a SUMMARY page and 2–3 deep-dive pages.
The sidebar shows a selectbox for page navigation; summary dashboards include
"Inspect customer" / "Explore entity" hooks that call `set_page()` to navigate.
A back-to-summary button appears on every deep-dive page.

Five new page modules were created:
- `page_fm_entity.py` — Entity detail: KPIs, time trend, metric comparison, export.
- `page_fm_metric.py` — Metric explorer: top/bottom rankings, avg trend, IQR outliers, export.
- `page_order_customer.py` — Customer detail: revenue trend, product mix, full orders.
- `page_order_product.py` — Product detail: revenue trend, top customers, full orders.
- `page_order_anomaly.py` — Anomaly explorer: IQR large orders, high-revenue days, raw data.

**Consequences:**
- Users can navigate from aggregate summaries to single-entity depth without
  leaving the app or losing filter context.
- No Streamlit multipage app complexity — everything stays in a single entry
  point (`app.py`) with session-state routing.
- The `flat_metric_model.py` natural key was corrected to include `year`,
  and validators now detect natural key duplicates as warnings.
- `queries.py` gained 8 new functions for customer/product deep dives.
- `flat_metric_queries.py` gained 10 new functions for entity/metric deep dives.
- Adding a new deep-dive page requires: one page module, one enum value, and a
  routing clause in `app.py` — no framework overhead.

## ADR 011: Snapshot semantics for flat-metric rankings (Phase 4 Closeout)

**Context:** `get_fm_ranking()` and `get_fm_comparison()` returned raw rows from
`flat_metrics` without deduplication. When the year slider spanned multiple years,
the same entity could appear multiple times in a ranking (once per year), making
the table analytically meaningless. By contrast, the Metric Explorer's
`get_fm_metric_top_entities()` already used `DISTINCT ON (entity)`.

**Decision:** Enforce snapshot semantics on rankings and comparison:
- Both functions accept an optional `snapshot_year` parameter.
- When `snapshot_year` is set, only that year's data is returned (one row per entity).
- When it is `None`, a `DISTINCT ON (entity) ... ORDER BY entity, year DESC`
  subquery picks the latest available year per entity, then sorts by value.
- `resolve_snapshot_year()` determines the year: if the sidebar slider is pinned
  to a single value (`year_from == year_to`), use that; otherwise, use the latest
  year in the database.
- `get_page()` in `nav_state.py` now validates the stored page against the active
  profile's enum and resets to Summary if stale.

**Consequences:**
- Rankings always show one row per entity — no duplicates.
- Year context is explicit: subheaders, captions, and a "Snapshot Year" KPI card
  tell the user exactly which year the ranking represents.
- Trend views remain unchanged — they intentionally show all years.
- Cross-profile navigation is safe: switching profiles clears stale page state.

## ADR 012: Dockerized app + CI with Postgres service (Phase 5A)

**Context:** The project had no way to run the app in a container and no
integration test coverage in CI. All 23 integration tests were silently skipped
because `DATABASE_URL` was never set. The requirements file mixed runtime and
dev dependencies with no version pins.

**Decision:**
1. Add a `Dockerfile` (Python 3.11-slim, Streamlit on port 8501) and
   `.dockerignore`. The app service is added to `docker-compose.yml` under
   the `app` profile so `docker compose up -d` still starts only the DB.
2. Split CI into two jobs: **lint** (compile check + unit tests, no DB) and
   **integration** (Postgres service container, seed, integration tests).
   Use a proper `pytest.mark.integration` marker via `conftest.py` instead of
   ad-hoc `skipif` decorators.
3. Pin runtime dependency ranges in `requirements.txt` and extract `pytest`
   into `requirements-dev.txt`.
4. Add helper scripts: `dev-reseed.ps1`, `dev-test.ps1`, `smoke_test.py`.
5. Remove duplicate function definitions in `queries.py` (8 functions were
   defined twice — the second set silently shadowed the first).

**Consequences:**
- `docker compose --profile app up --build` runs the full stack.
- CI now actually exercises integration tests against a real Postgres instance.
- Unit and integration tests are cleanly separated by marker.
- `queries.py` dropped from ~607 to ~460 lines with no behaviour change.
- Dev dependencies are isolated; runtime containers stay lean.

## ADR 013: Saved views with local JSON persistence (Phase 5B)

**Context:** Users had no way to save and restore a useful analysis state.
Switching between views or sharing a setup required manually re-applying
filters, navigating to the right page, and selecting the right profile.
Exports were limited to per-table CSV.

**Decision:**
1. Introduce `SavedView` dataclass capturing full analytical state: profile
   type, page, deep-dive target, all filter values, top-N, title, description,
   and timestamp.
2. Persist each view as an individual JSON file under `saved_views/` (one file
   per UUID). No cloud storage, no auth, no database table. Directory is
   `.gitignore`'d so user views are not committed.
3. `apply_view()` validates page names against the active profile's enum and
   returns warnings for stale or invalid state.
4. Add `report_pack.py` — profile-aware JSON bundles with KPIs, trend/ranking
   tables, and a detail slice (capped at 500 rows). Available alongside the
   existing CSV export.
5. Add `demo_presets.py` — built-in preset views reusing the SavedView model
   with `is_preset=True` for demo/showcase flows.

**Consequences:**
- Users can save, load, and delete analytical states from the sidebar.
- Report packs provide richer export than CSV alone (metadata + KPIs + tables).
- Demo presets enable one-click showcase without manual filter setup.
- No cloud dependency or database schema changes.
- Stale state (deleted entities, renamed pages) is handled gracefully.

## ADR 014: File profiler + adapter registry (Phase 6)

**Context:** The import pipeline (Phase 3B) only accepted files matching the
exact canonical column names and structure. Real-world spreadsheets — Northwind
exports, government statistics downloads, partial extracts — are close to
canonical but need column renaming, ID resolution, unit conversion, and
wide-to-long reshaping. Users had no way to preview a file before importing.

**Decision:**
1. Introduce `file_profiler.py` with `profile_file(name, buf) → FileProfile`.
   Inspects CSV/XLSX/ZIP files via heuristics: canonical sheet matching,
   Northwind-style detection, flat-metric column detection, wide-metric
   detection, partial-entity detection, and ZIP content inspection.
2. Classify each file with an `Importability` status: FULL_IMPORT,
   ADAPTER_IMPORT, PREVIEW_ONLY, PARTIAL_DATASET, or UNSUPPORTED.
3. Introduce `adapters/` package with `BaseAdapter` ABC and a flat registry
   (no plugin system). Each adapter has `can_handle()`, `plan()`, and
   `transform()` methods.
4. Adapters produce canonical DataFrames that flow through the existing
   validate → normalize → load pipeline via `import_adapted_frames()`.
5. Add "Smart Upload" to the sidebar's Data Source section for both profiles.

**Consequences:**
- The app now handles Northwind-style workbooks and wide flat-metric tables.
- Partial datasets are detected and explained rather than silently rejected.
- ZIP archives are inspected and canonical CSV bundles inside are auto-detected.
- The adapter plan (field mappings, assumptions) is shown to the user before import.
- Existing canonical imports continue to work exactly as before.
- New adapters can be added by subclassing BaseAdapter and calling register_adapter().

## ADR 015: Northwind adapter — column aliasing and ID resolution (Phase 6)

**Context:** Northwind-style order workbooks use ID-based foreign keys
(`CustomerID`, `ProductID`, `CategoryID`) and different column names
(`OrderDate`, `UnitPrice`, `ordersdetails` sheet).

**Decision:**
Map aliases with fuzzy column matching (`_pick()`), resolve IDs to names
via companion sheets, convert dollar prices to cents (× 100), default
missing `status` to `"completed"`, and ignore `employees`/`shippers`/
`suppliers` sheets. All mappings and assumptions are documented in the
`AdapterPlan` shown to the user before import.

**Consequences:**
- Northwind exports can be imported with one click.
- Price conversion and default assumptions are transparent.
- ID resolution failures degrade gracefully (use ID as fallback name).

## ADR 016: Encoding-resilient CSV parsing (Phase 6A)

**Context:** Real-world CSV files frequently use non-UTF-8 encodings
(CP1252, Latin-1) and non-comma delimiters (semicolons, tabs). The bare
`pd.read_csv()` calls throughout the pipeline would crash on such files
with cryptic `UnicodeDecodeError` messages.

**Decision:** Introduce `csv_utils.py` with `read_csv_robust()` that tries
four encodings (utf-8, utf-8-sig, cp1252, latin-1) and three delimiters
(comma, semicolon, tab) using `csv.Sniffer` where possible. Returns a
structured `CsvReadResult` with diagnostics. Replace all bare `pd.read_csv()`
calls in `readers.py`, `file_profiler.py` (both CSV profiling and ZIP inner
CSV inspection) with `read_csv_robust()`.

**Consequences:**
- CP1252/Latin-1 CSVs and semicolon/tab-delimited files now parse correctly.
- Non-default encodings and delimiters surface as informational warnings.
- Existing UTF-8/comma CSV imports are unaffected (first candidate wins).
- One central function for all CSV I/O — easier to extend with new encodings.

## ADR 017: Northwind adapter price derivation from products sheet (Phase 6A)

**Context:** Northwind-style order details sheets often lack a price column
(the Frostonline variant has `OrderID`, `ProductID`, `Quantity` only). The
adapter was defaulting `unit_price_cents` to 0, which fails the positive-value
validator.

**Decision:** When no price column is found in order details, join
`ordersdetails.ProductID` → `products.ProductID` to derive prices from the
products sheet. Build a lookup dict, map through it, convert dollars to cents.
Report match statistics in warnings. Fall back to 0 only when the products
sheet itself has no price column.

**Consequences:**
- Northwind workbooks without detail-level prices can be imported.
- The adapter plan explicitly states "prices will be derived from products
  sheet via ProductID join" so users see the assumption.
- Match statistics (N/M items matched) give confidence in the derivation.

## ADR 018: Multi-file assembly workspace for Order Reporting (Phase 6A)

**Context:** Order Reporting requires five entity files, but users often have
data split across separate files (e.g. `customers.csv` from CRM, `orders.csv`
from ERP). Uploading one file at a time was a dead end — each upload was
evaluated independently and reported as "partial, missing 4 entities".

**Decision:** Introduce `assembly_workspace.py` — a session-state-backed
staging area where users collect partial files one by one. Each staged file
is bound to a detected entity. The workspace tracks coverage (covered vs.
missing entities), importability (minimum: orders + order_items + products),
and readiness labels. When ready, `build_assembled_frames()` re-reads all
staged bytes via `read_csv_robust()` and feeds them to `import_adapted_frames()`.

**Consequences:**
- Users can assemble a complete dataset from separate files across uploads.
- Coverage progress (N/5 entities, progress bar) gives clear feedback.
- Minimum import threshold allows partial datasets (customers/categories
  can be synthesized downstream if needed).
- Session-state scoping means the workspace is per-browser-tab, no persistence.

## ADR 019: Reference file classification (Phase 6A)

**Context:** When a user uploads a file like `data_dictionary.csv` or
`employees.csv`, the profiler classified it as "preview only" with a generic
message. This felt like a failure when it should be recognized as a known
auxiliary file that simply isn't part of the reporting model.

**Decision:** Add `_classify_reference_file()` to the file profiler. It
checks the filename stem against two known sets: `_METADATA_STEMS` (data
dictionaries, changelogs, readmes) and `_AUXILIARY_STEMS` (employees,
shippers, suppliers, regions, territories, demographics). Sets
`file_category` on the FileProfile ("metadata", "auxiliary", "unknown").

**Consequences:**
- Known reference files get labeled with contextual messages instead of
  generic "preview only" noise.
- Auxiliary Northwind tables (employees, shippers) are recognized as
  intentionally excluded from the reporting model.
- Unknown files still get "preview only" with honest messaging.

## ADR 020: Deferred saved-view application (Phase 6B)

**Context:** `apply_view()` wrote directly to widget-bound session-state
keys (`_profile_radio`, `sel_statuses`, etc.) after those widgets had
already been instantiated in the same Streamlit script run. Streamlit
prohibits modifying widget-bound keys after widget instantiation, causing
a crash when loading a preset that switches profiles.

**Decision:** Switch to a "pending view" pattern. `apply_view()` stashes the
view under `_pending_view` in session state and returns immediately. The
caller triggers `st.rerun()`. At the top of app.py, `flush_pending_view()`
runs before any widgets — it reads the pending view, writes all state keys
(profile, page, target, filters, top_n, date range, year range), and reruns
so widgets pick up the new defaults cleanly.

**Consequences:**
- Presets and saved views can safely switch profiles without crashing.
- `top_n`, `date_from`/`date_to`, and `year_from`/`year_to` are now
  restored (previously missing from apply_view).
- Page name validation and warnings are preserved via `_view_warnings`.
- The dead duplicate `return warnings` in the old code is eliminated.

## ADR 021: Active dataset provenance tracking (Phase 6B)

**Context:** The app had no persistent concept of "what data is loaded" —
it checked row counts via live DB queries on every rerun. There was no way
for the sidebar to show how the current data arrived (CSV upload, Excel
workbook, adapter import, assembly, or demo seed).

**Decision:** Introduce `ingestion_state.py` with an `ActiveDataset`
dataclass (profile_type, source_type, source_label, row_counts, imported_at)
stored in session state keyed by profile type. `activate_from_result()`
creates and stores an `ActiveDataset` on successful import. The sidebar
displays a source badge with icon and label when an active dataset exists.

**Consequences:**
- Users see clear provenance: "🔄 northwind.xlsx" or "🗂️ Assembled dataset".
- Active dataset state is separate from assembly workspace state — no confusion.
- The `SourceType.ASSEMBLED` enum value (previously unused) is now properly
  used for multi-file assembly imports.
- Import success messaging now includes profile name and source label.
