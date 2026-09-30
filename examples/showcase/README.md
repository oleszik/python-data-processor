# Customer data cleanup showcase

## Scenario

A fictional client has exported customer records from a sales system and needs
them cleaned and checked before importing them into another platform.

## Input

[`input/messy_customers.csv`](input/messy_customers.csv) is fictional sample data.
It demonstrates inconsistent headers and whitespace, a duplicate and blank
record, missing required values, an invalid email, out-of-range numbers, a short
customer name, and unrecognized regions.

## Processing

The processor normalizes column names and text, removes duplicate and empty
records, and validates the remaining rows against
[`customer_validation.yaml`](customer_validation.yaml). It writes the cleaned
CSV, a machine-readable JSON validation report, and a self-contained HTML report
with processing metrics and readable validation findings.

## Results

This run read 8 rows, removed 1 duplicate and 1 empty row, and wrote 6 cleaned
rows. Validation passed for 2 rows; 4 rows were flagged with 9 findings. Missing
values decreased from 8 to 2. Invalid rows are retained in the cleaned file so
they can be reviewed and corrected before import.

- [Cleaned customer CSV](output/cleaned_customers.csv)
- [HTML validation report](output/customer_validation_report.html)
- [JSON validation report](output/customer_validation_report.json)

GitHub shows HTML files as source rather than rendering them as a web page. To
view the report, download it and open it locally in a browser; all styling is
embedded in the HTML file.

## Try it

From the repository root, install the project as described in the main README
and activate its virtual environment, then run:

```bash
python -m data_processor examples/showcase/input/messy_customers.csv \
  --config examples/showcase/customer_validation.yaml \
  --output examples/showcase/output/cleaned_customers.csv \
  --report examples/showcase/output/customer_validation_report.json \
  --html-report examples/showcase/output/customer_validation_report.html
```

Exit code `2` is expected for this deliberately invalid sample; all three
outputs are still written.
