"""Validate DataFrames against the canonical reporting model.

Pure functions — no DB or I/O.  Returns a list of ValidationIssue objects.
"""

from __future__ import annotations

import pandas as pd

from canonical_model import CANONICAL_ENTITIES, ENTITY_MAP, EntitySpec
from dataset_profile import ValidationIssue


# ── Public API ──────────────────────────────────────────────────


def validate_dataframes(
    frames: dict[str, pd.DataFrame],
) -> list[ValidationIssue]:
    """Validate a full set of entity DataFrames against the canonical model.

    *frames* maps entity name → DataFrame.
    Returns all issues found (errors + warnings).
    """
    issues: list[ValidationIssue] = []

    # 1. Required entities present
    for spec in CANONICAL_ENTITIES:
        if spec.name not in frames:
            issues.append(
                ValidationIssue(
                    entity=spec.name,
                    column="",
                    message=f"Missing required entity '{spec.name}'.",
                )
            )
            continue

        df = frames[spec.name]

        if df.empty:
            issues.append(
                ValidationIssue(
                    entity=spec.name,
                    column="",
                    message="Entity has zero rows.",
                )
            )
            continue

        issues.extend(_validate_entity(spec, df))

    # 2. Cross-entity referential checks (only if both sides present)
    issues.extend(_validate_references(frames))

    return issues


# ── Internal helpers ────────────────────────────────────────────


def _validate_entity(spec: EntitySpec, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Required columns
    actual = set(df.columns)
    for col in spec.columns:
        if col.name not in actual:
            issues.append(
                ValidationIssue(
                    entity=spec.name,
                    column=col.name,
                    message=f"Missing required column '{col.name}'.",
                )
            )

    # Per-column type/content checks (only for columns that exist)
    for col in spec.columns:
        if col.name not in actual:
            continue
        series = df[col.name]

        # Nulls
        if not col.nullable and series.isna().any():
            n = int(series.isna().sum())
            issues.append(
                ValidationIssue(
                    entity=spec.name,
                    column=col.name,
                    message=f"{n} null value(s) in non-nullable column.",
                )
            )

        # Type-specific checks
        if col.dtype == "int":
            issues.extend(_check_int_column(spec.name, col.name, series))
        elif col.dtype == "date":
            issues.extend(_check_date_column(spec.name, col.name, series))
        elif col.dtype == "text":
            issues.extend(_check_text_column(spec.name, col.name, series))

    # Positive-value constraints for price/quantity columns
    for col_name in ("unit_price_cents", "quantity"):
        if col_name in actual:
            issues.extend(
                _check_positive(spec.name, col_name, df[col_name])
            )

    return issues


def _check_int_column(
    entity: str, col: str, series: pd.Series
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    non_null = series.dropna()
    if non_null.empty:
        return issues
    try:
        pd.to_numeric(non_null, errors="raise")
    except (ValueError, TypeError):
        bad = pd.to_numeric(non_null, errors="coerce")
        n = int(bad.isna().sum())
        issues.append(
            ValidationIssue(
                entity=entity,
                column=col,
                message=f"{n} value(s) cannot be converted to integer.",
            )
        )
    return issues


def _check_date_column(
    entity: str, col: str, series: pd.Series
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    non_null = series.dropna()
    if non_null.empty:
        return issues
    coerced = pd.to_datetime(non_null, errors="coerce", format="mixed")
    bad_count = int(coerced.isna().sum())
    if bad_count:
        issues.append(
            ValidationIssue(
                entity=entity,
                column=col,
                message=f"{bad_count} value(s) cannot be parsed as dates.",
            )
        )
    return issues


def _check_text_column(
    entity: str, col: str, series: pd.Series
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    non_null = series.dropna()
    if non_null.empty:
        return issues
    # Warn on empty strings
    empty_count = int((non_null.astype(str).str.strip() == "").sum())
    if empty_count:
        issues.append(
            ValidationIssue(
                entity=entity,
                column=col,
                message=f"{empty_count} blank/empty string(s).",
                severity="warning",
            )
        )
    return issues


def _check_positive(
    entity: str, col: str, series: pd.Series
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return issues
    bad = int((numeric <= 0).sum())
    if bad:
        issues.append(
            ValidationIssue(
                entity=entity,
                column=col,
                message=f"{bad} value(s) <= 0 (must be positive).",
            )
        )
    return issues


def _validate_references(
    frames: dict[str, pd.DataFrame],
) -> list[ValidationIssue]:
    """Check foreign-key-like relationships across entities."""
    issues: list[ValidationIssue] = []

    # products.category → categories.name
    if "products" in frames and "categories" in frames:
        if "category" in frames["products"].columns and "name" in frames["categories"].columns:
            prod_cats = set(frames["products"]["category"].dropna().unique())
            cat_names = set(frames["categories"]["name"].dropna().unique())
            orphans = prod_cats - cat_names
            if orphans:
                issues.append(
                    ValidationIssue(
                        entity="products",
                        column="category",
                        message=(
                            f"{len(orphans)} category value(s) not found in "
                            f"categories: {sorted(orphans)[:5]}"
                        ),
                    )
                )

    # orders.customer → customers.name
    if "orders" in frames and "customers" in frames:
        if "customer" in frames["orders"].columns and "name" in frames["customers"].columns:
            order_custs = set(frames["orders"]["customer"].dropna().unique())
            cust_names = set(frames["customers"]["name"].dropna().unique())
            orphans = order_custs - cust_names
            if orphans:
                issues.append(
                    ValidationIssue(
                        entity="orders",
                        column="customer",
                        message=(
                            f"{len(orphans)} customer value(s) not found in "
                            f"customers: {sorted(orphans)[:5]}"
                        ),
                    )
                )

    # order_items.order_id → orders.order_id
    if "order_items" in frames and "orders" in frames:
        if "order_id" in frames["order_items"].columns and "order_id" in frames["orders"].columns:
            item_ids = set(frames["order_items"]["order_id"].dropna().astype(str).unique())
            order_ids = set(frames["orders"]["order_id"].dropna().astype(str).unique())
            orphans = item_ids - order_ids
            if orphans:
                issues.append(
                    ValidationIssue(
                        entity="order_items",
                        column="order_id",
                        message=(
                            f"{len(orphans)} order_id value(s) not found in "
                            f"orders: {sorted(orphans)[:5]}"
                        ),
                    )
                )

    # order_items.product → products.name
    if "order_items" in frames and "products" in frames:
        if "product" in frames["order_items"].columns and "name" in frames["products"].columns:
            item_prods = set(frames["order_items"]["product"].dropna().unique())
            prod_names = set(frames["products"]["name"].dropna().unique())
            orphans = item_prods - prod_names
            if orphans:
                issues.append(
                    ValidationIssue(
                        entity="order_items",
                        column="product",
                        message=(
                            f"{len(orphans)} product value(s) not found in "
                            f"products: {sorted(orphans)[:5]}"
                        ),
                    )
                )

    return issues
