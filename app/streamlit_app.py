"""Offline Streamlit demo for MedLink-LEO simulation and routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from medlink.orbit import utc_iso
from medlink.routing import RoutingComparisonReport, RoutingReport, compare_routing_strategies
from medlink.scenarios import IntermittentScenario, RoutingScenario, load_scenario
from medlink.simulation import compare_strategies, generate_link_trace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIMULATION_SCENARIO = PROJECT_ROOT / "examples" / "end_to_end_scenario.json"
ROUTING_SCENARIO = PROJECT_ROOT / "examples" / "contact_plan_medical_routing.json"
SAFETY_NOTICE = (
    "MedLink-LEO uses synthetic medical data only. It is an engineering simulation "
    "project and is not intended for diagnosis, treatment, clinical decision-making, "
    "or real-world medical operations."
)


def _load_simulation_scenario() -> IntermittentScenario:
    scenario = load_scenario(SIMULATION_SCENARIO)
    if not isinstance(scenario, IntermittentScenario):
        raise TypeError("the bundled simulation demo must use intermittent mode")
    return scenario


def _load_routing_scenario() -> RoutingScenario:
    scenario = load_scenario(ROUTING_SCENARIO)
    if not isinstance(scenario, RoutingScenario):
        raise TypeError("the bundled routing demo must use routing mode")
    return scenario


def _workload_frame(scenario: IntermittentScenario | RoutingScenario) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": item.id,
                "Synthetic data class": item.data_type,
                "Size (MB)": item.size_bytes / 1_000_000,
                "Priority class": item.priority.name,
                "Created (s)": item.created_at_s,
                "Absolute deadline (s)": item.due_at_s,
            }
            for item in scenario.medical_data
        ]
    )


def _scheduler_comparison_frame(comparison: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scheduler": report.strategy.value.upper(),
                "Delivered": report.metrics.delivered_count,
                "Undelivered": report.metrics.undelivered_count,
                "Deferred": report.metrics.deferred_count,
                "Deadline satisfaction (%)": report.metrics.deadline_satisfaction_rate * 100,
                "Critical-class satisfaction (%)": (
                    report.metrics.critical_deadline_satisfaction_rate * 100
                    if report.metrics.critical_deadline_satisfaction_rate is not None
                    else None
                ),
                "Average latency (s)": report.metrics.average_latency_s,
                "Link utilization (%)": report.metrics.link_utilization * 100,
            }
            for report in comparison.reports
        ]
    )


def _delivery_frame(report: Any) -> pd.DataFrame:
    rows = []
    for result in sorted(
        report.results,
        key=lambda item: (
            item.selection_order is None,
            item.selection_order if item.selection_order is not None else 0,
            item.data_id,
        ),
    ):
        rows.append(
            {
                "Order": result.selection_order,
                "ID": result.data_id,
                "Priority": result.priority.name,
                "Status": result.status,
                "Deferred": result.deferred,
                "Deadline met": result.deadline_met,
                "Started (s)": result.first_started_at_s,
                "Completed (s)": result.completed_at_s,
                "Latency (s)": result.latency_s,
                "Contact pauses": result.contact_pause_count,
                "Transferred (Mbit)": result.transferred_bits / 1_000_000,
                "Remaining (Mbit)": result.remaining_bits / 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def _simulation_contact_frame(report: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Start (UTC)": utc_iso(window.start_utc),
                "End (UTC)": utc_iso(window.end_utc),
                "Duration (s)": window.duration_s,
                "Maximum elevation (deg)": window.maximum_elevation_deg,
                "Minimum range (km)": window.minimum_range_m / 1_000,
            }
            for window in report.contact_windows
        ]
    )


def _trace_frame(scenario: IntermittentScenario) -> pd.DataFrame:
    trace = generate_link_trace(scenario, sample_step_s=10.0)
    return pd.DataFrame(
        [
            {
                "Elapsed time (min)": sample.time_s / 60,
                "Elevation (deg)": sample.elevation_deg,
                "Range (km)": sample.range_m / 1_000,
                "Effective rate (Mbit/s)": sample.effective_rate_bps / 1_000_000,
            }
            for sample in trace
        ]
    )


def _routing_comparison_frame(comparison: RoutingComparisonReport) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Routing strategy": report.strategy.value,
                "Delivered": report.metrics.delivered_count,
                "Failed": report.metrics.failed_count,
                "Deadline satisfaction (%)": report.metrics.deadline_satisfaction_rate * 100,
                "Critical-class satisfaction (%)": (
                    report.metrics.critical_deadline_satisfaction_rate * 100
                    if report.metrics.critical_deadline_satisfaction_rate is not None
                    else None
                ),
                "Delivery ratio (%)": report.metrics.delivery_ratio * 100,
                "Mean end-to-end latency (s)": (
                    report.metrics.average_end_to_end_latency_s
                ),
                "Contact utilization (%)": report.metrics.contact_utilization * 100,
            }
            for report in comparison.reports
        ]
    )


def _routing_contact_frame(report: RoutingReport) -> pd.DataFrame:
    station_by_id = {
        station.id: station for station in _load_routing_scenario().ground_stations
    }
    return pd.DataFrame(
        [
            {
                "Contact": contact.contact_id,
                "Ground Station": contact.ground_station_name,
                "Start (s)": contact.start_s,
                "End (s)": contact.end_s,
                "Duration (s)": contact.duration_s,
                "Capacity (Mbit)": contact.available_capacity_bits / 1_000_000,
                "Propagation (ms)": contact.propagation_delay_s * 1_000,
                "Backhaul (s)": station_by_id[
                    contact.ground_station_id
                ].backhaul_delay_s,
                "Maximum elevation (deg)": contact.maximum_elevation_deg,
            }
            for contact in report.contact_plan.contacts
        ]
    )


def _routing_result_frame(report: RoutingReport) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Order": result.scheduling_order,
                "Medical item": result.medical_data_id,
                "Priority": result.priority.name,
                "Ground Station": result.selected_ground_station_name,
                "Contact": result.selected_contact_id,
                "RF departure (s)": result.estimated_departure_s,
                "Hospital arrival (s)": result.estimated_arrival_s,
                "Deadline (s)": result.deadline_at_s,
                "Deadline margin (s)": result.deadline_margin_s,
                "Deadline feasible": result.deadline_feasible,
                "Outcome": "DELIVERED" if result.delivered else result.failure_reason.value,
            }
            for result in report.results
        ]
    )


def _candidate_frame(result: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ground Station": candidate.ground_station_name,
                "Next Contact": candidate.contact_start_s,
                "Capacity (Mbit)": candidate.capacity_available_bits / 1_000_000,
                "Backhaul (s)": candidate.backhaul_delay_s,
                "Estimated Arrival (s)": candidate.estimated_arrival_s,
                "Deadline Feasible": "Yes" if candidate.deadline_feasible else "No",
                "Selected": "Yes" if candidate.selected else "No",
            }
            for candidate in result.candidates
        ]
    )


def _render_routing_demo() -> None:
    scenario = _load_routing_scenario()
    st.header("Contact-Plan-Aware Medical Routing")
    st.write(
        "A single LEO satellite can downlink through Seoul, Sapporo, or Tokyo. The routing "
        "engine separates *which contact to use* from the existing EDF item scheduler and "
        "evaluates hospital arrival after RF transfer, propagation, and terrestrial backhaul."
    )

    columns = st.columns(4)
    columns[0].metric("Synthetic items", len(scenario.medical_data))
    columns[1].metric("Ground stations", len(scenario.ground_stations))
    columns[2].metric("Simulation horizon", f"{scenario.horizon_s / 60:.0f} min")
    columns[3].metric("Numerical timestep", f"{scenario.time_step_s:g} s")
    st.caption(
        f"Remote Clinic → {scenario.tle.satellite_name} → GS-A / GS-B / GS-C → "
        f"Hospital Gateway · frozen TLE epoch {utc_iso(scenario.tle.epoch_utc)}"
    )

    with st.expander("Inspect synthetic workload", expanded=False):
        st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")

    selected_strategy = st.selectbox(
        "Detailed routing view",
        options=("next-contact", "earliest-arrival", "deadline-aware"),
        format_func=lambda value: {
            "next-contact": "Next Available Contact",
            "earliest-arrival": "Earliest Hospital Arrival",
            "deadline-aware": "Deadline-Aware Medical Routing",
        }[value],
        key="routing_strategy",
    )
    run_requested = st.button(
        "Compare Routing Strategies",
        type="primary",
        key="compare_routing",
    )

    if not run_requested:
        st.info(
            "Run the bundled offline scenario to compare all three policies on the same "
            "deterministic contact plan."
        )
        return

    with st.spinner("Propagating the frozen orbit and integrating RF contact capacity…"):
        comparison = compare_routing_strategies(scenario)
        report_by_strategy = {
            report.strategy.value: report for report in comparison.reports
        }
        selected_report = report_by_strategy[selected_strategy]

    st.success(
        "Routing comparison complete. Every policy used the same workload and contact plan."
    )
    st.subheader("Strategy comparison")
    comparison_frame = _routing_comparison_frame(comparison)
    st.dataframe(
        comparison_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "Deadline satisfaction (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Critical-class satisfaction (%)": st.column_config.NumberColumn(
                format="%.1f%%"
            ),
            "Delivery ratio (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Contact utilization (%)": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    st.bar_chart(
        comparison_frame.set_index("Routing strategy")[["Deadline satisfaction (%)"]],
        y_label="Deadline satisfaction (%)",
    )

    st.subheader(f"Route decisions — {selected_strategy}")
    route_metrics = st.columns(4)
    route_metrics[0].metric("Delivered", selected_report.metrics.delivered_count)
    route_metrics[1].metric("Failed", selected_report.metrics.failed_count)
    route_metrics[2].metric(
        "Deadlines met", selected_report.metrics.deadline_met_items
    )
    route_metrics[3].metric(
        "Contact utilization", f"{selected_report.metrics.contact_utilization:.1%}"
    )
    st.dataframe(
        _routing_result_frame(selected_report),
        hide_index=True,
        width="stretch",
    )

    selected_item_id = st.selectbox(
        "Explain one routing decision",
        options=tuple(result.medical_data_id for result in selected_report.results),
        key="routing_item",
    )
    selected_result = next(
        result
        for result in selected_report.results
        if result.medical_data_id == selected_item_id
    )
    st.markdown("#### Why this route?")
    if selected_result.delivered:
        st.info(selected_result.decision_reason)
    else:
        st.warning(
            f"{selected_result.failure_reason.value}: {selected_result.decision_reason}"
        )
    st.dataframe(
        _candidate_frame(selected_result),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "The table shows explicit seconds and bits-derived capacity. Yes/No labels accompany "
        "the visual styling so outcomes are not communicated by color alone."
    )

    st.subheader("Contact plan")
    st.dataframe(
        _routing_contact_frame(selected_report),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Each capacity is integrated from the existing SGP4 range and RF link-budget model "
        "using deterministic midpoint sampling."
    )


def _render_existing_simulation() -> None:
    scenario = _load_simulation_scenario()
    st.header("Existing Intermittent-Link Simulation")
    st.write(
        "Compare deterministic FIFO, illustrative medical-priority, and EDF scheduling over "
        "one shared historical-orbit link trace."
    )
    columns = st.columns(4)
    columns[0].metric("Synthetic items", len(scenario.medical_data))
    columns[1].metric("Ground station", scenario.ground_station.name)
    columns[2].metric("Simulation horizon", f"{scenario.horizon_s / 60:.0f} min")
    columns[3].metric("Numerical timestep", f"{scenario.time_step_s:g} s")
    st.caption(
        f"Scenario {scenario.scenario_id} · {utc_iso(scenario.start_utc)} to "
        f"{utc_iso(scenario.end_utc)} · frozen TLE epoch {utc_iso(scenario.tle.epoch_utc)}"
    )
    with st.expander("Inspect synthetic workload", expanded=False):
        st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")

    selected_strategy = st.selectbox(
        "Detailed delivery view",
        options=("fifo", "priority", "edf"),
        format_func=lambda value: {
            "fifo": "FIFO",
            "priority": "Medical Priority (illustrative)",
            "edf": "Earliest Deadline First (EDF)",
        }[value],
        key="scheduler_strategy",
    )
    run_requested = st.button("Run Simulation", type="primary", key="run_simulation")
    if not run_requested:
        return

    with st.spinner("Propagating the frozen orbit and simulating all schedulers…"):
        comparison = compare_strategies(scenario)
        report_by_strategy = {
            report.strategy.value: report for report in comparison.reports
        }
        selected_report = report_by_strategy[selected_strategy]
        trace_frame = _trace_frame(scenario)

    st.success("Simulation complete. All schedulers used the same workload and link trace.")
    st.subheader("Scheduler comparison")
    comparison_frame = _scheduler_comparison_frame(comparison)
    st.dataframe(comparison_frame, hide_index=True, width="stretch")
    st.bar_chart(
        comparison_frame.set_index("Scheduler")[["Deadline satisfaction (%)"]],
        y_label="Deadline satisfaction (%)",
    )

    st.subheader("Contact and link")
    contact_frame = _simulation_contact_frame(selected_report)
    if contact_frame.empty:
        st.info("No contact occurs inside this simulation horizon.")
    else:
        st.dataframe(contact_frame, hide_index=True, width="stretch")
    link_left, link_right = st.columns(2)
    with link_left:
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Elevation (deg)"]],
            y_label="Elevation (deg)",
        )
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Range (km)"]],
            y_label="Range (km)",
        )
    with link_right:
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Effective rate (Mbit/s)"]],
            y_label="Effective rate (Mbit/s)",
        )
        st.caption(
            "The displayed rate is the configured efficiency fraction of the Shannon "
            "capacity upper bound."
        )

    st.subheader(f"Queue and delivery — {selected_strategy.upper()}")
    st.dataframe(_delivery_frame(selected_report), hide_index=True, width="stretch")
    st.caption(
        "An active transfer pauses at contact loss, retains transferred bits, and resumes "
        "before another item is scheduled. New arrivals do not preempt it."
    )


st.set_page_config(page_title="MedLink-LEO", page_icon="🛰️", layout="wide")
st.markdown(
    """
<style>
    .block-container {padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1200px;}
    [data-testid="stMetric"] {border: 1px solid #dbe5ea; border-radius: 0.75rem;
        padding: 0.8rem 1rem; background: #f8fbfc;}
    [data-testid="stDataFrame"] {border: 1px solid #e3eaee; border-radius: 0.6rem;}
    h2, h3 {letter-spacing: -0.015em;}
</style>
""",
    unsafe_allow_html=True,
)
st.title("MedLink-LEO")
st.caption("Reliable medical-data delivery over constrained LEO satellite links.")
st.warning(SAFETY_NOTICE)

mode = st.radio(
    "Mode",
    options=("Contact-Plan Routing", "Existing Simulation"),
    horizontal=True,
    key="demo_mode",
)
if mode == "Contact-Plan Routing":
    _render_routing_demo()
else:
    _render_existing_simulation()

with st.expander("Assumptions, safety, and model boundary"):
    st.markdown(
        f"""
- {SAFETY_NOTICE}
- Priority labels are illustrative simulation classes, not clinical guidance.
- The TLE is a frozen historical fixture propagated near its epoch, not current tracking data.
- The routing model is one satellite and three ground stations feeding one hospital gateway.
- Items are available on the satellite at creation time; the clinic uplink is abstracted.
- A route uses one contact. Full DTN/BPv7, contact splitting, and multi-satellite routing are not
  implemented.
- Dynamic capacity uses an explicit 1 s midpoint timestep and a documented RF abstraction.
- Protocol overheads, retransmissions, fading, interference, and adaptive coding are omitted.
"""
    )
