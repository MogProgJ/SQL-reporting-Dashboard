# Roadmap

Phased plan for the SQL Reporting Dashboard. Each phase builds on the last.
Only phases 0–2 are implemented. Later phases are honest intentions, not
promises.

## Phase 0 — Setup & DB Foundation ✅

- Repository scaffold (README, LICENSE, docs, docker-compose)
- Single `orders` table with minimal seed data
- Basic Streamlit app showing total orders and revenue
- `.env.example` and quickstart instructions

## Phase 1 — Reporting MVP ✅

- Normalised schema: `customers`, `categories`, `products`, `orders`,
  `order_items`
- Realistic seed data (~30 customers, 8 categories, 30 products, ~150 orders,
  ~500 line items)
- Query layer (`db.py` + `queries.py`) with parameterized SQL
- Dashboard: KPI row, sidebar filters (date, customer, category, product),
  trend charts, top customers, top products, category breakdown, order detail
  table, CSV export
- Lightweight test suite (unit + integration)

## Phase 2 — Decision Support Upgrade ✅

- Product vision and roadmap docs (`docs/vision.md`, `docs/roadmap.md`)
- Status filter added to sidebar and integrated across all queries
- Adjustable top-N controls for top lists
- Active-filter summary caption
- Category and product share-of-revenue analysis
- Customer drilldown: revenue vs order count comparison
- Anomaly surfacing: unusually large orders, high-revenue days (IQR-based,
  transparently explained)
- `@st.cache_data` on stable lookup queries
- Improved empty/error states with recovery guidance
- Consistent money formatting and section hierarchy
- Expanded test coverage for new filters, queries, and anomaly helpers
- ADR 005 for anomaly approach

## Phase 3 — Scenario Loading & Data Flexibility (planned)

- Pluggable seed datasets (e.g. swap orders/products for tickets/agents)
- Data import from CSV or external DB
- Schema migration support if tables evolve

## Phase 4 — Multi-Page Expansion (planned)

- Separate Streamlit pages for deep-dive views (customer detail, product
  detail, anomaly explorer)
- Navigation between summary and detail pages

## Phase 5 — Forecasting & Advanced Analytics (planned)

- Simple trend extrapolation (moving averages, linear projection)
- Seasonality detection if data supports it
- Keep it transparent — no black-box predictions

## Phase 6 — Deployment & Polish (planned)

- Dockerfile for the Streamlit app
- CI pipeline (lint, test, build)
- Optional cloud deployment guide (Railway, Render, etc.)
- Performance profiling for larger datasets
