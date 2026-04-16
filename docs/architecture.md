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
- **app.py** — Thin orchestrator (~305 lines). Sidebar has profile selector (Order Reporting / Flat Metric), per-profile Data Source section, and per-profile filters. Runs readiness check before rendering; shows clean recovery guidance when tables are missing or empty. Delegates rendering to `dashboard_order.py` or `dashboard_flat_metric.py`.
- **dashboard_order.py** — Order-profile dashboard: 4 tabs (Overview, Breakdown, Outliers, Detail & Export). Plotly charts, `st.column_config` formatting.
- **dashboard_flat_metric.py** — Flat-metric dashboard: 3 tabs (Rankings, Trends, Detail & Export). Horizontal bar chart, line chart, ranking table.
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
app.py              ← Streamlit orchestrator (entry point, profile selector)
dashboard_order.py  ← Order-profile dashboard (4 tabs)
dashboard_flat_metric.py ← Flat-metric dashboard (3 tabs)
formatters.py       ← Display helpers (currency, rank, %)
db.py               ← Database connection helper
queries.py          ← Order-profile query functions + anomaly helpers
flat_metric_queries.py ← Flat-metric query functions + filter builder
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
