"""Canonical model for the Flat Metric analytics profile.

Defines a single entity — ``flat_metrics`` — that captures generic
entity-by-metric-by-year data.  Suitable for country statistics,
university rankings, city indicators, etc.
"""

from __future__ import annotations

from canonical_model import ColumnSpec, EntitySpec

FLAT_METRICS = EntitySpec(
    name="flat_metrics",
    description=(
        "Generic flat table of metrics.  Each row records one metric "
        "value for an entity, optionally for a specific year."
    ),
    natural_key=("entity", "metric_name"),
    columns=(
        ColumnSpec("entity", "text", "The thing being measured (country, school, city, …)"),
        ColumnSpec("metric_name", "text", "What is being measured (GDP, Population, …)"),
        ColumnSpec("metric_value", "float", "The measurement value"),
        ColumnSpec("year", "int", "Year of measurement", nullable=True),
        ColumnSpec("score", "float", "Normalised score (0–100)", nullable=True),
        ColumnSpec("rank", "int", "Explicit ranking position", nullable=True),
    ),
)

FLAT_METRIC_ENTITIES: tuple[EntitySpec, ...] = (FLAT_METRICS,)
FLAT_METRIC_ENTITY_MAP: dict[str, EntitySpec] = {e.name: e for e in FLAT_METRIC_ENTITIES}
