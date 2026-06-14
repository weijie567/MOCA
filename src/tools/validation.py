"""Validation helpers for the unified tool catalog."""

from __future__ import annotations

from typing import Any


def validate_json_value(value: Any, schema: dict[str, Any]) -> None:
    """Validate the JSON Schema subset used by tool descriptors."""

    expected_type = schema.get("type")
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
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Expected integer")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Expected number")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValueError("Number is below exclusive minimum")
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise TypeError("Expected boolean")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Value is not in enum")


_validate_json_value = validate_json_value
