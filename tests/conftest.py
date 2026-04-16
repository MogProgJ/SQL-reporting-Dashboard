"""Shared pytest configuration."""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that require a running seeded Postgres instance",
    )


# Auto-skip integration tests when DATABASE_URL is absent
def pytest_collection_modifyitems(config, items):
    if os.getenv("DATABASE_URL"):
        return
    skip_marker = pytest.mark.skip(
        reason="DATABASE_URL not set — skipping integration tests",
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
