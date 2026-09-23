"""Cross-implementation validation; optional Pyorbital is a development dependency."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
from pyorbital.astronomy import observer_position
from pyorbital.orbital import Orbital
from sgp4.api import Satrec, jday

from medlink.orbit import find_contact_windows, propagate_orbit_many
from medlink.scenarios import RoutingScenario, load_scenario

# Set before measuring this fixture: sub-km/sub-degree geometry and sub-timestep events.
# These catch unit/frame/time mistakes; they are not operational accuracy requirements.
LIMITS = {
    "position_m": 100.0,
    "velocity_m_s": 0.1,
    "elevation_deg": 0.05,
    "azimuth_deg": 0.05,
    "range_m": 500.0,
    "event_s": 0.5,
}


def validate_orbit(scenario_path: str | Path) -> dict:
    scenario = load_scenario(scenario_path)
    if not isinstance(scenario, RoutingScenario):
        raise ValueError("validation requires a routing scenario")
    tle = scenario.tle
    reference = Orbital(tle.satellite_name, line1=tle.line1, line2=tle.line2)
    production = Satrec.twoline2rv(tle.line1, tle.line2)
    # Uniform 60 s samples across 24 h near epoch, including both endpoints.
    moments = [tle.epoch_utc + timedelta(seconds=i * 60) for i in range(1441)]
    # Pyorbital accepts UTC numpy datetimes without timezone; conversion is explicit.
    utc = np.array([np.datetime64(t.replace(tzinfo=None)) for t in moments])
    ref_position, ref_velocity = reference.get_position(utc, normalize=False)
    if not np.isfinite(ref_position).all() or not np.isfinite(ref_velocity).all():
        raise ValueError("reference state contains non-finite values")
    position_errors, velocity_errors = [], []
    for i, moment in enumerate(moments):
        jd, fraction = jday(
            moment.year,
            moment.month,
            moment.day,
            moment.hour,
            moment.minute,
            moment.second + moment.microsecond / 1e6,
        )
        error, position, velocity = production.sgp4(jd, fraction)
        if error:
            raise ValueError(f"SGP4 propagation failed with code {error}")
        if not np.isfinite(position).all() or not np.isfinite(velocity).all():
            raise ValueError("production state contains non-finite values")
        position_errors.append(float(np.linalg.norm(position - ref_position[:, i]) * 1000))
        velocity_errors.append(float(np.linalg.norm(velocity - ref_velocity[:, i]) * 1000))
    maxima = {
        "position_m": max(position_errors),
        "velocity_m_s": max(velocity_errors),
        "elevation_deg": 0.0,
        "azimuth_deg": 0.0,
        "range_m": 0.0,
        "event_s": 0.0,
    }
    station_rows = []
    for entry in scenario.ground_stations:
        ground = entry.ground_station
        args = (ground.longitude_deg, ground.latitude_deg, ground.altitude_m / 1000)
        azimuth, elevation = reference.get_observer_look(utc, *args)
        observer, _ = observer_position(utc, *args)
        ranges = (
            np.linalg.norm(ref_position - np.array(np.broadcast_arrays(*observer)), axis=0) * 1000
        )
        samples = propagate_orbit_many(tle, ground, moments)
        if not all(np.isfinite(value).all() for value in (azimuth, elevation, ranges)):
            raise ValueError("reference geometry contains non-finite values")
        for i, sample in enumerate(samples):
            if not np.isfinite([sample.elevation_deg, sample.azimuth_deg, sample.range_m]).all():
                raise ValueError("production geometry contains non-finite values")
            maxima["elevation_deg"] = max(
                maxima["elevation_deg"], abs(sample.elevation_deg - float(elevation[i]))
            )
            maxima["azimuth_deg"] = max(
                maxima["azimuth_deg"],
                abs((sample.azimuth_deg - float(azimuth[i]) + 180) % 360 - 180),
            )
            maxima["range_m"] = max(maxima["range_m"], abs(sample.range_m - float(ranges[i])))
        for mask in (10.0, 20.0):
            windows = find_contact_windows(
                tle, replace(ground, minimum_elevation_deg=mask), moments[0], moments[-1]
            )
            passes = reference.get_next_passes(
                moments[0].replace(tzinfo=None), 24, *args, tol=0.001, horizon=mask
            )
            if len(windows) != len(passes):
                raise AssertionError(f"contact count mismatch: {entry.id}, {mask}")
            errors = [
                abs((actual.replace(tzinfo=None) - expected).total_seconds())
                for window, ref in zip(windows, passes, strict=True)
                for actual, expected in ((window.start_utc, ref[0]), (window.end_utc, ref[1]))
            ]
            if not errors:
                raise AssertionError("validation fixture must contain contacts")
            maxima["event_s"] = max(maxima["event_s"], max(errors))
            station_rows.append(
                {
                    "station": entry.id,
                    "mask_deg": mask,
                    "contact_count": len(windows),
                    "max_event_error_s": max(errors),
                }
            )
    return {
        "scope": "cross-implementation agreement, not measured orbit truth",
        "tle_sha256": hashlib.sha256((tle.line1 + "\n" + tle.line2).encode()).hexdigest(),
        "versions": {name: version(name) for name in ("pyorbital", "sgp4", "skyfield", "numpy")},
        "start_utc": moments[0].isoformat(),
        "end_utc": moments[-1].isoformat(),
        "sample_count": len(moments),
        "sample_step_s": 60,
        "max_errors": maxima,
        "limits": LIMITS,
        "contacts": station_rows,
        "passed": all(maxima[key] <= limit for key, limit in LIMITS.items()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="examples/contact_plan_medical_routing.json")
    parser.add_argument("--output", default="artifacts/orbit-validation.json")
    args = parser.parse_args()
    result = validate_orbit(args.scenario)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit("orbit validation exceeded predeclared tolerances")


if __name__ == "__main__":
    main()
