"""Scenario-dispatching public simulation API."""

from __future__ import annotations

from medlink.orbit import find_contact_windows
from medlink.scenarios import FixedScenario, Scenario
from medlink.scheduling import SCHEDULER_ORDER, Strategy
from medlink.simulation.fixed import ComparisonReport
from medlink.simulation.fixed import SimulationReport as FixedSimulationReport
from medlink.simulation.fixed import simulate as simulate_fixed
from medlink.simulation.intermittent import (
    IntermittentSimulationReport,
    build_capacity_trace,
    simulate_intermittent,
)

SimulationReport = FixedSimulationReport | IntermittentSimulationReport


def simulate(scenario: Scenario, strategy: Strategy | str) -> SimulationReport:
    if isinstance(scenario, FixedScenario):
        return simulate_fixed(scenario, strategy)
    return simulate_intermittent(scenario, strategy)


def compare_strategies(scenario: Scenario) -> ComparisonReport:
    if isinstance(scenario, FixedScenario):
        reports = tuple(simulate_fixed(scenario, strategy) for strategy in SCHEDULER_ORDER)
    else:
        windows = find_contact_windows(
            scenario.tle,
            scenario.ground_station,
            scenario.start_utc,
            scenario.end_utc,
        )
        trace = build_capacity_trace(scenario, windows)
        reports = tuple(
            simulate_intermittent(
                scenario,
                strategy,
                capacity_trace=trace,
                contact_windows=windows,
            )
            for strategy in SCHEDULER_ORDER
        )
    return ComparisonReport(scenario_id=scenario.scenario_id, reports=reports)
