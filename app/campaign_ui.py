"""Streamlit transport for the six-hour campaign; all rules live in Python."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from medlink.campaign import CampaignState, GameError, apply_command, begin_day, load_campaign
from medlink.campaign.challenges import CATALOG, daily_challenge, exercise, exercise_model
from medlink.campaign.content import ORBIT_PLANS, RESEARCH, SATELLITE_TYPES, STATIONS
from medlink.campaign.flight import build_contacts, orbit_overlap, remaining_capacity_mb
from medlink.campaign.models import Assignment, DailyPlan, Satellite
from medlink.campaign.saves import SAVE_LIMIT
from medlink.campaign.service import chapter_goals, contract_lock, goal_title, preview_day

BOARD = components.declare_component("satellite_campaign", path=Path(__file__).parent / "campaign")


def board_model(state: CampaignState) -> dict:
    preview = state.report or preview_day(state)
    remaining = remaining_capacity_mb(state.book.contacts, preview.deliveries)
    facilities = {f.id: f for f in state.facilities}
    return {
        "state": state.to_dict(),
        "title": goal_title(state),
        "goals": chapter_goals(state),
        "daily_challenge": daily_challenge(state),
        "exercises": [
            {"id": row[0], "chapter": row[1], "title": row[2], "body": row[3]} for row in CATALOG
        ],
        "preview": asdict(preview),
        "comparisons": [asdict(preview_day(state, p)) for p in state.comparisons],
        "contacts": [
            {
                "id": c.id,
                "satellite": c.satellite,
                "station": c.station,
                "name": STATIONS[c.station]["name"],
                "start": c.start,
                "end": c.end,
                "capacity_mb": c.capacity_mb,
                "remaining_mb": remaining[c.id],
                "receivers": c.receivers,
                "delay": c.delay,
            }
            for c in state.book.contacts
        ],
        "contracts": [{**asdict(c), "lock": contract_lock(state, c)} for c in state.book.offers],
        "stations": [
            {
                "id": key,
                **settings,
                "facility": asdict(facilities[key]) if key in facilities else None,
            }
            for key, settings in STATIONS.items()
        ],
        "types": SATELLITE_TYPES,
        "orbits": ORBIT_PLANS,
        "research": RESEARCH,
        "orbit_comparisons": [
            {
                "id": key,
                "kind": kind,
                "overlap": orbit_overlap(state.book.contacts, proposed),
                "windows": len(proposed),
                "capacity_mb": sum(c.capacity_mb for c in proposed),
            }
            for kind in SATELLITE_TYPES
            for key in ORBIT_PLANS
            for proposed in [
                build_contacts(
                    (Satellite("candidate", kind, key),), state.facilities, state.book.event
                )
            ]
        ],
        "assets": {
            name: f"art/{name}-v2.png"
            for name in (
                "landscape", "satellite", "ground_station", "hospital", "remote_clinic", "parcel"
            )
        },
    }


def render_campaign() -> None:
    if "fleet_state" not in st.session_state:
        st.session_state.fleet_state = begin_day(CampaignState())
        st.session_state.fleet_restored = False
        st.session_state.fleet_ack = None
        st.session_state.fleet_notice = ""
        st.session_state.fleet_error = False
    state = st.session_state.fleet_state
    event = BOARD(
        model=board_model(state),
        restore_requested=not st.session_state.fleet_restored,
        ack=st.session_state.fleet_ack,
        notice=st.session_state.fleet_notice,
        error=st.session_state.fleet_error,
        restore_error=st.session_state.get("fleet_restore_error", False),
        pending_import=st.session_state.get("fleet_pending_import"),
        exercise=st.session_state.get("fleet_exercise"),
        key="fleet_board",
        default=None,
    )
    if st.session_state.fleet_restored:
        with st.expander("セーブファイル・配送の計算結果"):
            st.download_button(
                "セーブを書き出す",
                state.to_json(),
                "medlink-campaign-v2.json",
                mime="application/json",
                key="fleet_download",
            )
            st.download_button(
                "配送結果を書き出す",
                json.dumps(
                    asdict(state.report or preview_day(state)), ensure_ascii=False, indent=2
                ),
                "medlink-game-report.json",
                mime="application/json",
                key="fleet_report_download",
            )
            with st.form("fleet_import"):
                saved = st.file_uploader("セーブを読み込む（2 MBまで・旧形式も対応）", type="json")
                requested = st.form_submit_button("このセーブで再開")
            if requested:
                try:
                    if saved is None:
                        raise GameError("セーブファイルを選んでください。")
                    if saved.size > SAVE_LIMIT:
                        raise GameError("セーブは2 MBまでです。")
                    imported = load_campaign(saved.getvalue().decode("utf-8"))
                    # Tell the component to acquire its persistence lock before replacement.
                    st.session_state.fleet_pending_import = imported.to_dict()
                    st.rerun()
                except (GameError, UnicodeDecodeError) as error:
                    st.error(str(error))
    if (
        not isinstance(event, dict)
        or not isinstance(event.get("id"), str)
        or event["id"] == st.session_state.fleet_ack
    ):
        return
    st.session_state.fleet_ack = event["id"]
    st.session_state.fleet_error = False
    st.session_state.fleet_restore_error = False
    try:
        if event.get("action") != "restore" and not st.session_state.fleet_restored:
            raise GameError("保存した記録を復元しています。少し待ってから操作してください。")
        if event.get("action") == "restore":
            updated = load_campaign(event["save"]) if event.get("save") else state
            st.session_state.pop("fleet_exercise", None)
            st.session_state.fleet_restored = True
            notice = (
                "以前のセーブを引き継ぎました。"
                if updated.migrated
                else "通信センターの記録を開きました。"
            )
        elif event.get("action") in ("exercise", "exercise_plan", "exercise_example"):
            if event.get("revision") != state.revision:
                raise GameError("進行が変わりました。最新の記録を読み込んでください。")
            case = exercise(event.get("exercise"))
            if case["chapter"] > state.chapter:
                raise GameError("章を進めるとこの課題を開けます。")
            if event["action"] == "exercise_plan":
                allocations = event.get("allocations")
                if not isinstance(allocations, list) or len(allocations) > 100:
                    raise GameError("練習の配送計画を確認してください。")
                plan = DailyPlan(tuple(Assignment(a["parcel"], a["contact"]) for a in allocations))
            elif event["action"] == "exercise_example":
                choice = event.get("example")
                if type(choice) is not int or choice not in (0, 1):
                    raise GameError("比較する案を選んでください。")
                plan = case["plans"][choice]
            else:
                plan = case["plans"][0]
            st.session_state.fleet_exercise = exercise_model(case["id"], plan)
            updated = state
            notice = "練習課題を計算しました。本番の資金と依頼は変わりません。"
        elif event.get("action") == "import":
            if event.get("revision") != state.revision:
                raise GameError("進行が変わりました。最新のセーブを読み込んでください。")
            updated = load_campaign(event["save"])
            updated = replace(updated, revision=state.revision + 1)
            st.session_state.pop("fleet_pending_import", None)
            st.session_state.pop("fleet_exercise", None)
            notice = "セーブを読み込みました。"
        else:
            updated = apply_command(state, event)
            notice = {
                "claim": "報酬を受け取りました。設備への投資と翌日の準備ができます。",
                "commit": "今日の配送結果が確定しました。再生を待たずに報酬を受け取れます。",
                "next": "新しい朝です。依頼と運用条件を確認してください。",
            }.get(event.get("action"), "記録しました。")
        st.session_state.fleet_state = updated
        st.session_state.fleet_notice = notice
    except (GameError, ValueError, TypeError, KeyError) as error:
        st.session_state.fleet_error = True
        st.session_state.fleet_notice = str(error)
        if event.get("action") == "restore":
            # Keep a corrupt stored save intact; player can export it and start in memory.
            st.session_state.fleet_restored = True
            st.session_state.fleet_restore_error = True
            st.session_state.fleet_notice = (
                f"セーブを復元できませんでした。元の記録を保護しています。{error}"
            )
    st.rerun()
