from __future__ import annotations

from dataclasses import replace

import pytest

from medlink.campaign import CampaignState, begin_day, claim_day, commit_day, load_campaign
from medlink.campaign.challenges import CATALOG, exercise, exercise_model
from medlink.campaign.content import STATIONS
from medlink.campaign.flight import (
    auto_plan,
    build_contacts,
    integrate,
    orbit_overlap,
    remaining_capacity_mb,
    route_plan,
)
from medlink.campaign.models import Assignment, Contact, DailyPlan, Facility, Parcel, Satellite
from medlink.campaign.service import (
    accept,
    advance_chapter,
    apply_command,
    buy_satellite,
    chapter_goals,
    next_day,
    parcels,
    preview_day,
    research,
    sell_satellite,
    toggle_asset,
    unlock_station,
    upgrade_station,
)
from medlink.game import GameError, GameState, accept_contract, dispatch, settle


def finish(state):
    state = commit_day(state)
    return claim_day(state, state.report.id)


def regular_day(state):
    state = accept(state, f"d{state.day}-regular")
    if not state.book.recovery:
        state = accept(state, f"d{state.day}-bundle")
    return finish(state)


def test_preview_commit_reload_claim_are_identical_and_once_only():
    state = accept(begin_day(CampaignState()), "d1-regular")
    preview = preview_day(state)
    committed = commit_day(state)
    assert committed.report == preview
    assert load_campaign(committed.to_json()) == committed
    paid = claim_day(committed, preview.id)
    assert paid.credits == 500 + preview.profit
    assert claim_day(paid, preview.id) == paid
    assert load_campaign(paid.to_json()) == paid
    assert next_day(paid).day == 2
    with pytest.raises(GameError):
        next_day(committed)


def test_resource_calendars_allow_parallel_satellites_but_not_double_receive():
    contact = Contact("a", "sat-1", "gs-sapporo", 0, 100, 0, 1, ((0, 100, 8, 1),))
    second = replace(contact, id="b", satellite="sat-2")
    items = (Parcel("x", 60, 0, 100), Parcel("y", 60, 0, 100))
    plan = DailyPlan((Assignment("x", "a"), Assignment("y", "b")))
    one = route_plan(items, (contact, second), plan)
    assert one[0].completion == 60
    assert one[1].arrival is None
    assert "競合" in one[1].reason
    two = route_plan(items, (replace(contact, receivers=2), replace(second, receivers=2)), plan)
    assert [d.completion for d in two] == [60, 60]
    assert two[0].receiver != two[1].receiver
    same_sat = replace(second, satellite="sat-1", station="gs-tokyo")
    assert route_plan(items, (contact, same_sat), plan)[1].arrival is None


def test_remaining_capacity_uses_satellite_and_receiver_reservations_across_contacts():
    c = Contact("a", "sat-1", "gs-sapporo", 0, 100, 0, 1, ((0, 100, 8_000_000, 1),))
    other_sat = replace(c, id="b", satellite="sat-2")
    same_sat_other_site = replace(c, id="c", station="gs-tokyo")
    result = route_plan(
        (Parcel("p", 60_000_000, 0, 100),), (c,), DailyPlan((Assignment("p", "a"),))
    )
    remaining = remaining_capacity_mb((c, other_sat, same_sat_other_site), result)
    assert remaining == {"a": 40, "b": 40, "c": 40}
    assert remaining_capacity_mb((replace(other_sat, receivers=2),), result)["b"] == 100
    fragmented = route_plan(
        (Parcel("one", 10_000_000, 10, 100), Parcel("two", 10_000_000, 40, 100)),
        (c,),
        DailyPlan((Assignment("one", "a"), Assignment("two", "a"))),
    )
    assert remaining_capacity_mb((c,), fragmented)["a"] == 50


def test_future_generation_capacity_deadline_and_free_gap_backfill():
    c = Contact("a", "sat-1", "gs-sapporo", 0, 100, 10, 1, ((0, 100, 8, 1),))
    items = (Parcel("late", 20, 60, 100), Parcel("early", 30, 0, 39), Parcel("big", 101, 0, 100))
    result = route_plan(items, (c,), DailyPlan(tuple(Assignment(p.id, "a") for p in items)))
    assert result[0].departure == 60
    assert result[1].departure == 0  # reserve around a future transfer, not globally serialize
    assert not result[1].on_time and result[1].arrival > 39
    assert "容量" in result[2].reason
    assert (
        route_plan((Parcel("after", 1, 101, 200),), (c,), DailyPlan((Assignment("after", "a"),)))[
            0
        ].arrival
        is None
    )


def test_real_rf_manual_choices_change_results_and_profit():
    state = accept(accept(begin_day(CampaignState()), "d1-bulk"), "d1-urgent")
    contact = state.book.contacts[0]
    bulk = next(p for p in parcels(state) if "bulk" in p.id)
    urgent = [p for p in parcels(state) if "urgent" in p.id]
    a = DailyPlan(tuple(Assignment(p.id, contact.id) for p in [bulk, *urgent]))
    b = DailyPlan(tuple(Assignment(p.id, contact.id) for p in [*urgent, bulk]))
    assert preview_day(state, a).profit != preview_day(state, b).profit
    assert preview_day(state, a).on_time != preview_day(state, b).on_time


def test_satellite_orbit_and_equipment_change_inputs_and_calculated_results():
    base = begin_day(CampaignState(chapter=4, credits=10000, research=(3, 3, 3)))
    gain = upgrade_station(base, "gs-sapporo", "antenna")
    assert sum(c.capacity_mb for c in gain.book.contacts) > sum(
        c.capacity_mb for c in base.book.contacts
    )
    faster = upgrade_station(base, "gs-sapporo", "backhaul")
    old = preview_day(accept(base, "d1-regular"))
    new = preview_day(accept(faster, "d1-regular"))
    for before, after in zip(old.deliveries, new.deliveries, strict=True):
        assert before.completion == after.completion
        assert before.arrival - after.arrival == pytest.approx(18)
    relay = buy_satellite(base, "small", "relay")
    assert len(relay.book.contacts) > len(base.book.contacts)
    early = build_contacts((Satellite("new", orbit="early"),), base.facilities)
    complementary = build_contacts((Satellite("new", orbit="relay"),), base.facilities)
    assert orbit_overlap(base.book.contacts, early) > orbit_overlap(
        base.book.contacts, complementary
    )
    assert [c.start for c in early] != [c.start for c in complementary]
    power = build_contacts((Satellite(kind="power"),), base.facilities)
    bulk = build_contacts((Satellite(kind="bulk"),), base.facilities)
    assert sum(c.capacity_mb for c in power) > sum(c.capacity_mb for c in base.book.contacts)
    assert sum(c.capacity_mb for c in bulk) > sum(c.capacity_mb for c in base.book.contacts)


@pytest.mark.parametrize("chapter", [1, 2, 3, 4, 5])
def test_recovery_is_feasible_in_every_chapter_without_losing_assets(chapter):
    state = begin_day(
        CampaignState(
            chapter=chapter,
            credits=-150,
            satellites=(Satellite(), Satellite("sat-2", "bulk", "wide")),
            facilities=(Facility(), Facility("gs-tokyo")),
        )
    )
    original_assets = (state.satellites, state.facilities)
    for _ in range(4):
        assert state.book.recovery
        assert state.book.upkeep == 0
        assert {c.satellite for c in state.book.contacts} == {"sat-1"}
        state = finish(accept(state, f"d{state.day}-regular"))
        assert state.report.on_time == 2
        if state.credits >= 100:
            break
        state = next_day(state)
    assert state.credits >= 100
    assert (state.satellites, state.facilities) == original_assets


def test_commands_reject_stale_revision_and_duplicate_id_is_idempotent():
    state = begin_day(CampaignState())
    command = {"id": "first", "revision": 0, "action": "accept", "contract": "d1-regular"}
    updated = apply_command(state, command)
    assert apply_command(updated, command) == updated
    with pytest.raises(GameError, match="進行"):
        apply_command(updated, {**command, "id": "second"})
    assert updated.revision == 1
    with pytest.raises(GameError):
        apply_command(updated, {"id": "third", "revision": 1, "action": "buy"})


def test_version_one_waiting_and_dispatched_migrate_without_reward_duplication():
    waiting = accept_contract(GameState(), "morning")
    assert load_campaign(waiting.to_json()).accepted == ("d1-regular",)
    dispatched = dispatch(waiting, "deadline-aware", "edf")
    expected = settle(dispatched)
    migrated = load_campaign(dispatched.to_json())
    assert migrated.credits == expected.credits
    assert migrated.successes == expected.successes
    assert migrated.delivered == expected.delivered
    assert migrated.migrated
    assert load_campaign(migrated.to_json()) == migrated
    assert load_campaign(dispatched.to_json()) == migrated


@pytest.mark.parametrize("mutation", ["bool", "nan", "reward", "duplicate", "version", "capacity"])
def test_invalid_save_never_loads(mutation):
    state = commit_day(accept(begin_day(CampaignState()), "d1-regular"))
    payload = state.to_dict()
    if mutation == "bool":
        payload["credits"] = True
    if mutation == "nan":
        payload["book"]["contacts"][0]["start"] = float("nan")
    if mutation == "reward":
        payload["report"]["revenue"] += 100
    if mutation == "duplicate":
        payload["satellites"] = (*payload["satellites"], *payload["satellites"])
    if mutation == "version":
        payload["save_version"] = 12
    if mutation == "capacity":
        payload["book"]["contacts"][0]["intervals"] = ((0.0, 10.0, -5.0, 10.0),)
    with pytest.raises(GameError):
        load_campaign(payload)


def test_daily_conditions_are_frozen_and_all_event_variants_change_inputs():
    state = begin_day(CampaignState(day=5))
    assert begin_day(state) == state
    assert load_campaign(state.to_json()) == state
    assert begin_day(CampaignState(day=5)) == state
    reference = build_contacts(state.satellites, state.facilities)
    maintenance = build_contacts(state.satellites, state.facilities, "maintenance")
    weather = build_contacts(state.satellites, state.facilities, "weather")
    backhaul = build_contacts(state.satellites, state.facilities, "backhaul")
    assert len(maintenance) == len(reference) - 1
    assert sum(c.capacity_mb for c in weather) < sum(c.capacity_mb for c in reference)
    assert backhaul[0].delay == reference[0].delay + 120


def test_asset_pause_sale_and_after_settlement_save_roundtrip():
    state = begin_day(CampaignState(chapter=4, credits=10000))
    state = buy_satellite(state, "small", "relay")
    paused = toggle_asset(state, "sat-2")
    assert paused.book.upkeep < state.book.upkeep
    assert all(c.satellite != "sat-2" for c in paused.book.contacts)
    state = finish(accept(state, "d1-regular"))
    sold = sell_satellite(state, "sat-2")
    assert sold.credits - state.credits == 480
    assert load_campaign(sold.to_json()) == sold
    with pytest.raises(GameError):
        sell_satellite(state, "sat-1")


def test_unmodified_new_campaign_can_reach_every_chapter_and_endless_play():
    """Earn every purchase; no injected currency, counters, credit, or successful results."""
    state = begin_day(CampaignState())
    trace = []
    for _ in range(100):
        if state.report:
            state = next_day(state)
        state = regular_day(state)
        trace.append((state.day, state.chapter, state.credits))
        if state.chapter == 1 and not state.upgrade_count and state.credits >= 100:
            state = upgrade_station(state, "gs-sapporo", "antenna")
        if state.chapter >= 2:
            if len(state.satellites) < (4 if state.chapter >= 4 else 2) and state.credits >= 800:
                state = buy_satellite(
                    state, "small", ("relay", "wide", "early")[len(state.satellites) % 3]
                )
            candidates = [
                key
                for key in STATIONS
                if key not in {f.id for f in state.facilities}
                and STATIONS[key]["chapter"] <= state.chapter
            ]
            if candidates and state.credits >= STATIONS[candidates[0]]["cost"]:
                state = unlock_station(state, candidates[0])
        if (
            state.chapter >= 3
            and state.research[2] < 2
            and state.points >= 3 * (state.research[2] + 1)
            and state.credits >= 80 * (state.research[2] + 1)
        ):
            state = research(state, "operations")
        if (
            state.chapter == 3
            and state.research[2] >= 2
            and not state.ongoing_completed
            and not state.ongoing
        ):
            state = next_day(state)
            state = accept(state, f"d{state.day}-ongoing")
            state = finish(state)
        if all(v >= goal for _, v, goal in chapter_goals(state)) and state.chapter < 5:
            state = advance_chapter(state)
        assert load_campaign(state.to_json()) == state
        if state.chapter == 5:
            break
    assert state.chapter == 5, trace
    assert len(state.satellites) >= 4 and len(state.facilities) == 6
    assert state.ongoing_completed >= 1 and state.credit >= 60
    assert next_day(state).chapter == 5


@pytest.mark.parametrize("case_id", [row[0] for row in CATALOG])
def test_fixed_challenges_have_explainable_different_choices(case_id):
    case = exercise(case_id)
    first = exercise_model(case_id, case["plans"][0])
    second = exercise_model(case_id, case["plans"][1])
    assert (first["on_time"], first["score"]) != (second["on_time"], second["score"])
    assert first["parcels"] == second["parcels"]
    assert first["contacts"] == second["contacts"]
    assert exercise_model(case_id, case["plans"][0]) == first


def test_each_chapter_has_three_fixed_cases():
    assert len({row[0] for row in CATALOG}) == 12
    assert all(sum(row[1] == chapter for row in CATALOG) == 3 for chapter in range(1, 5))


def test_continuing_contract_restores_on_each_morning_before_dispatch():
    state = begin_day(CampaignState(chapter=3, research=(0, 0, 2)))
    state = accept(state, "d1-ongoing")
    for day in range(1, 4):
        assert state.day == day
        assert load_campaign(state.to_json()) == state
        state = finish(state)
        assert load_campaign(state.to_json()) == state
        if day < 3:
            state = next_day(state)
            assert state.ongoing[0] in state.book.offers
            assert state.ongoing[0].id in state.accepted
    assert state.ongoing_completed == 1


def test_satellite_station_and_backhaul_investments_each_win_a_different_workload():
    """Compare actual RF arrivals under three alternative equipment investments."""
    base = build_contacts((Satellite(),), (Facility(),))
    options = {
        "satellite": build_contacts(
            (Satellite(), Satellite("sat-2", orbit="relay")), (Facility(),)
        ),
        "station": build_contacts((Satellite(),), (Facility(), Facility("gs-tokyo"))),
        "backhaul": build_contacts((Satellite(),), (Facility(backhaul=2),)),
    }
    # A new station reaches an early deadline before the first Sapporo pass.
    station_arrival = integrate(options["station"][0], 10_000, 0)[2]
    basic_arrival = integrate(options["backhaul"][0], 10_000, 0)[2]
    early = Parcel("early", 10_000, 0, (station_arrival + basic_arrival) / 2)
    # A complementary satellite reaches a generated item during the existing gap.
    gap = Parcel("gap", 10_000, base[0].end + 100, 4000)
    # After Tokyo's pass closes, faster ground forwarding resolves a tight deadline.
    created = options["station"][0].end + 20
    old = integrate(base[0], 10_000, created)[2]
    fast = integrate(options["backhaul"][0], 10_000, created)[2]
    tight = Parcel("tight", 10_000, created, (old + fast) / 2)
    for expected, item in (("station", early), ("satellite", gap), ("backhaul", tight)):
        result = {
            name: route_plan((item,), contacts, auto_plan((item,), contacts))[0].on_time
            for name, contacts in options.items()
        }
        assert result == {name: name == expected for name in options}
