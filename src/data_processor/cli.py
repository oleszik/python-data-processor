"""Command-line interface for the data processor."""

import argparse
import json
import logging
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from data_processor.cleaning import clean_data, inspect_dataset
from data_processor.config import load_validation_config
from data_processor.errors import ConfigurationError, DataProcessorError, InputFileError
from data_processor.html_reporting import write_html_report
from data_processor.io import export_dataset, load_csv_chunks, load_dataset
from data_processor.reporting import (
    ProcessingSummary,
    build_count_summary,
    build_summary,
    format_summary,
)
from data_processor.validation import ValidationError, validate_dataframe
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
    html_report_path: Path | None,
) -> None:
    if config_path is not None and output_path.resolve() == config_path.resolve():
        raise ConfigurationError(
            "Output and validation config paths must be different."
        )
    if report_path is None:
        if html_report_path is None:
            return
    paths = [
        ("input", input_path),
        ("output", output_path),
        ("validation config", config_path),
    ]
    for label, report in (
        ("JSON report", report_path),
        ("HTML report", html_report_path),
    ):
        if report is None:
            continue
        for path_label, path in paths:
            if path is not None and report.resolve() == path.resolve():
                raise ConfigurationError(
                    f"{label} and {path_label} paths must be different."
                )
    if (
        report_path is not None
        and html_report_path is not None
        and report_path.resolve() == html_report_path.resolve()
    ):
        raise ConfigurationError("JSON and HTML report paths must be different.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_processor",
        description="Inspect, clean, and optionally validate CSV or XLSX datasets.",
    )
    parser.add_argument(
        "input", type=Path, help="Input .csv/.xlsx file or a directory of datasets"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output .csv/.xlsx file or output directory for batch input",
    )
    parser.add_argument(
        "--config", type=Path, help="YAML file containing column validation rules"
    )
    parser.add_argument(
        "--report", type=Path, help="Write a JSON validation report (requires --config)"
    )
    parser.add_argument(
        "--html-report",
        type=Path,
        help="Write a visual HTML report with cleaning and validation results",
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
) -> tuple[ProcessingSummary, list[ValidationError]]:
    chunks = load_csv_chunks(args.input, args.chunksize)
    seen_rows: set[tuple[object, ...]] = set()
    validation_errors: list[ValidationError] = []
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


def _process_file(
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    rules: dict[str, dict[str, Any]] | None,
) -> tuple[ProcessingSummary, list[ValidationError]]:
    file_args = argparse.Namespace(**vars(args))
    file_args.input = input_path
    file_args.output = output_path
    if args.chunksize is not None and input_path.suffix.lower() == ".csv":
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
        except OSError as exc:
            raise InputFileError(
                f"Could not prepare output file '{output_path}': {exc}"
            ) from exc
        file_args.output = temporary_path
        try:
            summary, errors = _process_csv_chunks(file_args, rules)
            try:
                temporary_path.replace(output_path)
            except OSError as exc:
                raise InputFileError(
                    f"Could not write output file '{output_path}': {exc}"
                ) from exc
            return replace(summary, output_path=str(output_path)), errors
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                raise InputFileError(
                    f"Could not remove temporary output '{temporary_path}': {exc}"
                ) from exc

    original = load_dataset(input_path)
    logger.info("Loaded %s", inspect_dataset(original))
    cleaned, stats = clean_data(
        original, missing_strategy=args.missing, fill_value=args.fill_value
    )
    validation_errors = validate_dataframe(cleaned, rules) if rules is not None else []
    written_path = export_dataset(cleaned, output_path)
    summary = build_summary(
        original=original,
        final=cleaned,
        duplicates_removed=stats.duplicates_removed,
        empty_rows_removed=stats.empty_rows_removed,
        output_path=written_path,
    )
    return summary, validation_errors


def _batch_validation_report(entries: list[dict[str, Any]]) -> dict[str, object]:
    files = []
    errors: list[dict[str, object]] = []
    errors_by_column: dict[str, int] = {}
    total_rows = valid_rows = invalid_rows = total_errors = 0
    for entry in entries:
        validation = entry["validation"]
        if validation is None:
            continue
        files.append({"file": entry["file"], **validation})
        total_rows += validation["total_rows_processed"]
        valid_rows += validation["valid_rows"]
        invalid_rows += validation["invalid_rows"]
        total_errors += validation["total_validation_errors"]
        for column, count in validation["errors_by_column"].items():
            errors_by_column[column] = errors_by_column.get(column, 0) + count
        errors.extend(
            {"file": entry["file"], **error} for error in validation["errors"]
        )
    return {
        "total_rows_processed": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "total_validation_errors": total_errors,
        "errors_by_column": dict(sorted(errors_by_column.items())),
        "errors": errors,
        "files": files,
        "files_failed": [
            {"file": entry["file"], "error": entry["failure"]}
            for entry in entries
            if entry["summary"] is None
        ],
    }


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
        _validate_file_paths(
            args.input,
            args.output,
            args.config,
            args.report,
            args.html_report,
        )
        if not args.input.exists():
            raise InputFileError(f"Input path does not exist: {args.input}")
        rules = load_validation_config(args.config) if args.config else None
        if args.input.is_dir():
            if args.output.resolve() == args.input.resolve():
                raise ConfigurationError(
                    "Batch output directory must be different from the input directory."
                )
            try:
                input_files = sorted(
                    path
                    for path in args.input.iterdir()
                    if path.is_file() and path.suffix.lower() in {".csv", ".xlsx"}
                )
            except OSError as exc:
                raise InputFileError(
                    f"Could not list input directory '{args.input}': {exc}"
                ) from exc
            if not input_files:
                raise InputFileError(
                    f"No CSV or XLSX files found in input directory: {args.input}"
                )
            output_paths = {
                args.output / f"{path.stem}{path.suffix}": path for path in input_files
            }
            if args.config is not None and args.config.resolve() in {
                destination.resolve() for destination in output_paths
            }:
                raise ConfigurationError(
                    "Batch outputs must not overwrite the validation config."
                )
            for report_path in (args.report, args.html_report):
                if report_path is None:
                    continue
                if report_path.resolve() in (
                    {source.resolve() for source in input_files}
                    | {destination.resolve() for destination in output_paths}
                    | {args.output.resolve()}
                ):
                    raise ConfigurationError(
                        "Report paths must not overwrite batch input or output files."
                    )
            try:
                args.output.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise InputFileError(
                    f"Could not create output directory '{args.output}': {exc}"
                ) from exc
            entries: list[dict[str, Any]] = []
            for destination, source in output_paths.items():
                try:
                    summary, errors = _process_file(source, destination, args, rules)
                    validation = (
                        build_validation_report(summary.final_row_count, errors)
                        if rules is not None
                        else None
                    )
                    entries.append(
                        {
                            "file": source.name,
                            "summary": summary,
                            "validation": validation,
                            "failure": None,
                        }
                    )
                except DataProcessorError as exc:
                    logger.error("Could not process %s: %s", source.name, exc)
                    entries.append(
                        {
                            "file": source.name,
                            "summary": None,
                            "validation": None,
                            "failure": str(exc),
                        }
                    )
            if args.report is not None:
                write_validation_report(_batch_validation_report(entries), args.report)
            if args.html_report is not None:
                write_html_report(entries, args.html_report)
            successful = [entry for entry in entries if entry["summary"] is not None]
            batch_summary = {
                "files_processed": len(successful),
                "files_failed": len(entries) - len(successful),
                "original_row_count": sum(
                    entry["summary"].original_row_count for entry in successful
                ),
                "final_row_count": sum(
                    entry["summary"].final_row_count for entry in successful
                ),
                "files": [
                    {
                        "file": entry["file"],
                        **entry["summary"].to_dict(),
                        "validation_errors": (
                            entry["validation"]["total_validation_errors"]
                            if entry["validation"] is not None
                            else 0
                        ),
                    }
                    for entry in entries
                    if entry["summary"] is not None
                ],
            }
            print(json.dumps(batch_summary, indent=2, ensure_ascii=False))
            if len(successful) != len(entries):
                return EXIT_APPLICATION_ERROR
            if any(
                entry["validation"] is not None
                and entry["validation"]["total_validation_errors"]
                for entry in entries
            ):
                return EXIT_VALIDATION_ERROR
            return EXIT_SUCCESS
        else:
            if args.chunksize is not None and (
                args.input.suffix.lower() != ".csv"
                or args.output.suffix.lower() != ".csv"
            ):
                raise ConfigurationError(
                    "--chunksize requires CSV input and CSV output files."
                )
            summary, validation_errors = _process_file(
                args.input, args.output, args, rules
            )
        if args.report is not None:
            write_validation_report(
                build_validation_report(summary.final_row_count, validation_errors),
                args.report,
            )
        if args.html_report is not None:
            write_html_report(
                [
                    {
                        "file": args.input.name,
                        "summary": summary,
                        "validation": (
                            build_validation_report(
                                summary.final_row_count, validation_errors
                            )
                            if rules is not None
                            else None
                        ),
                        "failure": None,
                    }
                ],
                args.html_report,
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
