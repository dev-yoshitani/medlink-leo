"""Orbit-domain models and UTC validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from medlink.models import ensure_finite


def require_utc(value: datetime, name: str = "time") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def parse_utc(value: str, name: str = "time") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp") from error
    return require_utc(parsed, name)


def utc_iso(value: datetime) -> str:
    return require_utc(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class FrozenTLE:
    satellite_name: str
    line1: str
    line2: str
    epoch_utc: datetime
    source_url: str
    source_note: str

    def __post_init__(self) -> None:
        if not isinstance(self.satellite_name, str) or not self.satellite_name.strip():
            raise ValueError("satellite_name must be non-empty")
        if not self.line1.startswith("1 ") or len(self.line1) < 69:
            raise ValueError("line1 must be a valid TLE first line")
        if not self.line2.startswith("2 ") or len(self.line2) < 69:
            raise ValueError("line2 must be a valid TLE second line")
        object.__setattr__(self, "epoch_utc", require_utc(self.epoch_utc, "epoch_utc"))
        if not isinstance(self.source_url, str) or not self.source_url.strip():
            raise ValueError("source_url must be non-empty")


@dataclass(frozen=True, slots=True)
class GroundStation:
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    minimum_elevation_deg: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("ground-station name must be non-empty")
        for field_name in (
            "latitude_deg",
            "longitude_deg",
            "altitude_m",
            "minimum_elevation_deg",
        ):
            object.__setattr__(
                self, field_name, ensure_finite(field_name, getattr(self, field_name))
            )
        if not -90 <= self.latitude_deg <= 90:
            raise ValueError("latitude_deg must be between -90 and 90")
        if not -180 <= self.longitude_deg <= 180:
            raise ValueError("longitude_deg must be between -180 and 180")
        if not 0 <= self.minimum_elevation_deg < 90:
            raise ValueError("minimum_elevation_deg must be >= 0 and < 90")


@dataclass(frozen=True, slots=True)
class OrbitSample:
    time_utc: datetime
    azimuth_deg: float
    elevation_deg: float
    range_m: float
    in_contact: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["time_utc"] = utc_iso(self.time_utc)
        return payload


@dataclass(frozen=True, slots=True)
class ContactWindow:
    start_utc: datetime
    end_utc: datetime
    maximum_elevation_deg: float
    minimum_range_m: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_utc", require_utc(self.start_utc, "start_utc"))
        object.__setattr__(self, "end_utc", require_utc(self.end_utc, "end_utc"))
        if self.end_utc <= self.start_utc:
            raise ValueError("contact-window end must be after start")
        if not 0 <= self.maximum_elevation_deg <= 90:
            raise ValueError("maximum_elevation_deg must be between 0 and 90")
        if self.minimum_range_m <= 0:
            raise ValueError("minimum_range_m must be > 0")

    @property
    def duration_s(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_utc": utc_iso(self.start_utc),
            "end_utc": utc_iso(self.end_utc),
            "duration_s": self.duration_s,
            "maximum_elevation_deg": self.maximum_elevation_deg,
            "minimum_range_m": self.minimum_range_m,
        }
