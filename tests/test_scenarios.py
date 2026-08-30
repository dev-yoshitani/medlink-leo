from __future__ import annotations

import json
from pathlib import Path

import pytest

from medlink.scenarios import load_scenario


def test_load_basic_scenario() -> None:
    scenario = load_scenario(Path("examples/basic_scenario.json"))
    assert scenario.scenario_id == "basic-synthetic-v0.1"
    assert len(scenario.medical_data) == 4


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

