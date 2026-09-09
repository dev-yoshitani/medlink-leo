"""Contact-plan-aware medical-data routing."""

from medlink.routing.contact_plan import build_contact_plan
from medlink.routing.engine import compare_routing_strategies, route_scenario
from medlink.routing.models import (
    ROUTING_STRATEGY_ORDER,
    ContactPlan,
    ContactPlanEntry,
    RouteCandidate,
    RouteFailureReason,
    RouteResult,
    RoutingComparisonReport,
    RoutingMetrics,
    RoutingReport,
    RoutingStrategy,
)

__all__ = [
    "ROUTING_STRATEGY_ORDER",
    "ContactPlan",
    "ContactPlanEntry",
    "RouteCandidate",
    "RouteFailureReason",
    "RouteResult",
    "RoutingComparisonReport",
    "RoutingMetrics",
    "RoutingReport",
    "RoutingStrategy",
    "build_contact_plan",
    "compare_routing_strategies",
    "route_scenario",
]
