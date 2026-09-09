"""Deterministic contact-plan construction from existing orbit and RF models."""

from __future__ import annotations

from medlink.link import SPEED_OF_LIGHT_M_PER_S
from medlink.orbit import find_contact_windows
from medlink.routing.models import ContactPlan, ContactPlanEntry
from medlink.scenarios import RoutingScenario
from medlink.simulation.capacity import CapacityInterval, build_station_capacity_trace


def _inside_window(
    interval: CapacityInterval, start_s: float, end_s: float
) -> bool:
    return interval.start_s >= start_s - 1e-6 and interval.end_s <= end_s + 1e-6


def build_contact_plan(scenario: RoutingScenario) -> ContactPlan:
    """Build a stable contact plan for every routing ground station."""
    contacts: list[ContactPlanEntry] = []
    for station in sorted(scenario.ground_stations, key=lambda value: value.id):
        windows = find_contact_windows(
            scenario.tle,
            station.ground_station,
            scenario.start_utc,
            scenario.end_utc,
        )
        trace = build_station_capacity_trace(
            tle=scenario.tle,
            ground_station=station.ground_station,
            rf_link=station.rf_link,
            start_utc=scenario.start_utc,
            end_utc=scenario.end_utc,
            time_step_s=scenario.time_step_s,
            contact_windows=windows,
        )
        for index, window in enumerate(windows, start=1):
            start_s = (window.start_utc - scenario.start_utc).total_seconds()
            end_s = (window.end_utc - scenario.start_utc).total_seconds()
            intervals = tuple(
                interval
                for interval in trace
                if _inside_window(interval, start_s, end_s)
                and interval.effective_rate_bps > 0
            )
            capacity = sum(interval.capacity_bits for interval in intervals)
            if capacity > 0:
                propagation_delay = sum(
                    interval.sample.range_m
                    / SPEED_OF_LIGHT_M_PER_S
                    * interval.capacity_bits
                    for interval in intervals
                ) / capacity
            else:
                propagation_delay = window.minimum_range_m / SPEED_OF_LIGHT_M_PER_S
            contacts.append(
                ContactPlanEntry(
                    contact_id=f"{scenario.satellite_id}--{station.id}--{index:03d}",
                    source=scenario.satellite_id,
                    destination=station.id,
                    ground_station_id=station.id,
                    ground_station_name=station.ground_station.name,
                    start_s=start_s,
                    end_s=end_s,
                    start_utc=window.start_utc,
                    end_utc=window.end_utc,
                    available_capacity_bits=capacity,
                    propagation_delay_s=propagation_delay,
                    maximum_elevation_deg=window.maximum_elevation_deg,
                    minimum_range_m=window.minimum_range_m,
                    intervals=intervals,
                )
            )
    return ContactPlan(
        scenario_id=scenario.scenario_id,
        source=scenario.satellite_id,
        contacts=tuple(
            sorted(
                contacts,
                key=lambda contact: (
                    contact.start_s,
                    contact.end_s,
                    contact.ground_station_id,
                    contact.contact_id,
                ),
            )
        ),
    )
