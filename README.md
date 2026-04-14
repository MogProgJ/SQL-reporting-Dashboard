# SQL Reporting Dashboard

> **Status:** Public build started on 2026-03-01. This repo is being developed in public from MVP onward.

A small reporting dashboard built on a relational database. Turns raw tables into decision-friendly metrics: KPIs, trends, filters, drilldowns, anomaly surfacing, and exports. Fast to run locally, easy to extend with new queries.

The UI is intentionally simple. The value is in the data model and the SQL.

## Tech stack
- PostgreSQL 16 (Docker)
- Python 3.10+
- Streamlit (dashboard UI)
- psycopg2 (database driver)
- pandas (data handling)

## What it shows
- **KPI row** — total revenue, total orders, average order value, unique customers
- **Filters** — date range, customer, category, product, order status (sidebar)
- **Top-N control** — adjustable slider for top lists
- **Trend charts** — revenue over time, order volume over time
- **Top lists** — top customers by revenue, top products by revenue
- **Category breakdown** — bar chart + table with % of total
- **Product revenue share** — each product's contribution to total revenue
- **Customer drilldown** — revenue, order count, AOV, segment, city per customer
- **Anomaly / outlier surfacing** — unusually large orders and high-revenue days (IQR rule)
- **Detail table** — filterable order-item-level view
- **CSV export** — download filtered data

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
db.py               Database connection helper
queries.py          Parameterized query functions
requirements.txt
docker-compose.yml
.env.example
seed/seed.sql       Schema + demo data (idempotent)
sql/kpis.sql        Reference queries
tests/              Test suite
docs/
  vision.md         Product vision
  roadmap.md        Phased roadmap
  schema.md         Table definitions
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
- [x] Adjustable top-N slider
- [x] Active-filter summary and improved empty states
- [ ] Additional chart types (pie, heatmap)
- [ ] Role-based views or saved filter presets
- [ ] Scheduled PDF/email reports

See [docs/roadmap.md](docs/roadmap.md) for the full phased plan and [docs/vision.md](docs/vision.md) for product direction.

## License
MIT