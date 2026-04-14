"""Query functions for the reporting dashboard.

Each function returns a pandas DataFrame (or scalar).
All SQL is parameterized where filters are involved.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from db import run_query

# ── Filter helpers ──────────────────────────────────────────────

def get_customers() -> list[str]:
    """Return a sorted list of all customer names."""
    df = run_query("SELECT name FROM customers ORDER BY name;")
    return df["name"].tolist()


def get_categories() -> list[str]:
    """Return a sorted list of all category names."""
    df = run_query("SELECT name FROM categories ORDER BY name;")
    return df["name"].tolist()


def get_products() -> list[str]:
    """Return a sorted list of all product names."""
    df = run_query("SELECT name FROM products ORDER BY name;")
    return df["name"].tolist()


def get_statuses() -> list[str]:
    """Return a sorted list of distinct order statuses."""
    df = run_query("SELECT DISTINCT status FROM orders ORDER BY status;")
    return df["status"].tolist()


def get_date_range() -> tuple[date, date]:
    """Return (min_date, max_date) from orders."""
    df = run_query("SELECT MIN(created_at)::date AS mn, MAX(created_at)::date AS mx FROM orders;")
    return df.iloc[0]["mn"], df.iloc[0]["mx"]


# ── WHERE-clause builder ────────────────────────────────────────

def _build_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    customers: list[str] | None = None,
    categories: list[str] | None = None,
    products: list[str] | None = None,
    statuses: list[str] | None = None,
) -> tuple[str, list]:
    """Return (where_clause, params) for the common filter set.

    Assumes the query already aliases:
      o   = orders
      c   = customers
      cat = categories
      p   = products
    """
    clauses: list[str] = []
    params: list = []

    if date_from:
        clauses.append("o.created_at >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("o.created_at < %s + INTERVAL '1 day'")
        params.append(date_to)
    if customers:
        clauses.append("c.name = ANY(%s)")
        params.append(customers)
    if categories:
        clauses.append("cat.name = ANY(%s)")
        params.append(categories)
    if products:
        clauses.append("p.name = ANY(%s)")
        params.append(products)
    if statuses:
        clauses.append("o.status = ANY(%s)")
        params.append(statuses)

    where = " AND ".join(clauses)
    if where:
        where = "WHERE " + where
    return where, params


# ── Base FROM join used by most queries ─────────────────────────

_BASE_JOIN = """
  FROM order_items oi
  JOIN orders     o   ON o.id   = oi.order_id
  JOIN customers  c   ON c.id   = o.customer_id
  JOIN products   p   ON p.id   = oi.product_id
  JOIN categories cat ON cat.id = p.category_id
"""

# ── KPIs ────────────────────────────────────────────────────────

def get_kpis(**filters) -> pd.DataFrame:
    """Return a single-row DataFrame with total_revenue, total_orders, avg_order_value, unique_customers."""
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS total_revenue_cents,
      COUNT(DISTINCT o.id)                                AS total_orders,
      CASE WHEN COUNT(DISTINCT o.id) > 0
           THEN SUM(oi.quantity * oi.unit_price_cents) / COUNT(DISTINCT o.id)
           ELSE 0 END                                     AS avg_order_value_cents,
      COUNT(DISTINCT c.id)                                AS unique_customers
    {_BASE_JOIN}
    {where};
    """
    return run_query(sql, tuple(params) if params else None)


# ── Revenue over time ───────────────────────────────────────────

def get_revenue_trend(**filters) -> pd.DataFrame:
    """Daily revenue and order count."""
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      o.created_at::date                             AS order_date,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      COUNT(DISTINCT o.id)                           AS order_count
    {_BASE_JOIN}
    {where}
    GROUP BY o.created_at::date
    ORDER BY order_date;
    """
    return run_query(sql, tuple(params) if params else None)


# ── Top customers ───────────────────────────────────────────────

def get_top_customers(limit: int = 10, **filters) -> pd.DataFrame:
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      c.name                                             AS customer,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      COUNT(DISTINCT o.id)                               AS order_count
    {_BASE_JOIN}
    {where}
    GROUP BY c.name
    ORDER BY revenue_cents DESC
    LIMIT %s;
    """
    params.append(limit)
    return run_query(sql, tuple(params))


# ── Top products ────────────────────────────────────────────────

def get_top_products(limit: int = 10, **filters) -> pd.DataFrame:
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      p.name                                             AS product,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      SUM(oi.quantity)                                   AS units_sold
    {_BASE_JOIN}
    {where}
    GROUP BY p.name
    ORDER BY revenue_cents DESC
    LIMIT %s;
    """
    params.append(limit)
    return run_query(sql, tuple(params))


# ── Category breakdown (with share) ─────────────────────────────

def get_category_breakdown(**filters) -> pd.DataFrame:
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      cat.name                                           AS category,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      SUM(oi.quantity)                                   AS units_sold
    {_BASE_JOIN}
    {where}
    GROUP BY cat.name
    ORDER BY revenue_cents DESC;
    """
    return run_query(sql, tuple(params) if params else None)


# ── Product share of revenue ────────────────────────────────────

def get_product_share(limit: int = 15, **filters) -> pd.DataFrame:
    """Top products with their percentage share of filtered revenue."""
    where, params = _build_filters(**filters)
    sql = f"""
    WITH totals AS (
      SELECT COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS grand_total
      {_BASE_JOIN}
      {where}
    )
    SELECT
      p.name                                              AS product,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      SUM(oi.quantity)                                    AS units_sold,
      ROUND(
        100.0 * SUM(oi.quantity * oi.unit_price_cents)
        / NULLIF((SELECT grand_total FROM totals), 0), 1
      )                                                   AS pct_of_total
    {_BASE_JOIN}
    {where}
    GROUP BY p.name
    ORDER BY revenue_cents DESC
    LIMIT %s;
    """
    params_copy = list(params) + list(params) + [limit]
    return run_query(sql, tuple(params_copy))


# ── Customer drilldown (revenue vs orders) ──────────────────────

def get_customer_drilldown(limit: int = 15, **filters) -> pd.DataFrame:
    """Top customers with revenue, order count, and avg order value."""
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      c.name                                              AS customer,
      c.segment,
      c.city,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
      COUNT(DISTINCT o.id)                                AS order_count,
      CASE WHEN COUNT(DISTINCT o.id) > 0
           THEN SUM(oi.quantity * oi.unit_price_cents) / COUNT(DISTINCT o.id)
           ELSE 0 END                                     AS avg_order_cents
    {_BASE_JOIN}
    {where}
    GROUP BY c.name, c.segment, c.city
    ORDER BY revenue_cents DESC
    LIMIT %s;
    """
    params.append(limit)
    return run_query(sql, tuple(params))


# ── Detail table ────────────────────────────────────────────────

def get_order_detail(**filters) -> pd.DataFrame:
    """Filtered item-level detail for the table / CSV export."""
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      o.id                                  AS order_id,
      o.created_at::date                    AS order_date,
      o.status,
      c.name                                AS customer,
      c.segment,
      c.city,
      p.name                                AS product,
      cat.name                              AS category,
      oi.quantity,
      oi.unit_price_cents,
      oi.quantity * oi.unit_price_cents      AS line_total_cents,
      SUM(oi.quantity * oi.unit_price_cents) OVER (PARTITION BY o.id) AS order_total_cents
    {_BASE_JOIN}
    {where}
    ORDER BY o.created_at DESC, o.id, oi.id;
    """
    return run_query(sql, tuple(params) if params else None)


# ── Anomaly helpers ─────────────────────────────────────────────

def get_order_totals(**filters) -> pd.DataFrame:
    """Per-order revenue totals for anomaly detection."""
    where, params = _build_filters(**filters)
    sql = f"""
    SELECT
      o.id                                              AS order_id,
      o.created_at::date                                AS order_date,
      c.name                                            AS customer,
      COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS order_total_cents
    {_BASE_JOIN}
    {where}
    GROUP BY o.id, o.created_at, c.name
    ORDER BY order_total_cents DESC;
    """
    return run_query(sql, tuple(params) if params else None)


def find_outlier_orders(df: pd.DataFrame, col: str = "order_total_cents") -> pd.DataFrame:
    """Return rows above Q3 + 1.5*IQR (classic box-plot rule)."""
    if df.empty or col not in df.columns:
        return df.head(0)
    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr
    return df[df[col] > threshold].copy()


def find_outlier_days(df: pd.DataFrame, col: str = "revenue_cents") -> pd.DataFrame:
    """Return days above Q3 + 1.5*IQR from a daily-revenue DataFrame."""
    if df.empty or col not in df.columns:
        return df.head(0)
    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr
    return df[df[col] > threshold].copy()
