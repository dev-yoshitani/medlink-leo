"""Offline Streamlit demo for MedLink-LEO simulation and routing."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from campaign_ui import render_campaign as render_game
from mission_scene import build_scene
from ui_labels import (
    DATA_LABELS,
    FAILURE_LABELS,
    PRIORITY_LABELS,
    ROUTING_LABELS,
    SCHEDULER_LABELS,
    outcome_label,
    route_explanation,
    station_label,
    station_name_label,
)

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
    "この画面は架空の医療データを使う工学シミュレーションです。診断・治療・臨床判断や、"
    "実際の医療活動には使えません。"
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
                "データの種類": DATA_LABELS.get(item.data_type, item.data_type),
                "種別コード": item.data_type,
                "容量（MB）": item.size_bytes / 1_000_000,
                "優先度": PRIORITY_LABELS[item.priority.name],
                "生成時刻（秒）": item.created_at_s,
                "期限（秒）": item.due_at_s,
            }
            for item in scenario.medical_data
        ]
    )


def _scheduler_comparison_frame(comparison: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "スケジューラ": SCHEDULER_LABELS[report.strategy.value],
                "到着": report.metrics.delivered_count,
                "未到着": report.metrics.undelivered_count,
                "保留": report.metrics.deferred_count,
                "期限内到着率（%）": report.metrics.deadline_satisfaction_rate * 100,
                "最優先クラスの期限内到着率（%）": (
                    report.metrics.critical_deadline_satisfaction_rate * 100
                    if report.metrics.critical_deadline_satisfaction_rate is not None
                    else None
                ),
                "平均遅延（秒）": report.metrics.average_latency_s,
                "通信利用率（%）": report.metrics.link_utilization * 100,
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
                "順番": result.selection_order,
                "ID": result.data_id,
                "優先度": PRIORITY_LABELS[result.priority.name],
                "状態": {
                    "delivered": "到着",
                    "undelivered": "未到着",
                    "deferred": "保留",
                }.get(result.status, result.status),
                "保留": "あり" if result.deferred else "なし",
                "期限内": "はい" if result.deadline_met else "いいえ",
                "送信開始（秒）": result.first_started_at_s,
                "送信完了（秒）": result.completed_at_s,
                "遅延（秒）": result.latency_s,
                "接触中断回数": result.contact_pause_count,
                "送信済み（Mbit）": result.transferred_bits / 1_000_000,
                "残量（Mbit）": result.remaining_bits / 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def _simulation_contact_frame(report: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "開始（UTC）": utc_iso(window.start_utc),
                "終了（UTC）": utc_iso(window.end_utc),
                "長さ（秒）": window.duration_s,
                "最大仰角（度）": window.maximum_elevation_deg,
                "最短距離（km）": window.minimum_range_m / 1_000,
            }
            for window in report.contact_windows
        ]
    )


def _trace_frame(scenario: IntermittentScenario) -> pd.DataFrame:
    trace = generate_link_trace(scenario, sample_step_s=10.0)
    return pd.DataFrame(
        [
            {
                "経過時間（分）": sample.time_s / 60,
                "仰角（度）": sample.elevation_deg,
                "距離（km）": sample.range_m / 1_000,
                "実効速度（Mbit/s）": sample.effective_rate_bps / 1_000_000,
            }
            for sample in trace
        ]
    )


def _routing_comparison_frame(comparison: RoutingComparisonReport) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "経路の選び方": ROUTING_LABELS[report.strategy.value],
                "到着": report.metrics.delivered_count,
                "未到着": report.metrics.failed_count,
                "期限内到着率（%）": report.metrics.deadline_satisfaction_rate * 100,
                "最優先クラスの期限内到着率（%）": (
                    report.metrics.critical_deadline_satisfaction_rate * 100
                    if report.metrics.critical_deadline_satisfaction_rate is not None
                    else None
                ),
                "到着率（%）": report.metrics.delivery_ratio * 100,
                "平均所要時間（秒）": (
                    report.metrics.average_end_to_end_latency_s
                ),
                "接触容量の使用率（%）": report.metrics.contact_utilization * 100,
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
                "接触ID": contact.contact_id,
                "地上局": station_label(contact.ground_station_id),
                "開始（秒）": contact.start_s,
                "終了（秒）": contact.end_s,
                "長さ（秒）": contact.duration_s,
                "容量（Mbit）": contact.available_capacity_bits / 1_000_000,
                "伝搬遅延（ms）": contact.propagation_delay_s * 1_000,
                "地上回線遅延（秒）": station_by_id[
                    contact.ground_station_id
                ].backhaul_delay_s,
                "最大仰角（度）": contact.maximum_elevation_deg,
            }
            for contact in report.contact_plan.contacts
        ]
    )


def _routing_result_frame(report: RoutingReport) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "順番": result.scheduling_order,
                "データID": result.medical_data_id,
                "優先度": PRIORITY_LABELS[result.priority.name],
                "地上局": station_label(result.selected_ground_station),
                "接触ID": result.selected_contact_id,
                "送信開始（秒）": result.estimated_departure_s,
                "病院到着（秒）": result.estimated_arrival_s,
                "期限（秒）": result.deadline_at_s,
                "期限との差（秒）": result.deadline_margin_s,
                "期限内": "はい" if result.deadline_feasible else "いいえ",
                "結果": outcome_label(result),
            }
            for result in report.results
        ]
    )


def _candidate_frame(result: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "地上局": station_label(candidate.ground_station_id),
                "接触開始（秒）": candidate.contact_start_s,
                "容量（Mbit）": candidate.capacity_available_bits / 1_000_000,
                "地上回線遅延（秒）": candidate.backhaul_delay_s,
                "病院到着見込み（秒）": candidate.estimated_arrival_s,
                "期限内": "はい" if candidate.deadline_feasible else "いいえ",
                "選択": "はい" if candidate.selected else "いいえ",
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


def _render_payload_queue(report: RoutingReport, scenario: RoutingScenario) -> None:
    size_by_id = {item.id: item.size_bytes * 8 / 1_000_000 for item in scenario.medical_data}
    rows = []
    for result in report.results:
        priority = result.priority.name
        status = outcome_label(result)
        station = station_label(result.selected_ground_station, "経路なし")
        data_label = DATA_LABELS.get(result.data_type, result.data_type)
        status_style = "done" if result.delivered else "failed"
        rows.append(
            '<div class="payload-row">'
            f'<span class="priority-dot {escape(priority.lower())}"></span>'
            f'<span class="payload-name"><b>{escape(result.medical_data_id)}</b>'
            f'<small>{escape(data_label)} · {PRIORITY_LABELS[priority]}</small></span>'
            f'<span class="payload-size">{size_by_id[result.medical_data_id]:.1f} Mbit</span>'
            f'<span class="payload-station">{escape(station)}</span>'
            f'<span class="payload-status {status_style}">{escape(status)}</span>'
            "</div>"
        )
    st.markdown(
        '<section class="mission-panel"><div class="panel-heading">荷物の行き先'
        '<small>架空データ</small></div>'
        + ''.join(rows)
        + '</section>',
        unsafe_allow_html=True,
    )


def _render_contact_timeline(report: RoutingReport, horizon_s: float) -> None:
    rows = []
    stations = (("gs-seoul", "ソウル"), ("gs-sapporo", "札幌"), ("gs-tokyo", "東京"))
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
            f'<span>{len(windows)}回</span></div>'
        )
    st.markdown(
        '<section class="mission-panel"><div class="panel-heading">通信できる時間'
        '<small>保存済みの軌道データ・経過時間</small></div>'
        + ''.join(rows)
        + '<div class="timeline-axis"><span>0分</span>'
        + f'<span>{horizon_s / 60:.0f}分</span></div></section>',
        unsafe_allow_html=True,
    )


def _render_route_decision(result: RouteResult) -> None:
    rows = []
    for candidate in result.candidates:
        if candidate.selected:
            state = "選択"
        elif candidate.failure_reason is not None:
            state = FAILURE_LABELS[candidate.failure_reason]
        elif not candidate.deadline_feasible:
            state = "期限超過"
        else:
            state = "ほかの候補"
        arrival = _mission_time(candidate.estimated_arrival_s)
        rows.append(
            f'<div class="candidate-row {"selected" if candidate.selected else ""}">'
            f'<b>{escape(station_label(candidate.ground_station_id))}</b>'
            f'<span class="candidate-state">{state}</span>'
            f'<span>到着（経過） {arrival}</span>'
            f'<span>容量 {candidate.capacity_available_bits / 1_000_000:.1f} Mbit</span>'
            '</div>'
        )
    if not rows:
        rows.append('<p>このデータに使える通信機会は残っていません。</p>')
    st.markdown(
        '<section class="mission-panel"><div class="panel-heading">この経路を選んだ理由</div>'
        f'<div class="decision-header"><div><strong>{escape(result.medical_data_id)}</strong>'
        f'<span>{PRIORITY_LABELS[result.priority.name]} · {outcome_label(result)}</span></div>'
        f'<div><strong>{_mission_time(result.estimated_arrival_s)}</strong>'
        '<span>病院到着（開始から）</span></div></div>'
        f'<p class="decision-reason">{escape(route_explanation(result))}</p>'
        f'<div class="candidate-list">{"".join(rows)}</div></section>',
        unsafe_allow_html=True,
    )


def _render_debrief_comparison(comparison: RoutingComparisonReport) -> None:
    rows = []
    for report in comparison.reports:
        metrics = report.metrics
        label = ROUTING_LABELS[report.strategy.value]
        rows.append(
            '<div class="strategy-row">'
            f'<strong>{escape(label)}</strong>'
            f'<span>{metrics.deadline_met_items}/{metrics.total_items}<small>期限内</small></span>'
            f'<span>{metrics.delivered_count}/{metrics.total_items}<small>到着</small></span>'
            f'<span>{_mission_time(metrics.average_end_to_end_latency_s)}'
            '<small>平均所要時間</small></span></div>'
        )
    st.markdown(
        '<section class="mission-panel"><div class="panel-heading">経路の選び方を比べる</div>'
        + ''.join(rows)
        + '</section>',
        unsafe_allow_html=True,
    )


def _render_routing_demo() -> None:
    scenario = _load_routing_scenario()
    st.markdown('<p class="mission-kicker">任務 01　東アジアの衛星通信</p>', unsafe_allow_html=True)
    st.header("医療データを届ける")
    st.write("衛星と地上局の通信機会を使い、架空のデータが病院に届く経路を調べます。")
    st.markdown(
        '<div class="scenario-strip">'
        f'<span><b>{len(scenario.medical_data)}</b>件のデータ</span>'
        f'<span><b>{len(scenario.ground_stations)}</b>か所の地上局</span>'
        f'<span><b>{scenario.horizon_s / 60:.0f}</b>分のシミュレーション</span>'
        '<span>衛星 1機</span></div>',
        unsafe_allow_html=True,
    )
    control_left, control_right = st.columns([2, 1], vertical_alignment="bottom")
    selected_strategy = control_left.selectbox(
        "経路の選び方",
        options=("next-contact", "earliest-arrival", "deadline-aware"),
        format_func=lambda value: ROUTING_LABELS[value],
        key="routing_strategy",
    )
    run_requested = control_right.button(
        "シミュレーション開始",
        type="primary",
        key="compare_routing",
        use_container_width=True,
    )

    if run_requested:
        with st.spinner("保存済みの軌道から通信機会を計算しています…"):
            st.session_state.routing_comparison = compare_routing_strategies(scenario)
    if "routing_comparison" not in st.session_state:
        st.image(
            build_scene(),
            width="stretch",
        )
        st.caption(
            "通信経路の模式図です。診療所から衛星への送信は計算対象外です。"
            "衛星の位置には保存済みの過去の軌道データを使います。"
        )
        return

    comparison = st.session_state.routing_comparison
    report_by_strategy = {report.strategy.value: report for report in comparison.reports}
    selected_report = report_by_strategy[selected_strategy]

    st.markdown(
        '<p class="run-note">計算完了。3つの選び方を、同じデータと通信機会で比べています。</p>',
        unsafe_allow_html=True,
    )
    selected_item_id = st.selectbox(
        "結果を見るデータ",
        options=tuple(result.medical_data_id for result in selected_report.results),
        key="routing_item",
    )
    selected_result = next(
        result
        for result in selected_report.results
        if result.medical_data_id == selected_item_id
    )
    if selected_result.delivered:
        station_name = station_label(selected_result.selected_ground_station)
        path_text = f"衛星上のデータ → {station_name} → 病院"
    else:
        path_text = f"{selected_result.medical_data_id}：病院まで届かず"
    st.markdown(
        '<div class="route-banner"><strong>選択中のデータ</strong>'
        f'<span>{escape(path_text)}</span><small>診療所から衛星への送信は計算対象外</small></div>',
        unsafe_allow_html=True,
    )
    st.image(
        build_scene(selected_result),
        width="stretch",
    )
    st.caption(
        "この図は通信経路の模式図で、現在位置の追跡ではありません。"
        "太い線は選ばれた経路、診療所からの点線は省略した送信区間を示します。"
    )
    _render_payload_queue(selected_report, scenario)
    _render_route_decision(selected_result)
    _render_contact_timeline(selected_report, scenario.horizon_s)

    st.subheader("結果を振り返る")
    st.markdown(
        '<div class="debrief-board"><div class="debrief-main">'
        f'<strong>{selected_report.metrics.delivered_count}'
        f'<small> / {selected_report.metrics.total_items}</small></strong>'
        '<span>病院に届いたデータ</span></div><div class="debrief-facts">'
        f'<p>期限内に到着 <b>{selected_report.metrics.deadline_met_items}件</b></p>'
        f'<p>接触容量の使用率 <b>{selected_report.metrics.contact_utilization:.1%}</b></p>'
        '<p>到着したデータの平均所要時間 '
        f'<b>{_mission_time(selected_report.metrics.average_end_to_end_latency_s)}</b></p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    comparison_frame = _routing_comparison_frame(comparison)
    _render_debrief_comparison(comparison)
    st.caption(
        "平均所要時間は到着したデータだけで計算します。遅れるデータを送らない方式では、"
        "同じデータが速く届かなくても平均値が小さくなる場合があります。"
    )

    with st.expander("詳しいデータと再現用ファイル"):
        st.download_button(
            "計算結果をJSONで保存",
            json.dumps(comparison.to_dict(), indent=2, allow_nan=False),
            file_name="medlink-routing-comparison.json",
            mime="application/json",
        )
        st.markdown("**架空データの一覧**")
        st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")
        st.markdown("**3方式の指標**")
        st.dataframe(comparison_frame, hide_index=True, width="stretch")
        st.bar_chart(
            comparison_frame.set_index("経路の選び方")[["期限内到着率（%）"]],
            y_label="期限内到着率（%）",
        )
        st.markdown("**経路の結果**")
        st.dataframe(_routing_result_frame(selected_report), hide_index=True, width="stretch")
        st.markdown("**候補となった通信機会**")
        st.dataframe(_candidate_frame(selected_result), hide_index=True, width="stretch")
        st.markdown("**通信機会の一覧**")
        st.dataframe(_routing_contact_frame(selected_report), hide_index=True, width="stretch")
        st.caption(
            "容量はSGP4による距離とRFモデルから、一定刻みの中点サンプリングで積算しています。"
            "数値の単位と候補の可否は表内に示しています。"
        )


def _render_existing_simulation() -> None:
    scenario = _load_simulation_scenario()
    st.markdown('<p class="mission-kicker">通信リンクの記録</p>', unsafe_allow_html=True)
    st.header("通信リンクを調べる")
    st.write(
        "衛星と地上局がつながる時間を使い、データを送る順番による違いを調べます。"
    )
    st.markdown(
        '<div class="scenario-strip">'
        f'<span><b>{len(scenario.medical_data)}</b>件のデータ</span>'
        f'<span>地上局 <b>{escape(station_name_label(scenario.ground_station.name))}</b></span>'
        f'<span><b>{scenario.horizon_s / 60:.0f}</b>分のシミュレーション</span>'
        f'<span>計算刻み {scenario.time_step_s:g}秒</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"シナリオ {scenario.scenario_id}・{utc_iso(scenario.start_utc)}から"
        f"{utc_iso(scenario.end_utc)}まで・保存済みTLEの基準時刻 "
        f"{utc_iso(scenario.tle.epoch_utc)}"
    )
    with st.expander("架空データの一覧", expanded=False):
        st.dataframe(_workload_frame(scenario), hide_index=True, width="stretch")

    selected_strategy = st.selectbox(
        "送る順番",
        options=("fifo", "priority", "edf"),
        format_func=lambda value: SCHEDULER_LABELS[value],
        key="scheduler_strategy",
    )
    run_requested = st.button("計算する", type="primary", key="run_simulation")
    if run_requested:
        with st.spinner("保存済みの軌道から通信状態を計算しています…"):
            st.session_state.simulation_comparison = compare_strategies(scenario)
            st.session_state.simulation_trace = _trace_frame(scenario)
    if "simulation_comparison" not in st.session_state:
        return

    comparison = st.session_state.simulation_comparison
    report_by_strategy = {report.strategy.value: report for report in comparison.reports}
    selected_report = report_by_strategy[selected_strategy]
    trace_frame = st.session_state.simulation_trace

    st.markdown(
        '<p class="run-note">計算完了。同じ架空データと通信状態で3方式を比べています。</p>',
        unsafe_allow_html=True,
    )
    st.subheader("送る順番による違い")
    comparison_frame = _scheduler_comparison_frame(comparison)
    st.dataframe(comparison_frame, hide_index=True, width="stretch")
    st.bar_chart(
        comparison_frame.set_index("スケジューラ")[["期限内到着率（%）"]],
        y_label="期限内到着率（%）",
    )

    st.subheader("衛星と地上局がつながる時間")
    contact_frame = _simulation_contact_frame(selected_report)
    if contact_frame.empty:
        st.info("この計算時間内に通信機会はありません。")
    else:
        st.dataframe(contact_frame, hide_index=True, width="stretch")
    link_left, link_right = st.columns(2)
    with link_left:
        st.line_chart(
            trace_frame.set_index("経過時間（分）")[["仰角（度）"]],
            y_label="仰角（度）",
        )
        st.line_chart(
            trace_frame.set_index("経過時間（分）")[["距離（km）"]],
            y_label="距離（km）",
        )
    with link_right:
        st.line_chart(
            trace_frame.set_index("経過時間（分）")[["実効速度（Mbit/s）"]],
            y_label="実効速度（Mbit/s）",
        )
        st.caption(
            "表示した速度は、シャノン容量の上限値に設定上の実装効率を掛けた値です。"
        )

    st.subheader(f"送信順と到着結果：{SCHEDULER_LABELS[selected_strategy]}")
    st.dataframe(_delivery_frame(selected_report), hide_index=True, width="stretch")
    st.caption(
        "通信が途切れると送信中のデータは一時停止し、送信済みの量を保持します。"
        "再接続後に残りを送ってから次のデータへ進みます。"
    )


st.set_page_config(
    page_title="MedLink-LEO",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    "<style>" + (Path(__file__).parent / "style.css").read_text(encoding="utf-8") + "</style>",
    unsafe_allow_html=True,
)

st.title("MedLink-LEO")
with st.sidebar:
    st.header("ゲーム・解析ツール")
    mode = st.radio(
        "見る画面",
        options=("通信センター", "経路シミュレーション", "通信リンク"),
        key="demo_mode",
    )
    st.caption(SAFETY_NOTICE)
    st.markdown("[ソースコードと設計資料](https://github.com/dev-yoshitani/medlink-leo)")
if mode == "通信センター":
    render_game()
elif mode == "経路シミュレーション":
    _render_routing_demo()
else:
    _render_existing_simulation()

with st.expander("計算の前提と利用上の注意"):
    st.markdown(
        f"""
- {SAFETY_NOTICE}
- 優先度はシミュレーション用の分類であり、臨床上の判断基準ではありません。
- TLEは過去の保存済みデータで、その基準時刻付近を計算しています。現在の衛星位置ではありません。
- 経路シミュレーションは衛星1機・地上局3か所です。ゲームは架空の円軌道と最大6機・6拠点を扱います。
- データは生成時点で衛星上にあると仮定し、診療所から衛星への送信は省略しています。
- 1件の配送には1回の通信機会を使います。完全なDTN/BPv7、通信機会の分割、
  衛星間中継は含みません。ゲームの複数衛星運用は、過去TLEの解析とは別の簡略モデルです。
- 通信容量は1秒刻みの中点サンプリングと、文書化したRFモデルで計算しています。
- プロトコルの追加データ、再送、フェージング、干渉、適応符号化は含めていません。
"""
    )
