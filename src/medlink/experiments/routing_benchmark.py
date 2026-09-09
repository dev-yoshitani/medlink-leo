"""Deterministic v1.1 contact-plan routing benchmark."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib import pyplot as plt

from medlink import __version__
from medlink.routing import ROUTING_STRATEGY_ORDER, build_contact_plan, route_scenario
from medlink.scenarios import RoutingGroundStation, RoutingScenario, load_scenario


@dataclass(frozen=True, slots=True)
class RoutingBenchmarkReport:
    config_id: str
    run_count: int
    output_dir: Path
    summary: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "project_version": __version__,
            "config_id": self.config_id,
            "run_count": self.run_count,
            "summary": list(self.summary),
        }


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("routing benchmark config must be a JSON object")
    if payload.get("schema_version") != "1.1":
        raise ValueError("routing benchmark schema_version must be '1.1'")
    if not isinstance(payload.get("config_id"), str) or not payload["config_id"].strip():
        raise ValueError("routing benchmark config_id must be non-empty")
    return payload


def _positive_factors(payload: dict[str, Any], key: str) -> tuple[float, ...]:
    values = payload.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"{key} must be a non-empty array")
    parsed = tuple(float(value) for value in values)
    if any(not math.isfinite(value) or value <= 0 for value in parsed):
        raise ValueError(f"{key} values must be finite and > 0")
    return parsed


def _workload(
    scenario: RoutingScenario,
    load_factor: float,
    deadline_factor: float,
):
    return tuple(
        replace(
            item,
            size_bytes=max(1, round(item.size_bytes * load_factor)),
            deadline_s=item.deadline_s * deadline_factor,
        )
        for item in scenario.medical_data
    )


def _stations(
    scenario: RoutingScenario,
    *,
    elevation_deg: float,
    rf_efficiency_factor: float,
    backhaul_factor: float,
) -> tuple[RoutingGroundStation, ...]:
    return tuple(
        replace(
            station,
            ground_station=replace(
                station.ground_station, minimum_elevation_deg=elevation_deg
            ),
            rf_link=replace(
                station.rf_link,
                implementation_efficiency=min(
                    1.0,
                    station.rf_link.implementation_efficiency * rf_efficiency_factor,
                ),
            ),
            backhaul_delay_s=station.backhaul_delay_s * backhaul_factor,
        )
        for station in scenario.ground_stations
    )


def _station_column(station_id: str) -> str:
    return "selected_" + station_id.replace("-", "_") + "_count"


def _summary_rows(
    raw: pd.DataFrame,
    station_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for strategy in ROUTING_STRATEGY_ORDER:
        subset = raw[raw["routing_strategy"] == strategy.value]
        row: dict[str, Any] = {
            "strategy": strategy.value,
            "scenario_count": int(len(subset)),
            "mean_deadline_satisfaction_rate": float(
                subset["deadline_satisfaction_rate"].mean()
            ),
            "mean_critical_deadline_satisfaction_rate": float(
                subset["critical_deadline_satisfaction_rate"].mean()
            ),
            "mean_delivery_ratio": float(subset["delivery_ratio"].mean()),
            "mean_end_to_end_latency_s": float(
                subset["average_end_to_end_latency_s"].mean()
            ),
            "mean_maximum_end_to_end_latency_s": float(
                subset["maximum_end_to_end_latency_s"].mean()
            ),
            "mean_contact_utilization": float(subset["contact_utilization"].mean()),
            "total_delivered_count": int(subset["delivered_count"].sum()),
            "total_failed_count": int(subset["failed_count"].sum()),
        }
        total_selected = row["total_delivered_count"]
        for station_id in station_ids:
            count_column = _station_column(station_id)
            count = int(subset[count_column].sum())
            row[count_column] = count
            row[count_column.replace("_count", "_share")] = (
                count / total_selected if total_selected else 0.0
            )
        rows.append(row)
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
        "mean_delivery_ratio",
        "mean_end_to_end_latency_s",
        "mean_contact_utilization",
        "total_delivered_count",
        "total_failed_count",
    ]
    rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for record in summary[columns].to_dict(orient="records"):
        cells = []
        for column in columns:
            value = record[column]
            cells.append(f"{float(value):.6f}" if column.startswith("mean_") else str(value))
        rows.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _plot_summary(
    summary: pd.DataFrame,
    output_dir: Path,
    station_ids: tuple[str, ...],
) -> None:
    strategies = summary["strategy"].tolist()
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    bars = axis.bar(
        strategies,
        summary["mean_deadline_satisfaction_rate"],
        color="#176b87",
    )
    axis.bar_label(bars, fmt="%.3f", padding=3)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Mean deadline satisfaction rate")
    axis.set_title("Routing benchmark: deadline satisfaction")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "deadline_satisfaction_by_routing_strategy.png", dpi=150)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    bars = axis.bar(
        strategies,
        summary["mean_end_to_end_latency_s"],
        color="#64a6bd",
    )
    axis.bar_label(bars, fmt="%.0f", padding=3)
    upper = float(summary["mean_end_to_end_latency_s"].max())
    axis.set_ylim(0, upper * 1.15 if upper else 1.0)
    axis.set_ylabel("Mean end-to-end latency (s)")
    axis.set_title("Routing benchmark: delivered-item latency")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "end_to_end_latency_by_routing_strategy.png", dpi=150)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    bottom = [0.0] * len(strategies)
    for station_id in station_ids:
        values = summary[_station_column(station_id)].tolist()
        axis.bar(strategies, values, bottom=bottom, label=station_id)
        bottom = [left + right for left, right in zip(bottom, values, strict=True)]
    axis.set_ylabel("Selected routes")
    axis.set_title("Routing benchmark: ground-station selection")
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "ground_station_selection_by_strategy.png", dpi=150)
    plt.close(figure)


def _publish(output_dir: Path, publish_dir: Path) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "summary.csv",
        "summary.json",
        "summary.md",
        "deadline_satisfaction_by_routing_strategy.png",
        "end_to_end_latency_by_routing_strategy.png",
        "ground_station_selection_by_strategy.png",
    ):
        shutil.copy2(output_dir / filename, publish_dir / filename)


def run_routing_benchmark(
    config_path: str | Path,
    output_dir: str | Path,
    publish_dir: str | Path | None = None,
) -> RoutingBenchmarkReport:
    """Run the v1.1 routing matrix and write deterministic evidence artifacts."""
    config_file = Path(config_path).resolve()
    config = _load_config(config_file)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    loaded = load_scenario((config_file.parent / config["base_scenario"]).resolve())
    if not isinstance(loaded, RoutingScenario):
        raise ValueError("routing benchmark base_scenario must use routing mode")

    load_factors = _positive_factors(config, "offered_load_factors")
    deadline_factors = _positive_factors(config, "deadline_factors")
    backhaul_factors = _positive_factors(config, "backhaul_factors")
    elevation_masks = _positive_factors(config, "minimum_elevation_degs")
    efficiency_factors = _positive_factors(config, "rf_efficiency_factors")
    station_ids = tuple(sorted(station.id for station in loaded.ground_stations))
    records: list[dict[str, Any]] = []

    for elevation_deg in elevation_masks:
        for efficiency_factor in efficiency_factors:
            plan_scenario = replace(
                loaded,
                ground_stations=_stations(
                    loaded,
                    elevation_deg=elevation_deg,
                    rf_efficiency_factor=efficiency_factor,
                    backhaul_factor=1.0,
                ),
            )
            contact_plan = build_contact_plan(plan_scenario)
            for backhaul_factor in backhaul_factors:
                stations = _stations(
                    loaded,
                    elevation_deg=elevation_deg,
                    rf_efficiency_factor=efficiency_factor,
                    backhaul_factor=backhaul_factor,
                )
                for load_factor in load_factors:
                    for deadline_factor in deadline_factors:
                        scenario = replace(
                            loaded,
                            ground_stations=stations,
                            medical_data=_workload(
                                loaded,
                                load_factor,
                                deadline_factor,
                            ),
                        )
                        for strategy in ROUTING_STRATEGY_ORDER:
                            report = route_scenario(
                                scenario,
                                strategy,
                                contact_plan=contact_plan,
                            )
                            metrics = report.metrics
                            row: dict[str, Any] = {
                                "config_id": config["config_id"],
                                "project_version": __version__,
                                "routing_strategy": strategy.value,
                                "scheduler": report.scheduling_strategy,
                                "time_step_s": scenario.time_step_s,
                                "offered_load_factor": load_factor,
                                "deadline_factor": deadline_factor,
                                "backhaul_factor": backhaul_factor,
                                "minimum_elevation_deg": elevation_deg,
                                "rf_efficiency_factor": efficiency_factor,
                                **{
                                    key: value
                                    for key, value in metrics.to_dict().items()
                                    if key not in {"ground_station_selection", "failure_counts"}
                                },
                            }
                            for station_id in station_ids:
                                row[_station_column(station_id)] = (
                                    metrics.ground_station_selection[station_id]
                                )
                            for reason, count in metrics.failure_counts.items():
                                row[f"failure_{reason.lower()}_count"] = count
                            records.append(row)

    raw = pd.DataFrame.from_records(records)
    raw.to_csv(output / "raw_results.csv", index=False, lineterminator="\n")
    summary_rows = _summary_rows(raw, station_ids)
    summary = pd.DataFrame.from_records(summary_rows)
    summary.to_csv(output / "summary.csv", index=False, lineterminator="\n")
    _write_json(
        output / "summary.json",
        {
            "schema_version": "1.1",
            "project_version": __version__,
            "config_id": config["config_id"],
            "run_count": len(records),
            "time_step_s": loaded.time_step_s,
            "factors": {
                "offered_load_factors": list(load_factors),
                "deadline_factors": list(deadline_factors),
                "backhaul_factors": list(backhaul_factors),
                "minimum_elevation_degs": list(elevation_masks),
                "rf_efficiency_factors": list(efficiency_factors),
            },
            "summary": list(summary_rows),
        },
    )
    _write_summary_markdown(output / "summary.md", summary)
    _plot_summary(summary, output, station_ids)
    _write_json(
        output / "run_metadata.json",
        {
            "schema_version": "1.1",
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "config_path": str(config_file),
            "variable_metadata": ["generated_at_utc", "config_path"],
        },
    )
    if publish_dir is not None:
        _publish(output, Path(publish_dir))
    return RoutingBenchmarkReport(
        config["config_id"], len(records), output, summary_rows
    )
