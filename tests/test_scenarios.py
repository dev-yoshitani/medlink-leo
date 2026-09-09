from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from medlink.scenarios import RoutingScenario, load_scenario


def test_load_basic_scenario() -> None:
    scenario = load_scenario(Path("examples/basic_scenario.json"))
    assert scenario.scenario_id == "basic-synthetic-v0.1"
    assert len(scenario.medical_data) == 4


def test_load_end_to_end_scenario() -> None:
    scenario = load_scenario(Path("examples/end_to_end_scenario.json"))
    assert scenario.scenario_id == "tokyo-iss-synthetic-v0.4"
    assert scenario.horizon_s == 6_900
    assert scenario.tle.satellite_name == "ISS (ZARYA)"


def test_load_contact_plan_routing_scenario() -> None:
    scenario = load_scenario(Path("examples/contact_plan_medical_routing.json"))
    assert isinstance(scenario, RoutingScenario)
    assert scenario.scenario_id == "east-asia-contact-plan-synthetic-v1.1"
    assert scenario.horizon_s == 6_900
    assert [station.id for station in scenario.ground_stations] == [
        "gs-seoul",
        "gs-sapporo",
        "gs-tokyo",
    ]
    assert [station.backhaul_delay_s for station in scenario.ground_stations] == [
        180.0,
        45.0,
        5.0,
    ]


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "scenario_id": "duplicates",
        "link": {"bandwidth_bps": 1},
        "medical_data": [
            {
                "id": "same",
                "data_type": "synthetic",
                "size_bytes": 1,
                "priority": "NORMAL",
                "created_at_s": 0,
                "deadline_s": 1,
            },
            {
                "id": "same",
                "data_type": "synthetic",
                "size_bytes": 1,
                "priority": "LOW",
                "created_at_s": 0,
                "deadline_s": 2,
            },
        ],
    }
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_scenario(path)


def test_empty_medical_data_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "scenario_id": "empty",
                "link": {"bandwidth_bps": 1},
                "medical_data": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least one"):
        load_scenario(path)


def test_direct_intermittent_scenario_rejects_naive_times() -> None:
    scenario = load_scenario(Path("examples/end_to_end_scenario.json"))
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(
            scenario,
            start_utc=datetime(2014, 1, 20, 22, 55),
            end_utc=datetime(2014, 1, 21, 0, 50),
        )


def test_direct_intermittent_scenario_normalizes_times_to_utc() -> None:
    scenario = load_scenario(Path("examples/end_to_end_scenario.json"))
    jst = timezone(timedelta(hours=9))
    normalized = replace(
        scenario,
        start_utc=datetime(2014, 1, 21, 7, 55, tzinfo=jst),
        end_utc=datetime(2014, 1, 21, 9, 50, tzinfo=jst),
    )
    assert normalized.start_utc == datetime(2014, 1, 20, 22, 55, tzinfo=UTC)
    assert normalized.end_utc == datetime(2014, 1, 21, 0, 50, tzinfo=UTC)
    assert normalized.start_utc.tzinfo is UTC
    assert normalized.end_utc.tzinfo is UTC
