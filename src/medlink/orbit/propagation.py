"""Skyfield-backed SGP4 propagation without live-network dependencies."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from skyfield.api import EarthSatellite, load, wgs84

from medlink._validation import required_field
from medlink.orbit.models import (
    ContactWindow,
    FrozenTLE,
    GroundStation,
    OrbitSample,
    parse_utc,
    require_utc,
)

_TIMESCALE = None


def _timescale():
    global _TIMESCALE  # noqa: PLW0603 - intentional process-local cache
    if _TIMESCALE is None:
        _TIMESCALE = load.timescale(builtin=True)
    return _TIMESCALE


@lru_cache(maxsize=16)
def _satellite(tle: FrozenTLE) -> EarthSatellite:
    satellite = EarthSatellite(tle.line1, tle.line2, tle.satellite_name, _timescale())
    parsed_epoch = satellite.epoch.utc_datetime().astimezone(UTC)
    if abs((parsed_epoch - tle.epoch_utc).total_seconds()) > 1.0:
        raise ValueError("documented TLE epoch does not match the parsed TLE epoch")
    return satellite


@lru_cache(maxsize=32)
def _station(station: GroundStation):
    return wgs84.latlon(
        station.latitude_deg,
        station.longitude_deg,
        elevation_m=station.altitude_m,
    )


@lru_cache(maxsize=64)
def _topocentric_vector(tle: FrozenTLE, station: GroundStation):
    return _satellite(tle) - _station(station)


def load_tle_json(path: str | Path) -> FrozenTLE:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TLE fixture must be a JSON object")
    return FrozenTLE(
        satellite_name=required_field(payload, "satellite_name"),
        line1=required_field(payload, "line1"),
        line2=required_field(payload, "line2"),
        epoch_utc=parse_utc(required_field(payload, "epoch_utc"), "epoch_utc"),
        source_url=required_field(payload, "source_url"),
        source_note=payload.get("source_note", ""),
    )


def load_bundled_tle() -> FrozenTLE:
    fixture = files("medlink.orbit").joinpath("data/iss_zarya_2014.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return FrozenTLE(
        satellite_name=payload["satellite_name"],
        line1=payload["line1"],
        line2=payload["line2"],
        epoch_utc=parse_utc(payload["epoch_utc"], "epoch_utc"),
        source_url=payload["source_url"],
        source_note=payload["source_note"],
    )


def propagate_orbit(tle: FrozenTLE, station: GroundStation, at_utc: datetime) -> OrbitSample:
    """Propagate one frozen TLE to a topocentric station observation."""
    at_utc = require_utc(at_utc, "at_utc")
    time = _timescale().from_datetime(at_utc)
    topocentric = _topocentric_vector(tle, station).at(time)
    altitude, azimuth, distance = topocentric.altaz()
    range_m = float(distance.m)
    if range_m <= 0:
        raise ValueError("propagated range must be positive")
    elevation_deg = float(altitude.degrees)
    return OrbitSample(
        time_utc=at_utc,
        azimuth_deg=float(azimuth.degrees) % 360.0,
        elevation_deg=elevation_deg,
        range_m=range_m,
        in_contact=elevation_deg >= station.minimum_elevation_deg,
    )


def propagate_orbit_many(
    tle: FrozenTLE,
    station: GroundStation,
    times_utc: tuple[datetime, ...] | list[datetime],
) -> tuple[OrbitSample, ...]:
    """Vector-propagate several UTC observations with one Skyfield call."""
    if not times_utc:
        return ()
    normalized = tuple(require_utc(moment, "times_utc item") for moment in times_utc)
    times = _timescale().from_datetimes(normalized)
    topocentric = _topocentric_vector(tle, station).at(times)
    altitude, azimuth, distance = topocentric.altaz()
    samples: list[OrbitSample] = []
    for moment, elevation, bearing, range_m in zip(
        normalized,
        altitude.degrees,
        azimuth.degrees,
        distance.m,
        strict=True,
    ):
        checked_range = float(range_m)
        if checked_range <= 0:
            raise ValueError("propagated range must be positive")
        elevation_deg = float(elevation)
        samples.append(
            OrbitSample(
                time_utc=moment,
                azimuth_deg=float(bearing) % 360.0,
                elevation_deg=elevation_deg,
                range_m=checked_range,
                in_contact=elevation_deg >= station.minimum_elevation_deg,
            )
        )
    return tuple(samples)


def is_in_contact(tle: FrozenTLE, station: GroundStation, at_utc: datetime) -> bool:
    return propagate_orbit(tle, station, at_utc).in_contact


def _minimum_range(
    tle: FrozenTLE,
    station: GroundStation,
    start: datetime,
    end: datetime,
    culmination: datetime,
) -> float:
    sample_times = {start, end, culmination}
    current = start
    while current < end:
        sample_times.add(current)
        current += timedelta(seconds=5)
    return min(
        sample.range_m
        for sample in propagate_orbit_many(tle, station, sorted(sample_times))
    )


def find_contact_windows(
    tle: FrozenTLE,
    station: GroundStation,
    start_utc: datetime,
    end_utc: datetime,
) -> tuple[ContactWindow, ...]:
    """Find ground-station visibility windows within an inclusive UTC interval."""
    start_utc = require_utc(start_utc, "start_utc")
    end_utc = require_utc(end_utc, "end_utc")
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc")

    satellite = _satellite(tle)
    times, events = satellite.find_events(
        _station(station),
        _timescale().from_datetime(start_utc),
        _timescale().from_datetime(end_utc),
        altitude_degrees=station.minimum_elevation_deg,
    )
    current_start: datetime | None = start_utc if is_in_contact(tle, station, start_utc) else None
    culmination: datetime | None = None
    windows: list[ContactWindow] = []

    for time, event in zip(times, events, strict=True):
        moment = time.utc_datetime().astimezone(UTC)
        event_code = int(event)
        if event_code == 0:
            current_start = moment
            culmination = None
        elif event_code == 1 and current_start is not None:
            culmination = moment
        elif event_code == 2 and current_start is not None:
            peak_time = culmination or current_start + (moment - current_start) / 2
            peak = propagate_orbit(tle, station, peak_time)
            windows.append(
                ContactWindow(
                    start_utc=current_start,
                    end_utc=moment,
                    maximum_elevation_deg=max(
                        station.minimum_elevation_deg, peak.elevation_deg
                    ),
                    minimum_range_m=_minimum_range(
                        tle, station, current_start, moment, peak_time
                    ),
                )
            )
            current_start = None
            culmination = None

    if current_start is not None and is_in_contact(tle, station, end_utc):
        peak_time = culmination or current_start + (end_utc - current_start) / 2
        peak = propagate_orbit(tle, station, peak_time)
        windows.append(
            ContactWindow(
                start_utc=current_start,
                end_utc=end_utc,
                maximum_elevation_deg=max(station.minimum_elevation_deg, peak.elevation_deg),
                minimum_range_m=_minimum_range(
                    tle, station, current_start, end_utc, peak_time
                ),
            )
        )
    return tuple(windows)
