import json
from pathlib import Path

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
