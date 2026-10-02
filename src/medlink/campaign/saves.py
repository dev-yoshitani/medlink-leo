"""Strict campaign restore and deterministic version-one migration."""

from __future__ import annotations

import json
import math
import types
from dataclasses import fields, is_dataclass
from typing import Any, Union, get_args, get_origin, get_type_hints

from medlink.game import load_save as load_legacy
from medlink.game import settle as settle_legacy

from .content import ORBIT_PLANS, SATELLITE_TYPES, STATIONS
from .models import CampaignState, Facility, GameError
from .service import accept, begin_day, preview_day

SAVE_LIMIT = 2_000_000


def _decode(expected: Any, value: Any) -> Any:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                return _decode(option, value)
            except (ValueError, TypeError):
                pass
        raise ValueError("セーブの型が一致しません。")
    if expected is type(None):
        if value is not None:
            raise ValueError("空の値を確認してください。")
        return None
    if origin is tuple:
        if not isinstance(value, (list, tuple)) or len(value) > 10_000:
            raise ValueError("セーブの一覧が正しくありません。")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(args[0], item) for item in value)
        if len(value) != len(args):
            raise ValueError("セーブの一覧の長さが正しくありません。")
        return tuple(_decode(kind, item) for kind, item in zip(args, value, strict=True))
    if isinstance(expected, type) and is_dataclass(expected):
        names = {f.name for f in fields(expected)}
        if not isinstance(value, dict) or set(value) != names:
            raise ValueError("セーブの項目が不足しているか不明な項目があります。")
        hints = get_type_hints(expected)
        return expected(**{key: _decode(hints[key], item) for key, item in value.items()})
    if expected is float:
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e18:
            raise ValueError("セーブの数値を確認してください。")
        return float(value)
    if expected in (int, bool, str):
        if type(value) is not expected:
            raise ValueError("セーブの型が一致しません。")
        if expected is int and abs(value) > 1_000_000_000:
            raise ValueError("セーブの数値が大きすぎます。")
        if expected is str and len(value) > 500:
            raise ValueError("セーブの文字列が長すぎます。")
        return value
    raise TypeError(f"unsupported save field {expected}")


def _unique(values) -> bool:
    return len(values) == len(set(values))


def validate(state: CampaignState) -> CampaignState:
    if (
        state.save_version != 2
        or not 1 <= state.chapter <= 5
        or state.day < 1
        or state.revision < 0
    ):
        raise ValueError("セーブの版・章・日数が正しくありません。")
    if (
        not 0 <= state.credit <= 100
        or any(
            v < 0
            for v in (
                state.points,
                state.successes,
                state.dispatches,
                state.delivered,
                state.on_time,
                state.upgrade_count,
                state.ongoing_completed,
            )
        )
        or state.on_time > state.delivered
        or any(not 0 <= r <= 3 for r in state.research)
    ):
        raise ValueError("セーブの実績・研究が正しくありません。")
    if not 1 <= len(state.satellites) <= 6 or not 1 <= len(state.facilities) <= 6:
        raise ValueError("衛星・拠点の数が正しくありません。")
    if not _unique([s.id for s in state.satellites]) or not _unique(
        [f.id for f in state.facilities]
    ):
        raise ValueError("衛星・拠点が重複しています。")
    for s in state.satellites:
        if (
            not s.id.startswith("sat-")
            or not s.id[4:].isdigit()
            or s.kind not in SATELLITE_TYPES
            or s.orbit not in ORBIT_PLANS
        ):
            raise ValueError("衛星が正しくありません。")
    for f in state.facilities:
        if (
            f.id not in STATIONS
            or not 1 <= f.antenna <= 5
            or not 1 <= f.backhaul <= 5
            or not 1 <= f.receivers <= 3
        ):
            raise ValueError("拠点の設備が正しくありません。")
    if not any(f.id == "gs-sapporo" for f in state.facilities):
        raise ValueError("札幌局がありません。")
    if len(state.history) > 30 or len(state.claimed) > 64 or len(state.command_ids) > 64:
        raise ValueError("保存履歴の上限を超えています。")
    if not _unique(state.claimed) or not _unique(state.command_ids) or len(state.comparisons) > 2:
        raise ValueError("保存履歴が重複しています。")
    if state.book is None:
        if state.report or state.accepted or state.plan.allocations:
            raise ValueError("当日の状況がありません。")
        return state
    if state.book.day != state.day or state.book.version < 1 or state.book.upkeep < 0:
        raise ValueError("営業日の状況が一致しません。")
    if not 6 <= len(state.book.offers) <= 12 or len(state.book.contacts) > 300:
        raise ValueError("依頼・通信枠の数が正しくありません。")
    offers = {c.id: c for c in state.book.offers}
    if (
        len(offers) != len(state.book.offers)
        or not _unique(state.accepted)
        or not set(state.accepted) <= set(offers)
    ):
        raise ValueError("受注した依頼が正しくありません。")
    # Continuing contracts also occur in today's offers. Validate both views,
    # but count today's parcels once, independently of dataclass equality.
    parcel_ids = [p.id for c in state.book.offers for p in c.parcels]
    for contract in (*state.book.offers, *state.ongoing):
        if (
            contract.kind not in ("regular", "urgent", "bulk", "bundle", "ongoing", "special")
            or not 1 <= contract.target <= len(contract.parcels) <= 8
            or min(contract.payment, contract.bonus, contract.penalty) < 0
            or not 1 <= contract.days_left <= 3
            or not 0 <= contract.completed_days <= 3
        ):
            raise ValueError("依頼の条件が正しくありません。")
        for p in contract.parcels:
            if not 1 <= p.size_bytes <= 1_000_000_000 or not 0 <= p.created < p.due <= 21600:
                raise ValueError("荷物の条件が正しくありません。")
    if not _unique(parcel_ids):
        raise ValueError("荷物が重複しています。")
    if not _unique([c.id for c in state.book.contacts]):
        raise ValueError("通信枠が重複しています。")
    for contact in state.book.contacts:
        if (
            (state.report is None and contact.satellite not in {s.id for s in state.satellites})
            or contact.station not in {f.id for f in state.facilities}
            or not 0 <= contact.start < contact.end <= 21600
            or contact.delay < 0
            or not 1 <= contact.receivers <= 3
            or not contact.intervals
        ):
            raise ValueError("通信枠が正しくありません。")
        last = contact.start
        for a, b, rate, distance in contact.intervals:
            if (
                a < last - 1e-6
                or not contact.start <= a < b <= contact.end
                or rate < 0
                or distance <= 0
            ):
                raise ValueError("通信容量の区間が正しくありません。")
            last = b
    from .flight import route_plan
    from .service import parcels

    for plan in (state.plan, *state.comparisons):
        route_plan(parcels(state), state.book.contacts, plan)
    if state.report is not None and preview_day(state) != state.report:
        raise ValueError("決算が保存した条件と一致しません。")
    if (
        state.report
        and state.report.id in state.claimed
        and not any(r == state.report for r in state.history)
    ):
        raise ValueError("受領済みの決算記録がありません。")
    return state


def migrate(payload: dict) -> CampaignState:
    legacy = load_legacy(payload)
    waiting = legacy.active is not None and not legacy.active.dispatched
    if legacy.active and legacy.active.dispatched:
        legacy = settle_legacy(legacy)
    facilities = tuple(Facility(f.id, f.antenna, f.backhaul) for f in legacy.stations if f.opened)
    state = begin_day(
        CampaignState(
            credits=legacy.credits,
            successes=legacy.successes,
            dispatches=legacy.dispatches,
            delivered=legacy.delivered,
            on_time=legacy.on_time,
            facilities=facilities,
            upgrade_count=sum(f.antenna + f.backhaul - 2 for f in facilities),
            migrated=True,
            tutorial=False,
        )
    )
    if waiting:
        state = accept(state, f"d{state.day}-regular")
    return state


def load_campaign(payload: str | dict) -> CampaignState:
    try:
        if isinstance(payload, str):
            if len(payload.encode("utf-8")) > SAVE_LIMIT:
                raise ValueError("セーブは2 MBまでです。")
            payload = json.loads(payload)
        if not isinstance(payload, dict) or type(payload.get("save_version")) is not int:
            raise ValueError("セーブ形式が正しくありません。")
        if payload["save_version"] == 1:
            return migrate(payload)
        if payload["save_version"] != 2:
            raise ValueError("対応していないセーブ形式です。")
        return begin_day(validate(_decode(CampaignState, payload)))
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise GameError(str(error)) from error
