"""Command-line interface for the data processor."""

import argparse
import logging
import sys
from pathlib import Path

from data_processor.cleaning import clean_data, inspect_dataset
from data_processor.errors import DataProcessorError
from data_processor.io import export_dataset, load_dataset
from data_processor.reporting import build_summary, format_summary

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_processor",
        description="Inspect and clean CSV or XLSX datasets.",
    )
    parser.add_argument("input", type=Path, help="Input .csv or .xlsx file")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output .csv or .xlsx file",
    )
    parser.add_argument(
        "--missing",
        choices=("keep", "drop", "fill"),
        default="keep",
        help="Missing-value strategy (default: keep)",
    )
    parser.add_argument(
        "--fill-value",
        help="Value used by --missing fill (default: not set)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.missing == "fill" and args.fill_value is None:
        parser.error("--fill-value is required when --missing fill is selected.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        original = load_dataset(args.input)
        logger.info("Loaded %s", inspect_dataset(original))
        cleaned, stats = clean_data(
            original,
            missing_strategy=args.missing,
            fill_value=args.fill_value,
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
        return 1

    print(format_summary(summary))
    return 0
