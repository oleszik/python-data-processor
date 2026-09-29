from pathlib import Path

import pandas as pd
import pytest

from data_processor.config import load_validation_config
from data_processor.errors import ConfigurationError
from data_processor.validation import validate_dataframe
from data_processor.validation_reporting import build_validation_report, write_validation_report


def test_validation_accepts_valid_row() -> None:
    frame = pd.DataFrame([{"email": "ada@example.com", "age": 30, "score": 4.5, "country": "Germany"}])
    rules = {"email": {"required": True, "type": "email"}, "age": {"type": "integer", "min": 18, "max": 120}, "score": {"type": "float"}, "country": {"allowed": ["Germany", "France"]}}
    assert validate_dataframe(frame, rules) == []


def test_validation_collects_errors_without_stopping() -> None:
    frame = pd.DataFrame([{"email": "bad", "age": "x", "score": "nope", "name": "A", "country": "Mars"}, {"email": None, "age": 130, "score": 1.2, "name": "way-too-long", "country": "Germany"}])
    rules = {"email": {"required": True, "type": "email"}, "age": {"type": "integer", "min": 18, "max": 120}, "score": {"type": "float"}, "name": {"min_length": 2, "max_length": 5}, "country": {"allowed": ["Germany", "France"]}}
    errors = validate_dataframe(frame, rules)
    assert {error.rule for error in errors} >= {"required", "type", "max", "min_length", "max_length", "allowed"}
    assert all(error.row >= 2 and error.column and error.message for error in errors)


def test_missing_required_column_is_reported() -> None:
    errors = validate_dataframe(pd.DataFrame([{"name": "Ada"}]), {"email": {"required": True}})
    assert errors[0].column == "email"
    assert errors[0].rule == "required"


def test_config_loads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("columns:\n  age:\n    type: integer\n    min: 18\n", encoding="utf-8")
    assert load_validation_config(path)["age"]["min"] == 18


@pytest.mark.parametrize("content", ["[broken", "hello: world", "columns:\n  age: nope\n"])
def test_bad_config_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_validation_config(path)


def test_report_counts_and_writes_json(tmp_path: Path) -> None:
    errors = validate_dataframe(pd.DataFrame([{"email": "bad"}, {"email": "ok@example.com"}]), {"email": {"type": "email"}})
    report = build_validation_report(2, errors)
    assert report["valid_rows"] == 1
    assert report["invalid_rows"] == 1
    assert report["errors_by_column"] == {"email": 1}
    path = write_validation_report(report, tmp_path / "report.json")
    assert '"total_validation_errors": 1' in path.read_text(encoding="utf-8")
