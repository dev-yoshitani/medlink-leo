"""Shared JSON boundary checks; model constructors validate field types and ranges."""

from typing import Any


def required_field(payload: dict[str, Any], key: str) -> Any:
    """Require a non-null value without silently coercing malformed user input."""
    if key not in payload or payload[key] is None:
        raise ValueError(f"{key} is required and must not be null")
    return payload[key]
