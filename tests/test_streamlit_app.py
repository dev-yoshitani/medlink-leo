from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_default_streamlit_demo_runs_offline() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert app.title[0].value == "MedLink-LEO"
    assert "synthetic medical data only" in app.warning[0].value
    assert app.button(key="run_simulation").label == "Run Simulation"

    app.button(key="run_simulation").click().run(timeout=30)

    assert not app.exception
    assert any("Simulation complete" in success.value for success in app.success)
    assert len(app.dataframe) >= 4
    comparison = app.dataframe[1].value
    assert comparison["Scheduler"].tolist() == ["FIFO", "PRIORITY", "EDF"]
    assert comparison["Delivered"].tolist() == [3, 2, 3]
