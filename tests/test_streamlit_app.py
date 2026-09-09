from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_default_streamlit_routing_demo_runs_offline() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert app.title[0].value == "MedLink-LEO"
    assert "synthetic medical data only" in app.warning[0].value
    assert app.button(key="compare_routing").label == "Compare Routing Strategies"

    app.button(key="compare_routing").click().run(timeout=30)

    assert not app.exception
    assert any("Routing comparison complete" in success.value for success in app.success)
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


def test_existing_simulation_mode_remains_available() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.radio(key="demo_mode").set_value("Existing Simulation").run(timeout=30)

    assert not app.exception
    assert app.button(key="run_simulation").label == "Run Simulation"
    app.button(key="run_simulation").click().run(timeout=30)

    assert not app.exception
    comparison = next(
        frame.value for frame in app.dataframe if "Scheduler" in frame.value.columns
    )
    assert comparison["Scheduler"].tolist() == ["FIFO", "PRIORITY", "EDF"]
    assert comparison["Delivered"].tolist() == [3, 2, 3]
