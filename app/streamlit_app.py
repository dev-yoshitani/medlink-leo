"""Offline Streamlit demo for MedLink-LEO simulation and routing."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from mission_scene import build_scene

from medlink.orbit import utc_iso
from medlink.routing import (
    RouteResult,
    RoutingComparisonReport,
    RoutingReport,
    compare_routing_strategies,
)
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


def _mission_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    rounded = round(seconds)
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds_part:02}"


def _metric_card(label: str, value: str, detail: str = "") -> str:
    return (
        '<div class="mission-metric">'
        f'<span class="mission-label">{escape(label)}</span>'
        f'<strong>{escape(value)}</strong>'
        f'<span class="mission-detail">{escape(detail)}</span></div>'
    )


def _render_payload_queue(report: RoutingReport, scenario: RoutingScenario) -> None:
    size_by_id = {item.id: item.size_bytes * 8 / 1_000_000 for item in scenario.medical_data}
    rows = []
    for result in report.results:
        priority = result.priority.name
        status = "DELIVERED" if result.delivered else result.failure_reason.value
        station = result.selected_ground_station_name or "No route"
        data_label = result.data_type.replace("synthetic_", "").replace("_", " ").title()
        status_style = "done" if result.delivered else "failed"
        rows.append(
            '<div class="payload-row">'
            f'<span class="priority-dot {escape(priority.lower())}"></span>'
            f'<span class="payload-name"><b>{escape(result.medical_data_id)}</b>'
            f'<small>{escape(data_label)}</small></span>'
            f'<span class="payload-size">{size_by_id[result.medical_data_id]:.1f} Mbit</span>'
            f'<span class="payload-station">{escape(station)}</span>'
            f'<span class="payload-status {status_style}">{escape(status)}</span>'
            "</div>"
        )
    st.markdown(
        '<div class="mission-panel"><div class="panel-heading">PAYLOAD MANIFEST</div>'
        + ''.join(rows)
        + '</div>',
        unsafe_allow_html=True,
    )


def _render_contact_timeline(report: RoutingReport, horizon_s: float) -> None:
    rows = []
    stations = (("gs-seoul", "SEOUL"), ("gs-sapporo", "SAPPORO"), ("gs-tokyo", "TOKYO"))
    for station_id, label in stations:
        windows = []
        for contact in report.contact_plan.contacts:
            if contact.ground_station_id != station_id:
                continue
            left = max(0.0, min(100.0, contact.start_s / horizon_s * 100))
            width = max(0.0, min(100.0 - left, contact.duration_s / horizon_s * 100))
            windows.append(
                f'<span class="contact-window" style="left:{left:.3f}%;width:{width:.3f}%" '
                f'title="{escape(label)}: {_mission_time(contact.start_s)}–'
                f'{_mission_time(contact.end_s)}"></span>'
            )
        rows.append(
            f'<div class="timeline-row"><span>{label}</span>'
            f'<div class="timeline-track">{"".join(windows)}</div>'
            f'<span>{len(windows)} contact{"s" if len(windows) != 1 else ""}</span></div>'
        )
    st.markdown(
        '<div class="mission-panel"><div class="panel-heading">CONTACT TIMELINE'
        '<span>HISTORICAL FIXTURE · ELAPSED TIME</span></div>'
        + ''.join(rows)
        + '<div class="timeline-axis"><span>00:00</span>'
        + f'<span>{_mission_time(horizon_s)}</span></div></div>',
        unsafe_allow_html=True,
    )


def _render_route_decision(result: RouteResult) -> None:
    outcome = "DELIVERED" if result.delivered else result.failure_reason.value
    cards = []
    for candidate in result.candidates:
        if candidate.selected:
            state = "SELECTED"
        elif candidate.failure_reason is not None:
            state = candidate.failure_reason.value.replace("_", " ")
        elif not candidate.deadline_feasible:
            state = "MISSES DEADLINE"
        else:
            state = "ALTERNATIVE"
        arrival = _mission_time(candidate.estimated_arrival_s)
        cards.append(
            f'<div class="candidate-card {"selected" if candidate.selected else ""}">'
            f'<b>{escape(candidate.ground_station_name)}</b><span>{state}</span>'
            f'<small>Arrival {arrival} · Capacity '
            f'{candidate.capacity_available_bits / 1_000_000:.1f} Mbit</small>'
            '</div>'
        )
    if not cards:
        cards.append('<p>No contact candidate remains for this payload.</p>')
    st.markdown(
        '<div class="mission-panel"><div class="panel-heading">ROUTE DECISION</div>'
        f'<div class="decision-header"><div><strong>{escape(result.medical_data_id)}</strong>'
        f'<span>{escape(result.priority.name)} · {escape(outcome)}</span></div>'
        f'<div><strong>{_mission_time(result.estimated_arrival_s)}</strong>'
        '<span>HOSPITAL ARRIVAL</span></div></div>'
        f'<p class="decision-reason">{escape(result.decision_reason)}</p>'
        f'<div class="candidate-grid">{"".join(cards)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_debrief_comparison(comparison: RoutingComparisonReport) -> None:
    rows = []
    for report in comparison.reports:
        metrics = report.metrics
        label = report.strategy.value.replace('-', ' ').title()
        rows.append(
            '<div class="strategy-row">'
            f'<strong>{escape(label)}</strong>'
            f'<span>{metrics.deadline_met_items}/{metrics.total_items}<small>deadlines</small></span>'
            f'<span>{metrics.delivered_count}/{metrics.total_items}<small>delivered</small></span>'
            f'<span>{_mission_time(metrics.average_end_to_end_latency_s)}'
            '<small>mean latency</small></span></div>'
        )
    st.markdown(
        '<div class="mission-panel"><div class="panel-heading">ROUTING PERFORMANCE</div>'
        + ''.join(rows)
        + '</div>',
        unsafe_allow_html=True,
    )


def _render_routing_demo() -> None:
    scenario = _load_routing_scenario()
    st.markdown('<p class="mission-kicker">01 / ROUTING MISSION</p>', unsafe_allow_html=True)
    st.header("Mission Control")
    st.write("Move synthetic medical data through one LEO satellite and three ground sites.")
    st.markdown(
        '<div class="mission-metrics">'
        + _metric_card("PAYLOADS", str(len(scenario.medical_data)), "synthetic")
        + _metric_card("GROUND SITES", str(len(scenario.ground_stations)), "East Asia")
        + _metric_card("TIME WINDOW", f"{scenario.horizon_s / 60:.0f} min", "historical fixture")
        + _metric_card("SATELLITE", "1", "single spacecraft")
        + '</div>',
        unsafe_allow_html=True,
    )
    control_left, control_right = st.columns([2, 1], vertical_alignment="bottom")
    selected_strategy = control_left.selectbox(
        "Routing mode",
        options=("next-contact", "earliest-arrival", "deadline-aware"),
        format_func=lambda value: {
            "next-contact": "Next Contact",
            "earliest-arrival": "Earliest Hospital Arrival",
            "deadline-aware": "Deadline Aware",
        }[value],
        key="routing_strategy",
    )
    run_requested = control_right.button(
        "Start Mission",
        type="primary",
        key="compare_routing",
        use_container_width=True,
    )

    if run_requested:
        with st.spinner("Propagating the frozen orbit and integrating RF contact capacity…"):
            st.session_state.routing_comparison = compare_routing_strategies(scenario)
    if "routing_comparison" not in st.session_state:
        st.image(
            build_scene(),
            width="stretch",
        )
        st.caption(
            "Conceptual network diagram. Clinic uplink is abstracted; contacts come from a "
            "frozen historical orbit fixture."
        )
        st.info(
            "Start the offline mission to compare all three routing modes on the same "
            "contact plan."
        )
        return

    comparison = st.session_state.routing_comparison
    report_by_strategy = {report.strategy.value: report for report in comparison.reports}
    selected_report = report_by_strategy[selected_strategy]

    st.success("Mission complete. Every mode used the same synthetic workload and contact plan.")
    selected_item_id = st.selectbox(
        "Inspect payload",
        options=tuple(result.medical_data_id for result in selected_report.results),
        key="routing_item",
    )
    selected_result = next(
        result
        for result in selected_report.results
        if result.medical_data_id == selected_item_id
    )
    if selected_result.delivered:
        station_name = selected_result.selected_ground_station_name or "Ground site"
        path_text = f"On-satellite payload → {station_name} → Hospital gateway"
    else:
        path_text = f"{selected_result.medical_data_id}: no delivery route"
    st.markdown(
        '<div class="route-banner"><strong>SELECTED PAYLOAD PATH</strong>'
        f'<span>{escape(path_text)}</span><small>Clinic uplink is abstracted.</small></div>',
        unsafe_allow_html=True,
    )
    st.image(
        build_scene(selected_result),
        width="stretch",
    )
    st.caption(
        "Conceptual route map, not live tracking. The dashed clinic uplink is abstracted; "
        "the bright path marks the selected delivery route."
    )
    _render_payload_queue(selected_report, scenario)
    _render_route_decision(selected_result)
    _render_contact_timeline(selected_report, scenario.horizon_s)

    st.subheader("Mission Debrief")
    st.markdown(
        '<div class="mission-metrics">'
        + _metric_card(
            "DELIVERED",
            f"{selected_report.metrics.delivered_count}/{selected_report.metrics.total_items}",
            selected_strategy,
        )
        + _metric_card(
            "DEADLINES MET",
            f"{selected_report.metrics.deadline_met_items}/{selected_report.metrics.total_items}",
        )
        + _metric_card("CONTACT USE", f"{selected_report.metrics.contact_utilization:.1%}")
        + _metric_card(
            "MEAN ARRIVAL LATENCY",
            _mission_time(selected_report.metrics.average_end_to_end_latency_s),
            "delivered only",
        )
        + '</div>',
        unsafe_allow_html=True,
    )
    comparison_frame = _routing_comparison_frame(comparison)
    _render_debrief_comparison(comparison)
    st.caption(
        "Compare delivery and deadlines first. Rejecting late payloads can lower mean "
        "latency without speeding up shared deliveries."
    )

    with st.expander("Engineering data · full results and reproducibility"):
        st.download_button(
            "Download reproducible routing results (JSON)",
            json.dumps(comparison.to_dict(), indent=2, allow_nan=False),
            file_name="medlink-routing-comparison.json",
            mime="application/json",
        )
        st.markdown("**Synthetic workload**")
        st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")
        st.markdown("**All policy metrics**")
        st.dataframe(comparison_frame, hide_index=True, width="stretch")
        st.bar_chart(
            comparison_frame.set_index("Routing strategy")[["Deadline satisfaction (%)"]],
            y_label="Deadline satisfaction (%)",
        )
        st.markdown("**Route outcomes**")
        st.dataframe(_routing_result_frame(selected_report), hide_index=True, width="stretch")
        st.markdown("**Candidate contacts**")
        st.dataframe(_candidate_frame(selected_result), hide_index=True, width="stretch")
        st.markdown("**Contact plan**")
        st.dataframe(_routing_contact_frame(selected_report), hide_index=True, width="stretch")
        st.caption(
            "Capacities are integrated from the existing SGP4 range and RF model using "
            "deterministic midpoint sampling. Candidate tables retain explicit units and "
            "Yes/No labels."
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
    if run_requested:
        with st.spinner("Propagating the frozen orbit and simulating all schedulers…"):
            st.session_state.simulation_comparison = compare_strategies(scenario)
            st.session_state.simulation_trace = _trace_frame(scenario)
    if "simulation_comparison" not in st.session_state:
        return

    comparison = st.session_state.simulation_comparison
    report_by_strategy = {report.strategy.value: report for report in comparison.reports}
    selected_report = report_by_strategy[selected_strategy]
    trace_frame = st.session_state.simulation_trace

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


st.set_page_config(
    page_title="MedLink-LEO",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
<style>
    .block-container {padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1320px;}
    h1, h2, h3 {letter-spacing: -0.025em;}
    h1 {font-weight: 850; text-transform: uppercase;}
    [data-testid="stDataFrame"] {border: 1px solid #31475a; border-radius: 0.4rem;}
    [data-testid="stImage"] img {border: 1px solid #31475a; border-radius: 1.1rem;}
    .mission-kicker, .mission-label, .panel-heading {font-size: .72rem; font-weight: 800;
        letter-spacing: .14em; color: #9bb5c6;}
    .mission-kicker {margin: 1.4rem 0 -.8rem; color: #67c9aa;}
    .mission-metrics {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .7rem; margin: 1rem 0 1.5rem;}
    .mission-metric {display: flex; flex-direction: column; min-height: 106px;
        padding: .9rem 1rem; background: #14202d; border: 1px solid #31475a;
        border-top: 3px solid #557e9b; border-radius: .45rem;}
    .mission-metric strong {font-size: 1.55rem; line-height: 1.5; color: #f2f5f3;}
    .mission-detail {font-size: .76rem; color: #a7bdd0;}
    .mission-panel {background: #14202d; border: 1px solid #31475a;
        border-radius: .55rem; padding: 1rem 1.1rem; margin: 1rem 0;}
    .route-banner {display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; align-items: baseline;
        padding: .75rem 1rem; margin: .6rem 0; border-left: 4px solid #67c9aa;
        background: #153032; border-radius: .25rem;}
    .route-banner strong {font-size: .68rem; letter-spacing: .12em; color: #9bdec8;}
    .route-banner span {font-size: .9rem; font-weight: 750;}
    .route-banner small {color: #b3c6d1;}
    .panel-heading {display: flex; justify-content: space-between; gap: 1rem;
        padding-bottom: .75rem; border-bottom: 1px solid #31475a;}
    .panel-heading span {color: #a7bdd0; font-weight: 600;}
    .payload-row {display: grid; grid-template-columns: 12px minmax(180px, 2fr) 1fr 1.3fr 1.2fr;
        gap: .7rem; align-items: center; padding: .72rem .15rem;
        border-bottom: 1px solid #263949; color: #e6edf2; font-size: .86rem;}
    .payload-row:last-child {border-bottom: 0;}
    .priority-dot {width: 8px; height: 8px; border-radius: 50%; background: #89a6bd;}
    .priority-dot.critical {background: #e37474;}
    .priority-dot.high {background: #e9b44c;}
    .priority-dot.normal {background: #67b5dd;}
    .payload-name {display: flex; flex-direction: column;}
    .payload-name small, .payload-size, .payload-station {color: #a7bdd0;}
    .payload-status {font-size: .7rem; font-weight: 800; letter-spacing: .07em;}
    .payload-status.done {color: #67c9aa;} .payload-status.failed {color: #e9b44c;}
    .decision-header {display: flex; justify-content: space-between; gap: 1rem; margin: 1rem 0;}
    .decision-header div {display: flex; flex-direction: column;}
    .decision-header strong {font-size: 1.25rem; color: #f2f5f3;}
    .decision-header span {font-size: .72rem; font-weight: 800;
        letter-spacing: .09em; color: #a7bdd0;}
    .decision-reason {font-size: .9rem; color: #d4e1e8;}
    .candidate-grid {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .55rem;}
    .candidate-card {display: flex; flex-direction: column; gap: .3rem; padding: .8rem;
        background: #1b2b39; border: 1px solid #354c5e; border-radius: .4rem;}
    .candidate-card.selected {border-color: #67c9aa; background: #1b3537;}
    .candidate-card b {font-size: .85rem;}
    .candidate-card span {font-size: .68rem; color: #67c9aa; font-weight: 800;}
    .candidate-card small {font-size: .75rem; color: #b3c6d1;}
    .timeline-row {display: grid; grid-template-columns: 115px 1fr 85px;
        gap: .8rem; align-items: center; margin: .8rem 0; font-size: .8rem;}
    .timeline-row > span:last-child {text-align: right; color: #a7bdd0;}
    .timeline-track {height: 13px; position: relative; border-radius: 7px; background: #263949;}
    .contact-window {position: absolute; top: 0; bottom: 0;
        border-radius: 7px; background: #67b5dd;}
    .timeline-axis {display: flex; justify-content: space-between; margin-left: 128px;
        margin-right: 95px; color: #a7bdd0; font-size: .72rem;}
    .strategy-row {display: grid; grid-template-columns: minmax(180px, 2fr) repeat(3, 1fr);
        gap: 1rem; align-items: center; padding: .75rem .15rem;
        border-bottom: 1px solid #263949; font-size: .85rem;}
    .strategy-row:last-child {border-bottom: 0;}
    .strategy-row span {display: flex; flex-direction: column; font-weight: 800;}
    .strategy-row small {font-weight: 500; color: #a7bdd0;}
    @media (max-width: 750px) {
        .mission-metrics {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .candidate-grid {grid-template-columns: 1fr;}
        .payload-row {grid-template-columns: 12px minmax(90px, 1fr) 1fr;
            gap: .4rem; font-size: .72rem;}
        .payload-size, .payload-station {display: none;}
        .timeline-row {grid-template-columns: 66px 1fr 55px; gap: .3rem; font-size: .67rem;}
        .timeline-axis {margin-left: 69px; margin-right: 58px;}
        .panel-heading span {display: none;}
        .strategy-row {grid-template-columns: repeat(3, 1fr); gap: .45rem; font-size: .75rem;}
        .strategy-row > strong {grid-column: 1 / -1;}
    }
</style>
""",
    unsafe_allow_html=True,
)
st.title("MedLink-LEO")
st.caption("OFFLINE NETWORK SIMULATOR  /  ORBIT · RF LINK · ROUTING · DEADLINES")
st.warning(SAFETY_NOTICE)
st.markdown(
    "Run a bundled mission, choose a routing mode, and inspect the path taken by each payload. "
    "[Source and engineering evidence](https://github.com/dev-yoshitani/medlink-leo)"
)

mode = st.radio(
    "Mode",
    options=("Routing Mission", "Link Simulator"),
    horizontal=True,
    key="demo_mode",
)
if mode == "Routing Mission":
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
