from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from streamlit.testing.v1 import AppTest

from app.mission_scene import ASSET_DIR, build_scene
from app.ui_labels import ROUTING_LABELS, STATION_LABELS
from medlink.campaign import CampaignState, begin_day, commit_day
from medlink.campaign.service import accept
from medlink.routing import compare_routing_strategies
from medlink.scenarios import load_scenario


def test_campaign_transport_restores_before_accepting_commands_after_session_loss(monkeypatch):
    import importlib

    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    monkeypatch.syspath_prepend(str(app_path.parent))
    campaign_ui = importlib.import_module("campaign_ui")

    event = [{"id": "lost-session", "revision": 0, "action": "accept", "contract": "d1-regular"}]
    monkeypatch.setattr(campaign_ui, "BOARD", lambda **kwargs: event[0])
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not app.exception
    assert not app.session_state.fleet_restored
    assert app.session_state.fleet_error
    assert app.session_state.fleet_state.accepted == ()
    saved = begin_day(CampaignState(credits=770, revision=18))
    event[0] = {"id": "restore-session", "action": "restore", "save": saved.to_dict()}
    app.run()
    assert app.session_state.fleet_restored
    assert app.session_state.fleet_state == saved
    assert not app.session_state.fleet_error


def test_purchase_comparisons_use_selected_type_and_daily_event():
    from app.campaign_ui import board_model

    state = begin_day(CampaignState(day=4))
    comparisons = board_model(state)["orbit_comparisons"]
    assert len(comparisons) == 9
    small = next(c for c in comparisons if c["kind"] == "small" and c["id"] == "early")
    power = next(c for c in comparisons if c["kind"] == "power" and c["id"] == "early")
    assert power["capacity_mb"] > small["capacity_mb"]
    assert small["overlap"] == 1


def test_mission_scene_uses_bundled_vectors_and_actual_selected_route() -> None:
    for name in (
        "satellite",
        "remote_clinic",
        "ground_station",
        "hospital",
        "medical_packet_critical",
        "medical_packet_normal",
    ):
        ElementTree.parse(ASSET_DIR / f"{name}.svg")

    scenario_path = (
        Path(__file__).resolve().parents[1] / "examples" / "contact_plan_medical_routing.json"
    )
    comparison = compare_routing_strategies(load_scenario(scenario_path))
    result = next(result for result in comparison.reports[0].results if result.delivered)
    scene = build_scene(result)
    ElementTree.fromstring(scene)

    assert result.selected_ground_station is not None
    assert "選択した地上局" in scene
    assert STATION_LABELS[result.selected_ground_station] in scene
    assert "送信区間は省略" in scene


def test_default_streamlit_routing_demo_runs_offline() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert app.radio(key="demo_mode").value == "通信センター"
    app.radio(key="demo_mode").set_value("経路シミュレーション").run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "MedLink-LEO"
    assert any("架空の医療データ" in mark.value for mark in app.markdown)
    assert app.button(key="compare_routing").label == "シミュレーション開始"

    app.button(key="compare_routing").click().run(timeout=30)

    assert not app.exception
    assert any("計算完了" in mark.value for mark in app.markdown)
    assert any(header.value == "結果を振り返る" for header in app.subheader)
    comparison = next(
        frame.value for frame in app.dataframe if "経路の選び方" in frame.value.columns
    )
    assert comparison["経路の選び方"].tolist() == list(ROUTING_LABELS.values())
    station_comparison = next(
        frame.value for frame in app.dataframe if "接触開始（秒）" in frame.value.columns
    )
    assert list(station_comparison.columns) == [
        "地上局",
        "接触開始（秒）",
        "容量（Mbit）",
        "地上回線遅延（秒）",
        "病院到着見込み（秒）",
        "期限内",
        "選択",
    ]

    app.selectbox(key="routing_strategy").set_value("deadline-aware").run(timeout=30)
    assert not app.exception
    assert app.selectbox(key="routing_strategy").value == "deadline-aware"
    item_ids = app.selectbox(key="routing_item").options
    app.selectbox(key="routing_item").set_value(item_ids[-1]).run(timeout=30)
    assert not app.exception
    assert any("接触開始（秒）" in frame.value.columns for frame in app.dataframe)
    assert any("病院まで届かず" in mark.value for mark in app.markdown)
    app.radio(key="demo_mode").set_value("通信リンク").run(timeout=30)
    app.radio(key="demo_mode").set_value("経路シミュレーション").run(timeout=30)
    assert any("経路の選び方" in frame.value.columns for frame in app.dataframe)


def test_existing_simulation_mode_remains_available() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.radio(key="demo_mode").set_value("通信リンク").run(timeout=30)

    assert not app.exception
    assert app.button(key="run_simulation").label == "計算する"
    app.button(key="run_simulation").click().run(timeout=30)

    assert not app.exception
    comparison = next(
        frame.value for frame in app.dataframe if "スケジューラ" in frame.value.columns
    )
    assert comparison["スケジューラ"].tolist() == [
        "到着順（FIFO）",
        "優先度順（説明用）",
        "期限が近い順（EDF）",
    ]
    assert comparison["到着"].tolist() == [3, 2, 3]
    app.selectbox(key="scheduler_strategy").set_value("edf").run(timeout=30)
    assert not app.exception
    assert any("送信順と到着結果：期限が近い順（EDF）" == header.value for header in app.subheader)


def test_campaign_save_and_report_controls_render_for_resumed_delivery() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.session_state["fleet_state"] = commit_day(accept(begin_day(CampaignState()), "d1-regular"))
    app.session_state["fleet_restored"] = True
    app.run(timeout=30)

    assert not app.exception
    assert len(app.get("download_button")) == 2
    assert app.button[0].label == "このセーブで再開"
