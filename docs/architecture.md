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
│  app.py  (Streamlit UI)       │  Filters, KPIs, charts, tables, CSV export
├───────────────────────────────┤
│  queries.py                   │  Parameterized query functions (returns DataFrames)
├───────────────────────────────┤
│  db.py                        │  Connection helper (psycopg2 + DATABASE_URL)
├───────────────────────────────┤
│  PostgreSQL (Docker)          │  customers, categories, products, orders, order_items
└───────────────────────────────┘
```

- **app.py** — Streamlit page: sidebar filters (date, status, customer, category, product, top-N), active-filter summary, KPI row, trend charts, top lists, category breakdown, product revenue share, customer drilldown, anomaly/outlier surfacing, detail table, CSV export.
- **queries.py** — All SQL lives here. Functions accept filter kwargs and return DataFrames. Parameterized queries prevent injection. Includes IQR-based anomaly helpers.
- **db.py** — Thin connection wrapper around `psycopg2`. Reads `DATABASE_URL` from `.env`.
- **sql/kpis.sql** — Reference copy of key queries for manual testing / documentation.
- **seed/seed.sql** — Idempotent script that creates the schema and inserts demo data.

## File layout

```
app.py              ← Streamlit dashboard (entry point)
db.py               ← Database connection helper
queries.py          ← Query functions + anomaly helpers
requirements.txt
docker-compose.yml
.env.example
seed/seed.sql       ← Schema + demo data
sql/kpis.sql        ← Reference queries
tests/              ← Lightweight test coverage
docs/
  vision.md
  roadmap.md
  schema.md
  architecture.md
  decisions.md
```
