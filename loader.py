"""Load normalized DataFrames into the canonical reporting tables.

Replaces the current dataset atomically inside a single transaction.
The Postgres schema (created by seed.sql) is reused — tables are
truncated and repopulated so the dashboard queries stay unchanged.
"""

from __future__ import annotations

import pandas as pd
import psycopg2

from db import get_connection


def load_into_db(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace reporting data with the contents of *frames*.

    Returns a dict of entity_name → rows inserted.
    Raises on failure (transaction is rolled back automatically).
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Truncate in reverse-FK order
                cur.execute(
                    "TRUNCATE order_items, orders, products, categories, customers "
                    "RESTART IDENTITY CASCADE;"
                )

                counts: dict[str, int] = {}

                # ── customers ────────────────────────────────
                if "customers" in frames:
                    counts["customers"] = _load_customers(cur, frames["customers"])

                # ── categories ───────────────────────────────
                if "categories" in frames:
                    counts["categories"] = _load_categories(cur, frames["categories"])

                # ── products ─────────────────────────────────
                if "products" in frames:
                    counts["products"] = _load_products(cur, frames["products"])

                # ── orders ───────────────────────────────────
                if "orders" in frames:
                    counts["orders"] = _load_orders(cur, frames["orders"])

                # ── order_items ──────────────────────────────
                if "order_items" in frames:
                    counts["order_items"] = _load_order_items(cur, frames["order_items"])

        return counts
    finally:
        conn.close()


# ── Per-entity loaders ──────────────────────────────────────────

def _load_customers(cur, df: pd.DataFrame) -> int:
    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO customers (name, segment, city) VALUES (%s, %s, %s);",
            (str(row["name"]), str(row.get("segment", "Standard")), str(row.get("city", "Unknown"))),
        )
    return len(df)


def _load_categories(cur, df: pd.DataFrame) -> int:
    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO categories (name) VALUES (%s);",
            (str(row["name"]),),
        )
    return len(df)


def _load_products(cur, df: pd.DataFrame) -> int:
    # Build category name → id lookup
    cur.execute("SELECT id, name FROM categories;")
    cat_map = {name: cid for cid, name in cur.fetchall()}

    for _, row in df.iterrows():
        cat_name = str(row["category"])
        cat_id = cat_map.get(cat_name)
        if cat_id is None:
            raise ValueError(f"Product '{row['name']}' references unknown category '{cat_name}'")
        cur.execute(
            "INSERT INTO products (name, category_id, unit_price_cents) VALUES (%s, %s, %s);",
            (str(row["name"]), cat_id, int(row["unit_price_cents"])),
        )
    return len(df)


def _load_orders(cur, df: pd.DataFrame) -> int:
    # Build customer name → id lookup
    cur.execute("SELECT id, name FROM customers;")
    cust_map = {name: cid for cid, name in cur.fetchall()}

    for _, row in df.iterrows():
        cust_name = str(row["customer"])
        cust_id = cust_map.get(cust_name)
        if cust_id is None:
            raise ValueError(f"Order '{row['order_id']}' references unknown customer '{cust_name}'")
        cur.execute(
            "INSERT INTO orders (id, customer_id, status, created_at) VALUES (%s, %s, %s, %s);",
            (int(row["order_id"]), cust_id, str(row.get("status", "completed")), row["created_at"]),
        )

    # Reset sequence to max id
    cur.execute("SELECT setval('orders_id_seq', COALESCE(MAX(id), 1)) FROM orders;")
    return len(df)


def _load_order_items(cur, df: pd.DataFrame) -> int:
    # Build product name → id lookup
    cur.execute("SELECT id, name FROM products;")
    prod_map = {name: pid for pid, name in cur.fetchall()}

    for _, row in df.iterrows():
        prod_name = str(row["product"])
        prod_id = prod_map.get(prod_name)
        if prod_id is None:
            raise ValueError(f"Order item references unknown product '{prod_name}'")
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) "
            "VALUES (%s, %s, %s, %s);",
            (int(row["order_id"]), prod_id, int(row["quantity"]), int(row["unit_price_cents"])),
        )
    return len(df)


# ── Flat-metric profile loader ──────────────────────────────────

def load_flat_metrics(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace flat_metrics table with the contents of *frames*.

    Returns a dict of entity_name → rows inserted.
    Raises on failure (transaction is rolled back automatically).
    """
    df = frames.get("flat_metrics")
    if df is None or df.empty:
        return {"flat_metrics": 0}

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE flat_metrics RESTART IDENTITY;")
                for _, row in df.iterrows():
                    cur.execute(
                        "INSERT INTO flat_metrics "
                        "(entity, metric_name, metric_value, year, score, rank) "
                        "VALUES (%s, %s, %s, %s, %s, %s);",
                        (
                            str(row["entity"]),
                            str(row["metric_name"]),
                            float(row["metric_value"]),
                            int(row["year"]) if pd.notna(row.get("year")) else None,
                            float(row["score"]) if pd.notna(row.get("score")) else None,
                            int(row["rank"]) if pd.notna(row.get("rank")) else None,
                        ),
                    )
        return {"flat_metrics": len(df)}
    finally:
        conn.close()
