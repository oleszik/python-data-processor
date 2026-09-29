"""Validation report creation and JSON output."""

import json
from collections import Counter
from pathlib import Path

from data_processor.errors import DataProcessorError
from data_processor.validation import ValidationError


def build_validation_report(total_rows: int, errors: list[ValidationError]) -> dict[str, object]:
    invalid_row_numbers = {error.row for error in errors}
    return {
        "total_rows_processed": total_rows,
        "valid_rows": total_rows - len(invalid_row_numbers),
        "invalid_rows": len(invalid_row_numbers),
        "total_validation_errors": len(errors),
        "errors_by_column": dict(sorted(Counter(error.column for error in errors).items())),
        "errors": [error.to_dict() for error in errors],
    }


def write_validation_report(report: dict[str, object], path: str | Path) -> Path:
    destination = Path(path)
    try:
        destination.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        raise DataProcessorError(f"Could not write validation report '{destination}': {exc}") from exc
    return destination
