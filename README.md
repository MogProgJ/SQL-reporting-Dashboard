# SQL Reporting Dashboard

> **Status:** Public build started on 2026-03-01. This repo is being developed in public from MVP onward.

A small reporting dashboard built on a relational database. Turns raw tables into decision-friendly metrics: KPIs, trends, filters, drilldowns, anomaly surfacing, and exports. Fast to run locally, easy to extend with new queries.

The UI is intentionally simple. The value is in the data model and the SQL.

## Tech stack
- PostgreSQL 16 (Docker)
- Python 3.10+
- Streamlit (dashboard UI)
- Plotly (charts)
- psycopg2 (database driver)
- pandas (data handling)
- openpyxl (Excel import)

## What it shows
- **Data source switching** — demo seed, CSV bundle upload, or Excel workbook upload
- **Import validation** — schema checks, type checks, referential integrity, error/warning display
- **KPI cards** — total revenue, total orders, average order value, unique customers
- **Filters** — date range, customer, category, product, order status (sidebar with clear-all)
- **Top-N control** — adjustable slider for top lists
- **Tabs** — Overview, Breakdown, Outliers, Detail & Export
- **Trend charts** — Plotly area chart (revenue) and bar chart (order volume)
- **Top lists** — ranked customers and products by revenue
- **Category breakdown** — horizontal bar chart + table with % share
- **Product revenue share** — donut chart + ranked table
- **Customer drilldown** — revenue, order count, AOV, segment, city per customer
- **Anomaly / outlier surfacing** — unusually large orders and high-revenue days (IQR rule)
- **Detail table** — formatted order-item view with order totals
- **CSV export** — download raw filtered data

## Schema
Five tables: `customers`, `categories`, `products`, `orders`, `order_items`.
See [docs/schema.md](docs/schema.md) for the full column reference.

## Quickstart (local)

**Prerequisites:** Docker and Python 3.10+.

```bash
# 1. Start the database
docker compose up -d

# 2. Create a virtual environment and install deps
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 3. Seed the database
psql postgresql://postgres:postgres@localhost:5434/reporting -f seed/seed.sql

# 4. Run the dashboard
streamlit run app.py
```

## Configuration

The app reads `DATABASE_URL` from a `.env` file or environment variable.

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5434/reporting
```

Copy `.env.example` to `.env` to get started.

## Repo layout

```
app.py              Streamlit dashboard (entry point)
formatters.py       Display helpers (currency, rank, %)
db.py               Database connection helper
queries.py          Parameterized query functions
canonical_model.py  Canonical entity/column specs
dataset_profile.py  Import result + profile value types
importer.py         Import orchestrator (CSV / Excel → DB)
readers.py          CSV bundle + Excel workbook readers
validators.py       Schema + referential validation
normalizers.py      Type coercion (Int64, dates, text)
loader.py           Atomic TRUNCATE + reload into Postgres
requirements.txt
docker-compose.yml
.env.example
seed/seed.sql       Schema + demo data (idempotent)
sql/kpis.sql        Reference queries
tests/              Test suite (unit + integration)
docs/
  vision.md         Product vision
  roadmap.md        Phased roadmap
  schema.md         Table definitions + import pipeline
  architecture.md   Layer diagram
  decisions.md      ADRs
```

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Integration tests require a running seeded Postgres instance.

## Roadmap
- [x] Normalised schema (customers, categories, products, orders, order_items)
- [x] Realistic seed data (~150 orders, ~500 line items)
- [x] Query layer separated from UI
- [x] KPI row, trend charts, top lists, category breakdown
- [x] Sidebar filters (date, customer, category, product)
- [x] Detail table + CSV export
- [x] Order status filter across all queries
- [x] Product revenue share and customer drilldown
- [x] Anomaly/outlier surfacing (IQR-based)
- [x] Adjustable top-N slider and active-filter summary
- [x] Plotly charts (area, bar, horizontal bar, donut)
- [x] Tab-based page structure (Overview, Breakdown, Outliers, Detail)
- [x] Column-config table formatting with ranks
- [x] Extracted formatters module
- [x] Canonical data model + import pipeline (CSV, Excel)
- [x] Data source switching UI with validation feedback
- [ ] Role-based views or saved filter presets
- [ ] Scheduled PDF/email reports

See [docs/roadmap.md](docs/roadmap.md) for the full phased plan and [docs/vision.md](docs/vision.md) for product direction.

## License
MIT
