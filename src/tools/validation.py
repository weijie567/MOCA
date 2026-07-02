"""Validation helpers for the unified tool catalog."""

from __future__ import annotations

from math import isfinite
from typing import Any


SUPPORTED_JSON_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "type",
        "properties",
        "items",
        "required",
        "additionalProperties",
        "enum",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
)


def validate_json_value(value: Any, schema: dict[str, Any]) -> None:
    """Validate the JSON Schema subset used by tool descriptors."""

    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        first_error: TypeError | ValueError | None = None
        for candidate_type in expected_type:
            try:
                validate_json_value(value, {**schema, "type": candidate_type})
            except (TypeError, ValueError) as exc:
                if first_error is None:
                    first_error = exc
                continue
            return
        if first_error is not None:
            raise first_error
        raise ValueError("No allowed types declared")
    if expected_type == "null":
        if value is not None:
            raise TypeError("Expected null")
        return
    if expected_type == "object":
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        for required_name in schema.get("required", []):
            if required_name not in value:
                raise ValueError("Missing required property")
        properties = schema.get("properties", {})
        for property_name, property_schema in properties.items():
            if property_name in value:
                validate_json_value(value[property_name], property_schema)
        if schema.get("additionalProperties") is False and any(name not in properties for name in value):
            raise ValueError("Unexpected property")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise TypeError("Expected array")
        item_schema = schema.get("items", {})
        for item in value:
            validate_json_value(item, item_schema)
    elif expected_type == "string":
        if not isinstance(value, str):
            raise TypeError("Expected string")
        if len(value) < schema.get("minLength", 0):
            raise ValueError("String is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValueError("String is too long")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Expected integer")
        _validate_numeric_bounds(value, schema)
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Expected number")
        if not isfinite(value):
            raise ValueError("Expected finite number")
        _validate_numeric_bounds(value, schema)
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise TypeError("Expected boolean")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Value is not in enum")


def _validate_numeric_bounds(value: int | float, schema: dict[str, Any]) -> None:
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        raise ValueError("Number is below exclusive minimum")
    if "minimum" in schema and value < schema["minimum"]:
        raise ValueError("Number is below minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise ValueError("Number is above maximum")
    if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
        raise ValueError("Number is above exclusive maximum")


_validate_json_value = validate_json_value
