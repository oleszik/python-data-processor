"""Reusable row-level dataframe validation."""

import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np
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
        if _missing(value):
            data["value"] = None
        else:
            if isinstance(value, np.generic):
                value = value.item()
            if isinstance(value, float) and not math.isfinite(value):
                value = str(value)
            if not isinstance(value, (str, int, float, bool, type(None))):
                value = str(value)
            data["value"] = value
        return data


def _missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    missing = pd.isna(value)
    return bool(missing) if pd.api.types.is_scalar(missing) else False


def _number(value: object, integer: bool = False) -> float | int | None:
    if isinstance(value, (bool, np.bool_)):
        return None
    if integer and isinstance(value, (int, np.integer)):
        return int(value)
    if integer and isinstance(value, str):
        try:
            decimal = Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
        if not decimal.is_finite() or decimal != decimal.to_integral_value():
            return None
        return int(decimal)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if integer and not number.is_integer():
        return None
    return int(number) if integer else number


def _error(
    row: int, column: str, value: object, rule: str, message: str
) -> ValidationError:
    return ValidationError(
        row=row, column=column, value=value, rule=rule, message=message
    )


def _is_allowed(value: object, allowed: list[object]) -> bool:
    for candidate in allowed:
        try:
            matches = value == candidate
        except (TypeError, ValueError):
            continue
        if pd.api.types.is_scalar(matches):
            try:
                if bool(matches):
                    return True
            except (TypeError, ValueError):
                continue
    return False


def validate_dataframe(
    dataframe: pd.DataFrame, config: dict[str, dict[str, Any]]
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for row_number, (_, record) in enumerate(dataframe.iterrows(), start=2):
        for column, rules in config.items():
            value = record[column] if column in dataframe.columns else None
            if _missing(value):
                if rules.get("required"):
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "required",
                            f"{column} is required",
                        )
                    )
                continue

            kind = rules.get("type")
            numeric: float | int | None = None
            if kind == "integer":
                numeric = _number(value, integer=True)
                if numeric is None:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "type",
                            f"{column} must be an integer",
                        )
                    )
            elif kind == "float":
                numeric = _number(value)
                if numeric is None:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "type",
                            f"{column} must be a number",
                        )
                    )
            elif kind == "email" and not EMAIL_RE.fullmatch(str(value).strip()):
                errors.append(
                    _error(
                        row_number,
                        column,
                        value,
                        "type",
                        f"{column} must be a valid email",
                    )
                )
            elif kind == "string" and not isinstance(value, str):
                errors.append(
                    _error(
                        row_number, column, value, "type", f"{column} must be a string"
                    )
                )

            if numeric is not None:
                if "min" in rules and numeric < rules["min"]:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "min",
                            f"{column} must be at least {rules['min']}",
                        )
                    )
                if "max" in rules and numeric > rules["max"]:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "max",
                            f"{column} must be at most {rules['max']}",
                        )
                    )

            if "min_length" in rules or "max_length" in rules:
                text = str(value)
                if "min_length" in rules and len(text) < rules["min_length"]:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "min_length",
                            f"{column} is too short",
                        )
                    )
                if "max_length" in rules and len(text) > rules["max_length"]:
                    errors.append(
                        _error(
                            row_number,
                            column,
                            value,
                            "max_length",
                            f"{column} is too long",
                        )
                    )
            if "allowed" in rules and not _is_allowed(value, rules["allowed"]):
                errors.append(
                    _error(
                        row_number,
                        column,
                        value,
                        "allowed",
                        f"{column} is not an allowed value",
                    )
                )
    return errors
