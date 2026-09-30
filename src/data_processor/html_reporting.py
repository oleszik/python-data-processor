"""Self-contained HTML reports for cleaned datasets."""

from html import escape
from pathlib import Path
from typing import Any

from data_processor.errors import DataProcessorError
from data_processor.reporting import ProcessingSummary


def _cell(value: object) -> str:
    return escape("" if value is None else str(value))


_STYLE = """
:root {
  color-scheme: light;
  --ink: #172b4d;
  --muted: #61738a;
  --line: #e3eaf2;
  --blue: #2457d6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #f4f7fb;
  color: var(--ink);
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
main { max-width: 1080px; margin: 0 auto; padding: 48px 24px 72px; }
header {
  padding: 34px;
  border-radius: 20px;
  color: white;
  background: linear-gradient(125deg, #152c64, #2866e8);
  box-shadow: 0 14px 36px #1d3f7c24;
}
.eyebrow {
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: .13em;
  font-size: 12px;
  font-weight: 700;
  opacity: .78;
}
h1 { margin: 0; font-size: clamp(28px, 5vw, 42px); letter-spacing: -.03em; }
header p:last-child { margin: 10px 0 0; opacity: .86; }
.overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 14px;
  margin: 22px 0 32px;
}
.overview div, .file-card {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: white;
  box-shadow: 0 5px 18px #172b4d08;
}
.overview div { padding: 18px 20px; }
.overview strong {
  display: block;
  color: var(--blue);
  font-size: 27px;
  line-height: 1.25;
}
.overview span, .metrics span { color: var(--muted); font-size: 13px; }
.file-card { margin-top: 18px; padding: 24px; }
h2 { margin: 0 0 18px; font-size: 21px; overflow-wrap: anywhere; }
h3 { margin: 26px 0 10px; font-size: 16px; }
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}
.metrics div {
  min-height: 78px;
  padding: 13px;
  border-radius: 11px;
  background: #f5f8fd;
}
.metrics strong { display: block; font-size: 20px; }
.metrics span { display: block; }
.output { margin: 17px 0 0; color: var(--muted); overflow-wrap: anywhere; }
code { color: #31496a; }
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 620px;
  text-align: left;
}
th, td {
  padding: 11px 13px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
th {
  background: #f5f8fd;
  color: #526680;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .05em;
}
tr:last-child td { border-bottom: 0; }
.empty { padding: 14px; color: var(--muted); text-align: center; }
.failure {
  padding: 12px 14px;
  border-radius: 10px;
  background: #fff2f0;
  color: #a12c22;
}
footer { margin-top: 28px; color: var(--muted); font-size: 12px; }
@media (max-width: 600px) {
  main { padding: 24px 14px 48px; }
  header { padding: 25px; }
  .file-card { padding: 18px; }
}
"""


def build_html_report(entries: list[dict[str, Any]]) -> str:
    successful = [entry for entry in entries if entry["summary"] is not None]
    total_rows = sum(entry["summary"].final_row_count for entry in successful)
    invalid_rows = sum(
        entry["validation"]["invalid_rows"]
        for entry in successful
        if entry["validation"] is not None
    )
    errors = sum(
        entry["validation"]["total_validation_errors"]
        for entry in successful
        if entry["validation"] is not None
    )
    failed_files = sum(entry["summary"] is None for entry in entries)

    sections: list[str] = []
    for entry in entries:
        name = _cell(entry["file"])
        summary: ProcessingSummary | None = entry["summary"]
        validation: dict[str, Any] | None = entry["validation"]
        if summary is None:
            sections.append(
                f'<section class="file-card"><h2>{name}</h2><p class="failure">'
                f"Processing failed: {_cell(entry['failure'])}</p></section>"
            )
            continue

        validation_markup = ""
        if validation is not None:
            issue_rows = "".join(
                "<tr>"
                f"<td>{_cell(error['row'])}</td>"
                f"<td>{_cell(error['column'])}</td>"
                f"<td>{_cell(error['value'])}</td>"
                f"<td>{_cell(error['rule'])}</td>"
                f"<td>{_cell(error['message'])}</td>"
                "</tr>"
                for error in validation["errors"]
            )
            if not issue_rows:
                issue_rows = (
                    '<tr><td colspan="5" class="empty">No validation issues</td></tr>'
                )
            validation_markup = (
                '<h3>Validation details</h3><div class="table-wrap"><table>'
                "<thead><tr><th>Row</th><th>Column</th><th>Value</th>"
                "<th>Rule</th><th>Issue</th></tr></thead>"
                f"<tbody>{issue_rows}</tbody></table></div>"
            )
        sections.append(
            f'<section class="file-card"><h2>{name}</h2>'
            '<div class="metrics">'
            f"<div><strong>{summary.original_row_count:,}</strong>"
            "<span>Input rows</span></div>"
            f"<div><strong>{summary.final_row_count:,}</strong>"
            "<span>Output rows</span></div>"
            f"<div><strong>{summary.duplicates_removed:,}</strong>"
            "<span>Duplicates removed</span></div>"
            f"<div><strong>{summary.empty_rows_removed:,}</strong>"
            "<span>Empty rows removed</span></div>"
            f"<div><strong>{summary.missing_values_before:,}</strong>"
            "<span>Missing values before</span></div>"
            f"<div><strong>{summary.missing_values_after:,}</strong>"
            "<span>Missing values after</span></div>"
            "</div>"
            '<p class="output">Cleaned file: '
            f"<code>{_cell(summary.output_path)}</code></p>"
            f"{validation_markup}</section>"
        )

    files_markup = "".join(sections) or '<p class="empty">No input files processed.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Data processing report</title>
  <style>{_STYLE}</style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Python Data Processor</p>
      <h1>Dataset processing report</h1>
      <p>Cleaning results and validation findings at a glance.</p>
    </header>
    <section class="overview" aria-label="Overall results">
      <div><strong>{len(successful)}</strong><span>Files processed</span></div>
      <div><strong>{failed_files}</strong><span>Files failed</span></div>
      <div><strong>{total_rows:,}</strong><span>Clean rows written</span></div>
      <div><strong>{invalid_rows:,}</strong><span>Rows with issues</span></div>
      <div><strong>{errors:,}</strong><span>Validation findings</span></div>
    </section>
    {files_markup}
    <footer>Generated by Python Data Processor · Self-contained report</footer>
  </main>
</body>
</html>
"""


def write_html_report(entries: list[dict[str, Any]], path: str | Path) -> Path:
    destination = Path(path)
    try:
        destination.write_text(build_html_report(entries), encoding="utf-8")
    except OSError as exc:
        raise DataProcessorError(
            f"Could not write HTML report '{destination}': {exc}"
        ) from exc
    return destination
