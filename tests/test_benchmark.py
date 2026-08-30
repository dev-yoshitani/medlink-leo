from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from medlink.cli import main
from medlink.experiments import run_benchmark

CONFIG = Path("tests/fixtures/benchmark_smoke.json")


def test_benchmark_generates_expected_artifacts(tmp_path: Path) -> None:
    report = run_benchmark(CONFIG, tmp_path)
    assert report.config_id == "smoke-v0.5"
    assert report.run_count == 3
    for filename in (
        "raw_results.csv",
        "summary.csv",
        "summary.json",
        "summary.md",
        "run_metadata.json",
        "deadline_satisfaction_by_scheduler.png",
        "average_latency_by_scheduler.png",
    ):
        assert (tmp_path / filename).is_file()
        assert (tmp_path / filename).stat().st_size > 0

    raw = pd.read_csv(tmp_path / "raw_results.csv")
    assert raw["scheduler"].tolist() == ["fifo", "priority", "edf"]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_count"] == 3


def test_benchmark_machine_outputs_are_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    run_benchmark(CONFIG, first)
    run_benchmark(CONFIG, second)
    for filename in ("raw_results.csv", "summary.csv", "summary.json", "summary.md"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_benchmark_cli(capsys, tmp_path: Path) -> None:
    assert (
        main(
            [
                "benchmark",
                "--config",
                str(CONFIG),
                "--output-dir",
                str(tmp_path),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["config_id"] == "smoke-v0.5"
    assert payload["run_count"] == 3

