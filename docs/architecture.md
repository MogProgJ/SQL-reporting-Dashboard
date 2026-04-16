# Architecture

This project is intentionally small, but structured like production code.

## Goals
- Clear separation of concerns
- Repeatable local setup
- Small, testable units
- A database schema that matches real workflows

## Layers

```
┌───────────────────────────────┐
│  app.py  (Streamlit UI)       │  Tabs, Plotly charts, data-source switcher
├───────────────────┬───────────┤
│  formatters.py    │ importer  │  Display helpers │ Import orchestrator
├───────────────────┤  .py      │
│  queries.py       ├───────────┤
│                   │ readers   │  CSV / Excel → DataFrames
│                   │ validators│  Schema + referential checks
│                   │ normaliz… │  Type coercion
│                   │ loader.py │  Atomic DB reload
├───────────────────┴───────────┤
│  db.py                        │  Connection helper (psycopg2 + DATABASE_URL)
├───────────────────────────────┤
│  PostgreSQL (Docker)          │  customers … order_items + flat_metrics
└───────────────────────────────┘
```

- **profile_state.py** — Profile readiness checks. Queries `information_schema.tables` to determine if a profile's backing tables exist and contain data. Returns `ProfileReadiness` (status, present/missing tables, row counts). Used by `app.py` to gate rendering.
- **app.py** — Thin orchestrator (~330 lines). Sidebar has profile selector (Order Reporting / Flat Metric), page navigation, per-profile Data Source section, and per-profile filters. Runs readiness check before rendering; routes to summary dashboards or deep-dive pages based on nav state. Shows clean recovery guidance when tables are missing or empty. Delegates rendering to `dashboard_order.py`, `dashboard_flat_metric.py`, or the five `page_*` modules.
- **dashboard_order.py** — Order-profile summary dashboard: 4 tabs (Overview, Breakdown, Outliers, Detail & Export). Plotly charts, `st.column_config` formatting. Includes navigation hooks to drill into customer/product detail.
- **dashboard_flat_metric.py** — Flat-metric summary dashboard: 3 tabs (Rankings, Trends, Detail & Export). Horizontal bar chart, line chart, ranking table. Includes navigation hooks to drill into entity/metric detail.
- **nav_state.py** — Lightweight session-state navigation. Per-profile page enums (`OrderPage`, `FlatMetricPage`), page/target state in `st.session_state`, sidebar selectbox, back button.
- **page_fm_entity.py** — Flat Metric Entity Detail deep-dive: KPIs, time trend (metric selector), metric comparison bar chart, full data export.
- **page_fm_metric.py** — Flat Metric Metric Explorer deep-dive: top/bottom entity rankings, average trend over time, IQR outlier detection, full data export.
- **page_order_customer.py** — Order Customer Detail deep-dive: revenue and volume trends, product mix, full order-item table with export.
- **page_order_product.py** — Order Product Detail deep-dive: revenue and units trends, top customers, full order-item table with export.
- **page_order_anomaly.py** — Order Anomaly Explorer deep-dive: IQR-flagged large orders, high-revenue days with threshold display, raw data export.
- **formatters.py** — Pure display helpers: `cents_to_dollars`, `fmt_number`, `fmt_pct`, `add_rank`. Tested independently.
- **queries.py** — All SQL lives here. Functions accept filter kwargs and return DataFrames. Parameterized queries prevent injection. Includes IQR-based anomaly helpers.
- **db.py** — Thin connection wrapper around `psycopg2`. Reads `DATABASE_URL` from `.env`. Also provides `table_exists()` helper via `information_schema`.
- **canonical_model.py** — Defines the five canonical order-profile entities (columns, types, natural keys).
- **flat_metric_model.py** — Defines the flat-metric entity (entity, metric_name, metric_value, year, score, rank). Supports "float" dtype.
- **flat_metric_queries.py** — SQL queries for the flat-metric dashboard — KPIs, rankings, comparison, trend, detail with parameterised filter builder.
- **importer.py** — High-level orchestrator: `import_csv_bundle()` / `import_excel_workbook()`. Calls readers → validators → normalizers → loader.
- **readers.py** — `read_csv_bundle(files)` and `read_excel_workbook(buf)` return `dict[str, DataFrame]`.
- **validators.py** — Schema checks, null/type/positive-value checks, cross-entity referential integrity.
- **normalizers.py** — Column name cleanup, Int64/date/text coercion per canonical spec. Pure functions.
- **loader.py** — Atomic TRUNCATE + reload into the five reporting tables, respecting FK order.
- **dataset_profile.py** — Value types: `ProfileType`, `SourceType`, `ValidationIssue`, `ImportResult`, `DatasetProfile`.
- **sql/kpis.sql** — Reference copy of key queries for manual testing / documentation.
- **seed/seed.sql** — Idempotent script that creates the schema and inserts demo data.

## File layout

```
profile_state.py    ← Profile readiness checks (table existence + row counts)
app.py              ← Streamlit orchestrator (entry point, profile + page routing)
nav_state.py        ← Session-state navigation (page enums, set/get page, back button)
dashboard_order.py  ← Order-profile summary dashboard (4 tabs)
dashboard_flat_metric.py ← Flat-metric summary dashboard (3 tabs)
page_fm_entity.py   ← Flat Metric Entity Detail deep-dive
page_fm_metric.py   ← Flat Metric Metric Explorer deep-dive
page_order_customer.py ← Order Customer Detail deep-dive
page_order_product.py  ← Order Product Detail deep-dive
page_order_anomaly.py  ← Order Anomaly Explorer deep-dive
formatters.py       ← Display helpers (currency, rank, %)
db.py               ← Database connection helper
queries.py          ← Order-profile query functions + customer/product detail + anomaly helpers
flat_metric_queries.py ← Flat-metric query functions + entity/metric detail + filter builder
canonical_model.py  ← Order entity/column specs (the import contract)
flat_metric_model.py← Flat-metric entity spec
dataset_profile.py  ← ProfileType, ImportResult, profile value types
importer.py         ← Import orchestrator (CSV / Excel → DB, both profiles)
readers.py          ← CSV bundle + Excel workbook + flat-metric readers
validators.py       ← Schema + referential validation (parameterised)
normalizers.py      ← Type coercion (Int64, float64, dates, text)
loader.py           ← Atomic TRUNCATE + reload into Postgres (both profiles)
requirements.txt
docker-compose.yml
.env.example
scripts/
  dev-up.ps1        ← One-command local bootstrap (PowerShell)
seed/seed.sql       ← Schema + demo data
sql/kpis.sql        ← Reference queries
tests/              ← Unit + integration test suites
docs/
  vision.md
  roadmap.md
  schema.md
  importing-data.md
  architecture.md
  decisions.md
```
