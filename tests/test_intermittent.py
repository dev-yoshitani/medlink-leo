from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from medlink.link import LinkBudgetResult, RFLinkTemplate
from medlink.models import MedicalData, Priority
from medlink.orbit import (
    ContactWindow,
    GroundStation,
    OrbitSample,
    find_contact_windows,
    load_bundled_tle,
)
from medlink.scenarios import IntermittentScenario, load_scenario
from medlink.simulation import CapacityInterval, build_capacity_trace, simulate_intermittent

START = datetime(2014, 1, 20, 22, 0, tzinfo=UTC)


def item(
    identifier: str,
    *,
    size_bytes: int = 1,
    priority: Priority = Priority.NORMAL,
    created_at_s: float = 0.0,
    deadline_s: float = 10.0,
) -> MedicalData:
    return MedicalData(
        identifier,
        "synthetic",
        size_bytes,
        priority,
        created_at_s,
        deadline_s,
    )


def scenario(
    *items: MedicalData, horizon_s: float = 3.0, step_s: float = 1.0
) -> IntermittentScenario:
    return IntermittentScenario(
        schema_version="1.0",
        scenario_id="intermittent-test",
        description="",
        start_utc=START,
        end_utc=START + timedelta(seconds=horizon_s),
        time_step_s=step_s,
        tle=load_bundled_tle(),
        ground_station=GroundStation("test", 0.0, 0.0, 0.0, 10.0),
        rf_link=RFLinkTemplate(1.0e9, 30.0, 0.0, 0.0, 0.0, 290.0, 1.0e6, 0.5),
        medical_data=items,
    )


def budget(rate_bps: float) -> LinkBudgetResult:
    return LinkBudgetResult(0.0, 0.0, 0.0, 0.0, rate_bps, rate_bps, None)


def interval(start_s: float, end_s: float, rate_bps: float = 0.0) -> CapacityInterval:
    in_contact = rate_bps > 0
    return CapacityInterval(
        start_s,
        end_s,
        OrbitSample(
            START + timedelta(seconds=(start_s + end_s) / 2),
            0.0,
            20.0 if in_contact else -20.0,
            1_000_000.0,
            in_contact,
        ),
        budget(rate_bps) if in_contact else None,
    )


def window(start_s: float, end_s: float) -> ContactWindow:
    return ContactWindow(
        START + timedelta(seconds=start_s),
        START + timedelta(seconds=end_s),
        20.0,
        1_000_000.0,
    )


def test_no_contact_means_zero_transfer() -> None:
    report = simulate_intermittent(
        scenario(item("a")),
        "fifo",
        capacity_trace=(interval(0, 3),),
        contact_windows=(),
    )
    result = report.results[0]
    assert result.transferred_bits == 0
    assert result.status == "undelivered"
    assert report.metrics.link_utilization == 0


def test_transfer_pauses_and_same_item_resumes() -> None:
    report = simulate_intermittent(
        scenario(item("a", size_bytes=2)),
        "fifo",
        capacity_trace=(interval(0, 1, 8), interval(1, 2), interval(2, 3, 8)),
        contact_windows=(window(0, 1), window(2, 3)),
    )
    result = report.results[0]
    assert result.status == "delivered"
    assert result.transferred_bits == 16
    assert result.remaining_bits == 0
    assert result.first_started_at_s == 0
    assert result.completed_at_s == 3
    assert result.contact_pause_count == 1


def test_new_critical_item_does_not_preempt_active_transfer() -> None:
    report = simulate_intermittent(
        scenario(
            item("low", size_bytes=2, priority=Priority.LOW),
            item("critical", priority=Priority.CRITICAL, created_at_s=0.5),
        ),
        "priority",
        capacity_trace=(interval(0, 3, 8),),
        contact_windows=(window(0, 3),),
    )
    by_id = {result.data_id: result for result in report.results}
    assert by_id["low"].selection_order == 0
    assert by_id["low"].completed_at_s == 2
    assert by_id["critical"].selection_order == 1
    assert by_id["critical"].first_started_at_s == 2


def test_horizon_classifies_undelivered_and_deferred() -> None:
    report = simulate_intermittent(
        scenario(
            item("overdue", size_bytes=100, deadline_s=1),
            item("future", size_bytes=100, deadline_s=10),
            horizon_s=2,
        ),
        "fifo",
        capacity_trace=(interval(0, 2, 8),),
        contact_windows=(window(0, 2),),
    )
    by_id = {result.data_id: result for result in report.results}
    assert by_id["overdue"].deadline_missed is True
    assert by_id["overdue"].deferred is False
    assert by_id["future"].deferred is True
    assert report.metrics.undelivered_count == 2
    assert report.metrics.deferred_count == 1


def test_capacity_trace_rate_changes_with_range(monkeypatch) -> None:
    test_scenario = scenario(item("a"), horizon_s=2)

    def fake_propagation(tle, ground_station, times):
        del tle, ground_station
        return (
            OrbitSample(times[0], 0.0, 20.0, 1_000.0, True),
            OrbitSample(times[1], 0.0, 20.0, 2_000.0, True),
        )

    monkeypatch.setattr(
        "medlink.simulation.intermittent.propagate_orbit_many", fake_propagation
    )
    trace = build_capacity_trace(test_scenario, (window(0, 2),))
    assert len(trace) == 2
    assert trace[0].sample.range_m < trace[1].sample.range_m
    assert trace[0].effective_rate_bps > trace[1].effective_rate_bps


def test_explicit_empty_contact_windows_do_not_trigger_a_second_search(
    monkeypatch,
) -> None:
    test_scenario = scenario(item("a"), horizon_s=2)

    def unexpected_search(*args, **kwargs):
        del args, kwargs
        raise AssertionError("explicit contact windows must be honored")

    monkeypatch.setattr(
        "medlink.simulation.intermittent.find_contact_windows", unexpected_search
    )
    trace = build_capacity_trace(test_scenario, ())
    assert len(trace) == 2


def test_fixed_trace_is_deterministic_and_step_sane() -> None:
    test_scenario = scenario(item("a", size_bytes=2), horizon_s=2)
    coarse = (interval(0, 2, 8),)
    fine = (interval(0, 1, 8), interval(1, 2, 8))
    coarse_report = simulate_intermittent(
        test_scenario,
        "fifo",
        capacity_trace=coarse,
        contact_windows=(window(0, 2),),
    )
    fine_report = simulate_intermittent(
        test_scenario,
        "fifo",
        capacity_trace=fine,
        contact_windows=(window(0, 2),),
    )
    repeated = simulate_intermittent(
        test_scenario,
        "fifo",
        capacity_trace=coarse,
        contact_windows=(window(0, 2),),
    )
    assert coarse_report.to_dict() == repeated.to_dict()
    assert coarse_report.results == fine_report.results
    assert coarse_report.metrics.transferred_bits == fine_report.metrics.transferred_bits


def test_link_utilization_uses_available_contact_capacity() -> None:
    report = simulate_intermittent(
        scenario(item("a"), horizon_s=2),
        "fifo",
        capacity_trace=(interval(0, 2, 8),),
        contact_windows=(window(0, 2),),
    )
    assert report.metrics.transferred_bits == 8
    assert report.metrics.available_capacity_bits == 16
    assert report.metrics.link_utilization == pytest.approx(0.5)


def test_real_example_timestep_convergence() -> None:
    loaded = load_scenario(Path("examples/end_to_end_scenario.json"))
    assert isinstance(loaded, IntermittentScenario)
    windows = find_contact_windows(
        loaded.tle, loaded.ground_station, loaded.start_utc, loaded.end_utc
    )
    one_second = build_capacity_trace(loaded, windows)
    half_second_scenario = replace(loaded, time_step_s=0.5)
    half_second = build_capacity_trace(half_second_scenario, windows)
    capacity_one = sum(
        interval.effective_rate_bps * interval.duration_s for interval in one_second
    )
    capacity_half = sum(
        interval.effective_rate_bps * interval.duration_s for interval in half_second
    )
    assert capacity_one == pytest.approx(capacity_half, rel=1e-4)

    report_one = simulate_intermittent(
        loaded,
        "edf",
        capacity_trace=one_second,
        contact_windows=windows,
    )
    report_half = simulate_intermittent(
        half_second_scenario,
        "edf",
        capacity_trace=half_second,
        contact_windows=windows,
    )
    assert report_one.metrics.delivered_count == report_half.metrics.delivered_count
    assert report_one.metrics.deadline_met_items == report_half.metrics.deadline_met_items
