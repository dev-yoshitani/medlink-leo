"""MedLink-LEO simulation package."""

from medlink.link import LinkBudgetResult, RFLinkConfig, calculate_link_budget
from medlink.models import LinkConfig, MedicalData, Priority
from medlink.orbit import (
    ContactWindow,
    FrozenTLE,
    GroundStation,
    OrbitSample,
    find_contact_windows,
    load_bundled_tle,
    propagate_orbit,
)
from medlink.routing import (
    ContactPlan,
    RouteResult,
    RoutingReport,
    RoutingStrategy,
    build_contact_plan,
    compare_routing_strategies,
    route_scenario,
)
from medlink.scenarios import FixedScenario, RoutingScenario, load_scenario
from medlink.simulation import ComparisonReport, SimulationReport, compare_strategies, simulate

__all__ = [
    "ComparisonReport",
    "ContactPlan",
    "FixedScenario",
    "FrozenTLE",
    "GroundStation",
    "LinkConfig",
    "MedicalData",
    "OrbitSample",
    "Priority",
    "RFLinkConfig",
    "RouteResult",
    "RoutingReport",
    "RoutingScenario",
    "RoutingStrategy",
    "LinkBudgetResult",
    "SimulationReport",
    "ContactWindow",
    "compare_strategies",
    "compare_routing_strategies",
    "build_contact_plan",
    "calculate_link_budget",
    "load_scenario",
    "load_bundled_tle",
    "find_contact_windows",
    "propagate_orbit",
    "route_scenario",
    "simulate",
]

__version__ = "1.1.0"
