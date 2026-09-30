# Python Data Processor

A production-style command-line utility for cleaning and validating CSV/XLSX datasets. It demonstrates practical Python automation: reusable validation rules, YAML configuration, structured JSON reporting, deterministic exit codes, and tested data-cleaning workflows.

## Features

- Load and export CSV and XLSX files.
- Normalize column names, trim text, remove empty rows and duplicates.
- Keep, drop, or fill missing values.
- Configure validation in YAML instead of hard-coding business rules.
- Validate required values, integer/float/email/string types, numeric min/max, string lengths, and allowed values.
- Continue processing after row-level validation failures and report every issue with row, column, value, rule, and message.
- Optionally write a machine-readable JSON validation report.

## Installation

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Validation configuration

```yaml
columns:
  email:
    required: true
    type: email
  order_count:
    required: true
    type: integer
    min: 0
    max: 1000
  region:
    allowed: [North, South, East, West]
```

See `examples/customer_validation.yaml` for a complete example.

## CLI

```bash
python -m data_processor --help

python -m data_processor examples/messy_customers.csv \
  --config examples/customer_validation.yaml \
  --output cleaned.csv \
  --report validation_report.json

# Process a large CSV without loading all rows into memory
python -m data_processor large_input.csv \
  --config examples/customer_validation.yaml \
  --output cleaned.csv \
  --chunksize 10000
```

Validation is applied to the cleaned dataset. Row-level validation errors do not stop processing or prevent cleaned output from being written.

Exit codes:

- `0`: processing completed with no validation errors.
- `1`: application, input/output, or configuration failure.
- `2`: processing completed, but one or more rows failed validation.

Invalid command-line usage is handled by `argparse`, which also exits with status `2`
before processing starts.

The JSON report contains `total_rows_processed`, `valid_rows`, `invalid_rows`, `total_validation_errors`, `errors_by_column`, and detailed `errors`.

## Project structure

```text
src/data_processor/
    cli.py
    cleaning.py
    config.py
    errors.py
    io.py
    reporting.py
    validation.py
    validation_reporting.py
tests/
    test_data_processor.py
    test_validation.py
    test_validation_cli.py
examples/
    messy_customers.csv
    customer_validation.yaml
```

## Tests and quality checks

```bash
pytest
ruff check .
ruff format --check .
```

## Next steps

Potential extensions include richer structured logging, additional input formats, and configurable transformations. CSV inputs can be processed incrementally with `--chunksize`; chunked processing preserves global duplicate removal and is currently limited to CSV output.
