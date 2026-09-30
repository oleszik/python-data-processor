"""Load and validate YAML validation configuration."""

import math
from pathlib import Path
from typing import Any

import yaml

from data_processor.errors import ConfigurationError

SUPPORTED_TYPES = {"integer", "float", "email", "string"}
SUPPORTED_RULES = {
    "required",
    "type",
    "min",
    "max",
    "min_length",
    "max_length",
    "allowed",
}


def _validate_rule_values(column: str, rules: dict[str, Any]) -> None:
    if "required" in rules and not isinstance(rules["required"], bool):
        raise ConfigurationError(f"'required' for '{column}' must be a boolean.")

    value_type = rules.get("type")
    for rule in ("min", "max"):
        if rule not in rules:
            continue
        if value_type not in {"integer", "float"}:
            raise ConfigurationError(
                f"'{rule}' for '{column}' requires type 'integer' or 'float'."
            )
        value = rules[rule]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigurationError(f"'{rule}' for '{column}' must be numeric.")
        finite = isinstance(value, int) or math.isfinite(value)
        if not finite:
            raise ConfigurationError(f"'{rule}' for '{column}' must be numeric.")

    if "min" in rules and "max" in rules and rules["min"] > rules["max"]:
        raise ConfigurationError(
            f"'min' for '{column}' must not be greater than 'max'."
        )

    for rule in ("min_length", "max_length"):
        if rule not in rules:
            continue
        value = rules[rule]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ConfigurationError(
                f"'{rule}' for '{column}' must be a non-negative integer."
            )

    if (
        "min_length" in rules
        and "max_length" in rules
        and rules["min_length"] > rules["max_length"]
    ):
        raise ConfigurationError(
            f"'min_length' for '{column}' must not be greater than 'max_length'."
        )


def load_validation_config(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ConfigurationError(
            f"Validation config does not exist or is not a file: {source}"
        )
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(
            f"Could not read validation config '{source}': {exc}"
        ) from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("columns"), dict):
        raise ConfigurationError("Validation config must contain a 'columns' mapping.")

    result: dict[str, dict[str, Any]] = {}
    for column, rules in raw["columns"].items():
        if not isinstance(column, str) or not isinstance(rules, dict):
            raise ConfigurationError(
                "Each configured column must map to validation rules."
            )
        if not all(isinstance(rule, str) for rule in rules):
            raise ConfigurationError(
                f"Each validation rule for '{column}' must have a string name."
            )
        unknown = set(rules) - SUPPORTED_RULES
        if unknown:
            raise ConfigurationError(
                f"Unsupported rule(s) for '{column}': {', '.join(sorted(unknown))}"
            )
        value_type = rules.get("type")
        if value_type is not None and (
            not isinstance(value_type, str) or value_type not in SUPPORTED_TYPES
        ):
            raise ConfigurationError(f"Unsupported type for '{column}': {value_type}")
        _validate_rule_values(column, rules)
        if "allowed" in rules and not isinstance(rules["allowed"], list):
            raise ConfigurationError(f"'allowed' for '{column}' must be a list.")
        result[column] = rules
    return result
