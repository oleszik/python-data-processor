"""Command-line interface for the data processor."""

import argparse
import logging
import sys
from pathlib import Path

from data_processor.cleaning import clean_data, inspect_dataset
from data_processor.config import load_validation_config
from data_processor.errors import ConfigurationError, DataProcessorError
from data_processor.io import export_dataset, load_dataset
from data_processor.reporting import build_summary, format_summary
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.missing == "fill" and args.fill_value is None:
        parser.error("--fill-value is required when --missing fill is selected.")
    if args.report is not None and args.config is None:
        parser.error("--report requires --config.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        _validate_file_paths(args.input, args.output, args.config, args.report)
        original = load_dataset(args.input)
        logger.info("Loaded %s", inspect_dataset(original))
        cleaned, stats = clean_data(
            original, missing_strategy=args.missing, fill_value=args.fill_value
        )
        validation_errors = []
        if args.config is not None:
            rules = load_validation_config(args.config)
            validation_errors = validate_dataframe(cleaned, rules)
            if args.report is not None:
                write_validation_report(
                    build_validation_report(len(cleaned), validation_errors),
                    args.report,
                )

        output_path = export_dataset(cleaned, args.output)
        summary = build_summary(
            original=original,
            final=cleaned,
            duplicates_removed=stats.duplicates_removed,
            empty_rows_removed=stats.empty_rows_removed,
            output_path=output_path,
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
