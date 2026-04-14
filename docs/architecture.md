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
│  app.py  (Streamlit UI)       │  Tabs, Plotly charts, column-config tables
├───────────────────────────────┤
│  formatters.py                │  Display helpers (currency, rank, %)
├───────────────────────────────┤
│  queries.py                   │  Parameterized query functions (returns DataFrames)
├───────────────────────────────┤
│  db.py                        │  Connection helper (psycopg2 + DATABASE_URL)
├───────────────────────────────┤
│  PostgreSQL (Docker)          │  customers, categories, products, orders, order_items
└───────────────────────────────┘
```

- **app.py** — Streamlit page organised into four content tabs (Overview, Breakdown, Outliers, Detail & Export). Sidebar filters (date, status, customer, category, product, top-N) with clear-all button. Plotly charts for trends, categories, and product share. `st.column_config` formatting on all tables.
- **formatters.py** — Pure display helpers: `cents_to_dollars`, `fmt_number`, `fmt_pct`, `add_rank`. Tested independently.
- **queries.py** — All SQL lives here. Functions accept filter kwargs and return DataFrames. Parameterized queries prevent injection. Includes IQR-based anomaly helpers.
- **db.py** — Thin connection wrapper around `psycopg2`. Reads `DATABASE_URL` from `.env`.
- **sql/kpis.sql** — Reference copy of key queries for manual testing / documentation.
- **seed/seed.sql** — Idempotent script that creates the schema and inserts demo data.

## File layout

```
app.py              ← Streamlit dashboard (entry point)
formatters.py       ← Display helpers (currency, rank, %)
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
