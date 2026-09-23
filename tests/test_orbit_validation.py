from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from medlink.experiments import orbit_validation

ROOT = Path(__file__).resolve().parents[1]


def test_independent_orbit_and_contacts_agree_without_network(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("validation must not use network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = orbit_validation.validate_orbit(ROOT / "examples/contact_plan_medical_routing.json")
    assert result["passed"], result["max_errors"]
    assert result["sample_count"] == 1441
    assert len(result["contacts"]) == 6
    assert all(row["contact_count"] > 0 for row in result["contacts"])


def test_validation_command_fails_closed_and_writes_failed_evidence(monkeypatch, tmp_path) -> None:
    output = tmp_path / "failed.json"
    monkeypatch.setattr(orbit_validation, "validate_orbit", lambda _: {"passed": False})
    monkeypatch.setattr(sys, "argv", ["validation", "--output", str(output)])
    with pytest.raises(SystemExit, match="exceeded"):
        orbit_validation.main()
    assert '"passed": false' in output.read_text()
