"""Streamlit bridge for a browser-local 2D campaign component."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from ui_labels import DATA_LABELS, PRIORITY_LABELS, outcome_label, route_explanation

from medlink.game import (
    CONTRACT_BY_ID,
    CONTRACTS,
    MAX_LEVEL,
    STATION_NAMES,
    UNLOCKS,
    GameError,
    GameState,
    abandon,
    accept_contract,
    campaign_contact_plan,
    chapter,
    dispatch,
    equipment_scenario,
    load_save,
    mission_items,
    mission_report,
    settle,
    unlock_station,
    upgrade,
    upgrade_cost,
)

BOARD = components.declare_component("communication_center", path=Path(__file__).parent / "game")


def _assets() -> dict[str, str]:
    folder = Path(__file__).parent / "assets"
    return {
        name: "data:image/svg+xml;base64," + base64.b64encode(
            (folder / f"{name}.svg").read_bytes()
        ).decode("ascii")
        for name in ("satellite", "ground_station", "hospital", "remote_clinic",
                     "medical_packet_normal", "medical_packet_critical")
    }


def board_model(state: GameState) -> dict[str, Any]:
    number, title = chapter(state)
    scenario = equipment_scenario(state.stations)
    plan = campaign_contact_plan(state.stations)
    configured = {station.id: station for station in scenario.ground_stations}
    stations = []
    for station in state.stations:
        required, cost = UNLOCKS[station.id]
        current = configured.get(station.id)
        stations.append({
            **asdict(station), "name": STATION_NAMES[station.id],
            "required": required, "unlock_cost": cost,
            "antenna_cost": upgrade_cost(station.antenna),
            "backhaul_cost": upgrade_cost(station.backhaul),
            "capacity_mbit": sum(contact.available_capacity_bits for contact in plan.contacts
                                 if contact.ground_station_id == station.id) / 1_000_000,
            "gain_dbi": current.rf_link.rx_antenna_gain_dbi if current else None,
            "delay_s": current.backhaul_delay_s if current else None,
        })
    active = None
    report_data = None
    if state.active is not None:
        contract = CONTRACT_BY_ID[state.active.contract_id]
        active = {**asdict(state.active), "title": contract.title, "target": contract.target,
                  "tip": contract.tip, "bounty": contract.bounty}
        items = mission_items(state.active)
        active["items"] = [{
            "id": item.id, "name": f"{DATA_LABELS[item.data_type]} {i + 1}",
            "priority": PRIORITY_LABELS[item.priority.name],
            "size_mb": item.size_bytes / 1_000_000,
            "created": item.created_at_s, "deadline": item.due_at_s,
        } for i, item in enumerate(items)]
        if state.active.dispatched:
            report = mission_report(state)
            metrics = report.metrics
            results = [{
                "id": result.medical_data_id, "station": result.selected_ground_station,
                "created": result.created_at_s, "departure": result.estimated_departure_s,
                "rf_complete": result.estimated_rf_completion_s,
                "arrival": result.estimated_arrival_s, "deadline": result.deadline_at_s,
                "delivered": result.delivered, "on_time": result.deadline_feasible,
                "outcome": outcome_label(result), "reason": route_explanation(result),
                "critical": result.priority.name == "CRITICAL",
            } for result in report.results]
            reward = ((20 if metrics.delivered_count else 0) + metrics.deadline_met_items * 50
                      + (contract.bounty if metrics.deadline_met_items >= contract.target else 0))
            report_data = {
                "results": results, "total": metrics.total_items,
                "delivered": metrics.delivered_count, "on_time": metrics.deadline_met_items,
                "success": metrics.deadline_met_items >= contract.target, "reward": reward,
                "end_time": max(1, *(result.estimated_arrival_s or result.created_at_s
                                      for result in report.results)),
            }
    next_unlock = next((station for station in stations if not station["opened"]), None)
    if next_unlock:
        next_goal = (f"{next_unlock['name']}の地上局を開放：依頼達成"
                     f"{state.successes}/{next_unlock['required']}回・"
                     f"資金{next_unlock['unlock_cost']} C")
    elif state.successes < 10:
        next_goal = f"広域の依頼を開放：依頼達成{state.successes}/10回"
    else:
        next_goal = "設備を育てながら、広域の依頼で期限内到着を増やそう"
    return {
        "state": state.to_dict(), "chapter": number, "chapter_title": title,
        "next_goal": next_goal, "stations": stations,
        "contracts": [{
            "id": contract.id, "title": contract.title, "client": contract.client,
            "description": contract.description, "required": contract.required_successes,
            "target": contract.target, "total": len(contract.parcels), "bounty": contract.bounty,
        } for contract in CONTRACTS],
        "active": active, "report": report_data, "assets": _assets(), "max_level": MAX_LEVEL,
    }


def apply_event(state: GameState, event: dict[str, Any]) -> tuple[GameState, str]:
    action = event.get("action")
    if action in ("restore", "import"):
        if event.get("save") is None and action == "restore":
            return state, "札幌の通信センターへようこそ。まずは「朝の定期便」を受けてみよう。"
        return load_save(event.get("save")), "前回の運用を読み込みました。続きから遊べます。"
    if action == "accept":
        updated = accept_contract(state, event.get("contract_id"))
        return updated, "受注しました。配送の方針を選ぼう。"
    if action == "dispatch":
        updated = dispatch(state, event.get("strategy"), event.get("scheduler"))
        mission_report(updated)
        return updated, "配送結果を計算しました。地図上で再生します。"
    if action == "settle":
        updated = settle(state)
        record = updated.history[-1]
        prefix = "依頼達成！" if record.success else "配送を終えました。設備と方針を見直そう。"
        return updated, f"{prefix} +{record.reward} C。次の依頼や設備強化へ進めます。"
    if action == "upgrade":
        updated = upgrade(state, event.get("station_id"), event.get("equipment"))
        return updated, "設備を強化しました。地図と通信性能に反映されています。"
    if action == "unlock":
        updated = unlock_station(state, event.get("station_id"))
        return updated, "地上局を開放しました。次の依頼から使えます。"
    if action == "abandon":
        return abandon(state), "受注を取り下げました。資金は減りません。"
    raise GameError("操作を確認してください。")


def render_game() -> None:
    if "campaign_state" not in st.session_state:
        st.session_state.campaign_state = GameState()
        st.session_state.campaign_restored = False
        st.session_state.campaign_notice = ""
        st.session_state.campaign_event_id = None
    state = st.session_state.campaign_state
    event = BOARD(
        model=board_model(state), restore_requested=not st.session_state.campaign_restored,
        notice=st.session_state.campaign_notice, ack=st.session_state.campaign_event_id,
        key="campaign_board", default=None,
    )
    if st.session_state.campaign_restored:
        _render_save_files(state)
    if not isinstance(event, dict) or not isinstance(event.get("id"), str):
        return
    if event["id"] == st.session_state.campaign_event_id:
        return
    st.session_state.campaign_event_id = event["id"]
    try:
        updated, notice = apply_event(state, event)
        st.session_state.campaign_state = updated
        st.session_state.campaign_notice = notice
    except (GameError, TypeError) as error:
        st.session_state.campaign_notice = (
            str(error) if isinstance(error, GameError) else "操作の内容を確認してください。"
        )
    st.session_state.campaign_restored = True
    st.rerun()


def _render_save_files(state: GameState) -> None:
    with st.expander("セーブファイル・配送の計算結果"):
        st.caption("ブラウザーを変えるときや、進行を保管するときに使えます。")
        st.download_button(
            "セーブを書き出す", state.to_json(), "medlink-campaign.json",
            mime="application/json", key="campaign_download",
        )
        with st.form("campaign_import", clear_on_submit=True):
            saved_file = st.file_uploader("セーブを読み込む（200 KBまで）", type="json")
            st.caption("読み込むと現在の進行を置き換えます。前の進行はブラウザーに残ります。")
            import_requested = st.form_submit_button("このセーブで再開")
        if import_requested:
            if saved_file is None:
                st.warning("セーブファイルを選んでください。")
            else:
                try:
                    if saved_file.size > 200_000:
                        raise GameError("セーブファイルが大きすぎます。")
                    updated = load_save(saved_file.getvalue().decode("utf-8"))
                except (GameError, UnicodeDecodeError) as error:
                    st.error(str(error) if isinstance(error, GameError)
                             else "UTF-8のセーブファイルを選んでください。")
                else:
                    st.session_state.campaign_state = updated
                    st.session_state.campaign_notice = "セーブを読み込みました。続きから遊べます。"
                    st.rerun()
        if state.active is not None and state.active.dispatched:
            st.download_button(
                "配送の計算結果を書き出す",
                json.dumps(mission_report(state).to_dict(), ensure_ascii=False, indent=2),
                "medlink-campaign-routing.json", mime="application/json",
                key="campaign_report_download",
            )
