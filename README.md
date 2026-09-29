# Python Data Processor

## Goal

Build a polished Python tool for common CSV/Excel automation: validate structure, clean and normalize data, handle missing values, remove duplicates, combine datasets, calculate summaries, and export clean results.

This repository is being developed as a professional portfolio project demonstrating practical Python automation and data-processing skills for freelance work.

## Implemented features

- Read CSV and XLSX files, selected automatically from their filename extensions.
- Inspect row and column counts, column names, inferred data types, missing-value counts, and duplicate rows.
- Trim whitespace in text values and normalize column names to lowercase snake_case.
- Remove completely empty rows and duplicate records.
- Keep missing values, drop rows with missing values, or fill them with a supplied value.
- Export cleaned datasets to CSV or XLSX.
- Print a JSON processing summary with row counts, removals, missing values before/after, processed columns, and output path.

## Project structure

```text
src/data_processor/
    __init__.py
    __main__.py
    cli.py
    cleaning.py
    errors.py
    io.py
    reporting.py
tests/
examples/
    messy_customers.csv
```

## Installation

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## CLI usage

```bash
python -m data_processor --help
python -m data_processor input.xlsx --output cleaned.xlsx --missing keep
python -m data_processor input.csv --output cleaned.csv --missing drop
python -m data_processor input.csv --output cleaned.xlsx --missing fill --fill-value unknown
```

The output extension selects CSV or XLSX. Use `--missing fill` together with `--fill-value`.
Errors such as missing inputs and unsupported file formats are reported with a non-zero exit
status.

## Example workflow

The synthetic input at `examples/messy_customers.csv` includes duplicate rows, missing data,
inconsistent whitespace, awkward column labels, text, and numeric columns.

```bash
python -m data_processor examples/messy_customers.csv \
  --output /tmp/cleaned_customers.xlsx \
  --missing keep
```

The command prints a JSON summary and writes the cleaned workbook to the selected output path.
Choose `--missing drop` or `--missing fill --fill-value VALUE` to apply a different missing
value strategy.

## Tests and lint

```bash
pytest
ruff check .
ruff format --check .
```

## Planned future improvements

These are not implemented in the current MVP:

- Combine or merge multiple datasets.
- Calculate additional summary statistics and offer configurable validation rules.
- Add richer logging and more detailed reports.
- Consider a simple GUI or drag-and-drop interface after the CLI is stable.
