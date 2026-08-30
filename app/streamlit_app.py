"""Offline Streamlit demo for the MedLink-LEO simulation core."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from medlink.orbit import utc_iso
from medlink.scenarios import IntermittentScenario, load_scenario
from medlink.simulation import compare_strategies, generate_link_trace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = PROJECT_ROOT / "examples" / "end_to_end_scenario.json"
SAFETY_NOTICE = (
    "MedLink-LEO uses synthetic medical data only. It is an engineering simulation "
    "project and is not intended for diagnosis, treatment, clinical decision-making, "
    "or real-world medical operations."
)


def _load_default_scenario() -> IntermittentScenario:
    scenario = load_scenario(DEFAULT_SCENARIO)
    if not isinstance(scenario, IntermittentScenario):
        raise TypeError("the bundled demo must use an intermittent scenario")
    return scenario


def _workload_frame(scenario: IntermittentScenario) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": item.id,
                "Synthetic data class": item.data_type,
                "Size (MB)": item.size_bytes / 1_000_000,
                "Priority class": item.priority.name,
                "Created (s)": item.created_at_s,
                "Deadline after creation (s)": item.deadline_s,
            }
            for item in scenario.medical_data
        ]
    )


def _comparison_frame(comparison) -> pd.DataFrame:
    rows = []
    for report in comparison.reports:
        metrics = report.metrics
        rows.append(
            {
                "Scheduler": report.strategy.value.upper(),
                "Delivered": metrics.delivered_count,
                "Undelivered": metrics.undelivered_count,
                "Deferred": metrics.deferred_count,
                "Deadline satisfaction": metrics.deadline_satisfaction_rate * 100,
                "Critical-class satisfaction": (
                    metrics.critical_deadline_satisfaction_rate * 100
                    if metrics.critical_deadline_satisfaction_rate is not None
                    else None
                ),
                "Average latency (s)": metrics.average_latency_s,
                "Maximum latency (s)": metrics.maximum_latency_s,
                "Link utilization": metrics.link_utilization * 100,
            }
        )
    return pd.DataFrame(rows)


def _delivery_frame(report) -> pd.DataFrame:
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


def _contact_frame(report) -> pd.DataFrame:
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


st.set_page_config(page_title="MedLink-LEO", page_icon="🛰️", layout="wide")
st.title("MedLink-LEO")
st.caption("Reliable medical-data delivery over constrained LEO satellite links.")
st.warning(SAFETY_NOTICE)

scenario = _load_default_scenario()

st.header("Problem and scenario")
st.write(
    "This demo compares deterministic FIFO, illustrative medical-priority, and EDF "
    "scheduling over the same intermittent historical-orbit scenario."
)

summary_left, summary_middle, summary_right = st.columns(3)
with summary_left:
    st.metric("Synthetic items", len(scenario.medical_data))
    st.metric("Simulation horizon", f"{scenario.horizon_s / 60:.0f} min")
with summary_middle:
    st.metric("Ground station", scenario.ground_station.name)
    st.metric("Elevation mask", f"{scenario.ground_station.minimum_elevation_deg:.0f}°")
with summary_right:
    st.metric("Frozen TLE", scenario.tle.satellite_name)
    st.metric("Numerical timestep", f"{scenario.time_step_s:g} s")

st.caption(
    f"Scenario: {scenario.scenario_id} · UTC horizon: {utc_iso(scenario.start_utc)} to "
    f"{utc_iso(scenario.end_utc)} · frozen TLE epoch: {utc_iso(scenario.tle.epoch_utc)}"
)
st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")

selected_strategy = st.selectbox(
    "Detailed delivery view",
    options=("fifo", "priority", "edf"),
    format_func=lambda value: {
        "fifo": "FIFO",
        "priority": "Medical Priority (illustrative)",
        "edf": "Earliest Deadline First (EDF)",
    }[value],
)

run_requested = st.button("Run Simulation", type="primary", key="run_simulation")

if run_requested:
    with st.spinner("Propagating the frozen orbit and simulating all schedulers…"):
        comparison = compare_strategies(scenario)
        report_by_strategy = {report.strategy.value: report for report in comparison.reports}
        selected_report = report_by_strategy[selected_strategy]
        trace_frame = _trace_frame(scenario)

    st.success("Simulation complete. All schedulers used the same workload and link trace.")

    st.header("Scheduler comparison")
    comparison_frame = _comparison_frame(comparison)
    st.dataframe(
        comparison_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "Deadline satisfaction": st.column_config.NumberColumn(format="%.1f%%"),
            "Critical-class satisfaction": st.column_config.NumberColumn(format="%.1f%%"),
            "Link utilization": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    deadline_chart = comparison_frame.set_index("Scheduler")[["Deadline satisfaction"]]
    st.bar_chart(deadline_chart, y_label="Deadline satisfaction (%)")

    st.header("Contact and link")
    contact_frame = _contact_frame(selected_report)
    if contact_frame.empty:
        st.info("No contact occurs inside this simulation horizon.")
    else:
        st.dataframe(contact_frame, hide_index=True, width="stretch")

    link_left, link_right = st.columns(2)
    with link_left:
        st.subheader("Elevation and range")
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Elevation (deg)"]],
            y_label="Elevation (deg)",
        )
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Range (km)"]],
            y_label="Range (km)",
        )
    with link_right:
        st.subheader("Effective rate")
        st.line_chart(
            trace_frame.set_index("Elapsed time (min)")[["Effective rate (Mbit/s)"]],
            y_label="Effective rate (Mbit/s)",
        )
        st.caption(
            "Rate is the configured implementation-efficiency fraction of the Shannon "
            "capacity upper bound, sampled from range every 10 s for this display."
        )

    st.header(f"Queue and delivery — {selected_strategy.upper()}")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Delivered", selected_report.metrics.delivered_count)
    metric_columns[1].metric("Undelivered", selected_report.metrics.undelivered_count)
    metric_columns[2].metric("Deadlines met", selected_report.metrics.deadline_met_items)
    metric_columns[3].metric(
        "Link utilization", f"{selected_report.metrics.link_utilization:.1%}"
    )
    st.dataframe(_delivery_frame(selected_report), hide_index=True, width="stretch")
    st.caption(
        "An active transfer pauses at contact loss, retains transferred bits, and resumes "
        "before another item is scheduled. New arrivals do not preempt it."
    )

with st.expander("Assumptions, safety, and model boundary"):
    st.markdown(
        f"""
- {SAFETY_NOTICE}
- Priority labels are illustrative simulation classes, not clinical guidance.
- The TLE is a frozen historical fixture propagated near its epoch; it is not current tracking data.
- The model is single-satellite, single-ground-station, single-hop, and resumable.
- Scheduling is non-preemptive. Protocol overheads, fading, interference, and
  retransmissions are omitted.
- Dynamic capacity uses an explicit 1 s midpoint timestep; display traces are sampled every 10 s.
- Shannon capacity is an upper bound, and `implementation_efficiency` is an explicit abstraction.
"""
    )
