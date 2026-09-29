"""Dataset inspection and cleaning operations."""

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd

MissingStrategy = Literal["keep", "drop", "fill"]


@dataclass(frozen=True)
class CleaningStats:
    """Counts describing rows removed during cleaning."""

    empty_rows_removed: int
    duplicates_removed: int


def normalize_column_name(name: object) -> str:
    """Convert a column label to lowercase snake_case."""
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower()).strip("_")
    return normalized or "column"


def _normalize_column_names(columns: pd.Index) -> list[str]:
    names: list[str] = []
    occurrences: dict[str, int] = {}
    for column in columns:
        base = normalize_column_name(column)
        occurrences[base] = occurrences.get(base, 0) + 1
        names.append(base if occurrences[base] == 1 else f"{base}_{occurrences[base]}")
    return names


def inspect_dataset(dataframe: pd.DataFrame) -> dict[str, object]:
    """Return basic dataset shape, schema, missing-value, and duplicate metrics."""
    return {
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": list(dataframe.columns),
        "data_types": {
            str(column): str(dtype) for column, dtype in dataframe.dtypes.items()
        },
        "missing_values": {
            str(column): int(count) for column, count in dataframe.isna().sum().items()
        },
        "duplicate_rows": int(dataframe.duplicated().sum()),
    }


def clean_data(
    dataframe: pd.DataFrame,
    missing_strategy: MissingStrategy = "keep",
    fill_value: object | None = None,
) -> tuple[pd.DataFrame, CleaningStats]:
    """Trim text, normalize columns, remove empty/duplicate rows, and handle nulls."""
    if missing_strategy not in {"keep", "drop", "fill"}:
        raise ValueError(f"Unknown missing-value strategy: {missing_strategy}")
    if missing_strategy == "fill" and fill_value is None:
        raise ValueError("A fill_value is required when missing_strategy is 'fill'.")

    cleaned = dataframe.copy()
    cleaned.columns = _normalize_column_names(cleaned.columns)
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
        cleaned[column] = cleaned[column].replace("", pd.NA)

    original_count = len(cleaned)
    cleaned = cleaned.dropna(how="all")
    empty_rows_removed = original_count - len(cleaned)

    before_duplicates = len(cleaned)
    cleaned = cleaned.drop_duplicates()
    duplicates_removed = before_duplicates - len(cleaned)

    if missing_strategy == "drop":
        cleaned = cleaned.dropna()
    elif missing_strategy == "fill":
        cleaned = cleaned.fillna(fill_value)

    return cleaned.reset_index(drop=True), CleaningStats(
        empty_rows_removed=empty_rows_removed,
        duplicates_removed=duplicates_removed,
    )
