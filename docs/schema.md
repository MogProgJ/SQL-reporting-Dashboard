# Database Schema

All monetary values are stored in **cents** to avoid floating-point rounding issues.

## Canonical model

The import pipeline enforces a **canonical model** (`canonical_model.py`) that every data source must satisfy before loading. The five entities below map directly to Postgres tables. Import data uses **natural keys** (names) which the loader resolves to surrogate IDs during insert.

See the [import pipeline docs](#import-pipeline) below for how CSV / Excel data is validated and loaded.

## customers

| Column   | Type      | Constraints             |
|----------|-----------|-------------------------|
| id       | BIGSERIAL | PRIMARY KEY             |
| name     | TEXT      | NOT NULL                |
| segment  | TEXT      | NOT NULL, DEFAULT 'Standard' |
| city     | TEXT      | NOT NULL, DEFAULT 'Unknown'  |

## categories

| Column | Type      | Constraints        |
|--------|-----------|--------------------|
| id     | BIGSERIAL | PRIMARY KEY        |
| name   | TEXT      | NOT NULL, UNIQUE   |

## products

| Column           | Type      | Constraints                          |
|------------------|-----------|--------------------------------------|
| id               | BIGSERIAL | PRIMARY KEY                          |
| name             | TEXT      | NOT NULL                             |
| category_id      | BIGINT    | NOT NULL, FK → categories(id)        |
| unit_price_cents | INTEGER   | NOT NULL, CHECK (unit_price_cents > 0) |

## orders

| Column      | Type        | Constraints                     |
|-------------|-------------|---------------------------------|
| id          | BIGSERIAL   | PRIMARY KEY                     |
| customer_id | BIGINT      | NOT NULL, FK → customers(id)    |
| status      | TEXT        | NOT NULL, DEFAULT 'completed'   |
| created_at  | TIMESTAMPTZ | NOT NULL, DEFAULT now()         |

## order_items

| Column           | Type      | Constraints                          |
|------------------|-----------|--------------------------------------|
| id               | BIGSERIAL | PRIMARY KEY                          |
| order_id         | BIGINT    | NOT NULL, FK → orders(id)            |
| product_id       | BIGINT    | NOT NULL, FK → products(id)          |
| quantity         | INTEGER   | NOT NULL, CHECK (quantity > 0)       |
| unit_price_cents | INTEGER   | NOT NULL, CHECK (unit_price_cents > 0) |

## Relationships

```
customers  1──∞  orders
orders     1──∞  order_items
products   1──∞  order_items
categories 1──∞  products
```

This schema supports: top products, category mix, customer revenue, order trends, and average order value reporting.

---

## Flat-metric profile

The flat-metric profile (`flat_metric_model.py`) provides a second analytics family that stores generic entity-by-metric-by-year data. No FK relationships — each row is self-contained.

### flat_metrics

| Column       | Type             | Constraints          |
|--------------|------------------|----------------------|
| id           | BIGSERIAL        | PRIMARY KEY          |
| entity       | TEXT             | NOT NULL             |
| metric_name  | TEXT             | NOT NULL             |
| metric_value | DOUBLE PRECISION | NOT NULL             |
| year         | INTEGER          |                      |
| score        | DOUBLE PRECISION |                      |
| rank         | INTEGER          |                      |

The demo seed populates 90 rows: 10 countries × 3 metrics (GDP per Capita, Life Expectancy, HDI Score) × 3 years (2021–2023).

### Flat-metric import

When importing flat-metric CSV or Excel files, the import pipeline:

1. **Reads** a single CSV file or the first sheet of an Excel workbook.
2. **Validates** against the flat-metric entity spec — required columns (`entity`, `metric_name`, `metric_value`), types (float, int, text), nullability. Nullable columns (`year`, `score`, `rank`) may be absent entirely.
3. **Normalizes** column names (lowercase, stripped) and coerces types (`float64` for metric_value/score, `Int64` for year/rank).
4. **Loads** atomically: TRUNCATE `flat_metrics` + INSERT.

---

## Import pipeline

When importing CSV bundles or Excel workbooks, the import pipeline:

1. **Reads** files/sheets matching canonical entity names (case-insensitive).
2. **Validates** against the canonical model — required entities, required columns, types, nulls, positive values, and cross-entity references.
3. **Normalizes** column names (lowercase, stripped) and coerces types (Int64, datetime, stripped text).
4. **Loads** atomically: TRUNCATE all five tables with CASCADE, then INSERT in FK order (customers → categories → products → orders → order_items). Natural keys (names) are resolved to surrogate IDs during insert.

Import data uses these natural-key columns for references:
- `products.category` → `categories.name`
- `orders.customer` → `customers.name`
- `order_items.order_id` → `orders.order_id`
- `order_items.product` → `products.name`
