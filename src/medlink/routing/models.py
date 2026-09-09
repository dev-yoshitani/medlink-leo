"""Public models for deterministic contact-plan-aware routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from medlink.models import Priority
from medlink.orbit import utc_iso
from medlink.simulation.capacity import CapacityInterval


class RoutingStrategy(StrEnum):
    NEXT_CONTACT = "next-contact"
    EARLIEST_ARRIVAL = "earliest-arrival"
    DEADLINE_AWARE = "deadline-aware"

    @classmethod
    def parse(cls, value: RoutingStrategy | str) -> RoutingStrategy:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).lower())
        except ValueError as error:
            choices = ", ".join(strategy.value for strategy in cls)
            raise ValueError(f"routing strategy must be one of: {choices}") from error


ROUTING_STRATEGY_ORDER: tuple[RoutingStrategy, ...] = (
    RoutingStrategy.NEXT_CONTACT,
    RoutingStrategy.EARLIEST_ARRIVAL,
    RoutingStrategy.DEADLINE_AWARE,
)


class RouteFailureReason(StrEnum):
    NO_CONTACT = "NO_CONTACT"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
    DEADLINE_INFEASIBLE = "DEADLINE_INFEASIBLE"
    OUTSIDE_SIMULATION_HORIZON = "OUTSIDE_SIMULATION_HORIZON"


@dataclass(frozen=True, slots=True)
class ContactPlanEntry:
    contact_id: str
    source: str
    destination: str
    ground_station_id: str
    ground_station_name: str
    start_s: float
    end_s: float
    start_utc: datetime
    end_utc: datetime
    available_capacity_bits: float
    propagation_delay_s: float
    maximum_elevation_deg: float
    minimum_range_m: float
    intervals: tuple[CapacityInterval, ...] = field(repr=False)

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "source": self.source,
            "destination": self.destination,
            "ground_station_id": self.ground_station_id,
            "ground_station_name": self.ground_station_name,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "start_utc": utc_iso(self.start_utc),
            "end_utc": utc_iso(self.end_utc),
            "duration_s": self.duration_s,
            "available_capacity_bits": self.available_capacity_bits,
            "propagation_delay_s": self.propagation_delay_s,
            "maximum_elevation_deg": self.maximum_elevation_deg,
            "minimum_range_m": self.minimum_range_m,
        }


@dataclass(frozen=True, slots=True)
class ContactPlan:
    scenario_id: str
    source: str
    contacts: tuple[ContactPlanEntry, ...]

    @property
    def total_available_capacity_bits(self) -> float:
        return sum(contact.available_capacity_bits for contact in self.contacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "scenario_id": self.scenario_id,
            "source": self.source,
            "contact_count": len(self.contacts),
            "total_available_capacity_bits": self.total_available_capacity_bits,
            "contacts": [contact.to_dict() for contact in self.contacts],
        }


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    ground_station_id: str
    ground_station_name: str
    contact_id: str
    contact_start_s: float
    contact_end_s: float
    estimated_departure_s: float | None
    estimated_rf_completion_s: float | None
    estimated_arrival_s: float | None
    deadline_at_s: float
    deadline_feasible: bool
    horizon_feasible: bool
    transfer_duration_s: float
    capacity_required_bits: float
    capacity_available_bits: float
    capacity_remaining_bits: float
    propagation_delay_s: float
    backhaul_delay_s: float
    failure_reason: RouteFailureReason | None = None
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failure_reason"] = self.failure_reason.value if self.failure_reason else None
        return payload


@dataclass(frozen=True, slots=True)
class RouteResult:
    medical_data_id: str
    data_type: str
    priority: Priority
    created_at_s: float
    strategy: RoutingStrategy
    scheduling_order: int
    selected_ground_station: str | None
    selected_ground_station_name: str | None
    selected_contact_id: str | None
    estimated_departure_s: float | None
    estimated_rf_completion_s: float | None
    estimated_arrival_s: float | None
    deadline_at_s: float
    deadline_feasible: bool
    deadline_margin_s: float | None
    transfer_duration_s: float | None
    capacity_required_bits: float
    capacity_available_bits: float
    decision_reason: str
    failure_reason: RouteFailureReason | None
    candidates: tuple[RouteCandidate, ...]

    @property
    def delivered(self) -> bool:
        return self.failure_reason is None and self.estimated_arrival_s is not None

    @property
    def latency_s(self) -> float | None:
        if self.estimated_arrival_s is None:
            return None
        return self.estimated_arrival_s - self.created_at_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "medical_data_id": self.medical_data_id,
            "data_type": self.data_type,
            "priority": self.priority.name,
            "priority_rank": int(self.priority),
            "created_at_s": self.created_at_s,
            "strategy": self.strategy.value,
            "scheduling_order": self.scheduling_order,
            "status": "delivered" if self.delivered else "failed",
            "selected_ground_station": self.selected_ground_station,
            "selected_ground_station_name": self.selected_ground_station_name,
            "selected_contact_id": self.selected_contact_id,
            "estimated_departure_s": self.estimated_departure_s,
            "estimated_rf_completion_s": self.estimated_rf_completion_s,
            "estimated_arrival_s": self.estimated_arrival_s,
            "deadline_at_s": self.deadline_at_s,
            "deadline_feasible": self.deadline_feasible,
            "deadline_margin_s": self.deadline_margin_s,
            "transfer_duration_s": self.transfer_duration_s,
            "latency_s": self.latency_s,
            "capacity_required_bits": self.capacity_required_bits,
            "capacity_available_bits": self.capacity_available_bits,
            "decision_reason": self.decision_reason,
            "failure_reason": self.failure_reason.value if self.failure_reason else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class RoutingMetrics:
    total_items: int
    delivered_count: int
    failed_count: int
    deadline_met_items: int
    deadline_missed_items: int
    deadline_satisfaction_rate: float
    critical_deadline_satisfaction_rate: float | None
    delivery_ratio: float
    average_end_to_end_latency_s: float
    maximum_end_to_end_latency_s: float
    contact_capacity_bits: float
    transferred_bits: float
    contact_utilization: float
    ground_station_selection: dict[str, int]
    failure_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RoutingReport:
    scenario_id: str
    strategy: RoutingStrategy
    scheduling_strategy: str
    contact_plan: ContactPlan
    results: tuple[RouteResult, ...]
    metrics: RoutingMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "scenario_id": self.scenario_id,
            "mode": "routing",
            "strategy": self.strategy.value,
            "scheduling_strategy": self.scheduling_strategy,
            "contact_plan": self.contact_plan.to_dict(),
            "results": [result.to_dict() for result in self.results],
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class RoutingComparisonReport:
    scenario_id: str
    scheduling_strategy: str
    contact_plan: ContactPlan
    reports: tuple[RoutingReport, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "scenario_id": self.scenario_id,
            "mode": "routing-comparison",
            "scheduling_strategy": self.scheduling_strategy,
            "contact_plan": self.contact_plan.to_dict(),
            "strategies": [report.to_dict() for report in self.reports],
        }
