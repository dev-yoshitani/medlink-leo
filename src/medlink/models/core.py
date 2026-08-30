"""Validated scheduling models with explicit units."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum


def ensure_finite(name: str, value: float | int) -> float:
    """Return *value* as float after rejecting booleans and non-finite numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite number")
    return converted


class Priority(IntEnum):
    """Illustrative simulation priority; lower values are selected first."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

    @classmethod
    def parse(cls, value: Priority | str | int) -> Priority:
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise ValueError("priority must be CRITICAL, HIGH, NORMAL, LOW, or 0-3")
        if isinstance(value, str):
            try:
                return cls[value.strip().upper()]
            except KeyError as error:
                raise ValueError(
                    "priority must be CRITICAL, HIGH, NORMAL, LOW, or 0-3"
                ) from error
        try:
            return cls(value)
        except (TypeError, ValueError) as error:
            raise ValueError("priority must be CRITICAL, HIGH, NORMAL, LOW, or 0-3") from error


@dataclass(frozen=True, slots=True)
class MedicalData:
    """One synthetic data item. All time fields use seconds."""

    id: str
    data_type: str
    size_bytes: int
    priority: Priority
    created_at_s: float
    deadline_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(self.data_type, str) or not self.data_type.strip():
            raise ValueError("data_type must be a non-empty string")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise ValueError("size_bytes must be a positive integer")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be > 0")
        object.__setattr__(self, "priority", Priority.parse(self.priority))
        created_at_s = ensure_finite("created_at_s", self.created_at_s)
        deadline_s = ensure_finite("deadline_s", self.deadline_s)
        if created_at_s < 0:
            raise ValueError("created_at_s must be >= 0")
        if deadline_s <= 0:
            raise ValueError("deadline_s must be > 0")
        object.__setattr__(self, "created_at_s", created_at_s)
        object.__setattr__(self, "deadline_s", deadline_s)

    @property
    def due_at_s(self) -> float:
        return self.created_at_s + self.deadline_s


@dataclass(frozen=True, slots=True)
class LinkConfig:
    """Fixed link configuration for v0.1."""

    bandwidth_bps: float

    def __post_init__(self) -> None:
        bandwidth_bps = ensure_finite("bandwidth_bps", self.bandwidth_bps)
        if bandwidth_bps <= 0:
            raise ValueError("bandwidth_bps must be > 0")
        object.__setattr__(self, "bandwidth_bps", bandwidth_bps)

    def transmission_duration_s(self, size_bytes: int) -> float:
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer")
        return size_bytes * 8.0 / self.bandwidth_bps

