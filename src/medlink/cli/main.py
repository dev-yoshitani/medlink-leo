"""Thin CLI adapter over MedLink-LEO's public Python functions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from medlink.experiments import run_benchmark, run_routing_benchmark
from medlink.routing import (
    RoutingComparisonReport,
    RoutingReport,
    RoutingStrategy,
    compare_routing_strategies,
    route_scenario,
)
from medlink.scenarios import RoutingScenario, load_scenario
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


def _format_routing(report: RoutingReport) -> str:
    metrics = report.metrics
    return (
        f"routing_strategy={report.strategy.value} "
        f"delivered={metrics.delivered_count}/{metrics.total_items} "
        f"deadline_rate={metrics.deadline_satisfaction_rate:.3f} "
        f"average_end_to_end_latency_s={metrics.average_end_to_end_latency_s:.3f} "
        f"contact_utilization={metrics.contact_utilization:.3f}\n"
    )


def _format_routing_comparison(report: RoutingComparisonReport) -> str:
    return "".join(_format_routing(strategy_report) for strategy_report in report.reports)


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

    route_parser = subparsers.add_parser(
        "route", help="route synthetic medical items over a generated contact plan"
    )
    route_parser.add_argument("--scenario", required=True)
    route_parser.add_argument(
        "--strategy", required=True, choices=[item.value for item in RoutingStrategy]
    )
    route_parser.add_argument("--json", action="store_true", dest="as_json")

    route_compare_parser = subparsers.add_parser(
        "route-compare", help="compare all contact-plan routing strategies"
    )
    route_compare_parser.add_argument("--scenario", required=True)
    route_compare_parser.add_argument("--json", action="store_true", dest="as_json")

    benchmark_parser = subparsers.add_parser("benchmark", help="run a benchmark matrix")
    benchmark_parser.add_argument("--config", required=True)
    benchmark_parser.add_argument("--output-dir", required=True)
    benchmark_parser.add_argument("--publish-dir")
    benchmark_parser.add_argument("--json", action="store_true", dest="as_json")

    routing_benchmark_parser = subparsers.add_parser(
        "routing-benchmark", help="run the contact-plan routing benchmark matrix"
    )
    routing_benchmark_parser.add_argument("--config", required=True)
    routing_benchmark_parser.add_argument("--output-dir", required=True)
    routing_benchmark_parser.add_argument("--publish-dir")
    routing_benchmark_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"benchmark", "routing-benchmark"}:
            benchmark = (
                run_benchmark(args.config, args.output_dir, args.publish_dir)
                if args.command == "benchmark"
                else run_routing_benchmark(args.config, args.output_dir, args.publish_dir)
            )
            output = (
                _json(benchmark.to_dict())
                if args.as_json
                else f"benchmark={benchmark.config_id} runs={benchmark.run_count} "
                f"output_dir={benchmark.output_dir}\n"
            )
            sys.stdout.write(output)
            return 0
        scenario = load_scenario(args.scenario)
        if args.command in {"route", "route-compare"}:
            if not isinstance(scenario, RoutingScenario):
                raise ValueError("route commands require a routing-mode scenario")
            if args.command == "route":
                routing_report = route_scenario(scenario, args.strategy)
                output = (
                    _json(routing_report.to_dict())
                    if args.as_json
                    else _format_routing(routing_report)
                )
            else:
                routing_comparison = compare_routing_strategies(scenario)
                output = (
                    _json(routing_comparison.to_dict())
                    if args.as_json
                    else _format_routing_comparison(routing_comparison)
                )
        elif args.command == "simulate":
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
