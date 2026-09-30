"""Command-line interface for the data processor."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from data_processor.cleaning import clean_data, inspect_dataset
from data_processor.config import load_validation_config
from data_processor.errors import ConfigurationError, DataProcessorError, InputFileError
from data_processor.io import export_dataset, load_csv_chunks, load_dataset
from data_processor.reporting import (
    build_count_summary,
    build_summary,
    format_summary,
)
from data_processor.validation import validate_dataframe
from data_processor.validation_reporting import (
    build_validation_report,
    write_validation_report,
)

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_APPLICATION_ERROR = 1
EXIT_VALIDATION_ERROR = 2


def _validate_file_paths(
    input_path: Path,
    output_path: Path,
    config_path: Path | None,
    report_path: Path | None,
) -> None:
    if config_path is not None and output_path.resolve() == config_path.resolve():
        raise ConfigurationError(
            "Output and validation config paths must be different."
        )
    if report_path is None:
        return
    other_paths = {
        "input": input_path,
        "output": output_path,
        "validation config": config_path,
    }
    for label, path in other_paths.items():
        if path is not None and report_path.resolve() == path.resolve():
            raise ConfigurationError(
                f"Validation report and {label} paths must be different."
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_processor",
        description="Inspect, clean, and optionally validate CSV or XLSX datasets.",
    )
    parser.add_argument("input", type=Path, help="Input .csv or .xlsx file")
    parser.add_argument(
        "--output", type=Path, required=True, help="Output .csv or .xlsx file"
    )
    parser.add_argument(
        "--config", type=Path, help="YAML file containing column validation rules"
    )
    parser.add_argument(
        "--report", type=Path, help="Write a JSON validation report (requires --config)"
    )
    parser.add_argument(
        "--missing",
        choices=("keep", "drop", "fill"),
        default="keep",
        help="Missing-value strategy (default: keep)",
    )
    parser.add_argument("--fill-value", help="Value used by --missing fill")
    parser.add_argument(
        "--chunksize",
        type=int,
        help="Process CSV input in chunks of this many rows",
    )
    return parser


def _row_key(row: tuple[object, ...]) -> tuple[object, ...]:
    key: list[object] = []
    for value in row:
        if pd.isna(value):
            key.append(None)
        elif isinstance(value, (str, int, float, bool, type(None))):
            key.append(value)
        else:
            key.append(str(value))
    return tuple(key)


def _process_csv_chunks(
    args: argparse.Namespace,
    rules: dict[str, dict[str, Any]] | None,
) -> tuple[object, list]:
    chunks = load_csv_chunks(args.input, args.chunksize)
    seen_rows: set[tuple[object, ...]] = set()
    validation_errors = []
    original_row_count = 0
    final_row_count = 0
    duplicates_removed = 0
    empty_rows_removed = 0
    missing_values_before = 0
    missing_values_after = 0
    columns_processed: list[str] = []
    output_initialized = False

    for chunk in chunks:
        original_row_count += len(chunk)
        missing_values_before += int(chunk.isna().sum().sum())
        cleaned, stats = clean_data(
            chunk, missing_strategy=args.missing, fill_value=args.fill_value
        )
        empty_rows_removed += stats.empty_rows_removed
        duplicates_removed += stats.duplicates_removed

        unique_rows = []
        for row in cleaned.itertuples(index=False, name=None):
            key = _row_key(row)
            if key in seen_rows:
                duplicates_removed += 1
                continue
            seen_rows.add(key)
            unique_rows.append(row)
        cleaned = pd.DataFrame(unique_rows, columns=cleaned.columns)
        columns_processed = [str(column) for column in cleaned.columns]
        validation_start = final_row_count + 2
        final_row_count += len(cleaned)
        missing_values_after += int(cleaned.isna().sum().sum())

        if rules is not None:
            validation_errors.extend(
                validate_dataframe(cleaned, rules, start_row=validation_start)
            )

        try:
            cleaned.to_csv(
                args.output,
                mode="w" if not output_initialized else "a",
                header=not output_initialized,
                index=False,
            )
        except (OSError, ValueError) as exc:
            raise InputFileError(
                f"Could not write output file '{args.output}': {exc}"
            ) from exc
        output_initialized = True

    if not output_initialized:
        try:
            pd.DataFrame().to_csv(args.output, index=False)
        except (OSError, ValueError) as exc:
            raise InputFileError(
                f"Could not write output file '{args.output}': {exc}"
            ) from exc
    summary = build_count_summary(
        original_row_count=original_row_count,
        final_row_count=final_row_count,
        duplicates_removed=duplicates_removed,
        empty_rows_removed=empty_rows_removed,
        missing_values_before=missing_values_before,
        missing_values_after=missing_values_after,
        columns_processed=columns_processed,
        output_path=args.output,
    )
    return summary, validation_errors


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.chunksize is not None and args.chunksize < 1:
        parser.error("--chunksize must be a positive integer.")
    if args.missing == "fill" and args.fill_value is None:
        parser.error("--fill-value is required when --missing fill is selected.")
    if args.report is not None and args.config is None:
        parser.error("--report requires --config.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        _validate_file_paths(args.input, args.output, args.config, args.report)
        if args.chunksize is not None and args.output.suffix.lower() != ".csv":
            raise ConfigurationError("--chunksize requires a CSV output file.")
        rules = load_validation_config(args.config) if args.config else None
        if args.chunksize is not None:
            summary, validation_errors = _process_csv_chunks(args, rules)
        else:
            original = load_dataset(args.input)
            logger.info("Loaded %s", inspect_dataset(original))
            cleaned, stats = clean_data(
                original, missing_strategy=args.missing, fill_value=args.fill_value
            )
            validation_errors = validate_dataframe(cleaned, rules) if rules else []
            output_path = export_dataset(cleaned, args.output)
            summary = build_summary(
                original=original,
                final=cleaned,
                duplicates_removed=stats.duplicates_removed,
                empty_rows_removed=stats.empty_rows_removed,
                output_path=output_path,
            )
        if args.report is not None:
            write_validation_report(
                build_validation_report(summary.final_row_count, validation_errors),
                args.report,
            )
    except DataProcessorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_APPLICATION_ERROR

    print(format_summary(summary))
    if validation_errors:
        print(
            f"Validation completed with {len(validation_errors)} error(s).",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS
