from __future__ import annotations

import math

import pytest

from medlink.models import LinkConfig, MedicalData, Priority


def test_transmission_duration() -> None:
    assert LinkConfig(1_000_000).transmission_duration_s(125_000) == pytest.approx(1.0)


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, -math.inf, True])
def test_invalid_bandwidth(value: float) -> None:
    with pytest.raises(ValueError):
        LinkConfig(value)


@pytest.mark.parametrize("field,value", [("created_at_s", math.nan), ("deadline_s", math.inf)])
def test_medical_data_rejects_non_finite(field: str, value: float) -> None:
    kwargs = {
        "id": "a",
        "data_type": "synthetic",
        "size_bytes": 10,
        "priority": Priority.NORMAL,
        "created_at_s": 0,
        "deadline_s": 1,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        MedicalData(**kwargs)


def test_priority_parsing() -> None:
    assert Priority.parse("critical") is Priority.CRITICAL
    assert Priority.parse(3) is Priority.LOW
    with pytest.raises(ValueError):
        Priority.parse("urgent")

