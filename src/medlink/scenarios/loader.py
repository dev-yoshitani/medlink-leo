"""JSON scenario loader for the fixed-link simulator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from medlink.models import LinkConfig, MedicalData, Priority


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


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("medical_data must be an array")
    return [_mapping(item, f"medical_data[{index}]") for index, item in enumerate(value)]


def load_scenario(path: str | Path) -> FixedScenario:
    """Load and validate a fixed-link JSON scenario."""
    scenario_path = Path(path)
    try:
        payload = json.loads(scenario_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {scenario_path}: {error.msg}") from error

    root = _mapping(payload, "scenario")
    link_data = _mapping(root.get("link"), "link")
    medical_data = tuple(
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
    return FixedScenario(
        schema_version=root.get("schema_version"),
        scenario_id=root.get("scenario_id"),
        description=root.get("description", ""),
        link=LinkConfig(bandwidth_bps=link_data.get("bandwidth_bps")),
        medical_data=medical_data,
    )

