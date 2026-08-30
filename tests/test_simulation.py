from __future__ import annotations

import pytest

from medlink.models import LinkConfig, MedicalData, Priority
from medlink.scenarios import FixedScenario
from medlink.simulation import compare_strategies, simulate


def scenario(*items: MedicalData, bandwidth: float = 8.0) -> FixedScenario:
    return FixedScenario("1.0", "test", "", LinkConfig(bandwidth), items)


def data(
    identifier: str,
    *,
    size: int = 1,
    priority: Priority = Priority.NORMAL,
    created: float = 0,
    deadline: float = 10,
) -> MedicalData:
    return MedicalData(identifier, "synthetic", size, priority, created, deadline)


def test_release_time_and_idle_clock_advance() -> None:
    report = simulate(scenario(data("later", created=5)), "fifo")
    result = report.results[0]
    assert result.started_at_s == 5
    assert result.completed_at_s == 6
    assert result.latency_s == 1
    assert report.metrics.simulation_duration_s == 6
    assert report.metrics.link_utilization == pytest.approx(1 / 6)


def test_deadline_met_and_missed() -> None:
    report = simulate(
        scenario(data("met", deadline=1), data("missed", deadline=1)),
        "fifo",
    )
    assert [result.deadline_met for result in report.results] == [True, False]
    assert report.metrics.deadline_met_items == 1
    assert report.metrics.deadline_missed_items == 1
    assert report.metrics.deadline_satisfaction_rate == 0.5
    assert report.metrics.average_latency_s == 1.5
    assert report.metrics.maximum_latency_s == 2


def test_no_critical_metric_is_none() -> None:
    report = simulate(scenario(data("normal")), "fifo")
    assert report.metrics.critical_deadline_satisfaction_rate is None
    assert report.to_dict()["metrics"]["critical_deadline_satisfaction_rate"] is None


def test_strategy_comparison_order_is_stable() -> None:
    report = compare_strategies(scenario(data("a")))
    assert [item.strategy.value for item in report.reports] == ["fifo", "priority", "edf"]


def test_priority_strategy_can_change_transmission_order() -> None:
    report = simulate(
        scenario(data("normal"), data("critical", priority=Priority.CRITICAL)),
        "priority",
    )
    assert [result.data_id for result in report.results] == ["critical", "normal"]

