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
