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
│  PostgreSQL (Docker)          │  customers, categories, products, orders, order_items
└───────────────────────────────┘
```

- **app.py** — Streamlit page organised into four content tabs (Overview, Breakdown, Outliers, Detail & Export). Sidebar has Data Source section (demo/CSV/Excel import) and filters (date, status, customer, category, product, top-N) with clear-all button. Plotly charts for trends, categories, and product share. `st.column_config` formatting on all tables.
- **formatters.py** — Pure display helpers: `cents_to_dollars`, `fmt_number`, `fmt_pct`, `add_rank`. Tested independently.
- **queries.py** — All SQL lives here. Functions accept filter kwargs and return DataFrames. Parameterized queries prevent injection. Includes IQR-based anomaly helpers.
- **db.py** — Thin connection wrapper around `psycopg2`. Reads `DATABASE_URL` from `.env`.
- **canonical_model.py** — Defines the five canonical entities (columns, types, natural keys) that every data source must satisfy.
- **importer.py** — High-level orchestrator: `import_csv_bundle()` / `import_excel_workbook()`. Calls readers → validators → normalizers → loader.
- **readers.py** — `read_csv_bundle(files)` and `read_excel_workbook(buf)` return `dict[str, DataFrame]`.
- **validators.py** — Schema checks, null/type/positive-value checks, cross-entity referential integrity.
- **normalizers.py** — Column name cleanup, Int64/date/text coercion per canonical spec. Pure functions.
- **loader.py** — Atomic TRUNCATE + reload into the five reporting tables, respecting FK order.
- **dataset_profile.py** — Value types: `SourceType`, `ValidationIssue`, `ImportResult`, `DatasetProfile`.
- **sql/kpis.sql** — Reference copy of key queries for manual testing / documentation.
- **seed/seed.sql** — Idempotent script that creates the schema and inserts demo data.

## File layout

```
app.py              ← Streamlit dashboard (entry point)
formatters.py       ← Display helpers (currency, rank, %)
db.py               ← Database connection helper
queries.py          ← Query functions + anomaly helpers
canonical_model.py  ← Entity/column specs (the import contract)
dataset_profile.py  ← Import result + profile value types
importer.py         ← Import orchestrator (CSV / Excel → DB)
readers.py          ← CSV bundle + Excel workbook readers
validators.py       ← Schema + referential validation
normalizers.py      ← Type coercion (Int64, dates, text)
loader.py           ← Atomic TRUNCATE + reload into Postgres
requirements.txt
docker-compose.yml
.env.example
seed/seed.sql       ← Schema + demo data
sql/kpis.sql        ← Reference queries
tests/              ← Unit + integration test suites
docs/
  vision.md
  roadmap.md
  schema.md
  architecture.md
  decisions.md
```
