# Roadmap

Phased plan for the SQL Reporting Dashboard. Each phase builds on the last.
Only phases 0–3C are implemented. Later phases are honest intentions, not
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

## Phase 3A — Dashboard Productization ✅

- Content tabs: Overview, Breakdown, Outliers, Detail & Export
- Plotly charts: area, bar, horizontal bar, donut (replacing Streamlit defaults)
- `st.column_config` formatting on all tables (currency, %, counts, ranks)
- CSS-styled KPI metric cards and download button
- Horizontal bar chart for categories (readable labels)
- Donut chart for product revenue share
- `order_total_cents` window function in detail query
- `formatters.py` module extracted and tested
- "Clear all filters" button, multiselect placeholders
- Active-filter summary in bordered container
- `plotly` added as dependency

## Phase 3B — Data Flexibility + Import UX + Local Bootstrap ✅

- Canonical reporting model (`canonical_model.py`) — import contract
- CSV bundle and Excel workbook import pipeline
- Data Source sidebar with UI feedback
- Graceful error handling: missing openpyxl, incompatible workbooks, bad data
- Early workbook-shape validation before deep import
- Downloadable example templates (CSV zip + Excel workbook)
- Import documentation (`docs/importing-data.md`)
- `scripts/dev-up.ps1` — one-command local bootstrap for VS Code / PowerShell
- `.env.example` cleaned up (DATABASE_URL only, documented)
- `.gitignore` cleaned (removed Java-template noise)
- Nested `.github/.github` structure fixed
- CI workflow now runs `pytest` alongside `compileall`
- Current limitation: only the canonical five-entity model is supported;
  arbitrary flat spreadsheets are not yet accepted

## Phase 3C — Multi-Profile Analytics ✅

- `ProfileType` enum: `ORDER_REPORTING`, `FLAT_METRIC` — extensible profile families
- Flat-metric canonical model (`flat_metric_model.py`) — single entity with entity/metric_name/metric_value/year/score/rank; "float" dtype support
- `flat_metrics` Postgres table + 90-row demo dataset (10 countries × 3 metrics × 3 years)
- Parameterised validators and normalizers — accept any entity spec tuple
- Nullable-column tolerance — missing nullable columns accepted without error
- Flat-metric readers (`read_flat_metric_csv`, `read_flat_metric_excel`)
- Flat-metric loader (`load_flat_metrics`) — atomic TRUNCATE + INSERT
- Flat-metric import orchestration in `importer.py`
- Full flat-metric query module (`flat_metric_queries.py`) — KPIs, rankings, comparison, trend, detail with parameterised filter builder
- Extracted order dashboard → `dashboard_order.py` (4 tabs)
- New flat-metric dashboard → `dashboard_flat_metric.py` (3 tabs: Rankings, Trends, Detail & Export)
- `app.py` rewritten as thin orchestrator (~240 lines, down from ~680)
- Profile selector radio in sidebar
- `scripts/dev-up.ps1` seeding fixed (pipe instead of fragile redirect)
- 30 new tests (102 total, 17 skipped, 0 failures)

## Phase 3C Closeout — Multi-Profile Hardening ✅

- `profile_state.py` — `ReadinessStatus` enum + `ProfileReadiness` dataclass
- `db.table_exists()` via `information_schema.tables` for safe pre-checks
- Readiness guards in `app.py` — clean messages for SCHEMA_MISSING / NO_DATA
- Hardened `importer` row-count helpers — return zeros for missing tables
- `scripts/dev-up.ps1` rewrite: `-Reseed`, `-SkipDocker`, `-SkipInstall` flags,
  direct venv python, Docker reachability check, `ON_ERROR_STOP=1`
- `dashboard_order.py` error message fix (reseed guidance instead of misleading text)
- 18 new tests (120 total, 0 unit failures)
- ADR 009: profile readiness + stale-schema recovery

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
