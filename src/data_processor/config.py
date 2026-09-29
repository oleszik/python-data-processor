"""Load and validate YAML validation configuration."""

from pathlib import Path
from typing import Any

import yaml

from data_processor.errors import ConfigurationError

SUPPORTED_TYPES = {"integer", "float", "email", "string"}
SUPPORTED_RULES = {"required", "type", "min", "max", "min_length", "max_length", "allowed"}


def load_validation_config(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ConfigurationError(f"Validation config does not exist or is not a file: {source}")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not read validation config '{source}': {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("columns"), dict):
        raise ConfigurationError("Validation config must contain a 'columns' mapping.")

    result: dict[str, dict[str, Any]] = {}
    for column, rules in raw["columns"].items():
        if not isinstance(column, str) or not isinstance(rules, dict):
            raise ConfigurationError("Each configured column must map to validation rules.")
        unknown = set(rules) - SUPPORTED_RULES
        if unknown:
            raise ConfigurationError(
                f"Unsupported rule(s) for '{column}': {', '.join(sorted(unknown))}"
            )
        value_type = rules.get("type")
        if value_type is not None and value_type not in SUPPORTED_TYPES:
            raise ConfigurationError(f"Unsupported type for '{column}': {value_type}")
        if "allowed" in rules and not isinstance(rules["allowed"], list):
            raise ConfigurationError(f"'allowed' for '{column}' must be a list.")
        result[column] = rules
    return result
