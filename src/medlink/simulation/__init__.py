"""Simulation entry points."""

from medlink.simulation.api import SimulationReport, compare_strategies, simulate
from medlink.simulation.fixed import ComparisonReport, TransmissionResult
from medlink.simulation.intermittent import (
    CapacityInterval,
    IntermittentMetrics,
    IntermittentSimulationReport,
    IntermittentTransmissionResult,
    LinkTraceSample,
    build_capacity_trace,
    generate_link_trace,
    simulate_intermittent,
)

__all__ = [
    "ComparisonReport",
    "CapacityInterval",
    "IntermittentMetrics",
    "IntermittentSimulationReport",
    "IntermittentTransmissionResult",
    "LinkTraceSample",
    "SimulationReport",
    "TransmissionResult",
    "compare_strategies",
    "build_capacity_trace",
    "generate_link_trace",
    "simulate",
    "simulate_intermittent",
]
