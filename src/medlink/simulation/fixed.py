"""Deterministic fixed-bandwidth simulation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from medlink.metrics import SimulationMetrics, calculate_metrics
from medlink.models import Priority
from medlink.scenarios import FixedScenario
from medlink.scheduling import SCHEDULER_ORDER, Strategy, get_scheduler


@dataclass(frozen=True, slots=True)
class TransmissionResult:
    data_id: str
    data_type: str
    priority: Priority
    created_at_s: float
    deadline_at_s: float
    started_at_s: float
    completed_at_s: float
    transmission_time_s: float
    latency_s: float
    deadline_met: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = self.priority.name
        payload["priority_rank"] = int(self.priority)
        return payload


@dataclass(frozen=True, slots=True)
class SimulationReport:
    scenario_id: str
    strategy: Strategy
    results: tuple[TransmissionResult, ...]
    metrics: SimulationMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "scenario_id": self.scenario_id,
            "strategy": self.strategy.value,
            "results": [result.to_dict() for result in self.results],
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    scenario_id: str
    reports: tuple[Any, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "scenario_id": self.scenario_id,
            "strategies": [
                {"strategy": report.strategy.value, "metrics": report.metrics.to_dict()}
                for report in self.reports
            ],
        }


def simulate(scenario: FixedScenario, strategy: Strategy | str) -> SimulationReport:
    parsed_strategy = Strategy.parse(strategy)
    scheduler = get_scheduler(parsed_strategy)
    remaining = list(scenario.medical_data)
    now_s = 0.0
    results: list[TransmissionResult] = []

    while remaining:
        ready = [item for item in remaining if item.created_at_s <= now_s]
        if not ready:
            now_s = min(item.created_at_s for item in remaining)
            ready = [item for item in remaining if item.created_at_s <= now_s]
        item = scheduler(ready, now_s)
        started_at_s = now_s
        transmission_time_s = scenario.link.transmission_duration_s(item.size_bytes)
        completed_at_s = started_at_s + transmission_time_s
        results.append(
            TransmissionResult(
                data_id=item.id,
                data_type=item.data_type,
                priority=item.priority,
                created_at_s=item.created_at_s,
                deadline_at_s=item.due_at_s,
                started_at_s=started_at_s,
                completed_at_s=completed_at_s,
                transmission_time_s=transmission_time_s,
                latency_s=completed_at_s - item.created_at_s,
                deadline_met=completed_at_s <= item.due_at_s,
            )
        )
        remaining.remove(item)
        now_s = completed_at_s

    result_tuple = tuple(results)
    return SimulationReport(
        scenario_id=scenario.scenario_id,
        strategy=parsed_strategy,
        results=result_tuple,
        metrics=calculate_metrics(result_tuple),
    )


def compare_strategies(scenario: FixedScenario) -> ComparisonReport:
    return ComparisonReport(
        scenario_id=scenario.scenario_id,
        reports=tuple(simulate(scenario, strategy) for strategy in SCHEDULER_ORDER),
    )
