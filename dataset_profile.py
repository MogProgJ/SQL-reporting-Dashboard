"""Dataset profile and import result types.

A DatasetProfile describes how a data source maps into the canonical
reporting model.  The importer pipeline reads a profile, validates the
source, and loads the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SourceType(str, Enum):
    """Supported data-source types."""

    DEMO_SEED = "demo_seed"
    CSV_BUNDLE = "csv_bundle"
    EXCEL_WORKBOOK = "excel_workbook"


@dataclass
class ValidationIssue:
    """One problem found during import validation."""

    entity: str  # canonical entity name or "" for global issues
    column: str  # column name or "" for entity-level issues
    message: str
    severity: str = "error"  # "error" | "warning"

    def __str__(self) -> str:
        loc = self.entity
        if self.column:
            loc = f"{self.entity}.{self.column}"
        return f"[{self.severity.upper()}] {loc}: {self.message}"


@dataclass
class ImportResult:
    """Outcome of one import attempt."""

    success: bool
    source_type: SourceType
    source_label: str  # human-readable name for the dataset
    issues: list[ValidationIssue] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)  # entity → rows loaded

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


@dataclass
class DatasetProfile:
    """Describes the currently-active dataset in the dashboard."""

    source_type: SourceType
    label: str
    row_counts: dict[str, int] = field(default_factory=dict)
