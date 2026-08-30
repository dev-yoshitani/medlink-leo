"""JSON scenario loader for the fixed-link simulator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from medlink.link import RFLinkTemplate
from medlink.models import LinkConfig, MedicalData, Priority, ensure_finite
from medlink.orbit import FrozenTLE, GroundStation, load_bundled_tle
from medlink.orbit.models import parse_utc, require_utc


@dataclass(frozen=True, slots=True)
class FixedScenario:
    schema_version: str
    scenario_id: str
    description: str
    link: LinkConfig
    medical_data: tuple[MedicalData, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be '1.0'")
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not self.medical_data:
            raise ValueError("medical_data must contain at least one item")
        ids = [item.id for item in self.medical_data]
        if len(ids) != len(set(ids)):
            raise ValueError("medical_data IDs must be unique")


@dataclass(frozen=True, slots=True)
class IntermittentScenario:
    schema_version: str
    scenario_id: str
    description: str
    start_utc: datetime
    end_utc: datetime
    time_step_s: float
    tle: FrozenTLE
    ground_station: GroundStation
    rf_link: RFLinkTemplate
    medical_data: tuple[MedicalData, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be '1.0'")
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        object.__setattr__(self, "start_utc", require_utc(self.start_utc, "start_utc"))
        object.__setattr__(self, "end_utc", require_utc(self.end_utc, "end_utc"))
        if self.end_utc <= self.start_utc:
            raise ValueError("simulation end_utc must be after start_utc")
        time_step_s = ensure_finite("time_step_s", self.time_step_s)
        if time_step_s <= 0:
            raise ValueError("time_step_s must be > 0")
        object.__setattr__(self, "time_step_s", time_step_s)
        if not self.medical_data:
            raise ValueError("medical_data must contain at least one item")
        ids = [item.id for item in self.medical_data]
        if len(ids) != len(set(ids)):
            raise ValueError("medical_data IDs must be unique")
        if any(item.created_at_s > self.horizon_s for item in self.medical_data):
            raise ValueError("medical_data created_at_s must be within the simulation horizon")

    @property
    def horizon_s(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds()


Scenario = FixedScenario | IntermittentScenario


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("medical_data must be an array")
    return [_mapping(item, f"medical_data[{index}]") for index, item in enumerate(value)]


def _parse_medical_data(root: dict[str, Any]) -> tuple[MedicalData, ...]:
    return tuple(
        MedicalData(
            id=item.get("id"),
            data_type=item.get("data_type"),
            size_bytes=item.get("size_bytes"),
            priority=Priority.parse(item.get("priority")),
            created_at_s=item.get("created_at_s"),
            deadline_s=item.get("deadline_s"),
        )
        for item in _items(root.get("medical_data"))
    )


def _parse_tle(value: Any) -> FrozenTLE:
    if value == "bundled_iss_zarya_2014":
        return load_bundled_tle()
    payload = _mapping(value, "orbit.tle")
    return FrozenTLE(
        satellite_name=payload.get("satellite_name"),
        line1=payload.get("line1"),
        line2=payload.get("line2"),
        epoch_utc=parse_utc(payload.get("epoch_utc"), "orbit.tle.epoch_utc"),
        source_url=payload.get("source_url", "user-provided"),
        source_note=payload.get("source_note", "User-provided TLE"),
    )


def _load_fixed(root: dict[str, Any]) -> FixedScenario:
    link_data = _mapping(root.get("link"), "link")
    return FixedScenario(
        schema_version=root.get("schema_version"),
        scenario_id=root.get("scenario_id"),
        description=root.get("description", ""),
        link=LinkConfig(bandwidth_bps=link_data.get("bandwidth_bps")),
        medical_data=_parse_medical_data(root),
    )


def _load_intermittent(root: dict[str, Any]) -> IntermittentScenario:
    simulation = _mapping(root.get("simulation"), "simulation")
    orbit = _mapping(root.get("orbit"), "orbit")
    station_data = _mapping(orbit.get("ground_station"), "orbit.ground_station")
    link_data = _mapping(root.get("link"), "link")
    return IntermittentScenario(
        schema_version=root.get("schema_version"),
        scenario_id=root.get("scenario_id"),
        description=root.get("description", ""),
        start_utc=parse_utc(simulation.get("start_utc"), "simulation.start_utc"),
        end_utc=parse_utc(simulation.get("end_utc"), "simulation.end_utc"),
        time_step_s=simulation.get("time_step_s"),
        tle=_parse_tle(orbit.get("tle")),
        ground_station=GroundStation(
            name=station_data.get("name"),
            latitude_deg=station_data.get("latitude_deg"),
            longitude_deg=station_data.get("longitude_deg"),
            altitude_m=station_data.get("altitude_m"),
            minimum_elevation_deg=station_data.get("minimum_elevation_deg"),
        ),
        rf_link=RFLinkTemplate(
            frequency_hz=link_data.get("frequency_hz"),
            tx_power_dbm=link_data.get("tx_power_dbm"),
            tx_antenna_gain_dbi=link_data.get("tx_antenna_gain_dbi"),
            rx_antenna_gain_dbi=link_data.get("rx_antenna_gain_dbi"),
            system_losses_db=link_data.get("system_losses_db"),
            noise_temperature_k=link_data.get("noise_temperature_k"),
            channel_bandwidth_hz=link_data.get("channel_bandwidth_hz"),
            implementation_efficiency=link_data.get("implementation_efficiency"),
            required_snr_db=link_data.get("required_snr_db"),
        ),
        medical_data=_parse_medical_data(root),
    )


def load_scenario(path: str | Path) -> Scenario:
    """Load and validate a fixed or intermittent JSON scenario."""
    scenario_path = Path(path)
    try:
        payload = json.loads(scenario_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {scenario_path}: {error.msg}") from error

    root = _mapping(payload, "scenario")
    mode = root.get("mode", "fixed")
    if mode == "fixed":
        return _load_fixed(root)
    if mode == "intermittent":
        return _load_intermittent(root)
    raise ValueError("mode must be 'fixed' or 'intermittent'")
