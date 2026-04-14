# Changelog

## Unreleased

### Added
- Normalised schema: customers, categories, products, orders, order_items
- Realistic seed data (~30 customers, 8 categories, 30 products, ~150 orders, ~500 line items)
- Query layer: `db.py` (connection helper) + `queries.py` (parameterized query functions)
- Dashboard MVP: KPI row, sidebar filters, trend charts, top lists, category breakdown, detail table, CSV export
- Lightweight test suite (`tests/`)

### Changed
- `app.py` rewritten to use query layer and expanded dashboard sections
- `seed/seed.sql` rebuilt with full schema and procedural data generation
- `sql/kpis.sql` updated with reference queries matching new schema
- README, schema.md, architecture.md, decisions.md aligned with actual codebase
