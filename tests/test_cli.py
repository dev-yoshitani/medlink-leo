from __future__ import annotations

import json

from medlink.cli import main


def test_cli_simulate(capsys) -> None:
    exit_code = main(
        [
            "simulate",
            "--scenario",
            "examples/basic_scenario.json",
            "--strategy",
            "fifo",
        ]
    )
    assert exit_code == 0
    assert "strategy=fifo" in capsys.readouterr().out


def test_cli_compare(capsys) -> None:
    exit_code = main(["compare", "--scenario", "examples/basic_scenario.json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert (
        output.index("strategy=fifo")
        < output.index("strategy=priority")
        < output.index("strategy=edf")
    )


def test_cli_json_is_deterministic(capsys) -> None:
    args = ["compare", "--scenario", "examples/basic_scenario.json", "--json"]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert [item["strategy"] for item in payload["strategies"]] == ["fifo", "priority", "edf"]


def test_cli_end_to_end_scenario(capsys) -> None:
    args = [
        "simulate",
        "--scenario",
        "examples/end_to_end_scenario.json",
        "--strategy",
        "edf",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "intermittent"
    assert payload["contact_windows"]
    assert payload["metrics"]["available_capacity_bits"] > 0


def test_cli_route(capsys) -> None:
    args = [
        "route",
        "--scenario",
        "examples/contact_plan_medical_routing.json",
        "--strategy",
        "earliest-arrival",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "routing"
    assert payload["strategy"] == "earliest-arrival"
    assert payload["contact_plan"]["contact_count"] == 5
    assert payload["metrics"]["delivered_count"] == 3


def test_cli_route_compare_json_is_deterministic(capsys) -> None:
    args = [
        "route-compare",
        "--scenario",
        "examples/contact_plan_medical_routing.json",
        "--json",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert [entry["strategy"] for entry in payload["strategies"]] == [
        "next-contact",
        "earliest-arrival",
        "deadline-aware",
    ]


def test_cli_rejects_routing_scenario_for_scheduler_command(capsys) -> None:
    assert (
        main(
            [
                "compare",
                "--scenario",
                "examples/contact_plan_medical_routing.json",
            ]
        )
        == 2
    )
    assert "route-compare" in capsys.readouterr().err
