# Turn messy spreadsheets into clean, reviewable data

Python Data Processor is a small automation tool for the spreadsheet work clients
actually hand off: normalize inconsistent columns, trim values, remove empty and
duplicate rows, apply configurable validation, and deliver both a cleaned file and
a report that makes exceptions easy to review.

**Messy CSV/XLSX in → cleaned CSV/XLSX + visual HTML report out.** Run it on one
file or point it at a folder to process a batch.

## Features

- Load and export CSV and XLSX files.
- Normalize column names, trim text, remove empty rows and duplicates.
- Keep, drop, or fill missing values.
- Configure validation in YAML instead of hard-coding business rules.
- Validate required values, integer/float/email/string types, numeric min/max, string lengths, and allowed values.
- Continue processing after row-level validation failures and report every issue with row, column, value, rule, and message.
- Write a self-contained HTML report for people and a JSON report for downstream tools.
- Batch-process every CSV and XLSX file in a folder while keeping each cleaned output separate.

## See it in action

The included [messy customer dataset](examples/messy_customers.csv) has inconsistent
headers, extra whitespace, duplicate and empty rows, and validation problems.
The processor normalizes and cleans the data without hiding invalid records:

| Before | After cleaning |
| --- | --- |
| ` Customer Name ` | `customer_name` |
| ` Alice Smith ` | `Alice Smith` |
| Duplicate Alice row | Removed |
| Blank row | Removed |
| `not-an-email` | Kept and flagged in the report |

Run the example from the repository root:

```bash
python -m data_processor examples/messy_customers.csv \
  --config examples/customer_validation.yaml \
  --output cleaned_customers.csv \
  --report validation_report.json \
  --html-report customer_report.html
```

Open `customer_report.html` in a browser for an at-a-glance processing summary and
a readable table of validation findings. The cleaned dataset and report are still
written when data rows fail validation; the command then exits with code `2`.

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
  --report validation_report.json \
  --html-report validation_report.html

# Process a folder of CSV/XLSX files into a separate output folder
python -m data_processor incoming/ \
  --config examples/customer_validation.yaml \
  --output cleaned/ \
  --report batch_validation.json \
  --html-report batch_report.html

# Process a large CSV incrementally in chunks
python -m data_processor large_input.csv \
  --config examples/customer_validation.yaml \
  --output cleaned.csv \
  --chunksize 10000
```

Batch mode scans the input folder (not recursively) for `.csv` and `.xlsx` files,
preserves each filename and extension in the output folder, and continues if an
individual file cannot be processed. If `--chunksize` is set, CSV files use
incremental processing; XLSX files in the same batch use the regular reader.
Validation is applied to the cleaned dataset. Row-level validation errors do not
stop processing or prevent cleaned output from being written.

Exit codes:

- `0`: processing completed with no validation errors.
- `1`: application, input/output, or configuration failure.
- `2`: processing completed, but one or more rows failed validation.

Invalid command-line usage is handled by `argparse`, which also exits with status `2`
before processing starts.

The JSON report contains `total_rows_processed`, `valid_rows`, `invalid_rows`,
`total_validation_errors`, `errors_by_column`, and detailed `errors`. In batch
mode it also includes per-file report entries, and errors identify their source
file. The HTML report is self-contained and can be opened locally or shared as a
single file.

## Project structure

```text
src/data_processor/
    cli.py
    cleaning.py
    config.py
    errors.py
    io.py
    reporting.py
    html_reporting.py
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

CSV inputs can also be processed incrementally with `--chunksize`; chunked
processing preserves global duplicate removal and currently writes CSV output.
