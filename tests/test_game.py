from __future__ import annotations

from dataclasses import replace

import pytest

from medlink.game import (
    CONTRACTS,
    GameError,
    GameState,
    StationProgress,
    abandon,
    accept_contract,
    campaign_contact_plan,
    chapter,
    dispatch,
    equipment_scenario,
    load_save,
    mission_report,
    settle,
    unlock_station,
    upgrade,
)


def run_contract(state: GameState, name: str = "morning") -> GameState:
    return dispatch(accept_contract(state, name), "deadline-aware", "edf")


def test_delivery_rewards_and_save_survive_full_campaign_loop() -> None:
    state = GameState()
    before = state.to_json()
    state = run_contract(state)
    report = mission_report(state)
    assert report.metrics.deadline_met_items == 2
    assert all(result.selected_ground_station == "gs-sapporo" for result in report.results)
    restored = load_save(state.to_json())
    assert mission_report(restored).to_dict() == report.to_dict()
    settled = settle(restored)
    assert settled.credits > GameState().credits
    assert settled.successes == settled.dispatches == 1
    assert settled.delivered == settled.on_time == report.metrics.delivered_count
    assert settled.active is None
    assert load_save(settled.to_json()) == settled
    assert GameState().to_json() == before  # original state is immutable
    with pytest.raises(GameError):
        settle(settled)  # the same result cannot pay twice
    assert run_contract(settled).active.cycle == 1


def test_upgrades_change_engine_inputs_capacity_and_arrival() -> None:
    state = GameState(credits=1000)
    baseline_scenario = equipment_scenario(state.stations)
    baseline_plan = campaign_contact_plan(state.stations)
    antenna = upgrade(state, "gs-sapporo", "antenna")
    changed = equipment_scenario(antenna.stations)
    assert changed.ground_stations[0].rf_link.rx_antenna_gain_dbi > (
        baseline_scenario.ground_stations[0].rf_link.rx_antenna_gain_dbi
    )
    assert campaign_contact_plan(antenna.stations).total_available_capacity_bits > (
        baseline_plan.total_available_capacity_bits
    )
    backhaul = upgrade(state, "gs-sapporo", "backhaul")
    faster_scenario = equipment_scenario(backhaul.stations)
    assert faster_scenario.ground_stations[0].backhaul_delay_s == pytest.approx(27)
    original = mission_report(run_contract(state))
    faster = mission_report(run_contract(backhaul))
    for old, new in zip(original.results, faster.results, strict=True):
        assert old.selected_contact_id == new.selected_contact_id
        assert old.estimated_rf_completion_s == new.estimated_rf_completion_s
        assert old.estimated_arrival_s - new.estimated_arrival_s == pytest.approx(18)
    assert baseline_scenario.ground_stations[0].backhaul_delay_s == 45


def test_unlocks_and_contracts_follow_earned_progress() -> None:
    state = GameState()
    with pytest.raises(GameError):
        unlock_station(state, "gs-seoul")
    with pytest.raises(GameError):
        accept_contract(state, "images")
    for _ in range(2):
        state = settle(run_contract(state))
    assert chapter(state)[0] == 2
    state = unlock_station(state, "gs-seoul")
    assert len(equipment_scenario(state.stations).ground_stations) == 2
    assert all(contact.ground_station_id != "gs-tokyo"
               for contact in campaign_contact_plan(state.stations).contacts)
    for _ in range(4):
        state = settle(run_contract(state))
    state = unlock_station(state, "gs-tokyo")
    assert len(equipment_scenario(state.stations).ground_stations) == 3
    assert accept_contract(state, "express").active.contract_id == "express"
    assert load_save(state.to_json()) == state


def test_active_mission_freezes_equipment_and_rejects_invalid_commands() -> None:
    state = accept_contract(GameState(), "morning")
    with pytest.raises(GameError):
        accept_contract(state, "morning")
    with pytest.raises(GameError):
        upgrade(state, "gs-sapporo", "antenna")
    with pytest.raises(GameError):
        unlock_station(state, "gs-seoul")
    with pytest.raises(GameError):
        dispatch(state, "invented-strategy", "edf")
    assert abandon(state).active is None
    dispatched = dispatch(state, "next-contact", "fifo")
    with pytest.raises(GameError):
        dispatch(dispatched, "next-contact", "fifo")
    with pytest.raises(GameError):
        abandon(dispatched)


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda contract: contract.id)
def test_every_contract_is_achievable_with_developed_facilities(contract) -> None:
    state = GameState(
        credits=10000, successes=10, dispatches=10,
        stations=tuple(StationProgress(id_, True, 5, 5) for id_ in (
            "gs-seoul", "gs-sapporo", "gs-tokyo"
        )),
    )
    state = run_contract(state, contract.id)
    report = mission_report(state)
    assert report.metrics.deadline_met_items >= contract.target
    assert settle(state).successes == 11


def test_failed_delivery_has_real_results_and_can_be_followed_by_another_job() -> None:
    state = GameState(successes=10, dispatches=10)
    state = run_contract(state, "overnight")
    report = mission_report(state)
    assert report.metrics.failed_count > 0
    settled = settle(state)
    assert settled.credits >= state.credits
    assert settled.successes == state.successes
    assert settled.history[-1].delivered == report.metrics.delivered_count
    assert run_contract(settled).active is not None


def test_long_running_campaign_keeps_totals_after_recent_history_is_capped() -> None:
    state = GameState()
    for _ in range(30):
        state = settle(run_contract(state))
    assert state.successes == state.dispatches == 30
    assert state.on_time == state.delivered == 60
    assert len(state.history) == 24
    assert state.history[0].cycle == 6
    assert chapter(state)[0] == 4
    assert load_save(state.to_json()) == state


@pytest.mark.parametrize("change", [
    {"save_version": True}, {"save_version": 99}, {"credits": -1}, {"credits": True},
    {"successes": 3}, {"stations": []}, {"on_time": 1},
    {"active": {"contract_id": "unknown"}}, {"history": [None]},
])
def test_invalid_saves_do_not_replace_valid_progress(change) -> None:
    state = GameState()
    payload = {**state.to_dict(), **change}
    with pytest.raises(GameError):
        load_save(payload)
    assert state == GameState()


def test_save_rejects_duplicate_stations_bad_levels_and_unearned_unlock() -> None:
    payload = GameState().to_dict()
    for stations in (
        (StationProgress("gs-sapporo", True),) * 3,
        (StationProgress("gs-seoul", True), StationProgress("gs-sapporo", True),
         StationProgress("gs-tokyo")),
        (StationProgress("gs-seoul"), StationProgress("gs-sapporo", True, 6),
         StationProgress("gs-tokyo")),
    ):
        with pytest.raises(GameError):
            load_save(replace(GameState(), stations=stations).to_json())
    with pytest.raises(GameError):
        load_save("not json")
    assert load_save(payload) == GameState()


def test_maximum_level_and_affordability_do_not_spend_money() -> None:
    state = GameState(credits=0)
    with pytest.raises(GameError):
        upgrade(state, "gs-sapporo", "antenna")
    state = GameState(credits=10000)
    for _ in range(4):
        state = upgrade(state, "gs-sapporo", "antenna")
    with pytest.raises(GameError):
        upgrade(state, "gs-sapporo", "antenna")
    assert state.stations[1].antenna == 5
