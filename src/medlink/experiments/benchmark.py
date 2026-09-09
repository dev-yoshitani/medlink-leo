"""Canonical scheduler benchmark runner and artifact generation."""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "medlink-leo-matplotlib")
)
import matplotlib
import pandas as pd

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from medlink.models import MedicalData
from medlink.orbit import find_contact_windows
from medlink.scenarios import IntermittentScenario, load_scenario
from medlink.scheduling import SCHEDULER_ORDER
from medlink.simulation import build_capacity_trace, simulate_intermittent

LEGACY_BENCHMARK_PROJECT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    config_id: str
    run_count: int
    output_dir: Path
    summary: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "project_version": LEGACY_BENCHMARK_PROJECT_VERSION,
            "config_id": self.config_id,
            "run_count": self.run_count,
            "summary": list(self.summary),
        }


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark config must be a JSON object")
    if payload.get("schema_version") != "1.0":
        raise ValueError("benchmark schema_version must be '1.0'")
    return payload


def _number_list(payload: dict[str, Any], key: str) -> tuple[float, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty array")
    result = tuple(float(item) for item in value)
    if any(item <= 0 or not math.isfinite(item) for item in result):
        raise ValueError(f"{key} values must be finite and > 0")
    return result


def _base_workload(
    scenario: IntermittentScenario,
    *,
    seed: int,
    repetitions: int,
    spacing_s: float,
    jitter_s: float,
) -> tuple[MedicalData, ...]:
    if repetitions <= 0:
        raise ValueError("workload.repetitions must be > 0")
    if spacing_s < 0 or jitter_s < 0:
        raise ValueError("workload spacing and jitter must be >= 0")
    rng = random.Random(seed)
    generated: list[MedicalData] = []
    for repetition in range(repetitions):
        for original in scenario.medical_data:
            jitter = rng.uniform(0.0, jitter_s) if jitter_s else 0.0
            created = min(
                original.created_at_s + repetition * spacing_s + jitter,
                scenario.horizon_s - 1e-3,
            )
            generated.append(
                replace(
                    original,
                    id=f"{original.id}-r{repetition + 1}",
                    created_at_s=round(created, 6),
                )
            )
    return tuple(generated)


def _workload_for_factors(
    base: tuple[MedicalData, ...], load_factor: float, deadline_factor: float
) -> tuple[MedicalData, ...]:
    return tuple(
        replace(
            item,
            size_bytes=max(1, round(item.size_bytes * load_factor)),
            deadline_s=item.deadline_s * deadline_factor,
        )
        for item in base
    )


def _rf_presets(payload: dict[str, Any]) -> tuple[tuple[str, dict[str, float]], ...]:
    presets = payload.get("rf_presets")
    if not isinstance(presets, list) or not presets:
        raise ValueError("rf_presets must be a non-empty array")
    parsed: list[tuple[str, dict[str, float]]] = []
    for preset in presets:
        if not isinstance(preset, dict) or not isinstance(preset.get("id"), str):
            raise ValueError("each RF preset must have an id")
        overrides = preset.get("overrides")
        if not isinstance(overrides, dict):
            raise ValueError("each RF preset must have an overrides object")
        parsed.append((preset["id"], {key: float(value) for key, value in overrides.items()}))
    return tuple(parsed)


def _summary_rows(raw: pd.DataFrame) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for strategy in (item.value for item in SCHEDULER_ORDER):
        subset = raw[raw["scheduler"] == strategy]
        rows.append(
            {
                "strategy": strategy,
                "scenario_count": int(len(subset)),
                "mean_deadline_satisfaction_rate": float(
                    subset["deadline_satisfaction_rate"].mean()
                ),
                "mean_critical_deadline_satisfaction_rate": float(
                    subset["critical_deadline_satisfaction_rate"].mean()
                ),
                "mean_average_latency_s": float(subset["average_latency_s"].mean()),
                "mean_maximum_latency_s": float(subset["maximum_latency_s"].mean()),
                "mean_link_utilization": float(subset["link_utilization"].mean()),
                "total_delivered_count": int(subset["delivered_count"].sum()),
                "total_undelivered_count": int(subset["undelivered_count"].sum()),
                "total_deferred_count": int(subset["deferred_count"].sum()),
            }
        )
    return tuple(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_summary_markdown(path: Path, summary: pd.DataFrame) -> None:
    columns = [
        "strategy",
        "scenario_count",
        "mean_deadline_satisfaction_rate",
        "mean_critical_deadline_satisfaction_rate",
        "mean_average_latency_s",
        "mean_link_utilization",
        "total_delivered_count",
        "total_undelivered_count",
    ]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for record in summary[columns].to_dict(orient="records"):
        formatted: list[str] = []
        for column in columns:
            value = record[column]
            if column.startswith("mean_"):
                formatted.append(f"{float(value):.6f}")
            else:
                formatted.append(str(value))
        rows.append("| " + " | ".join(formatted) + " |")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _plot_summary(summary: pd.DataFrame, output_dir: Path) -> None:
    strategies = summary["strategy"].tolist()
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    bars = axis.bar(
        strategies, summary["mean_deadline_satisfaction_rate"], color="#2a6f97"
    )
    axis.bar_label(bars, fmt="%.3f", padding=3)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Mean deadline satisfaction rate")
    axis.set_title("Canonical benchmark: deadline satisfaction")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "deadline_satisfaction_by_scheduler.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    bars = axis.bar(strategies, summary["mean_average_latency_s"], color="#61a5c2")
    axis.bar_label(bars, fmt="%.0f", padding=3)
    axis.set_ylim(0, float(summary["mean_average_latency_s"].max()) * 1.15)
    axis.set_ylabel("Mean per-run average latency (s)")
    axis.set_title("Canonical benchmark: delivered-item latency")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "average_latency_by_scheduler.png", dpi=150)
    plt.close(fig)


def _publish(output_dir: Path, publish_dir: Path) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "summary.csv",
        "summary.json",
        "summary.md",
        "deadline_satisfaction_by_scheduler.png",
        "average_latency_by_scheduler.png",
    ):
        shutil.copy2(output_dir / name, publish_dir / name)


def run_benchmark(
    config_path: str | Path,
    output_dir: str | Path,
    publish_dir: str | Path | None = None,
) -> BenchmarkReport:
    """Run a deterministic benchmark matrix and write reproducible artifacts."""
    config_path = Path(config_path).resolve()
    config = _load_config(config_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    base_path = (config_path.parent / config["base_scenario"]).resolve()
    loaded = load_scenario(base_path)
    if not isinstance(loaded, IntermittentScenario):
        raise ValueError("benchmark base_scenario must use intermittent mode")
    seed = int(config["seed"])
    workload_config = config.get("workload", {})
    if not isinstance(workload_config, dict):
        raise ValueError("workload must be an object")
    base_items = _base_workload(
        loaded,
        seed=seed,
        repetitions=int(workload_config.get("repetitions", 1)),
        spacing_s=float(workload_config.get("arrival_spacing_s", 0.0)),
        jitter_s=float(workload_config.get("arrival_jitter_s", 0.0)),
    )
    load_factors = _number_list(config, "offered_load_factors")
    deadline_factors = _number_list(config, "deadline_factors")
    elevation_masks = _number_list(config, "minimum_elevation_degs")
    rf_presets = _rf_presets(config)

    records: list[dict[str, Any]] = []
    for load_factor in load_factors:
        for deadline_factor in deadline_factors:
            items = _workload_for_factors(base_items, load_factor, deadline_factor)
            for elevation_deg in elevation_masks:
                station = replace(loaded.ground_station, minimum_elevation_deg=elevation_deg)
                for rf_id, overrides in rf_presets:
                    rf_link = replace(loaded.rf_link, **overrides)
                    scenario = replace(
                        loaded,
                        medical_data=items,
                        ground_station=station,
                        rf_link=rf_link,
                    )
                    windows = find_contact_windows(
                        scenario.tle,
                        scenario.ground_station,
                        scenario.start_utc,
                        scenario.end_utc,
                    )
                    trace = build_capacity_trace(scenario, windows)
                    for strategy in SCHEDULER_ORDER:
                        report = simulate_intermittent(
                            scenario,
                            strategy,
                            capacity_trace=trace,
                            contact_windows=windows,
                        )
                        metrics = report.metrics
                        records.append(
                            {
                                "config_id": config["config_id"],
                                "project_version": LEGACY_BENCHMARK_PROJECT_VERSION,
                                "scheduler": strategy.value,
                                "seed": seed,
                                "time_step_s": scenario.time_step_s,
                                "offered_load_factor": load_factor,
                                "deadline_factor": deadline_factor,
                                "minimum_elevation_deg": elevation_deg,
                                "rf_preset": rf_id,
                                **metrics.to_dict(),
                            }
                        )

    raw = pd.DataFrame.from_records(records)
    raw.to_csv(output / "raw_results.csv", index=False, lineterminator="\n")
    summary_rows = _summary_rows(raw)
    summary = pd.DataFrame.from_records(summary_rows)
    summary.to_csv(output / "summary.csv", index=False, lineterminator="\n")
    summary_payload = {
        "schema_version": "1.0",
        "project_version": LEGACY_BENCHMARK_PROJECT_VERSION,
        "config_id": config["config_id"],
        "run_count": len(records),
        "seed": seed,
        "time_step_s": loaded.time_step_s,
        "summary": list(summary_rows),
    }
    _write_json(output / "summary.json", summary_payload)
    _write_summary_markdown(output / "summary.md", summary)
    _plot_summary(summary, output)
    _write_json(
        output / "run_metadata.json",
        {
            "schema_version": "1.0",
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "config_path": str(config_path),
            "variable_metadata": ["generated_at_utc", "config_path"],
        },
    )
    if publish_dir is not None:
        _publish(output, Path(publish_dir))
    return BenchmarkReport(config["config_id"], len(records), output, summary_rows)
