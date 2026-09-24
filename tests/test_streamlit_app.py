from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from streamlit.testing.v1 import AppTest

from app.mission_scene import ASSET_DIR, build_scene
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
    assert "ROUTE SELECTED" in scene
    assert result.selected_ground_station.split("-")[-1].upper() in scene
    assert "UPLINK ABSTRACTED" in scene


def test_default_streamlit_routing_demo_runs_offline() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert app.title[0].value == "MedLink-LEO"
    assert "synthetic medical data only" in app.warning[0].value
    assert app.button(key="compare_routing").label == "Start Mission"

    app.button(key="compare_routing").click().run(timeout=30)

    assert not app.exception
    assert any("Mission complete" in success.value for success in app.success)
    assert any(header.value == "Mission Debrief" for header in app.subheader)
    comparison = next(
        frame.value
        for frame in app.dataframe
        if "Routing strategy" in frame.value.columns
    )
    assert comparison["Routing strategy"].tolist() == [
        "next-contact",
        "earliest-arrival",
        "deadline-aware",
    ]
    station_comparison = next(
        frame.value
        for frame in app.dataframe
        if "Next Contact" in frame.value.columns
    )
    assert list(station_comparison.columns) == [
        "Ground Station",
        "Next Contact",
        "Capacity (Mbit)",
        "Backhaul (s)",
        "Estimated Arrival (s)",
        "Deadline Feasible",
        "Selected",
    ]

    app.selectbox(key="routing_strategy").set_value("deadline-aware").run(timeout=30)
    assert not app.exception
    assert any("deadline-aware" in mark.value for mark in app.markdown)
    item_ids = app.selectbox(key="routing_item").options
    app.selectbox(key="routing_item").set_value(item_ids[-1]).run(timeout=30)
    assert not app.exception
    assert any("Next Contact" in frame.value.columns for frame in app.dataframe)
    assert any("no delivery route" in mark.value for mark in app.markdown)
    app.radio(key="demo_mode").set_value("Link Simulator").run(timeout=30)
    app.radio(key="demo_mode").set_value("Routing Mission").run(timeout=30)
    assert any("Routing strategy" in frame.value.columns for frame in app.dataframe)


def test_existing_simulation_mode_remains_available() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.radio(key="demo_mode").set_value("Link Simulator").run(timeout=30)

    assert not app.exception
    assert app.button(key="run_simulation").label == "Run Simulation"
    app.button(key="run_simulation").click().run(timeout=30)

    assert not app.exception
    comparison = next(
        frame.value for frame in app.dataframe if "Scheduler" in frame.value.columns
    )
    assert comparison["Scheduler"].tolist() == ["FIFO", "PRIORITY", "EDF"]
    assert comparison["Delivered"].tolist() == [3, 2, 3]
    app.selectbox(key="scheduler_strategy").set_value("edf").run(timeout=30)
    assert not app.exception
    assert any("Queue and delivery — EDF" == header.value for header in app.subheader)
