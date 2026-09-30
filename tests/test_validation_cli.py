import json
from pathlib import Path

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
