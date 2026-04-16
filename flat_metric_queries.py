"""Query functions for the flat-metric analytics profile.

Each function returns a pandas DataFrame (or scalar).
All SQL is parameterized where filters are involved.
"""

from __future__ import annotations

import pandas as pd

from db import run_query


# ── Filter helpers ──────────────────────────────────────────────

def get_fm_entities() -> list[str]:
    """Return a sorted list of distinct entity values."""
    df = run_query("SELECT DISTINCT entity FROM flat_metrics ORDER BY entity;")
    return df["entity"].tolist()


def get_fm_metric_names() -> list[str]:
    """Return a sorted list of distinct metric names."""
    df = run_query("SELECT DISTINCT metric_name FROM flat_metrics ORDER BY metric_name;")
    return df["metric_name"].tolist()


def get_fm_year_range() -> tuple[int, int] | None:
    """Return (min_year, max_year) or None if no year data exists."""
    df = run_query(
        "SELECT MIN(year) AS mn, MAX(year) AS mx "
        "FROM flat_metrics WHERE year IS NOT NULL;"
    )
    if df.empty or pd.isna(df.iloc[0]["mn"]):
        return None
    return int(df.iloc[0]["mn"]), int(df.iloc[0]["mx"])


# ── WHERE-clause builder ────────────────────────────────────────

def _build_fm_filters(
    entities: list[str] | None = None,
    metric_names: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> tuple[str, list]:
    """Return (where_clause, params) for the flat-metric filter set."""
    clauses: list[str] = []
    params: list = []

    if entities:
        clauses.append("entity = ANY(%s)")
        params.append(entities)
    if metric_names:
        clauses.append("metric_name = ANY(%s)")
        params.append(metric_names)
    if year_from is not None:
        clauses.append("year >= %s")
        params.append(year_from)
    if year_to is not None:
        clauses.append("year <= %s")
        params.append(year_to)

    where = " AND ".join(clauses)
    if where:
        where = "WHERE " + where
    return where, params


# ── KPIs ────────────────────────────────────────────────────────

def get_fm_kpis(**filters) -> pd.DataFrame:
    """Return a single-row DataFrame with total_rows, unique_entities, metric_count, year_span, avg_score."""
    where, params = _build_fm_filters(**filters)
    sql = f"""
    SELECT
      COUNT(*)                        AS total_rows,
      COUNT(DISTINCT entity)          AS unique_entities,
      COUNT(DISTINCT metric_name)     AS metric_count,
      MIN(year)                       AS min_year,
      MAX(year)                       AS max_year,
      ROUND(AVG(score)::numeric, 1)   AS avg_score
    FROM flat_metrics
    {where};
    """
    return run_query(sql, tuple(params) if params else None)


# ── Rankings ────────────────────────────────────────────────────

def get_fm_ranking(
    metric_name: str,
    limit: int = 10,
    **filters,
) -> pd.DataFrame:
    """Entities ranked by metric_value for a specific metric (descending)."""
    where, params = _build_fm_filters(**filters)
    # Add metric_name filter
    if where:
        where += " AND metric_name = %s"
    else:
        where = "WHERE metric_name = %s"
    params.append(metric_name)

    sql = f"""
    SELECT
      entity,
      metric_value,
      year,
      score,
      rank
    FROM flat_metrics
    {where}
    ORDER BY metric_value DESC
    LIMIT %s;
    """
    params.append(limit)
    return run_query(sql, tuple(params))


# ── Comparison bar chart ────────────────────────────────────────

def get_fm_comparison(metric_name: str, **filters) -> pd.DataFrame:
    """All entities for one metric, sorted by value (for bar charts)."""
    where, params = _build_fm_filters(**filters)
    if where:
        where += " AND metric_name = %s"
    else:
        where = "WHERE metric_name = %s"
    params.append(metric_name)

    sql = f"""
    SELECT
      entity,
      metric_value,
      year
    FROM flat_metrics
    {where}
    ORDER BY metric_value DESC;
    """
    return run_query(sql, tuple(params))


# ── Trend over years ───────────────────────────────────────────

def get_fm_trend(metric_name: str, **filters) -> pd.DataFrame:
    """Metric values over years for selected entities."""
    where, params = _build_fm_filters(**filters)
    if where:
        where += " AND metric_name = %s AND year IS NOT NULL"
    else:
        where = "WHERE metric_name = %s AND year IS NOT NULL"
    params.append(metric_name)

    sql = f"""
    SELECT
      entity,
      year,
      metric_value
    FROM flat_metrics
    {where}
    ORDER BY year, entity;
    """
    return run_query(sql, tuple(params))


# ── Detail table ────────────────────────────────────────────────

def get_fm_detail(**filters) -> pd.DataFrame:
    """Full filtered flat-metric table."""
    where, params = _build_fm_filters(**filters)
    sql = f"""
    SELECT
      entity,
      metric_name,
      metric_value,
      year,
      score,
      rank
    FROM flat_metrics
    {where}
    ORDER BY entity, metric_name, year;
    """
    return run_query(sql, tuple(params) if params else None)


# ── Entity detail queries ───────────────────────────────────────


def get_fm_entity_summary(entity: str) -> pd.DataFrame:
    """Summary stats for a single entity across all metrics and years."""
    sql = """
    SELECT
      COUNT(*)                    AS total_rows,
      COUNT(DISTINCT metric_name) AS metric_count,
      MIN(year)                   AS min_year,
      MAX(year)                   AS max_year,
      ROUND(AVG(score)::numeric, 1)  AS avg_score
    FROM flat_metrics
    WHERE entity = %s;
    """
    return run_query(sql, (entity,))


def get_fm_entity_metrics(entity: str) -> pd.DataFrame:
    """All metric values for a single entity, ordered by metric and year."""
    sql = """
    SELECT
      metric_name,
      metric_value,
      year,
      score,
      rank
    FROM flat_metrics
    WHERE entity = %s
    ORDER BY metric_name, year;
    """
    return run_query(sql, (entity,))


def get_fm_entity_trend(entity: str, metric_name: str) -> pd.DataFrame:
    """Year-over-year values for one entity + one metric."""
    sql = """
    SELECT year, metric_value, score, rank
    FROM flat_metrics
    WHERE entity = %s AND metric_name = %s AND year IS NOT NULL
    ORDER BY year;
    """
    return run_query(sql, (entity, metric_name))


def get_fm_entity_comparison(entity: str, year: int | None = None) -> pd.DataFrame:
    """All metrics for an entity in a given year (or latest)."""
    if year is not None:
        sql = """
        SELECT metric_name, metric_value, score, rank
        FROM flat_metrics
        WHERE entity = %s AND year = %s
        ORDER BY metric_name;
        """
        return run_query(sql, (entity, year))
    # Latest year per metric
    sql = """
    SELECT DISTINCT ON (metric_name)
      metric_name, metric_value, year, score, rank
    FROM flat_metrics
    WHERE entity = %s AND year IS NOT NULL
    ORDER BY metric_name, year DESC;
    """
    return run_query(sql, (entity,))


# ── Metric explorer queries ─────────────────────────────────────


def get_fm_metric_summary(metric_name: str) -> pd.DataFrame:
    """Summary stats for a single metric across all entities and years."""
    sql = """
    SELECT
      COUNT(*)                  AS total_rows,
      COUNT(DISTINCT entity)    AS entity_count,
      MIN(year)                 AS min_year,
      MAX(year)                 AS max_year,
      ROUND(AVG(metric_value)::numeric, 2) AS avg_value,
      ROUND(MIN(metric_value)::numeric, 2) AS min_value,
      ROUND(MAX(metric_value)::numeric, 2) AS max_value
    FROM flat_metrics
    WHERE metric_name = %s;
    """
    return run_query(sql, (metric_name,))


def get_fm_metric_top_entities(
    metric_name: str, limit: int = 10, year: int | None = None
) -> pd.DataFrame:
    """Top entities by metric_value for a given metric (descending)."""
    if year is not None:
        sql = """
        SELECT entity, metric_value, year, score, rank
        FROM flat_metrics
        WHERE metric_name = %s AND year = %s
        ORDER BY metric_value DESC
        LIMIT %s;
        """
        return run_query(sql, (metric_name, year, limit))
    sql = """
    SELECT DISTINCT ON (entity)
      entity, metric_value, year, score, rank
    FROM flat_metrics
    WHERE metric_name = %s AND year IS NOT NULL
    ORDER BY entity, year DESC;
    """
    df = run_query(sql, (metric_name,))
    return df.sort_values("metric_value", ascending=False).head(limit)


def get_fm_metric_bottom_entities(
    metric_name: str, limit: int = 10, year: int | None = None
) -> pd.DataFrame:
    """Bottom entities by metric_value for a given metric (ascending)."""
    if year is not None:
        sql = """
        SELECT entity, metric_value, year, score, rank
        FROM flat_metrics
        WHERE metric_name = %s AND year = %s
        ORDER BY metric_value ASC
        LIMIT %s;
        """
        return run_query(sql, (metric_name, year, limit))
    sql = """
    SELECT DISTINCT ON (entity)
      entity, metric_value, year, score, rank
    FROM flat_metrics
    WHERE metric_name = %s AND year IS NOT NULL
    ORDER BY entity, year DESC;
    """
    df = run_query(sql, (metric_name,))
    return df.sort_values("metric_value", ascending=True).head(limit)


def get_fm_metric_trend_avg(metric_name: str) -> pd.DataFrame:
    """Average metric_value per year across all entities."""
    sql = """
    SELECT
      year,
      ROUND(AVG(metric_value)::numeric, 2) AS avg_value,
      COUNT(DISTINCT entity)                AS entity_count
    FROM flat_metrics
    WHERE metric_name = %s AND year IS NOT NULL
    GROUP BY year
    ORDER BY year;
    """
    return run_query(sql, (metric_name,))


def get_fm_metric_detail(metric_name: str, **filters) -> pd.DataFrame:
    """All rows for a specific metric with optional filters."""
    where, params = _build_fm_filters(**filters)
    if where:
        where += " AND metric_name = %s"
    else:
        where = "WHERE metric_name = %s"
    params.append(metric_name)

    sql = f"""
    SELECT entity, metric_value, year, score, rank
    FROM flat_metrics
    {where}
    ORDER BY entity, year;
    """
    return run_query(sql, tuple(params))


def get_fm_metric_outliers(metric_name: str, year: int | None = None) -> pd.DataFrame:
    """Return entities with values for IQR-based outlier detection."""
    if year is not None:
        sql = """
        SELECT entity, metric_value, year, score, rank
        FROM flat_metrics
        WHERE metric_name = %s AND year = %s
        ORDER BY metric_value DESC;
        """
        df = run_query(sql, (metric_name, year))
    else:
        sql = """
        SELECT DISTINCT ON (entity)
          entity, metric_value, year, score, rank
        FROM flat_metrics
        WHERE metric_name = %s AND year IS NOT NULL
        ORDER BY entity, year DESC;
        """
        df = run_query(sql, (metric_name,))
    return df
