# SQL Reporting Dashboard

A lightweight analytics app that turns raw tabular data into clean dashboards.

It supports two analysis modes:

- **Order Reporting** — for order, customer, product, and category data
- **Flat Metric** — for entity + metric style datasets such as country, year, value tables

The app is built to help you:
- inspect uploaded files
- detect their structure
- import or adapt supported formats
- explore the data through dashboards, drilldowns, filters, and exports

---

## What the app does

This project takes structured data and turns it into a usable reporting interface.

Depending on the dataset, it can show:

- KPI cards
- trends over time
- top lists
- drilldowns
- anomaly views
- detail tables
- CSV / JSON exports

It also includes a **Smart Upload** flow that can:

- preview uploaded files
- detect whether they are importable
- classify partial datasets
- guide you toward the right import path

---

## Supported import formats

### Order Reporting
You can import Order Reporting data in these ways:

- **CSV bundle**
  - `customers.csv`
  - `categories.csv`
  - `products.csv`
  - `orders.csv`
  - `order_items.csv`

- **Excel workbook**
  - one sheet per entity:
    - `customers`
    - `categories`
    - `products`
    - `orders`
    - `order_items`

- **Smart Upload**
  - CSV
  - Excel
  - ZIP
  - supported near-match formats may be previewed, staged, or adapted before import

### Flat Metric
You can import Flat Metric data as:

- a flat CSV
- an Excel workbook
- supported wide metric spreadsheets through Smart Upload, when recognized by the adapter flow

---

## Run the app

### Requirements

- **Docker**
- **Python 3.10+**

---

### Option 1 — easiest local run

```bash
docker compose up -d
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
Get-Content .\seed\seed.sql -Raw | docker exec -i reporting_db psql -U postgres -d reporting
python -m streamlit run app.py
````

Open:

```text
http://localhost:8501
```

---

### Option 2 — full Docker run

```bash
docker compose --profile app up --build
```

Open:

```text
http://localhost:8501
```

---

## How to use it

1. Start the app
2. Choose a profile:

   * **Order Reporting**
   * **Flat Metric**
3. Use one of the import paths:

   * **Demo seed**
   * **Upload CSV bundle**
   * **Upload Excel workbook**
   * **Smart Upload**
4. If using **Smart Upload**:

   * preview the file
   * follow the suggested import path
   * stage partial datasets if needed
   * import once the dataset is ready
5. Explore the dashboard using filters, drilldowns, and exports

---

## Notes

* The app ships with demo data for both supported profiles
* Smart Upload does **not** guarantee that every random file can be imported directly
* Some files may be:

  * preview-only
  * partial and stageable
  * importable via adapter
  * fully importable

License - MIT
