from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from medlink.orbit import (
    GroundStation,
    find_contact_windows,
    load_bundled_tle,
    propagate_orbit,
    propagate_orbit_many,
)


def station(minimum_elevation_deg: float = 10.0) -> GroundStation:
    return GroundStation(
        name="Tokyo Reference Ground Station",
        latitude_deg=35.6895,
        longitude_deg=139.6917,
        altitude_m=40.0,
        minimum_elevation_deg=minimum_elevation_deg,
    )


def test_bundled_tle_loads_with_documented_epoch() -> None:
    tle = load_bundled_tle()
    assert tle.satellite_name == "ISS (ZARYA)"
    assert tle.epoch_utc == datetime(2014, 1, 20, 22, 23, 4, tzinfo=UTC)


def test_fixed_time_propagation_is_deterministic() -> None:
    tle = load_bundled_tle()
    at = datetime(2014, 1, 20, 22, 23, 4, tzinfo=UTC)
    first = propagate_orbit(tle, station(), at)
    second = propagate_orbit(tle, station(), at)
    assert first == second
    assert first.azimuth_deg == pytest.approx(284.388827, abs=1e-6)
    assert first.elevation_deg == pytest.approx(-73.098268, abs=1e-6)
    assert first.range_m == pytest.approx(12_639_664.78, abs=0.02)
    assert first.in_contact is False


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        propagate_orbit(
            load_bundled_tle(), station(), datetime(2014, 1, 20, 22, 23, 4)
        )


def test_vector_propagation_matches_scalar_results() -> None:
    tle = load_bundled_tle()
    times = [tle.epoch_utc, tle.epoch_utc + timedelta(minutes=5)]
    vector = propagate_orbit_many(tle, station(), times)
    scalar = tuple(propagate_orbit(tle, station(), moment) for moment in times)
    assert vector == scalar


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude_deg", 91.0),
        ("longitude_deg", -181.0),
        ("minimum_elevation_deg", -1.0),
        ("minimum_elevation_deg", 90.0),
    ],
)
def test_ground_station_validation(field: str, value: float) -> None:
    values = {
        "name": "station",
        "latitude_deg": 0.0,
        "longitude_deg": 0.0,
        "altitude_m": 0.0,
        "minimum_elevation_deg": 10.0,
    }
    values[field] = value
    with pytest.raises(ValueError):
        GroundStation(**values)


def test_contact_windows_are_ordered_and_above_threshold() -> None:
    tle = load_bundled_tle()
    start = tle.epoch_utc
    windows = find_contact_windows(tle, station(), start, start + timedelta(hours=24))
    assert len(windows) == 5
    assert all(window.start_utc < window.end_utc for window in windows)
    assert all(window.maximum_elevation_deg >= 10.0 for window in windows)
    assert all(window.minimum_range_m > 0 for window in windows)
    assert list(windows) == sorted(windows, key=lambda window: window.start_utc)


def test_high_mask_has_no_more_contacts_than_low_mask() -> None:
    tle = load_bundled_tle()
    start = tle.epoch_utc
    end = start + timedelta(hours=24)
    low = find_contact_windows(tle, station(5.0), start, end)
    high = find_contact_windows(tle, station(30.0), start, end)
    assert len(high) <= len(low)


def test_short_below_horizon_interval_has_no_contact() -> None:
    tle = load_bundled_tle()
    start = tle.epoch_utc
    sample = propagate_orbit(tle, station(), start)
    assert sample.in_contact is False
    assert find_contact_windows(tle, station(), start, start + timedelta(seconds=30)) == ()


def test_end_must_follow_start() -> None:
    tle = load_bundled_tle()
    with pytest.raises(ValueError, match="after"):
        find_contact_windows(tle, station(), tle.epoch_utc, tle.epoch_utc)
