"""Database connection helper.

Provides a thin wrapper around psycopg2 for executing queries and
returning pandas DataFrames. No ORM — just parameterized SQL.
"""

import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")


def get_connection():
    """Return a new psycopg2 connection using DATABASE_URL."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg2.connect(DATABASE_URL)


def run_query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Execute *sql* with optional *params* and return a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def fetch_scalar(sql: str, params: tuple | None = None):
    """Execute *sql* and return the first column of the first row."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None


def table_exists(table_name: str) -> bool:
    """Return True if *table_name* exists in the public schema."""
    val = fetch_scalar(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables"
        "  WHERE table_schema = 'public' AND table_name = %s"
        ");",
        (table_name,),
    )
    return bool(val)
