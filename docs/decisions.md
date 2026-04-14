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
