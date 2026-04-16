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
