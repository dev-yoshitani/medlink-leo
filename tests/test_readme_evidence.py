from __future__ import annotations

import json
from pathlib import Path


def test_readme_benchmark_table_matches_committed_summary() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    payload = json.loads(
        (root / "docs" / "assets" / "benchmark" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    labels = {"fifo": "FIFO", "priority": "Priority", "edf": "EDF"}

    assert payload["config_id"] == "canonical-v1.0"
    assert payload["project_version"] == "1.0.0"
    for row in payload["summary"]:
        expected = (
            f"| {labels[row['strategy']]} | "
            f"{row['mean_deadline_satisfaction_rate']:.2%} | "
            f"{row['mean_critical_deadline_satisfaction_rate']:.2%} | "
            f"{row['mean_average_latency_s']:.2f} s | "
            f"{row['total_delivered_count']} / "
            f"{row['total_delivered_count'] + row['total_undelivered_count']} |"
        )
        assert expected in readme


def test_safety_disclaimer_is_visible_in_readme_and_web_demo() -> None:
    root = Path(__file__).resolve().parents[1]
    required = "uses synthetic medical data only"
    assert required in (root / "README.md").read_text(encoding="utf-8")
    assert required in (root / "app" / "streamlit_app.py").read_text(encoding="utf-8")
