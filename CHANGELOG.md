# Changelog

## Unreleased

### Added (Phase 2 — Decision Support Upgrade)
- Product vision (`docs/vision.md`) and phased roadmap (`docs/roadmap.md`)
- Order status filter in sidebar, integrated across all queries
- Adjustable top-N slider for top lists
- Active-filter summary caption above the dashboard
- Product revenue share table (% of total)
- Customer drilldown table (revenue, order count, avg order value, segment, city)
- Anomaly/outlier section: unusually large orders + high-revenue days (IQR rule)
- Improved empty/error states with recovery guidance
- Category breakdown now shows % of total column
- ADR 005 for IQR-based anomaly approach
- 7 new anomaly-helper unit tests, 2 new status-filter unit tests
- 6 new integration tests (statuses, product share, customer drilldown, order totals, combined filters)

### Changed
- `_build_filters()` now supports `statuses` parameter
- `app.py` upgraded from MVP to decision-support dashboard
- Architecture and decisions docs updated for Phase 2

### Added (Phase 1 — Reporting MVP)
- Normalised schema: customers, categories, products, orders, order_items
- Realistic seed data (~30 customers, 8 categories, 30 products, ~150 orders, ~500 line items)
- Query layer: `db.py` (connection helper) + `queries.py` (parameterized query functions)
- Dashboard MVP: KPI row, sidebar filters, trend charts, top lists, category breakdown, detail table, CSV export
- Lightweight test suite (`tests/`)

### Changed (Phase 1)
- `app.py` rewritten to use query layer and expanded dashboard sections
- `seed/seed.sql` rebuilt with full schema and procedural data generation
- `sql/kpis.sql` updated with reference queries matching new schema
- README, schema.md, architecture.md, decisions.md aligned with actual codebase
