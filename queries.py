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
) -> tuple[str, list]:
    """Return (where_clause, params) for the common filter set.

    Assumes the query already aliases:
      o  = orders
      c  = customers
      cat = categories
      p  = products
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


# ── Category breakdown ──────────────────────────────────────────

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
      oi.quantity * oi.unit_price_cents      AS line_total_cents
    {_BASE_JOIN}
    {where}
    ORDER BY o.created_at DESC, o.id, oi.id;
    """
    return run_query(sql, tuple(params) if params else None)
