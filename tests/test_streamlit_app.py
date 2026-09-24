from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from streamlit.testing.v1 import AppTest

from app.mission_scene import ASSET_DIR, build_scene
from app.ui_labels import ROUTING_LABELS, STATION_LABELS
from medlink.routing import compare_routing_strategies
from medlink.scenarios import load_scenario


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
        Path(__file__).resolve().parents[1]
        / "examples"
        / "contact_plan_medical_routing.json"
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

    assert not app.exception
    assert app.title[0].value == "MedLink-LEO"
    assert any("架空の医療データ" in mark.value for mark in app.markdown)
    assert app.button(key="compare_routing").label == "シミュレーション開始"

    app.button(key="compare_routing").click().run(timeout=30)

    assert not app.exception
    assert any("計算完了" in mark.value for mark in app.markdown)
    assert any(header.value == "結果を振り返る" for header in app.subheader)
    comparison = next(
        frame.value
        for frame in app.dataframe
        if "経路の選び方" in frame.value.columns
    )
    assert comparison["経路の選び方"].tolist() == list(ROUTING_LABELS.values())
    station_comparison = next(
        frame.value
        for frame in app.dataframe
        if "接触開始（秒）" in frame.value.columns
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
