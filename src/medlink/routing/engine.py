"""Greedy single-radio routing over a deterministic contact plan."""

from __future__ import annotations

from dataclasses import replace

from medlink.models import MedicalData, Priority
from medlink.routing.contact_plan import build_contact_plan
from medlink.routing.models import (
    ROUTING_STRATEGY_ORDER,
    ContactPlan,
    RouteCandidate,
    RouteFailureReason,
    RouteResult,
    RoutingComparisonReport,
    RoutingMetrics,
    RoutingReport,
    RoutingStrategy,
)
from medlink.scenarios import RoutingGroundStation, RoutingScenario
from medlink.scheduling import Strategy, get_scheduler
from medlink.simulation.capacity import estimate_capacity_transfer


def _candidate_for_contact(
    *,
    scenario: RoutingScenario,
    item: MedicalData,
    now_s: float,
    contact,
    station: RoutingGroundStation,
) -> RouteCandidate:
    earliest = max(now_s, item.created_at_s, contact.start_s)
    required = float(item.size_bytes * 8)
    estimate = estimate_capacity_transfer(
        contact.intervals,
        earliest_start_s=earliest,
        required_bits=required,
    )
    arrival = (
        estimate.completed_s + contact.propagation_delay_s + station.backhaul_delay_s
        if estimate.completed_s is not None
        else None
    )
    horizon_feasible = arrival is not None and arrival <= scenario.horizon_s + 1e-9
    deadline_feasible = arrival is not None and arrival <= item.due_at_s + 1e-9
    failure: RouteFailureReason | None = None
    if estimate.completed_s is None:
        failure = RouteFailureReason.INSUFFICIENT_CAPACITY
    elif not horizon_feasible:
        failure = RouteFailureReason.OUTSIDE_SIMULATION_HORIZON
    return RouteCandidate(
        ground_station_id=station.id,
        ground_station_name=station.ground_station.name,
        contact_id=contact.contact_id,
        contact_start_s=contact.start_s,
        contact_end_s=contact.end_s,
        estimated_departure_s=estimate.departure_s,
        estimated_rf_completion_s=estimate.completed_s,
        estimated_arrival_s=arrival,
        deadline_at_s=item.due_at_s,
        deadline_feasible=deadline_feasible,
        horizon_feasible=horizon_feasible,
        transfer_duration_s=estimate.transmission_time_s,
        capacity_required_bits=required,
        capacity_available_bits=estimate.capacity_available_bits,
        capacity_remaining_bits=max(0.0, estimate.capacity_available_bits - required),
        propagation_delay_s=contact.propagation_delay_s,
        backhaul_delay_s=station.backhaul_delay_s,
        failure_reason=failure,
    )


def _candidate_rank(
    candidate: RouteCandidate, strategy: RoutingStrategy
) -> tuple[float | str, ...]:
    departure = candidate.estimated_departure_s or 0.0
    completion = candidate.estimated_rf_completion_s or float("inf")
    arrival = candidate.estimated_arrival_s or float("inf")
    capacity_tie = -candidate.capacity_remaining_bits
    stable = (candidate.ground_station_id, candidate.contact_id)
    if strategy is RoutingStrategy.NEXT_CONTACT:
        return (departure, completion, capacity_tie, *stable)
    if strategy is RoutingStrategy.EARLIEST_ARRIVAL:
        return (arrival, departure, completion, capacity_tie, *stable)
    return (arrival, capacity_tie, departure, *stable)


def _selection_reason(
    selected: RouteCandidate,
    eligible: list[RouteCandidate],
    strategy: RoutingStrategy,
) -> str:
    assert selected.estimated_arrival_s is not None
    if strategy is RoutingStrategy.NEXT_CONTACT:
        basis = (
            f"Selected {selected.ground_station_id} / {selected.contact_id} because it offers "
            f"the earliest feasible RF departure at {selected.estimated_departure_s:.3f} s."
        )
    elif strategy is RoutingStrategy.EARLIEST_ARRIVAL:
        basis = (
            f"Selected {selected.ground_station_id} / {selected.contact_id} because its "
            f"estimated hospital arrival at {selected.estimated_arrival_s:.3f} s is earliest "
            "after waiting, dynamic-rate transfer, propagation, and backhaul."
        )
    else:
        margin = selected.deadline_at_s - float(selected.estimated_arrival_s)
        basis = (
            f"Selected {selected.ground_station_id} / {selected.contact_id} because it is "
            f"deadline-feasible, has the earliest estimated arrival at "
            f"{selected.estimated_arrival_s:.3f} s, and retains "
            f"{selected.capacity_remaining_bits:.0f} contact bits; deadline margin is "
            f"{margin:.3f} s."
        )
    if len(eligible) > 1 and strategy is not RoutingStrategy.NEXT_CONTACT:
        runner_up = sorted(eligible, key=lambda value: _candidate_rank(value, strategy))[1]
        assert runner_up.estimated_arrival_s is not None
        delta = float(runner_up.estimated_arrival_s) - float(selected.estimated_arrival_s)
        basis += f" The next-best feasible route arrives {delta:.3f} s later."
    return basis


def _failure_result(
    *,
    item: MedicalData,
    strategy: RoutingStrategy,
    scheduling_order: int,
    reason: RouteFailureReason,
    candidates: tuple[RouteCandidate, ...],
) -> RouteResult:
    explanations = {
        RouteFailureReason.NO_CONTACT: "No contact remains after the item becomes ready.",
        RouteFailureReason.INSUFFICIENT_CAPACITY: (
            "Contacts remain, but none has enough unelapsed capacity to complete the item."
        ),
        RouteFailureReason.DEADLINE_INFEASIBLE: (
            "Capacity-feasible routes exist, but none reaches the hospital by the deadline."
        ),
        RouteFailureReason.OUTSIDE_SIMULATION_HORIZON: (
            "No candidate can reach the hospital inside the finite simulation horizon."
        ),
    }
    return RouteResult(
        medical_data_id=item.id,
        data_type=item.data_type,
        priority=item.priority,
        created_at_s=item.created_at_s,
        strategy=strategy,
        scheduling_order=scheduling_order,
        selected_ground_station=None,
        selected_ground_station_name=None,
        selected_contact_id=None,
        estimated_departure_s=None,
        estimated_rf_completion_s=None,
        estimated_arrival_s=None,
        deadline_at_s=item.due_at_s,
        deadline_feasible=False,
        deadline_margin_s=None,
        transfer_duration_s=None,
        capacity_required_bits=float(item.size_bytes * 8),
        capacity_available_bits=max(
            (candidate.capacity_available_bits for candidate in candidates), default=0.0
        ),
        decision_reason=explanations[reason],
        failure_reason=reason,
        candidates=candidates,
    )


def _route_item(
    *,
    scenario: RoutingScenario,
    plan: ContactPlan,
    item: MedicalData,
    now_s: float,
    strategy: RoutingStrategy,
    scheduling_order: int,
) -> RouteResult:
    if max(now_s, item.created_at_s) >= scenario.horizon_s - 1e-9:
        return _failure_result(
            item=item,
            strategy=strategy,
            scheduling_order=scheduling_order,
            reason=RouteFailureReason.OUTSIDE_SIMULATION_HORIZON,
            candidates=(),
        )
    station_by_id = {station.id: station for station in scenario.ground_stations}
    relevant = tuple(
        contact
        for contact in plan.contacts
        if contact.end_s > max(now_s, item.created_at_s) + 1e-9
    )
    if not relevant:
        return _failure_result(
            item=item,
            strategy=strategy,
            scheduling_order=scheduling_order,
            reason=RouteFailureReason.NO_CONTACT,
            candidates=(),
        )
    candidates = tuple(
        _candidate_for_contact(
            scenario=scenario,
            item=item,
            now_s=now_s,
            contact=contact,
            station=station_by_id[contact.ground_station_id],
        )
        for contact in relevant
    )
    capacity_feasible = [
        candidate
        for candidate in candidates
        if candidate.estimated_rf_completion_s is not None
    ]
    if not capacity_feasible:
        return _failure_result(
            item=item,
            strategy=strategy,
            scheduling_order=scheduling_order,
            reason=RouteFailureReason.INSUFFICIENT_CAPACITY,
            candidates=candidates,
        )
    horizon_feasible = [candidate for candidate in capacity_feasible if candidate.horizon_feasible]
    if not horizon_feasible:
        return _failure_result(
            item=item,
            strategy=strategy,
            scheduling_order=scheduling_order,
            reason=RouteFailureReason.OUTSIDE_SIMULATION_HORIZON,
            candidates=candidates,
        )
    eligible = horizon_feasible
    if strategy is RoutingStrategy.DEADLINE_AWARE:
        eligible = [candidate for candidate in horizon_feasible if candidate.deadline_feasible]
        if not eligible:
            return _failure_result(
                item=item,
                strategy=strategy,
                scheduling_order=scheduling_order,
                reason=RouteFailureReason.DEADLINE_INFEASIBLE,
                candidates=candidates,
            )
    selected = min(eligible, key=lambda value: _candidate_rank(value, strategy))
    assert selected.estimated_arrival_s is not None
    marked = tuple(
        replace(candidate, selected=candidate.contact_id == selected.contact_id)
        for candidate in candidates
    )
    margin = item.due_at_s - float(selected.estimated_arrival_s)
    return RouteResult(
        medical_data_id=item.id,
        data_type=item.data_type,
        priority=item.priority,
        created_at_s=item.created_at_s,
        strategy=strategy,
        scheduling_order=scheduling_order,
        selected_ground_station=selected.ground_station_id,
        selected_ground_station_name=selected.ground_station_name,
        selected_contact_id=selected.contact_id,
        estimated_departure_s=selected.estimated_departure_s,
        estimated_rf_completion_s=selected.estimated_rf_completion_s,
        estimated_arrival_s=selected.estimated_arrival_s,
        deadline_at_s=item.due_at_s,
        deadline_feasible=selected.deadline_feasible,
        deadline_margin_s=margin,
        transfer_duration_s=selected.transfer_duration_s,
        capacity_required_bits=selected.capacity_required_bits,
        capacity_available_bits=selected.capacity_available_bits,
        decision_reason=_selection_reason(selected, eligible, strategy),
        failure_reason=None,
        candidates=marked,
    )


def _metrics(
    scenario: RoutingScenario,
    plan: ContactPlan,
    results: tuple[RouteResult, ...],
) -> RoutingMetrics:
    delivered = [result for result in results if result.delivered]
    critical = [result for result in results if result.priority is Priority.CRITICAL]
    latencies: list[float] = []
    for result in delivered:
        latency = result.latency_s
        assert latency is not None
        latencies.append(latency)
    transferred = sum(result.capacity_required_bits for result in delivered)
    selection = {
        station.id: sum(result.selected_ground_station == station.id for result in delivered)
        for station in sorted(scenario.ground_stations, key=lambda value: value.id)
    }
    failures = {
        reason.value: sum(result.failure_reason is reason for result in results)
        for reason in RouteFailureReason
    }
    deadline_met = sum(result.deadline_feasible for result in results)
    return RoutingMetrics(
        total_items=len(results),
        delivered_count=len(delivered),
        failed_count=len(results) - len(delivered),
        deadline_met_items=deadline_met,
        deadline_missed_items=len(results) - deadline_met,
        deadline_satisfaction_rate=deadline_met / len(results),
        critical_deadline_satisfaction_rate=(
            sum(result.deadline_feasible for result in critical) / len(critical)
            if critical
            else None
        ),
        delivery_ratio=len(delivered) / len(results),
        average_end_to_end_latency_s=(sum(latencies) / len(latencies) if latencies else 0.0),
        maximum_end_to_end_latency_s=max(latencies, default=0.0),
        contact_capacity_bits=plan.total_available_capacity_bits,
        transferred_bits=transferred,
        contact_utilization=(
            transferred / plan.total_available_capacity_bits
            if plan.total_available_capacity_bits > 0
            else 0.0
        ),
        ground_station_selection=selection,
        failure_counts=failures,
    )


def route_scenario(
    scenario: RoutingScenario,
    strategy: RoutingStrategy | str,
    *,
    scheduling_strategy: Strategy | str | None = None,
    contact_plan: ContactPlan | None = None,
) -> RoutingReport:
    """Route every item using one shared single-radio timeline."""
    parsed_strategy = RoutingStrategy.parse(strategy)
    scheduler_strategy = Strategy.parse(scheduling_strategy or scenario.scheduling_strategy)
    plan = contact_plan or build_contact_plan(scenario)
    if plan.scenario_id != scenario.scenario_id:
        raise ValueError("contact plan scenario_id must match the routing scenario")
    scheduler = get_scheduler(scheduler_strategy)
    pending = {item.id: item for item in scenario.medical_data}
    results: list[RouteResult] = []
    now_s = 0.0
    order = 0
    while pending:
        ready = [item for item in pending.values() if item.created_at_s <= now_s + 1e-9]
        if not ready:
            now_s = min(item.created_at_s for item in pending.values())
            ready = [item for item in pending.values() if item.created_at_s <= now_s + 1e-9]
        selected_item = scheduler(ready, now_s + 1e-9)
        pending.pop(selected_item.id)
        result = _route_item(
            scenario=scenario,
            plan=plan,
            item=selected_item,
            now_s=now_s,
            strategy=parsed_strategy,
            scheduling_order=order,
        )
        results.append(result)
        order += 1
        if result.estimated_rf_completion_s is not None and result.failure_reason is None:
            now_s = result.estimated_rf_completion_s
    result_tuple = tuple(results)
    return RoutingReport(
        scenario_id=scenario.scenario_id,
        strategy=parsed_strategy,
        scheduling_strategy=scheduler_strategy.value,
        contact_plan=plan,
        results=result_tuple,
        metrics=_metrics(scenario, plan, result_tuple),
    )


def compare_routing_strategies(
    scenario: RoutingScenario,
    *,
    scheduling_strategy: Strategy | str | None = None,
    contact_plan: ContactPlan | None = None,
) -> RoutingComparisonReport:
    """Compare all routing strategies with the same scenario and contact plan."""
    scheduler_strategy = Strategy.parse(scheduling_strategy or scenario.scheduling_strategy)
    plan = contact_plan or build_contact_plan(scenario)
    reports = tuple(
        route_scenario(
            scenario,
            strategy,
            scheduling_strategy=scheduler_strategy,
            contact_plan=plan,
        )
        for strategy in ROUTING_STRATEGY_ORDER
    )
    return RoutingComparisonReport(
        scenario_id=scenario.scenario_id,
        scheduling_strategy=scheduler_strategy.value,
        contact_plan=plan,
        reports=reports,
    )
