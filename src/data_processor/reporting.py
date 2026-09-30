"""Processing summary data and rendering."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ProcessingSummary:
    original_row_count: int
    final_row_count: int
    duplicates_removed: int
    empty_rows_removed: int
    missing_values_before: int
    missing_values_after: int
    columns_processed: list[str]
    output_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_summary(
    original: pd.DataFrame,
    final: pd.DataFrame,
    duplicates_removed: int,
    empty_rows_removed: int,
    output_path: str | Path,
) -> ProcessingSummary:
    return ProcessingSummary(
        original_row_count=len(original),
        final_row_count=len(final),
        duplicates_removed=duplicates_removed,
        empty_rows_removed=empty_rows_removed,
        missing_values_before=int(original.isna().sum().sum()),
        missing_values_after=int(final.isna().sum().sum()),
        columns_processed=[str(column) for column in final.columns],
        output_path=str(output_path),
    )


def build_count_summary(
    *,
    original_row_count: int,
    final_row_count: int,
    duplicates_removed: int,
    empty_rows_removed: int,
    missing_values_before: int,
    missing_values_after: int,
    columns_processed: list[str],
    output_path: str | Path,
) -> ProcessingSummary:
    return ProcessingSummary(
        original_row_count=original_row_count,
        final_row_count=final_row_count,
        duplicates_removed=duplicates_removed,
        empty_rows_removed=empty_rows_removed,
        missing_values_before=missing_values_before,
        missing_values_after=missing_values_after,
        columns_processed=columns_processed,
        output_path=str(output_path),
    )


def format_summary(summary: ProcessingSummary) -> str:
    """Render a summary as human-readable JSON."""
    return json.dumps(summary.to_dict(), indent=2, ensure_ascii=False)
