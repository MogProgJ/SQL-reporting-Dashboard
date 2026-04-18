"""Adapter registry — transforms known near-match file shapes into canonical data.

Each adapter knows how to:
1. Detect whether it can handle a given ``FileProfile``
2. Describe the transformation plan (field mappings, assumptions)
3. Execute the transformation and return canonical DataFrames

The registry is a simple list — no plugin system, no dynamic loading.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pandas as pd

from file_profiler import FileProfile, Importability, ProfileFamily


# ── Transformation plan ─────────────────────────────────────────

@dataclass
class FieldMapping:
    """One source → target column mapping."""
    source: str
    target: str
    transform: str = ""  # brief description, e.g. "dollars → cents"


@dataclass
class AdapterPlan:
    """Describes what an adapter will do before it does it."""
    adapter_name: str
    description: str
    profile_family: ProfileFamily
    field_mappings: list[FieldMapping] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    ignored_sheets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    will_produce: str = ""  # e.g. "Full Order Reporting dataset"


@dataclass
class AdapterResult:
    """Outcome of an adapter transformation."""
    success: bool
    adapter_name: str
    profile_family: ProfileFamily
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    plan: AdapterPlan | None = None
    warnings: list[str] = field(default_factory=list)
    error: str = ""


# ── Base class ──────────────────────────────────────────────────

class BaseAdapter(ABC):
    """Interface for all adapters."""

    name: str = ""
    description: str = ""
    profile_family: ProfileFamily = ProfileFamily.UNKNOWN

    @abstractmethod
    def can_handle(self, profile: FileProfile) -> bool:
        """Return True if this adapter can transform the profiled file."""

    @abstractmethod
    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        """Build a transformation plan (no data modification yet)."""

    @abstractmethod
    def transform(self, buf: BytesIO) -> AdapterResult:
        """Execute the transformation and return canonical frames."""


# ── Registry ────────────────────────────────────────────────────

_ADAPTERS: list[BaseAdapter] = []


def register_adapter(adapter: BaseAdapter) -> None:
    """Add an adapter to the global registry."""
    _ADAPTERS.append(adapter)


def get_adapters() -> list[BaseAdapter]:
    """Return all registered adapters (ordered by registration)."""
    return list(_ADAPTERS)


def find_adapter(profile: FileProfile) -> BaseAdapter | None:
    """Find the first adapter that can handle the profiled file."""
    for adapter in _ADAPTERS:
        if adapter.can_handle(profile):
            return adapter
    return None


def find_adapter_by_name(name: str) -> BaseAdapter | None:
    """Look up an adapter by its name."""
    for adapter in _ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def load_all_adapters() -> None:
    """Import every adapter module so they auto-register.

    Call this once at startup (or in tests) before using the registry.
    Importing this module alone only gives you the base classes and
    registry functions — the concrete adapters live in sub-modules.

    Safe to call repeatedly — clears and re-registers each time.
    """
    import importlib

    _ADAPTERS.clear()

    import adapters.canonical
    import adapters.northwind_order
    import adapters.wide_flat_metric

    importlib.reload(adapters.canonical)
    importlib.reload(adapters.northwind_order)
    importlib.reload(adapters.wide_flat_metric)
