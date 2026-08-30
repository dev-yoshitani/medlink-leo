"""Thin CLI adapter over MedLink-LEO's public Python functions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from medlink.scenarios import load_scenario
from medlink.scheduling import Strategy
from medlink.simulation import ComparisonReport, SimulationReport, compare_strategies, simulate


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _format_metrics(report: SimulationReport) -> str:
    metrics = report.metrics
    critical = (
        "n/a"
        if metrics.critical_deadline_satisfaction_rate is None
        else f"{metrics.critical_deadline_satisfaction_rate:.3f}"
    )
    return (
        f"strategy={report.strategy.value} "
        f"completed={metrics.completed_items}/{metrics.total_items} "
        f"deadline_rate={metrics.deadline_satisfaction_rate:.3f} "
        f"critical_rate={critical} average_latency_s={metrics.average_latency_s:.3f} "
        f"utilization={metrics.link_utilization:.3f}"
    )


def _format_comparison(report: ComparisonReport) -> str:
    return "\n".join(_format_metrics(strategy_report) for strategy_report in report.reports) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medlink", description="MedLink-LEO simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate_parser = subparsers.add_parser("simulate", help="run one scheduling strategy")
    simulate_parser.add_argument("--scenario", required=True)
    simulate_parser.add_argument(
        "--strategy", required=True, choices=[item.value for item in Strategy]
    )
    simulate_parser.add_argument("--json", action="store_true", dest="as_json")

    compare_parser = subparsers.add_parser("compare", help="compare all scheduling strategies")
    compare_parser.add_argument("--scenario", required=True)
    compare_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        if args.command == "simulate":
            report = simulate(scenario, args.strategy)
            output = _json(report.to_dict()) if args.as_json else _format_metrics(report) + "\n"
        else:
            comparison = compare_strategies(scenario)
            output = _json(comparison.to_dict()) if args.as_json else _format_comparison(comparison)
        sys.stdout.write(output)
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
