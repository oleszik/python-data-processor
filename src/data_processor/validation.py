"""Reusable row-level dataframe validation."""

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class ValidationError:
    row: int
    column: str
    value: object
    rule: str
    message: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        value = data["value"]
        if pd.isna(value):
            data["value"] = None
        elif not isinstance(value, (str, int, float, bool, type(None))):
            data["value"] = str(value)
        return data


def _missing(value: object) -> bool:
    return value is None or (not isinstance(value, (list, dict)) and bool(pd.isna(value)))


def _number(value: object, integer: bool = False) -> float | int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if integer and not number.is_integer():
        return None
    return int(number) if integer else number


def _error(row: int, column: str, value: object, rule: str, message: str) -> ValidationError:
    return ValidationError(row=row, column=column, value=value, rule=rule, message=message)


def validate_dataframe(
    dataframe: pd.DataFrame, config: dict[str, dict[str, Any]]
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for index, record in dataframe.iterrows():
        row_number = int(index) + 2  # CSV-style row number including the header.
        for column, rules in config.items():
            value = record[column] if column in dataframe.columns else None
            if _missing(value):
                if rules.get("required"):
                    errors.append(_error(row_number, column, value, "required", f"{column} is required"))
                continue

            kind = rules.get("type")
            numeric: float | int | None = None
            if kind == "integer":
                numeric = _number(value, integer=True)
                if numeric is None:
                    errors.append(_error(row_number, column, value, "type", f"{column} must be an integer"))
            elif kind == "float":
                numeric = _number(value)
                if numeric is None:
                    errors.append(_error(row_number, column, value, "type", f"{column} must be a number"))
            elif kind == "email" and not EMAIL_RE.fullmatch(str(value).strip()):
                errors.append(_error(row_number, column, value, "type", f"{column} must be a valid email"))
            elif kind == "string" and not isinstance(value, str):
                errors.append(_error(row_number, column, value, "type", f"{column} must be a string"))

            if numeric is None and kind in {"integer", "float"}:
                numeric = _number(value, integer=kind == "integer")
            if numeric is not None:
                if "min" in rules and numeric < rules["min"]:
                    errors.append(_error(row_number, column, value, "min", f"{column} must be at least {rules['min']}"))
                if "max" in rules and numeric > rules["max"]:
                    errors.append(_error(row_number, column, value, "max", f"{column} must be at most {rules['max']}"))

            text = str(value)
            if "min_length" in rules and len(text) < rules["min_length"]:
                errors.append(_error(row_number, column, value, "min_length", f"{column} is too short"))
            if "max_length" in rules and len(text) > rules["max_length"]:
                errors.append(_error(row_number, column, value, "max_length", f"{column} is too long"))
            if "allowed" in rules and value not in rules["allowed"]:
                errors.append(_error(row_number, column, value, "allowed", f"{column} is not an allowed value"))
    return errors
