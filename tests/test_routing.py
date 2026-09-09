from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from medlink.link import LinkBudgetResult, RFLinkTemplate
from medlink.models import MedicalData, Priority
from medlink.orbit import ContactWindow, GroundStation, OrbitSample, load_bundled_tle
from medlink.routing import (
    ContactPlan,
    ContactPlanEntry,
    RouteFailureReason,
    RoutingStrategy,
    build_contact_plan,
    compare_routing_strategies,
    route_scenario,
)
from medlink.routing import contact_plan as contact_plan_module
from medlink.scenarios import RoutingGroundStation, RoutingScenario
from medlink.simulation.capacity import CapacityInterval

START = datetime(2014, 1, 20, 22, 55, tzinfo=UTC)


def _link() -> RFLinkTemplate:
    return RFLinkTemplate(
        frequency_hz=2.2e9,
        tx_power_dbm=30.0,
        tx_antenna_gain_dbi=10.0,
        rx_antenna_gain_dbi=20.0,
        system_losses_db=2.0,
        noise_temperature_k=290.0,
        channel_bandwidth_hz=1.0e6,
        implementation_efficiency=0.5,
    )


def _station(station_id: str, backhaul_delay_s: float) -> RoutingGroundStation:
    return RoutingGroundStation(
        id=station_id,
        ground_station=GroundStation(
            name=f"Station {station_id}",
            latitude_deg=35.0,
            longitude_deg=139.0,
            altitude_m=20.0,
            minimum_elevation_deg=10.0,
        ),
        rf_link=_link(),
        backhaul_delay_s=backhaul_delay_s,
    )


def _scenario(
    items: tuple[MedicalData, ...],
    stations: tuple[RoutingGroundStation, ...],
    *,
    horizon_s: float = 200.0,
) -> RoutingScenario:
    return RoutingScenario(
        schema_version="1.1",
        scenario_id="routing-unit",
        description="Synthetic routing unit scenario",
        start_utc=START,
        end_utc=START + timedelta(seconds=horizon_s),
        time_step_s=1.0,
        tle=load_bundled_tle(),
        remote_clinic_id="remote-clinic",
        satellite_id="leo-satellite",
        hospital_gateway_id="hospital-gateway",
        scheduling_strategy="edf",
        ground_stations=stations,
        medical_data=items,
    )


def _budget(rate_bps: float) -> LinkBudgetResult:
    return LinkBudgetResult(
        free_space_path_loss_db=160.0,
        received_power_dbm=-100.0,
        thermal_noise_dbm=-120.0,
        snr_db=20.0,
        channel_capacity_upper_bound_bps=rate_bps * 2.0,
        effective_rate_bps=rate_bps,
        link_margin_db=None,
    )


def _contact(
    station: RoutingGroundStation,
    *,
    start_s: float,
    end_s: float,
    rate_bps: float,
    suffix: int = 1,
    propagation_delay_s: float = 0.1,
) -> ContactPlanEntry:
    sample = OrbitSample(
        time_utc=START + timedelta(seconds=(start_s + end_s) / 2.0),
        azimuth_deg=180.0,
        elevation_deg=45.0,
        range_m=700_000.0,
        in_contact=True,
    )
    interval = CapacityInterval(start_s, end_s, sample, _budget(rate_bps))
    return ContactPlanEntry(
        contact_id=f"leo-satellite--{station.id}--{suffix:03d}",
        source="leo-satellite",
        destination=station.id,
        ground_station_id=station.id,
        ground_station_name=station.ground_station.name,
        start_s=start_s,
        end_s=end_s,
        start_utc=START + timedelta(seconds=start_s),
        end_utc=START + timedelta(seconds=end_s),
        available_capacity_bits=interval.capacity_bits,
        propagation_delay_s=propagation_delay_s,
        maximum_elevation_deg=45.0,
        minimum_range_m=700_000.0,
        intervals=(interval,),
    )


def _plan(*contacts: ContactPlanEntry) -> ContactPlan:
    return ContactPlan("routing-unit", "leo-satellite", contacts)


def _item(
    item_id: str = "item-a",
    *,
    size_bytes: int = 10,
    deadline_s: float = 50.0,
) -> MedicalData:
    return MedicalData(
        id=item_id,
        data_type="synthetic-imaging",
        size_bytes=size_bytes,
        priority=Priority.CRITICAL,
        created_at_s=0.0,
        deadline_s=deadline_s,
    )


def test_contact_plan_uses_shared_capacity_builder_for_multiple_stations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station_b = _station("gs-b", 10.0)
    station_a = _station("gs-a", 20.0)
    scenario = _scenario((_item(),), (station_b, station_a))
    calls: list[str] = []

    def fake_windows(*args, **kwargs):
        del args, kwargs
        return (
            ContactWindow(
                START + timedelta(seconds=10),
                START + timedelta(seconds=20),
                maximum_elevation_deg=40.0,
                minimum_range_m=650_000.0,
            ),
        )

    def fake_capacity_trace(*, ground_station, rf_link, **kwargs):
        del rf_link, kwargs
        calls.append(ground_station.name)
        return (
            CapacityInterval(
                10.0,
                20.0,
                OrbitSample(
                    START + timedelta(seconds=15),
                    180.0,
                    40.0,
                    650_000.0,
                    True,
                ),
                _budget(100.0),
            ),
        )

    monkeypatch.setattr(contact_plan_module, "find_contact_windows", fake_windows)
    monkeypatch.setattr(
        contact_plan_module,
        "build_station_capacity_trace",
        fake_capacity_trace,
    )

    plan = build_contact_plan(scenario)

    assert calls == ["Station gs-a", "Station gs-b"]
    assert [contact.ground_station_id for contact in plan.contacts] == ["gs-a", "gs-b"]
    assert all(contact.available_capacity_bits == 1_000.0 for contact in plan.contacts)


def test_routing_strategies_separate_next_contact_from_end_to_end_arrival() -> None:
    station_a = _station("gs-a", 100.0)
    station_b = _station("gs-b", 0.0)
    scenario = _scenario((_item(),), (station_a, station_b))
    plan = _plan(
        _contact(station_a, start_s=10.0, end_s=20.0, rate_bps=100.0),
        _contact(station_b, start_s=20.0, end_s=30.0, rate_bps=100.0),
    )

    next_contact = route_scenario(scenario, RoutingStrategy.NEXT_CONTACT, contact_plan=plan)
    earliest = route_scenario(scenario, RoutingStrategy.EARLIEST_ARRIVAL, contact_plan=plan)
    deadline = route_scenario(scenario, RoutingStrategy.DEADLINE_AWARE, contact_plan=plan)

    assert next_contact.results[0].selected_ground_station == "gs-a"
    assert next_contact.results[0].estimated_arrival_s == pytest.approx(110.9)
    assert not next_contact.results[0].deadline_feasible
    assert earliest.results[0].selected_ground_station == "gs-b"
    assert earliest.results[0].estimated_arrival_s == pytest.approx(20.9)
    assert deadline.results[0].selected_ground_station == "gs-b"
    assert "backhaul" in earliest.results[0].decision_reason


def test_deadline_aware_reports_deadline_infeasible_without_consuming_contact() -> None:
    station = _station("gs-a", 20.0)
    scenario = _scenario((_item(deadline_s=10.0),), (station,))
    plan = _plan(_contact(station, start_s=5.0, end_s=20.0, rate_bps=100.0))

    result = route_scenario(scenario, "deadline-aware", contact_plan=plan).results[0]

    assert result.failure_reason is RouteFailureReason.DEADLINE_INFEASIBLE
    assert result.selected_contact_id is None
    assert result.candidates[0].estimated_rf_completion_s is not None


def test_insufficient_capacity_is_rejected() -> None:
    station = _station("gs-a", 0.0)
    scenario = _scenario((_item(size_bytes=100),), (station,))
    plan = _plan(_contact(station, start_s=0.0, end_s=5.0, rate_bps=100.0))

    result = route_scenario(scenario, "next-contact", contact_plan=plan).results[0]

    assert result.failure_reason is RouteFailureReason.INSUFFICIENT_CAPACITY
    assert result.capacity_required_bits == 800.0
    assert result.capacity_available_bits == 500.0


def test_failure_reasons_distinguish_no_contact_and_horizon() -> None:
    station = _station("gs-a", 20.0)
    scenario = _scenario((_item(),), (station,), horizon_s=100.0)

    no_contact = route_scenario(scenario, "next-contact", contact_plan=_plan()).results[0]
    beyond_horizon = route_scenario(
        scenario,
        "earliest-arrival",
        contact_plan=_plan(
            _contact(station, start_s=90.0, end_s=99.0, rate_bps=100.0)
        ),
    ).results[0]

    assert no_contact.failure_reason is RouteFailureReason.NO_CONTACT
    assert beyond_horizon.failure_reason is RouteFailureReason.OUTSIDE_SIMULATION_HORIZON


def test_routing_tie_break_is_deterministic() -> None:
    station_b = _station("gs-b", 0.0)
    station_a = _station("gs-a", 0.0)
    scenario = _scenario((_item(),), (station_b, station_a))
    plan = _plan(
        _contact(station_b, start_s=10.0, end_s=20.0, rate_bps=100.0),
        _contact(station_a, start_s=10.0, end_s=20.0, rate_bps=100.0),
    )

    result = route_scenario(scenario, "earliest-arrival", contact_plan=plan).results[0]

    assert result.selected_ground_station == "gs-a"


def test_multiple_items_contend_for_unelapsed_contact_capacity() -> None:
    station = _station("gs-a", 0.0)
    scenario = _scenario(
        (
            _item("item-a", size_bytes=60, deadline_s=100.0),
            _item("item-b", size_bytes=60, deadline_s=100.0),
        ),
        (station,),
    )
    plan = _plan(_contact(station, start_s=0.0, end_s=8.0, rate_bps=100.0))

    report = route_scenario(scenario, "next-contact", contact_plan=plan)

    assert report.results[0].delivered
    assert report.results[0].estimated_rf_completion_s == pytest.approx(4.8)
    assert report.results[1].failure_reason is RouteFailureReason.INSUFFICIENT_CAPACITY
    assert report.results[1].capacity_available_bits == pytest.approx(320.0)
    assert report.metrics.delivery_ratio == 0.5
    assert report.metrics.contact_utilization == pytest.approx(0.6)
    assert report.metrics.ground_station_selection == {"gs-a": 1}


def test_comparison_json_is_stable_and_strategy_order_is_explicit() -> None:
    station = _station("gs-a", 0.0)
    scenario = _scenario((_item(),), (station,))
    plan = _plan(_contact(station, start_s=0.0, end_s=10.0, rate_bps=100.0))

    first = compare_routing_strategies(scenario, contact_plan=plan).to_dict()
    second = compare_routing_strategies(scenario, contact_plan=plan).to_dict()

    assert [entry["strategy"] for entry in first["strategies"]] == [
        "next-contact",
        "earliest-arrival",
        "deadline-aware",
    ]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
