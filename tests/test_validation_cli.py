import json
from pathlib import Path

import pandas as pd
import pytest

from data_processor.cli import main


def _files(tmp_path: Path, csv: str) -> tuple[Path, Path]:
    data = tmp_path / "input.csv"
    config = tmp_path / "rules.yaml"
    data.write_text(csv, encoding="utf-8")
    config.write_text(
        "columns:\n  email:\n    required: true\n    type: email\n", encoding="utf-8"
    )
    return data, config


def test_cli_validation_success(tmp_path: Path) -> None:
    data, config = _files(tmp_path, "email\nada@example.com\n")
    assert (
        main(
            [
                str(data),
                "--config",
                str(config),
                "--output",
                str(tmp_path / "clean.csv"),
            ]
        )
        == 0
    )


def test_cli_validation_errors_return_two_and_write_report(tmp_path: Path) -> None:
    data, config = _files(tmp_path, "email\nnot-an-email\n")
    output = tmp_path / "clean.csv"
    report = tmp_path / "report.json"
    code = main(
        [
            str(data),
            "--config",
            str(config),
            "--output",
            str(output),
            "--report",
            str(report),
        ]
    )
    assert code == 2
    assert output.exists()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["invalid_rows"] == 1
    assert payload["total_validation_errors"] == 1


def test_cli_configuration_failure_returns_one(tmp_path: Path) -> None:
    data = tmp_path / "input.csv"
    config = tmp_path / "bad.yaml"
    data.write_text("email\na@example.com\n", encoding="utf-8")
    config.write_text("[bad", encoding="utf-8")
    assert (
        main(
            [str(data), "--config", str(config), "--output", str(tmp_path / "out.csv")]
        )
        == 1
    )


@pytest.mark.parametrize("collision", ["input", "output", "config"])
def test_cli_rejects_report_path_collisions(tmp_path: Path, collision: str) -> None:
    data, config = _files(tmp_path, "email\nnot-an-email\n")
    output = tmp_path / "clean.csv"
    paths = {"input": data, "output": output, "config": config}

    code = main(
        [
            str(data),
            "--config",
            str(config),
            "--output",
            str(output),
            "--report",
            str(paths[collision]),
        ]
    )

    assert code == 1
    assert data.read_text(encoding="utf-8") == "email\nnot-an-email\n"
    assert "required: true" in config.read_text(encoding="utf-8")
    if collision == "output":
        assert not output.exists()


def test_cli_rejects_output_overwriting_config(tmp_path: Path) -> None:
    data, config = _files(tmp_path, "email\nada@example.com\n")

    assert main([str(data), "--config", str(config), "--output", str(config)]) == 1
    assert "required: true" in config.read_text(encoding="utf-8")


def test_cli_chunked_processing_matches_regular_processing(tmp_path: Path) -> None:
    data, config = _files(
        tmp_path,
        "email\nada@example.com\nnot-an-email\nada@example.com\n",
    )
    output = tmp_path / "clean.csv"
    report = tmp_path / "report.json"

    code = main(
        [
            str(data),
            "--config",
            str(config),
            "--output",
            str(output),
            "--report",
            str(report),
            "--chunksize",
            "1",
        ]
    )

    assert code == 2
    assert output.read_text(encoding="utf-8") == (
        "email\nada@example.com\nnot-an-email\n"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["total_rows_processed"] == 2
    assert payload["invalid_rows"] == 1
    assert payload["errors"][0]["row"] == 3


def test_cli_rejects_non_csv_output_for_chunked_processing(tmp_path: Path) -> None:
    data, config = _files(tmp_path, "email\nada@example.com\n")

    assert (
        main(
            [
                str(data),
                "--config",
                str(config),
                "--output",
                str(tmp_path / "clean.xlsx"),
                "--chunksize",
                "1",
            ]
        )
        == 1
    )


def test_cli_html_report_shows_validation_findings_safely(tmp_path: Path) -> None:
    data, config = _files(tmp_path, "email\n<script>alert(1)</script>\n")
    html_report = tmp_path / "report.html"

    code = main(
        [
            str(data),
            "--config",
            str(config),
            "--output",
            str(tmp_path / "clean.csv"),
            "--html-report",
            str(html_report),
        ]
    )

    page = html_report.read_text(encoding="utf-8")
    assert code == 2
    assert "Dataset processing report" in page
    assert "Validation details" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_cli_batch_processes_csv_and_xlsx_and_writes_reports(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "incoming"
    input_dir.mkdir()
    (input_dir / "first.csv").write_text(
        "email\nada@example.com\nnot-an-email\n", encoding="utf-8"
    )
    pd.DataFrame({"email": ["grace@example.com"]}).to_excel(
        input_dir / "second.xlsx", index=False
    )
    config = tmp_path / "rules.yaml"
    config.write_text(
        "columns:\n  email:\n    required: true\n    type: email\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "cleaned"
    json_report = tmp_path / "batch.json"
    html_report = tmp_path / "batch.html"

    code = main(
        [
            str(input_dir),
            "--config",
            str(config),
            "--output",
            str(output_dir),
            "--report",
            str(json_report),
            "--html-report",
            str(html_report),
            "--chunksize",
            "1",
        ]
    )

    assert code == 2
    assert (output_dir / "first.csv").exists()
    assert (output_dir / "second.xlsx").exists()
    assert pd.read_excel(output_dir / "second.xlsx").to_dict("records") == [
        {"email": "grace@example.com"}
    ]
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["total_rows_processed"] == 3
    assert report["invalid_rows"] == 1
    assert {item["file"] for item in report["files"]} == {
        "first.csv",
        "second.xlsx",
    }
    page = html_report.read_text(encoding="utf-8")
    assert "first.csv" in page
    assert "second.xlsx" in page
    assert "Files processed" in page


def test_cli_batch_continues_after_a_file_fails(tmp_path: Path) -> None:
    input_dir = tmp_path / "incoming"
    input_dir.mkdir()
    (input_dir / "a_bad.csv").write_text('email\n"unfinished\n', encoding="utf-8")
    (input_dir / "b_good.csv").write_text("email\nada@example.com\n", encoding="utf-8")
    config = tmp_path / "rules.yaml"
    config.write_text(
        "columns:\n  email:\n    required: true\n    type: email\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "cleaned"
    json_report = tmp_path / "batch.json"
    html_report = tmp_path / "batch.html"

    code = main(
        [
            str(input_dir),
            "--config",
            str(config),
            "--output",
            str(output_dir),
            "--report",
            str(json_report),
            "--html-report",
            str(html_report),
        ]
    )

    assert code == 1
    assert not (output_dir / "a_bad.csv").exists()
    assert not list(output_dir.glob(".a_bad.csv.*.tmp"))
    assert (output_dir / "b_good.csv").exists()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["files_failed"][0]["file"] == "a_bad.csv"
    assert report["files_failed"][0]["error"]
    page = html_report.read_text(encoding="utf-8")
    assert "a_bad.csv" in page
    assert "Processing failed" in page
    assert "b_good.csv" in page
