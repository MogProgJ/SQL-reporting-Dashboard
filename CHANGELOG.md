# Changelog

## Unreleased

### Added (Phase 3B — Local Bootstrap & Repo Hygiene)
- `scripts/dev-up.ps1` — one-command local bootstrap: venv, deps, Docker, seed, Streamlit
- CI workflow (`ci.yml`) now runs `python -m pytest tests/ -v` after compile check

### Fixed (Phase 3B — Repo Hygiene)
- `.env.example` cleaned: removed stale JWT/PORT/LOG fields, added comments
- `.gitignore` cleaned: removed Java-template noise (*.class, *.jar, *.war)
- `.github/.github/` nested directory flattened — `bug_report.md` moved to correct level
- README quickstart: added Docker-based seeding alternative, bootstrap script docs
- Architecture and roadmap docs updated with `scripts/` and `importing-data.md`

### Added (Phase 3B — Data Flexibility)
- Canonical reporting model (`canonical_model.py`) — 5 entity specs with column types and natural keys
- Dataset profile types (`dataset_profile.py`) — `SourceType`, `ValidationIssue`, `ImportResult`, `DatasetProfile`
- Validation layer (`validators.py`) — schema checks, type checks, null checks, positive-value constraints, cross-entity referential integrity
- CSV bundle reader and Excel workbook reader (`readers.py`)
- Type normalizer (`normalizers.py`) — column name cleanup, Int64/date/text coercion
- Database loader (`loader.py`) — atomic TRUNCATE + reload with FK-ordered inserts
- Import orchestrator (`importer.py`) — ties readers → validators → normalizers → loader
- Data Source sidebar section with radio selector (Demo / CSV / Excel)
- CSV bundle uploader (multi-file) with import button and result display
- Excel workbook uploader (.xlsx) with import button and result display
- Table row counts expander in sidebar
- `openpyxl` added to requirements.txt

### Added (Phase 3B Closeout — Import UX Hardening)
- `ReaderError` exception class in `readers.py` for structured user-facing failures
- Early workbook-shape validation: incompatible/missing sheets detected before deeper import
- Graceful openpyxl dependency detection with clear install instructions
- CSV bundle validation: no recognised files produces a clear error with expected names
- `_show_import_result()` helper in `app.py` for consistent success/error/warning display
- Downloadable example templates: CSV bundle (.zip) and Excel workbook (.xlsx)
- Template generator functions in `importer.py` (`generate_example_csv_zip`, `generate_example_excel`)
- Import contract helper text in sidebar (shows required files/sheets before upload)
- `docs/importing-data.md` — full import guide with column specs, validation rules, limitations
- Import UX hardening tests (`tests/test_import_pipeline.py`) — openpyxl detection, workbook shape, CSV errors

### Added (Phase 3A — Dashboard Productization)
- `formatters.py` module with `cents_to_dollars`, `fmt_number`, `fmt_pct`, `add_rank`
- Top-level content tabs: Overview, Breakdown, Outliers, Detail & Export
- Plotly charts: area (revenue trend), bar (order volume), horizontal bar (categories), donut (product share)
- `st.column_config` formatting across all tables (currency, percentages, counts)
- Rank column in top lists, product share, and customer drilldown tables
- CSS-styled KPI metric cards
- Active-filter summary in bordered container
- "Clear all filters" sidebar button
- Placeholder text on all multiselect filters
- `order_total_cents` window function in detail query
- Line item count / order count summary on detail tab
- Chart captions explaining each visualization
- CSV note clarifying raw-data export format
- Formatter unit tests (`fmt_number`, `fmt_pct`, `add_rank`)
- `plotly` added to requirements.txt

### Changed
- Page structure reorganized from flat sections into four content tabs
- Charts migrated from Streamlit defaults to Plotly Express
- Category breakdown now uses horizontal bar chart (readable labels)
- Product share now includes donut chart alongside table
- All tables use `column_config` with proper display names and formats
- Detail table now shows order total per line for context
- Empty states upgraded from `st.info` to `st.warning` with bolder guidance
- Download button styled with accent border

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
