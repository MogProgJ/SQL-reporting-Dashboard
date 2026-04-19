# Importing Data

The dashboard supports three data sources. All imports must match the
**canonical reporting model** — five entities with specific columns.

## Supported sources

| Source | Description |
|--------|-------------|
| **Demo seed** | Built-in sample data loaded by `seed/seed.sql`. Always available. |
| **CSV bundle** | Upload five `.csv` files — one per entity. |
| **Excel workbook** | Upload one `.xlsx` file with five sheets — one per entity. |

## Required entities and columns

Every import source must provide these five entities. Column names are
matched case-insensitively; extra columns are ignored.

### customers
| Column   | Type | Required | Notes |
|----------|------|----------|-------|
| name     | text | yes      | Customer display name |
| segment  | text | yes      | e.g. SMB, Enterprise |
| city     | text | yes      | Customer city |

### categories
| Column | Type | Required | Notes |
|--------|------|----------|-------|
| name   | text | yes      | Unique category name |

### products
| Column           | Type | Required | Notes |
|------------------|------|----------|-------|
| name             | text | yes      | Product display name |
| category         | text | yes      | Must match a `categories.name` value |
| unit_price_cents | int  | yes      | Price in cents, must be > 0 |

### orders
| Column     | Type | Required | Notes |
|------------|------|----------|-------|
| order_id   | text | yes      | Unique order identifier |
| customer   | text | yes      | Must match a `customers.name` value |
| status     | text | yes      | e.g. completed, pending, cancelled |
| created_at | date | yes      | Date the order was placed (e.g. 2026-01-15) |

### order_items
| Column           | Type | Required | Notes |
|------------------|------|----------|-------|
| order_id         | text | yes      | Must match an `orders.order_id` value |
| product          | text | yes      | Must match a `products.name` value |
| quantity         | int  | yes      | Must be > 0 |
| unit_price_cents | int  | yes      | Price in cents, must be > 0 |

## CSV bundle format

Upload five files named:
- `customers.csv`
- `categories.csv`
- `products.csv`
- `orders.csv`
- `order_items.csv`

Each file must have column headers in the first row. File names are matched
case-insensitively (stem only — `Customers.CSV` works).

## Excel workbook format

Upload a single `.xlsx` file with five sheets named:
- `customers`
- `categories`
- `products`
- `orders`
- `order_items`

Sheet names are matched case-insensitively. Each sheet must have column
headers in the first row.

**Requirement:** Excel import requires the `openpyxl` Python package.
Install it with `pip install openpyxl`.

## Example templates

The sidebar includes downloadable example templates (CSV zip and Excel
workbook) that contain sample data matching the required format. Download
one, replace the sample rows with your own data, and import.

## Encoding and delimiter support

CSV files do not need to be UTF-8 with comma delimiters. The import pipeline
tries four encodings and three delimiters automatically:

| Encoding  | Notes |
|-----------|-------|
| UTF-8     | Default, tried first |
| UTF-8 BOM | Windows-exported CSVs with `\xEF\xBB\xBF` byte-order mark |
| CP1252    | Common Windows encoding (curly quotes, accented characters) |
| Latin-1   | ISO 8859-1 fallback for Western European characters |

| Delimiter  | Notes |
|------------|-------|
| Comma (`,`)    | Default, tried first |
| Semicolon (`;`) | Common in European CSV exports |
| Tab (`\t`)     | TSV files with `.csv` extension |

When a non-default encoding or delimiter is detected, the Smart Upload
panel shows an informational note (e.g. "Encoding: cp1252" or
"Delimiter: semicolon").

## Northwind-style workbooks

Excel workbooks with Northwind-style structure (sheets like `customers`,
`categories`, `products`, `orders`, `ordersdetails`) are auto-detected.
The adapter handles:

- **Column aliasing** — `CustomerName` → `name`, `OrderDate` → `created_at`, etc.
- **ID resolution** — `CustomerID`, `ProductID`, `CategoryID` are resolved to
  display names via companion sheets.
- **Price derivation** — If order details lacks a price column, unit prices
  are derived from the products sheet via `ProductID` join.
- **Dollar-to-cents conversion** — Dollar values are multiplied by 100.
- **Default status** — Missing `status` column defaults to `"completed"`.

## Multi-file assembly

When individual partial files are uploaded (e.g. just `customers.csv`),
Smart Upload detects the entity and offers a **Stage** button. Staged files
accumulate in an **Assembly Workspace** panel that shows:

- Coverage progress (N/5 entities, with a progress bar)
- Which required entities are still missing
- Remove buttons per staged entity
- An **Import** button once the minimum required entities are present

Minimum required entities: `orders`, `order_items`, `products`.
Optional entities (`customers`, `categories`) can be synthesized if absent.

## Reference and auxiliary files

Files that don't match the reporting model are classified:

| Category | Example files | Behaviour |
|----------|--------------|-----------|
| **Metadata** | `data_dictionary.csv`, `readme.csv` | Preview only, labeled as metadata |
| **Auxiliary** | `employees.csv`, `shippers.csv`, `suppliers.csv` | Preview only, labeled as auxiliary (Northwind tables excluded from reporting model) |
| **Unknown** | `random_data.csv` | Preview only, generic message |

## Validation

The import pipeline validates your data before loading:

1. **Entity check** — all five entities must be present.
2. **Column check** — required columns must exist.
3. **Null check** — non-nullable columns cannot contain blanks.
4. **Type check** — integers must be numeric, dates must be parseable.
5. **Positive-value check** — `unit_price_cents` and `quantity` must be > 0.
6. **Referential check** — foreign-key-like relationships are validated:
   - `products.category` → `categories.name`
   - `orders.customer` → `customers.name`
   - `order_items.order_id` → `orders.order_id`
   - `order_items.product` → `products.name`

If validation fails, the import is blocked and the app shows which issues
to fix. Warnings (e.g. blank text fields) do not block the import.

## Current limitations

- **Arbitrary spreadsheets are not supported.** The import path expects the
  canonical five-entity reporting model described above. A single flat
  spreadsheet (e.g. `Sheet1` with mixed data) will be rejected.
- **One dataset at a time.** Importing replaces the current dataset entirely
  (TRUNCATE + reload). There is no merge or append mode.
- **No auth.** Any user can import data. There is no access control.
- **Money in cents.** All monetary values must be in cents (integers), not
  dollars. The dashboard converts to dollars for display. Northwind-style
  dollar values are auto-converted by the adapter.
- **Assembly workspace is session-scoped.** Staged files are lost if the
  browser tab is closed. There is no server-side persistence.

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Excel import requires openpyxl" | Missing Python package | `pip install openpyxl` |
| "This workbook is not compatible" | No sheets match canonical entities | Use a workbook with sheets named customers, categories, etc. |
| "Workbook is missing required sheets" | Some sheets present, others not | Add the missing sheets |
| "No recognised CSV files" | File names don't match entity names | Rename files to customers.csv, categories.csv, etc. |
| "Missing required entity" | Entity file/sheet not included | Add the missing entity |
| "Missing required column" | A required column is absent | Add the column to your data |
| "null value(s) in non-nullable column" | Blanks in required fields | Fill in the missing values |
| "cannot be converted to integer" | Text in a numeric column | Fix the non-numeric values |
| "cannot be parsed as dates" | Invalid date format | Use ISO dates (YYYY-MM-DD) |
| "value(s) <= 0" | Negative or zero price/quantity | Use positive integers |
| "value(s) not found in …" | Broken reference | Ensure referenced names exist in the parent entity |
