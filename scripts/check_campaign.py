"""Generate earned campaign milestones and reproducible gameplay evidence.

No currency or completion counters are injected into the playthrough. Recovery
is a separately labeled fault fixture. Outputs belong to local verification only.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from medlink.campaign import CampaignState, apply_command, begin_day, load_campaign
from medlink.campaign.challenges import CATALOG, exercise, exercise_model
from medlink.campaign.content import STATIONS
from medlink.campaign.service import chapter_goals


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    state = begin_day(CampaignState())
    serial = 0
    trace = []
    milestones = {}

    def record(name):
        path = output / f"{name}.json"
        path.write_text(state.to_json(), encoding="utf-8")
        assert load_campaign(path.read_text(encoding="utf-8")) == state
        milestones[name] = {
            "day": state.day,
            "chapter": state.chapter,
            "credits": state.credits,
            "file": path.name,
        }

    def command(action, **fields):
        nonlocal state, serial
        serial += 1
        event = {
            "id": f"walkthrough-{serial}",
            "revision": state.revision,
            "action": action,
            **fields,
        }
        state = apply_command(state, event)
        assert apply_command(state, event) == state
        assert load_campaign(state.to_json()) == state

    record("new-campaign")
    for _ in range(100):
        if state.report:
            command("next")
        command("accept", contract=f"d{state.day}-regular")
        if not state.book.recovery:
            command("accept", contract=f"d{state.day}-bundle")
        if state.day <= 3:
            record(f"day-{state.day}-planned")
        command("commit")
        command("claim", settlement=state.report.id)
        trace.append(
            {
                "day": state.day,
                "chapter": state.chapter,
                "credits": state.credits,
                "on_time": state.report.on_time,
                "total": state.report.total,
                "profit": state.report.profit,
            }
        )
        if state.chapter == 1 and not state.upgrade_count and state.credits >= 100:
            command("upgrade", asset="gs-sapporo", equipment="antenna")
        if state.chapter >= 2:
            if len(state.satellites) < (4 if state.chapter >= 4 else 2) and state.credits >= 800:
                command(
                    "buy", kind="small", orbit=("relay", "wide", "early")[len(state.satellites) % 3]
                )
                if len(state.satellites) == 2:
                    record("second-satellite")
            candidates = [
                key
                for key in STATIONS
                if key not in {f.id for f in state.facilities}
                and STATIONS[key]["chapter"] <= state.chapter
            ]
            if candidates and state.credits >= STATIONS[candidates[0]]["cost"]:
                command("unlock", asset=candidates[0])
        if (
            state.chapter >= 3
            and state.research[2] < 2
            and state.points >= 3 * (state.research[2] + 1)
            and state.credits >= 80 * (state.research[2] + 1)
        ):
            command("research", branch="operations")
        if (
            state.chapter == 3
            and state.research[2] >= 2
            and not state.ongoing_completed
            and not state.ongoing
        ):
            command("next")
            command("accept", contract=f"d{state.day}-ongoing")
            command("commit")
            command("claim", settlement=state.report.id)
        if all(v >= goal for _, v, goal in chapter_goals(state)) and state.chapter < 5:
            if state.chapter == 4:
                record("final-chapter-ready")
            command("chapter")
            record(f"chapter-{state.chapter}")
        if state.chapter == 5:
            break
    assert state.chapter == 5
    command("next")
    record("endless-morning")
    # Deliberate insolvency is a fault injection, not an earned campaign result.
    recovery = begin_day(
        replace(
            state,
            credits=-150,
            book=None,
            accepted=(),
            report=None,
            plan=type(state.plan)(),
            comparisons=(),
        )
    )
    (output / "recovery-fault-fixture.json").write_text(recovery.to_json(), encoding="utf-8")
    cases = []
    for row in CATALOG:
        case = exercise(row[0])
        a, b = [exercise_model(row[0], p) for p in case["plans"]]
        assert (a["on_time"], a["score"]) != (b["on_time"], b["score"])
        cases.append(
            {
                "id": row[0],
                "title": row[2],
                "a": {"on_time": a["on_time"], "score": a["score"]},
                "b": {"on_time": b["on_time"], "score": b["score"]},
            }
        )
    result = {
        "scope": "local deterministic walkthrough, not human playtesting",
        "milestones": milestones,
        "trace": trace,
        "practice_cases": cases,
        "ending": {
            "chapter": state.chapter,
            "satellites": len(state.satellites),
            "facilities": len(state.facilities),
            "credit": state.credit,
        },
    }
    (output / "walkthrough-evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1] / "outputs" / "campaign-check")
    print(json.dumps({"days": len(result["trace"]), "ending": result["ending"]}))
