"""End-to-end single-hop simulation over intermittent LEO contacts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from medlink.link import LinkBudgetResult, calculate_link_budget
from medlink.models import MedicalData, Priority
from medlink.orbit import (
    ContactWindow,
    OrbitSample,
    find_contact_windows,
    propagate_orbit_many,
)
from medlink.scenarios import IntermittentScenario
from medlink.scheduling import Strategy, get_scheduler


@dataclass(slots=True)
class _TransferState:
    item: MedicalData
    total_bits: float
    transferred_bits: float = 0.0
    first_started_at_s: float | None = None
    completed_at_s: float | None = None
    transmission_time_s: float = 0.0
    contact_pause_count: int = 0
    selection_order: int | None = None

    @property
    def remaining_bits(self) -> float:
        return max(0.0, self.total_bits - self.transferred_bits)


@dataclass(frozen=True, slots=True)
class IntermittentTransmissionResult:
    data_id: str
    data_type: str
    priority: Priority
    created_at_s: float
    deadline_at_s: float
    total_bits: float
    transferred_bits: float
    remaining_bits: float
    first_started_at_s: float | None
    completed_at_s: float | None
    transmission_time_s: float
    contact_pause_count: int
    selection_order: int | None
    latency_s: float | None
    deadline_met: bool
    deadline_missed: bool
    status: str
    deferred: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = self.priority.name
        payload["priority_rank"] = int(self.priority)
        return payload


@dataclass(frozen=True, slots=True)
class IntermittentMetrics:
    total_items: int
    completed_items: int
    delivered_count: int
    undelivered_count: int
    deferred_count: int
    deadline_met_items: int
    deadline_missed_items: int
    deadline_satisfaction_rate: float
    critical_deadline_satisfaction_rate: float | None
    average_latency_s: float
    maximum_latency_s: float
    simulation_duration_s: float
    total_transmission_time_s: float
    contact_time_s: float
    available_capacity_bits: float
    transferred_bits: float
    link_utilization: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LinkTraceSample:
    time_s: float
    azimuth_deg: float
    elevation_deg: float
    range_m: float
    in_contact: bool
    effective_rate_bps: float
    snr_db: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class IntermittentSimulationReport:
    scenario_id: str
    strategy: Strategy
    results: tuple[IntermittentTransmissionResult, ...]
    metrics: IntermittentMetrics
    contact_windows: tuple[ContactWindow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "scenario_id": self.scenario_id,
            "mode": "intermittent",
            "strategy": self.strategy.value,
            "contact_windows": [window.to_dict() for window in self.contact_windows],
            "results": [result.to_dict() for result in self.results],
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CapacityInterval:
    start_s: float
    end_s: float
    sample: OrbitSample
    link_budget: LinkBudgetResult | None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def effective_rate_bps(self) -> float:
        return self.link_budget.effective_rate_bps if self.link_budget is not None else 0.0


def _event_boundaries(
    scenario: IntermittentScenario, windows: tuple[ContactWindow, ...]
) -> tuple[float, ...]:
    horizon = scenario.horizon_s
    boundaries = {0.0, horizon}
    step = scenario.time_step_s
    count = int(math.ceil(horizon / step))
    boundaries.update(min(index * step, horizon) for index in range(1, count + 1))
    boundaries.update(item.created_at_s for item in scenario.medical_data)
    for window in windows:
        boundaries.add(max(0.0, (window.start_utc - scenario.start_utc).total_seconds()))
        boundaries.add(min(horizon, (window.end_utc - scenario.start_utc).total_seconds()))
    return tuple(sorted(value for value in boundaries if 0 <= value <= horizon))


def build_capacity_trace(
    scenario: IntermittentScenario,
    windows: tuple[ContactWindow, ...] | None = None,
) -> tuple[CapacityInterval, ...]:
    """Build deterministic midpoint-sampled physical capacity intervals."""
    contact_windows = (
        windows
        if windows is not None
        else find_contact_windows(
            scenario.tle,
            scenario.ground_station,
            scenario.start_utc,
            scenario.end_utc,
        )
    )
    boundaries = _event_boundaries(scenario, contact_windows)
    pairs = tuple(zip(boundaries[:-1], boundaries[1:], strict=True))
    midpoints = [
        scenario.start_utc + timedelta(seconds=(start + end) / 2.0) for start, end in pairs
    ]
    samples = propagate_orbit_many(
        scenario.tle,
        scenario.ground_station,
        midpoints,
    )
    intervals: list[CapacityInterval] = []
    for (start, end), sample in zip(pairs, samples, strict=True):
        budget = (
            calculate_link_budget(scenario.rf_link.at_range(sample.range_m))
            if sample.in_contact
            else None
        )
        intervals.append(CapacityInterval(start, end, sample, budget))
    return tuple(intervals)


def _select_next(
    states: dict[str, _TransferState],
    strategy: Strategy,
    now_s: float,
    next_order: int,
) -> _TransferState | None:
    candidates = [
        state.item
        for state in states.values()
        if state.selection_order is None and state.item.created_at_s <= now_s + 1e-9
    ]
    if not candidates:
        return None
    selected = get_scheduler(strategy)(candidates, now_s + 1e-9)
    state = states[selected.id]
    state.selection_order = next_order
    return state


def _results_and_metrics(
    scenario: IntermittentScenario,
    states: dict[str, _TransferState],
    available_capacity_bits: float,
    contact_time_s: float,
) -> tuple[tuple[IntermittentTransmissionResult, ...], IntermittentMetrics]:
    results: list[IntermittentTransmissionResult] = []
    for item in scenario.medical_data:
        state = states[item.id]
        delivered = state.completed_at_s is not None
        deferred = not delivered and item.due_at_s > scenario.horizon_s
        deadline_met = delivered and state.completed_at_s <= item.due_at_s
        deadline_missed = (delivered and not deadline_met) or (
            not delivered and item.due_at_s <= scenario.horizon_s
        )
        latency = state.completed_at_s - item.created_at_s if delivered else None
        results.append(
            IntermittentTransmissionResult(
                data_id=item.id,
                data_type=item.data_type,
                priority=item.priority,
                created_at_s=item.created_at_s,
                deadline_at_s=item.due_at_s,
                total_bits=state.total_bits,
                transferred_bits=state.transferred_bits,
                remaining_bits=state.remaining_bits,
                first_started_at_s=state.first_started_at_s,
                completed_at_s=state.completed_at_s,
                transmission_time_s=state.transmission_time_s,
                contact_pause_count=state.contact_pause_count,
                selection_order=state.selection_order,
                latency_s=latency,
                deadline_met=deadline_met,
                deadline_missed=deadline_missed,
                status="delivered" if delivered else "undelivered",
                deferred=deferred,
            )
        )
    result_tuple = tuple(results)
    delivered_results = [result for result in result_tuple if result.status == "delivered"]
    latencies = [result.latency_s for result in delivered_results if result.latency_s is not None]
    critical = [result for result in result_tuple if result.priority is Priority.CRITICAL]
    total_transferred = min(
        sum(result.transferred_bits for result in result_tuple), available_capacity_bits
    )
    metrics = IntermittentMetrics(
        total_items=len(result_tuple),
        completed_items=len(delivered_results),
        delivered_count=len(delivered_results),
        undelivered_count=len(result_tuple) - len(delivered_results),
        deferred_count=sum(result.deferred for result in result_tuple),
        deadline_met_items=sum(result.deadline_met for result in result_tuple),
        deadline_missed_items=sum(result.deadline_missed for result in result_tuple),
        deadline_satisfaction_rate=sum(result.deadline_met for result in result_tuple)
        / len(result_tuple),
        critical_deadline_satisfaction_rate=(
            sum(result.deadline_met for result in critical) / len(critical) if critical else None
        ),
        average_latency_s=sum(latencies) / len(latencies) if latencies else 0.0,
        maximum_latency_s=max(latencies, default=0.0),
        simulation_duration_s=scenario.horizon_s,
        total_transmission_time_s=sum(result.transmission_time_s for result in result_tuple),
        contact_time_s=contact_time_s,
        available_capacity_bits=available_capacity_bits,
        transferred_bits=total_transferred,
        link_utilization=(
            total_transferred / available_capacity_bits if available_capacity_bits > 0 else 0.0
        ),
    )
    return result_tuple, metrics


def simulate_intermittent(
    scenario: IntermittentScenario,
    strategy: Strategy | str,
    *,
    capacity_trace: tuple[CapacityInterval, ...] | None = None,
    contact_windows: tuple[ContactWindow, ...] | None = None,
) -> IntermittentSimulationReport:
    """Run a resumable, non-preemptive transfer simulation."""
    parsed_strategy = Strategy.parse(strategy)
    windows = (
        contact_windows
        if contact_windows is not None
        else find_contact_windows(
            scenario.tle,
            scenario.ground_station,
            scenario.start_utc,
            scenario.end_utc,
        )
    )
    trace = (
        capacity_trace
        if capacity_trace is not None
        else build_capacity_trace(scenario, windows)
    )
    states = {
        item.id: _TransferState(item=item, total_bits=float(item.size_bytes * 8))
        for item in scenario.medical_data
    }
    active: _TransferState | None = None
    selection_count = 0
    available_capacity_bits = 0.0
    contact_time_s = 0.0
    contact_end_s = {
        (window.end_utc - scenario.start_utc).total_seconds() for window in windows
    }

    for interval in trace:
        rate = interval.effective_rate_bps
        if rate <= 0:
            continue
        duration = interval.duration_s
        contact_time_s += duration
        capacity = rate * duration
        available_capacity_bits += capacity
        local_time = interval.start_s

        while capacity > 1e-9:
            if active is None:
                active = _select_next(states, parsed_strategy, local_time, selection_count)
                if active is None:
                    break
                selection_count += 1
            if active.first_started_at_s is None:
                active.first_started_at_s = local_time
            required_time = active.remaining_bits / rate
            available_time = capacity / rate
            if required_time <= available_time + 1e-12:
                used_bits = active.remaining_bits
                active.transferred_bits = active.total_bits
                active.transmission_time_s += required_time
                local_time += required_time
                capacity = max(0.0, capacity - used_bits)
                active.completed_at_s = local_time
                active = None
            else:
                active.transferred_bits += capacity
                active.transmission_time_s += available_time
                local_time += available_time
                capacity = 0.0

        if active is not None and any(
            abs(interval.end_s - end_s) <= 1e-6 for end_s in contact_end_s
        ):
            active.contact_pause_count += 1

    results, metrics = _results_and_metrics(
        scenario,
        states,
        available_capacity_bits,
        contact_time_s,
    )
    return IntermittentSimulationReport(
        scenario_id=scenario.scenario_id,
        strategy=parsed_strategy,
        results=results,
        metrics=metrics,
        contact_windows=windows,
    )


def generate_link_trace(
    scenario: IntermittentScenario, sample_step_s: float = 10.0
) -> tuple[LinkTraceSample, ...]:
    """Generate a compact physical trace for plots and inspection."""
    if sample_step_s <= 0 or not math.isfinite(sample_step_s):
        raise ValueError("sample_step_s must be a finite number > 0")
    count = int(math.ceil(scenario.horizon_s / sample_step_s))
    elapsed = [min(index * sample_step_s, scenario.horizon_s) for index in range(count + 1)]
    times = [scenario.start_utc + timedelta(seconds=value) for value in elapsed]
    samples = propagate_orbit_many(scenario.tle, scenario.ground_station, times)
    trace: list[LinkTraceSample] = []
    for time_s, sample in zip(elapsed, samples, strict=True):
        budget = (
            calculate_link_budget(scenario.rf_link.at_range(sample.range_m))
            if sample.in_contact
            else None
        )
        trace.append(
            LinkTraceSample(
                time_s=time_s,
                azimuth_deg=sample.azimuth_deg,
                elevation_deg=sample.elevation_deg,
                range_m=sample.range_m,
                in_contact=sample.in_contact,
                effective_rate_bps=budget.effective_rate_bps if budget else 0.0,
                snr_db=budget.snr_db if budget else None,
            )
        )
    return tuple(trace)
