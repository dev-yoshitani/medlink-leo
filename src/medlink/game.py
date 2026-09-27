"""Offline campaign layered over the unchanged orbital/RF routing engine.

Credits and unlocks are game rules. Delivery, deadlines, and capacity always come
from ``route_scenario``. No clinical outcome or real operational result is scored.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from medlink.models import MedicalData, Priority
from medlink.routing import ContactPlan, RoutingReport, RoutingStrategy, route_scenario
from medlink.routing.contact_plan import build_contact_plan
from medlink.scenarios import RoutingScenario, load_scenario
from medlink.scheduling import Strategy

SAVE_VERSION = 1
MAX_LEVEL = 5
STATION_IDS = ("gs-seoul", "gs-sapporo", "gs-tokyo")
STATION_NAMES = {"gs-seoul": "ソウル", "gs-sapporo": "札幌", "gs-tokyo": "東京"}
UNLOCKS = {"gs-seoul": (2, 350), "gs-sapporo": (0, 0), "gs-tokyo": (5, 650)}
CHAPTERS = (
    (0, "小さな通信センター"),
    (2, "もうひとつの窓口"),
    (5, "三都市をつなぐ"),
    (10, "広域通信の担い手"),
)


class GameError(ValueError):
    """A rejected player command or unsupported save, safe to show in the UI."""


@dataclass(frozen=True)
class StationProgress:
    id: str
    opened: bool = False
    antenna: int = 1
    backhaul: int = 1


@dataclass(frozen=True)
class ActiveMission:
    contract_id: str
    cycle: int
    dispatched: bool = False
    strategy: str = "deadline-aware"
    scheduler: str = "edf"


@dataclass(frozen=True)
class MissionRecord:
    contract_id: str
    cycle: int
    success: bool
    delivered: int
    on_time: int
    total: int
    reward: int


@dataclass(frozen=True)
class GameState:
    credits: int = 150
    successes: int = 0
    dispatches: int = 0
    delivered: int = 0
    on_time: int = 0
    stations: tuple[StationProgress, ...] = (
        StationProgress("gs-seoul"),
        StationProgress("gs-sapporo", opened=True),
        StationProgress("gs-tokyo"),
    )
    active: ActiveMission | None = None
    history: tuple[MissionRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"save_version": SAVE_VERSION, **asdict(self)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)


@dataclass(frozen=True)
class Contract:
    id: str
    title: str
    client: str
    description: str
    tip: str
    required_successes: int
    target: int
    bounty: int
    # size in MB, created seconds, relative deadline seconds, simulation priority
    parcels: tuple[tuple[float, float, float, Priority], ...]
    data_type: str


CONTRACTS = (
    Contract(
        "morning", "朝の定期便", "遠隔診療所のデータ係",
        "小さなバイタル記録を2件、期限内に届けよう。最初の運用にも向いた依頼。",
        "通信を待つ時間も到着時間に含まれます。まずは札幌の窓口で試してみよう。",
        0, 2, 100,
        ((0.4, 0, 1000, Priority.NORMAL), (0.6, 60, 900, Priority.CRITICAL)),
        "synthetic_vital_sign_summary",
    ),
    Contract(
        "waveforms", "波形をまとめて", "観測記録の整理係",
        "3件の波形データを期限内に。送る順番と、残りの通信容量に気をつけよう。",
        "受信アンテナを強化すると、同じ通信機会に送れる量が増えます。",
        1, 3, 170,
        ((1.2, 0, 1100, Priority.LOW), (1.6, 90, 850, Priority.HIGH),
         (2.4, 150, 900, Priority.NORMAL)),
        "synthetic_waveform_segment",
    ),
    Contract(
        "images", "画像のまとまった便", "画像データの保管係",
        "大きな画像3件のうち2件を期限内に。アンテナと拠点の育成が力になる。",
        "地上局が増えても衛星の無線機は1台です。同時に複数へは送れません。",
        3, 2, 250,
        ((3.0, 0, 1100, Priority.HIGH), (4.0, 90, 950, Priority.NORMAL),
         (2.0, 150, 1000, Priority.LOW)),
        "synthetic_medical_image",
    ),
    Contract(
        "express", "短い期限の依頼", "通信連絡室",
        "4件のうち3件を期限内に。回線が速い拠点と、経路の選び方を使い分けよう。",
        "地上回線の強化は、受信したデータが病院へ届くまでの時間を短くします。",
        5, 3, 320,
        ((0.6, 0, 380, Priority.LOW), (0.7, 60, 360, Priority.CRITICAL),
         (1.0, 120, 320, Priority.HIGH), (1.4, 180, 280, Priority.NORMAL)),
        "synthetic_vital_sign_summary",
    ),
    Contract(
        "overnight", "ふたつの通信機会", "広域データセンター",
        "時間をあけて生まれる6件のうち5件を期限内に。後半の通信機会も使おう。",
        "最後の依頼まで見届けよう。再生は早送りや最後まで進める操作もできます。",
        10, 5, 450,
        ((2.4, 0, 1000, Priority.HIGH), (3.2, 90, 950, Priority.NORMAL),
         (1.2, 150, 1000, Priority.CRITICAL), (1.6, 4500, 2200, Priority.HIGH),
         (2.4, 4560, 2140, Priority.NORMAL), (1.0, 4620, 2080, Priority.LOW)),
        "synthetic_archive_batch",
    ),
)
CONTRACT_BY_ID = {contract.id: contract for contract in CONTRACTS}


def chapter(state: GameState) -> tuple[int, str]:
    index = max(i for i, (required, _) in enumerate(CHAPTERS) if state.successes >= required)
    return index + 1, CHAPTERS[index][1]


def upgrade_cost(level: int) -> int:
    return 100 * level * level


def _idle(state: GameState) -> None:
    if state.active is not None:
        raise GameError("受注中の依頼を終えるか取り下げてから、設備を変更してください。")


def accept_contract(state: GameState, contract_id: str) -> GameState:
    _idle(state)
    contract = CONTRACT_BY_ID.get(contract_id)
    if contract is None:
        raise GameError("その依頼は見つかりません。")
    if state.successes < contract.required_successes:
        raise GameError("運用実績を積むと、この依頼が開放されます。")
    return replace(state, active=ActiveMission(contract.id, state.dispatches))


def dispatch(state: GameState, strategy: str, scheduler: str) -> GameState:
    if state.active is None or state.active.dispatched:
        raise GameError("配送を始められる受注中の依頼がありません。")
    try:
        strategy = RoutingStrategy.parse(strategy).value
        scheduler = Strategy.parse(scheduler).value
    except ValueError as error:
        raise GameError("経路と送信順の選び方を確認してください。") from error
    return replace(
        state, active=replace(state.active, dispatched=True, strategy=strategy, scheduler=scheduler)
    )


def abandon(state: GameState) -> GameState:
    if state.active is None:
        raise GameError("受注中の依頼はありません。")
    if state.active.dispatched:
        raise GameError("配送開始後は結果を確認して、依頼を終えてください。")
    return replace(state, active=None)


def upgrade(state: GameState, station_id: str, equipment: str) -> GameState:
    _idle(state)
    station = next((item for item in state.stations if item.id == station_id), None)
    if station is None or not station.opened or equipment not in ("antenna", "backhaul"):
        raise GameError("開放済みの地上局と設備を選んでください。")
    level = getattr(station, equipment)
    if level >= MAX_LEVEL:
        raise GameError("この設備は最大レベルです。")
    cost = upgrade_cost(level)
    if state.credits < cost:
        raise GameError("資金が足りません。依頼を届けて資金を増やしましょう。")
    changed = replace(station, **{equipment: level + 1})
    return replace(
        state, credits=state.credits - cost,
        stations=tuple(changed if item.id == station_id else item for item in state.stations),
    )


def unlock_station(state: GameState, station_id: str) -> GameState:
    _idle(state)
    station = next((item for item in state.stations if item.id == station_id), None)
    if station is None or station.opened:
        raise GameError("未開放の地上局を選んでください。")
    required, cost = UNLOCKS[station_id]
    if state.successes < required:
        raise GameError(f"この地上局の開放には依頼達成{required}回が必要です。")
    if state.credits < cost:
        raise GameError("地上局の開放に必要な資金が足りません。")
    return replace(
        state, credits=state.credits - cost,
        stations=tuple(replace(item, opened=True) if item.id == station_id else item
                       for item in state.stations),
    )


@lru_cache(maxsize=1)
def _base_scenario() -> RoutingScenario:
    path = Path(__file__).resolve().parents[2] / "examples" / "contact_plan_medical_routing.json"
    scenario = load_scenario(path)
    if not isinstance(scenario, RoutingScenario):
        raise GameError("ゲームの基準シナリオを読み込めませんでした。")
    return scenario


def equipment_scenario(stations: tuple[StationProgress, ...]) -> RoutingScenario:
    """Apply game upgrades to actual RF gain/backhaul inputs, never report values."""
    base = _base_scenario()
    progress = {station.id: station for station in stations}
    configured = []
    for station in base.ground_stations:
        level = progress[station.id]
        if not level.opened:
            continue
        configured.append(replace(
            station,
            rf_link=replace(
                station.rf_link,
                rx_antenna_gain_dbi=station.rf_link.rx_antenna_gain_dbi + 2.5 * (level.antenna - 1),
            ),
            backhaul_delay_s=station.backhaul_delay_s * 0.6 ** (level.backhaul - 1),
        ))
    return replace(base, scenario_id="medlink-game-v1", ground_stations=tuple(configured))


@lru_cache(maxsize=64)
def campaign_contact_plan(stations: tuple[StationProgress, ...]) -> ContactPlan:
    return build_contact_plan(equipment_scenario(stations))


def mission_items(active: ActiveMission) -> tuple[MedicalData, ...]:
    contract = CONTRACT_BY_ID[active.contract_id]
    # Repeatable variations are deterministic and bounded; no wall-clock waiting.
    scale = 1.0 + (active.cycle % 4) * 0.04
    shift = (active.cycle % 3) * 10
    return tuple(
        MedicalData(
            id=f"{contract.id}-{i + 1:02}", data_type=contract.data_type,
            size_bytes=round(size * scale * 1_000_000), priority=priority,
            created_at_s=created + shift, deadline_s=deadline,
        )
        for i, (size, created, deadline, priority) in enumerate(contract.parcels)
    )


@lru_cache(maxsize=64)
def _mission_report(stations: tuple[StationProgress, ...], active: ActiveMission) -> RoutingReport:
    scenario = replace(equipment_scenario(stations), medical_data=mission_items(active))
    return route_scenario(
        scenario, active.strategy, scheduling_strategy=active.scheduler,
        contact_plan=campaign_contact_plan(stations),
    )


def mission_report(state: GameState) -> RoutingReport:
    if state.active is None or not state.active.dispatched:
        raise GameError("配送開始後に結果を確認できます。")
    return _mission_report(state.stations, state.active)


def settle(state: GameState) -> GameState:
    report = mission_report(state)
    assert state.active is not None
    contract = CONTRACT_BY_ID[state.active.contract_id]
    metrics = report.metrics
    success = metrics.deadline_met_items >= contract.target
    reward = (
        (20 if metrics.delivered_count else 0) + metrics.deadline_met_items * 50
        + (contract.bounty if success else 0)
    )
    record = MissionRecord(
        contract.id, state.active.cycle, success, metrics.delivered_count,
        metrics.deadline_met_items, metrics.total_items, reward,
    )
    return replace(
        state, credits=state.credits + reward, successes=state.successes + int(success),
        dispatches=state.dispatches + 1, delivered=state.delivered + metrics.delivered_count,
        on_time=state.on_time + metrics.deadline_met_items, active=None,
        history=(*state.history[-23:], record),
    )


def _integer(value: Any, name: str, minimum: int = 0, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise GameError(f"セーブの「{name}」が正しくありません。")
    return value


def load_save(payload: str | dict[str, Any]) -> GameState:
    """Validate an offline, per-browser save before replacing the current campaign."""
    if isinstance(payload, str):
        if len(payload) > 200_000:
            raise GameError("セーブファイルが大きすぎます。")
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError) as error:
            raise GameError("セーブファイルを読み込めませんでした。") from error
    if (not isinstance(payload, dict) or type(payload.get("save_version")) is not int
            or payload["save_version"] != SAVE_VERSION):
        raise GameError("対応していないセーブ形式です。")
    try:
        values = {key: _integer(payload[key], key) for key in (
            "credits", "successes", "dispatches", "delivered", "on_time"
        )}
        if values["successes"] > values["dispatches"] or values["on_time"] > values["delivered"]:
            raise GameError("セーブの実績が正しくありません。")
        stations_data = payload["stations"]
        if not isinstance(stations_data, (list, tuple)) or len(stations_data) != 3:
            raise GameError("セーブの地上局が正しくありません。")
        stations = []
        for data in stations_data:
            if not isinstance(data, dict) or data["id"] not in STATION_IDS:
                raise GameError("セーブに不明な地上局があります。")
            if type(data["opened"]) is not bool:
                raise GameError("セーブの地上局の開放状態が正しくありません。")
            required, _ = UNLOCKS[data["id"]]
            if data["opened"] and values["successes"] < required:
                raise GameError("地上局と運用実績が一致しません。")
            stations.append(StationProgress(
                data["id"], data["opened"],
                _integer(data["antenna"], "受信アンテナ", 1, MAX_LEVEL),
                _integer(data["backhaul"], "地上回線", 1, MAX_LEVEL),
            ))
        by_id = {station.id: station for station in stations}
        if len(by_id) != 3 or not by_id["gs-sapporo"].opened:
            raise GameError("セーブの地上局の構成が正しくありません。")
        active = None
        data = payload.get("active")
        if data is not None:
            if not isinstance(data, dict) or data["contract_id"] not in CONTRACT_BY_ID:
                raise GameError("セーブの受注中の依頼が正しくありません。")
            if type(data["dispatched"]) is not bool:
                raise GameError("セーブの配送状態が正しくありません。")
            if values["successes"] < CONTRACT_BY_ID[data["contract_id"]].required_successes:
                raise GameError("受注中の依頼と実績が一致しません。")
            cycle = _integer(data["cycle"], "依頼番号")
            if cycle != values["dispatches"]:
                raise GameError("受注中の依頼番号が一致しません。")
            active = ActiveMission(
                data["contract_id"], cycle, data["dispatched"],
                RoutingStrategy.parse(data["strategy"]).value,
                Strategy.parse(data["scheduler"]).value,
            )
        history_data = payload.get("history", [])
        if not isinstance(history_data, (list, tuple)) or len(history_data) > 24:
            raise GameError("セーブの運用記録が正しくありません。")
        history = []
        for data in history_data:
            if not isinstance(data, dict) or data["contract_id"] not in CONTRACT_BY_ID:
                raise GameError("セーブの運用記録に不明な依頼があります。")
            if type(data["success"]) is not bool:
                raise GameError("セーブの達成記録が正しくありません。")
            numbers = {key: _integer(data[key], key) for key in (
                "cycle", "delivered", "on_time", "total", "reward"
            )}
            if not numbers["on_time"] <= numbers["delivered"] <= numbers["total"]:
                raise GameError("セーブの配送記録が正しくありません。")
            history.append(MissionRecord(data["contract_id"], success=data["success"], **numbers))
        return GameState(
            **values, stations=tuple(by_id[id_] for id_ in STATION_IDS),
            active=active, history=tuple(history),
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, GameError):
            raise
        raise GameError("セーブファイルの項目を確認してください。") from error
