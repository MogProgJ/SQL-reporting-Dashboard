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
