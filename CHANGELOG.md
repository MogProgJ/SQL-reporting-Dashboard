# Changelog

## Unreleased

### Added (Phase 5B — Workflow & Shareability)
- `saved_views.py` — SavedView dataclass model with JSON-file persistence (`saved_views/` directory, one file per view)
- `capture_current_state()` / `apply_view()` — serialise and restore full analytical state (profile, page, target, filters)
- Saved Views sidebar section in `app.py` — save, load, and delete views with title/description
- `report_pack.py` — profile-aware JSON report-pack builder with KPIs, trends, top-N tables, and detail slices
- Report pack download button alongside existing CSV export in both dashboards
- `demo_presets.py` — built-in preset views (Full overview, Top 5 products, Completed only for Order; All entities for FM)
- Demo presets sidebar section with one-click load
- Graceful stale-state handling: `apply_view()` validates page names against active profile enums, warns on unknown pages
- Profile radio now has explicit `key="_profile_radio"` for programmatic state restore
- `saved_views/` added to `.gitignore` (user views not committed)
- 26 new tests in `tests/test_phase5b.py`: SavedView model, persistence, capture, apply, report-pack helpers, demo presets

### Added (Phase 5A — Productionization & Delivery)
- `Dockerfile` — Python 3.11-slim app container with Streamlit on port 8501, healthcheck
- `.dockerignore` — excludes tests, docs, scripts, .venv from image
- `app` service in `docker-compose.yml` — opt-in via `--profile app`, depends on healthy DB
- CI upgraded to two jobs: **lint** (unit tests, no DB) and **integration** (Postgres service, seed, integration tests)
- `tests/conftest.py` — shared `pytest.mark.integration` marker with auto-skip when `DATABASE_URL` absent
- `requirements-dev.txt` — dev/test dependencies separated from runtime
- `scripts/dev-reseed.ps1` — re-seed the database
- `scripts/dev-test.ps1` — run unit / integration / all tests with flags
- `scripts/smoke_test.py` — verify DB connectivity + profile readiness
- ADR 012 in `docs/decisions.md`

### Changed (Phase 5A)
- `requirements.txt` — pinned dependency ranges, removed `pytest` (now in `requirements-dev.txt`)
- `.github/workflows/ci.yml` — split into lint + integration jobs; integration tests now actually run against Postgres
- `scripts/dev-up.ps1` — installs both `requirements.txt` and `requirements-dev.txt`
- `.vscode/tasks.json` — Python: Install task includes dev deps

### Fixed (Phase 5A)
- Removed 8 duplicate function definitions in `queries.py` (customer + product detail queries were defined twice; second set shadowed the first)
- Integration tests now use proper `pytest.mark.integration` marker instead of ad-hoc `skipif` decorators

### Added (Phase 4 Closeout — Semantic Hardening + Exploration Polish)
- `resolve_snapshot_year()` in `flat_metric_queries.py` — determines single snapshot year from filter state (pinned year or latest available)
- Snapshot semantics for `get_fm_ranking()` and `get_fm_comparison()` — one row per entity via `DISTINCT ON` or explicit `snapshot_year` parameter
- "Snapshot Year" KPI card in flat-metric summary dashboard
- Year context labels on ranking/comparison subheaders and captions throughout FM pages
- Cross-profile page validation in `nav_state.get_page()` — resets stale page values when switching profiles
- Cross-page navigation: Entity Detail → Metric Explorer selectbox, Metric Explorer → Entity Detail selectbox
- Snapshot context captions on Metric Explorer top/bottom rankings
- New tests in `tests/test_phase4_closeout.py`: `resolve_snapshot_year()` unit tests, cross-profile page validation, snapshot ranking/comparison integration tests

### Fixed (Phase 4 Closeout)
- Flat-metric rankings no longer show duplicate entities when year range spans multiple years
- Flat-metric comparison table now enforces one row per entity (snapshot semantics)
- `nav_state.get_page()` no longer returns stale page values from the other profile

### Added (Phase 4 — Multi-Page Expansion)
- `nav_state.py` — Lightweight session-state navigation with per-profile page enums (`OrderPage`, `FlatMetricPage`), `set_page()` / `get_page()` / `go_back()`, sidebar selectbox, and back-to-summary button
- `page_fm_entity.py` — Flat Metric Entity Detail deep-dive: summary KPIs, time trend (metric selector), metric comparison bar chart, full data export
- `page_fm_metric.py` — Flat Metric Metric Explorer deep-dive: top/bottom entity rankings, average trend, IQR-based outlier detection, full data export
- `page_order_customer.py` — Order Customer Detail deep-dive: revenue/volume trends, product mix chart + table, full order-item table with export
- `page_order_product.py` — Order Product Detail deep-dive: revenue/units trends, top customers chart + table, full order-item table with export
- `page_order_anomaly.py` — Order Anomaly Explorer deep-dive: IQR-flagged large orders, high-revenue days with Q₁/Q₃/threshold display, raw data export
- 8 new order-profile query functions in `queries.py`: `get_customer_summary`, `get_customer_trend`, `get_customer_products`, `get_customer_orders`, `get_product_summary`, `get_product_trend`, `get_product_customers`, `get_product_orders`
- 10 new flat-metric query functions in `flat_metric_queries.py`: entity detail (summary, metrics, trend, comparison) + metric explorer (summary, top/bottom entities, trend avg, detail, outliers)
- Navigation hooks in `dashboard_order.py` — "Inspect customer" / "Inspect product" selectboxes in Overview tab top lists
- Navigation hooks in `dashboard_flat_metric.py` — "Explore entity" / "Explore metric" controls in Rankings tab
- Page-aware routing in `app.py` — dispatches to summary or deep-dive page based on `nav_state.get_page()`
- Natural key duplicate detection in `validators.py` — warns on duplicate (entity, metric_name, year) rows
- 13 new unit tests + 17 integration tests in `tests/test_phase4.py` (133 total unit passes, 0 failures)

### Fixed (Phase 4)
- `flat_metric_model.py` — natural key corrected from `("entity", "metric_name")` to `("entity", "metric_name", "year")` (seed data has 3 rows per entity+metric, one per year)

### Added (Phase 3C Closeout — Multi-Profile Hardening)
- `profile_state.py` — `ReadinessStatus` enum, `ProfileReadiness` dataclass, `check_order_readiness()` / `check_flat_metric_readiness()`
- `db.table_exists()` — safe check via `information_schema.tables`
- Readiness guards in `app.py` — clean messages for missing tables (SCHEMA_MISSING) and empty datasets (NO_DATA) instead of raw tracebacks
- `_render_profile_not_ready()` helper with profile-specific reseed/import guidance
- Hardened `importer.get_current_row_counts()` / `get_flat_metric_row_counts()` — return zeros for missing tables
- `scripts/dev-up.ps1` rewrite — `-Reseed`, `-SkipDocker`, `-SkipInstall` flags, direct venv python (no Activate.ps1), Docker reachability check, `ON_ERROR_STOP=1` on psql
- 18 new unit tests in `tests/test_profile_state.py` (120 total, 0 unit failures)

### Fixed (Phase 3C Closeout)
- `dashboard_order.py` `render_filters()` error message now mentions reseed instead of misleading "tables appear empty"

### Added (Phase 3C — Multi-Profile Analytics)
- `ProfileType` enum (`ORDER_REPORTING`, `FLAT_METRIC`) in `dataset_profile.py`
- Flat-metric canonical model (`flat_metric_model.py`) — single entity with entity/metric_name/metric_value/year/score/rank columns, "float" dtype support
- `flat_metrics` table in `seed/seed.sql` with 90-row demo dataset (10 countries × 3 metrics × 3 years)
- Parameterised validators and normalizers — accept optional `entity_specs` for any profile family
- Nullable-column tolerance: missing nullable columns no longer produce validation errors
- Float dtype coercion in normalizers (explicit `float64` cast)
- Float dtype validation in validators (`_check_float_column`)
- Flat-metric CSV and Excel readers (`read_flat_metric_csv`, `read_flat_metric_excel`) in `readers.py`
- Flat-metric database loader (`load_flat_metrics`) in `loader.py`
- Flat-metric import orchestration (`import_flat_metric_csv`, `import_flat_metric_excel`) in `importer.py`
- Full flat-metric query module (`flat_metric_queries.py`) — KPIs, rankings, comparison, trend, detail with parameterised filter builder
- Flat-metric dashboard module (`dashboard_flat_metric.py`) — 3 tabs: Rankings, Trends, Detail & Export
- Extracted order-profile dashboard into `dashboard_order.py`
- Profile selector radio in sidebar — switches between Order Reporting and Flat Metric views
- `app.py` rewritten as thin orchestrator (~240 lines, down from ~680)
- 26 new flat-metric tests + 4 profile-type tests (102 total, 0 failures)

### Fixed (Phase 3C)
- `scripts/dev-up.ps1` seeding uses `Get-Content -Raw | docker exec` pipe (was fragile `< $seedFile` redirect)

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
