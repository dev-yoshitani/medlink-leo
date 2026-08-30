"""Delivery metric calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from medlink.models import Priority

if TYPE_CHECKING:
    from medlink.simulation.fixed import TransmissionResult


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    total_items: int
    completed_items: int
    deadline_met_items: int
    deadline_missed_items: int
    deadline_satisfaction_rate: float
    critical_deadline_satisfaction_rate: float | None
    average_latency_s: float
    maximum_latency_s: float
    simulation_duration_s: float
    total_transmission_time_s: float
    link_utilization: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_metrics(results: tuple[TransmissionResult, ...]) -> SimulationMetrics:
    if not results:
        return SimulationMetrics(0, 0, 0, 0, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0)
    deadline_met = sum(result.deadline_met for result in results)
    critical = [result for result in results if result.priority is Priority.CRITICAL]
    critical_rate = (
        sum(result.deadline_met for result in critical) / len(critical) if critical else None
    )
    latencies = [result.latency_s for result in results]
    simulation_duration = max(result.completed_at_s for result in results)
    total_transmission = sum(result.transmission_time_s for result in results)
    return SimulationMetrics(
        total_items=len(results),
        completed_items=len(results),
        deadline_met_items=deadline_met,
        deadline_missed_items=len(results) - deadline_met,
        deadline_satisfaction_rate=deadline_met / len(results),
        critical_deadline_satisfaction_rate=critical_rate,
        average_latency_s=sum(latencies) / len(latencies),
        maximum_latency_s=max(latencies),
        simulation_duration_s=simulation_duration,
        total_transmission_time_s=total_transmission,
        link_utilization=(
            total_transmission / simulation_duration if simulation_duration > 0 else 0.0
        ),
    )
