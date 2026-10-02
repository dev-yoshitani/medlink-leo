"""Pure campaign commands, fixed daily offers, progression, and once-only settlement."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, replace

from .content import (
    CHAPTER_NAMES,
    CONTENT_VERSION,
    EVENTS,
    HORIZON,
    KIND_NAMES,
    ORBIT_PLANS,
    RESEARCH,
    SATELLITE_TYPES,
    STATIONS,
)
from .flight import auto_plan, build_contacts, integrate, route_plan
from .models import (
    Assignment,
    CampaignState,
    Contact,
    Contract,
    ContractResult,
    DailyPlan,
    DayBook,
    DayReport,
    Facility,
    GameError,
    Parcel,
    Satellite,
)


def _normal_upkeep(state: CampaignState) -> int:
    return sum(SATELLITE_TYPES[s.kind]["upkeep"] for s in state.satellites if s.active) + sum(
        10 + 5 * (f.antenna + f.backhaul - 2) + 10 * (f.receivers - 1)
        for f in state.facilities
        if f.active
    )


def _offer(
    day: int, kind: str, reference: Contact, rng: random.Random, recovery: bool = False
) -> Contract:
    capacity = reference.capacity_mb
    # Workload is relative to the unupgraded starter window, never current upgrades.
    count = {"regular": 2, "urgent": 2, "bulk": 1, "bundle": 4, "ongoing": 2, "special": 3}[kind]
    ratios = {
        "regular": 0.12,
        "urgent": 0.22,
        "bulk": 0.92,
        "bundle": 0.23,
        "ongoing": 0.18,
        "special": 0.28,
    }
    ratio = 0.07 if recovery else ratios[kind]
    created = 0.0
    due = float(HORIZON - 60)
    if kind in ("urgent", "bulk"):
        due = min(due, reference.end + reference.delay + 1)
    if kind == "urgent":
        created = reference.start + 70
    parcels = tuple(
        Parcel(
            f"d{day}-{kind}-{i}",
            max(10_000, round(capacity * ratio * rng.uniform(0.95, 1.05) * 1_000_000)),
            created + i * 20,
            due,
        )
        for i in range(count)
    )
    if recovery:
        parcels = tuple(replace(p, created=0, due=float(HORIZON - 60)) for p in parcels)
    return Contract(
        id=f"d{day}-{kind}",
        kind=kind,
        title="立て直しの定期便" if recovery else f"{KIND_NAMES[kind]}・第{day}便",
        parcels=parcels,
        target=count if kind != "special" else 2,
        payment={
            "regular": 35,
            "urgent": 65,
            "bulk": 120,
            "bundle": 40,
            "ongoing": 55,
            "special": 60,
        }[kind],
        bonus={
            "regular": 35,
            "urgent": 100,
            "bulk": 160,
            "bundle": 100,
            "ongoing": 100,
            "special": 150,
        }[kind],
        penalty=0 if kind == "regular" else 30,
        minimum_credit=50 if kind == "special" else 0,
        days_left=3 if kind == "ongoing" else 1,
    )


def begin_day(state: CampaignState, recovering: bool = False) -> CampaignState:
    if state.book is not None:
        return state
    rng = random.Random(f"{state.seed}:{state.day}:{CONTENT_VERSION}")
    recovery = state.credits < _normal_upkeep(state) or (recovering and state.credits < 100)
    if recovery:
        # Ownership and levels stay; paused assets can be restarted individually.
        state = replace(
            state,
            satellites=tuple(replace(s, active=i == 0) for i, s in enumerate(state.satellites)),
            facilities=tuple(replace(f, active=f.id == "gs-sapporo") for f in state.facilities),
        )
    event_data = ("", "穏やかな朝", "今日は特別な運用条件はありません。")
    if state.day > 3 and not recovery:
        event_data = EVENTS[(state.day + state.seed) % len(EVENTS)]
    event, title, body = event_data
    contacts = build_contacts(state.satellites, state.facilities, event, recovery)
    reference_contacts = build_contacts((Satellite(),), (Facility(),))
    reference = next(c for c in reference_contacts if c.capacity_mb > 0.2)
    kinds = ("regular", "urgent", "bulk", "bundle", "ongoing", "special")
    offers = tuple(
        _offer(state.day, kind, reference, rng, recovery and kind == "regular") for kind in kinds
    )
    if event == "demand":
        offers = tuple(
            replace(
                c,
                bonus=c.bonus + 100,
                target=3,
                parcels=(*c.parcels, replace(c.parcels[-1], id=f"d{state.day}-special-extra")),
            )
            if c.kind == "special"
            else c
            for c in offers
        )
    # A continuing contract has a fresh parcel id each day, with unchanged economics.
    ongoing = tuple(
        replace(
            c,
            parcels=tuple(
                replace(p, id=f"{c.id}:day{state.day}:{i}") for i, p in enumerate(c.parcels)
            ),
        )
        for c in state.ongoing
    )
    book = DayBook(
        state.day,
        CONTENT_VERSION,
        event,
        title,
        body,
        (*offers, *ongoing),
        contacts,
        recovery,
        0 if recovery else _normal_upkeep(state),
    )
    updated = replace(state, book=book, ongoing=ongoing, accepted=tuple(c.id for c in ongoing))
    return replace(updated, plan=auto_plan(parcels(updated), contacts))


def accepted_contracts(state: CampaignState) -> tuple[Contract, ...]:
    if state.book is None:
        return ()
    return tuple(c for c in state.book.offers if c.id in state.accepted)


def parcels(state: CampaignState) -> tuple[Parcel, ...]:
    return tuple(p for c in accepted_contracts(state) for p in c.parcels)


def contract_lock(state: CampaignState, contract: Contract) -> str:
    if state.book and state.book.recovery and contract.kind != "regular":
        return "復旧中は定期便を使います。"
    if state.credit < contract.minimum_credit:
        return f"信用{contract.minimum_credit}から受注できます。"
    if contract.kind == "ongoing" and (state.chapter < 3 or state.research[2] < 2):
        return "第3章・運用研究Lv.2で開放します。"
    return ""


def _planning(state: CampaignState) -> None:
    if state.report is not None:
        raise GameError("決算を確認し、翌日へ進んでください。")
    if state.book is None:
        raise GameError("朝の状況を読み込んでください。")


def accept(state: CampaignState, contract_id: str) -> CampaignState:
    _planning(state)
    assert state.book is not None
    if contract_id in state.accepted:
        return state
    contract = next((c for c in state.book.offers if c.id == contract_id), None)
    if contract is None:
        raise GameError("この依頼は今日の手帳にありません。")
    if reason := contract_lock(state, contract):
        raise GameError(reason)
    if len(state.accepted) >= 3 + state.research[2]:
        raise GameError("同時受注の上限です。運用研究で増やせます。")
    updated = replace(state, accepted=(*state.accepted, contract_id), comparisons=())
    return replace(updated, plan=auto_plan(parcels(updated), state.book.contacts))


def cancel(state: CampaignState, contract_id: str) -> CampaignState:
    _planning(state)
    assert state.book is not None
    if any(c.id == contract_id for c in state.ongoing):
        raise GameError("継続契約は今日の決算まで続きます。")
    updated = replace(
        state, accepted=tuple(c for c in state.accepted if c != contract_id), comparisons=()
    )
    ids = {p.id for p in parcels(updated)}
    return replace(
        updated, plan=DailyPlan(tuple(a for a in state.plan.allocations if a.parcel in ids))
    )


def set_plan(state: CampaignState, plan: DailyPlan) -> CampaignState:
    _planning(state)
    assert state.book is not None
    route_plan(parcels(state), state.book.contacts, plan)  # validate references and duplicates
    return replace(state, plan=plan)


def _canonical(value):
    # JSON restore may turn an integral float into an int (or vice versa).
    # Settlement identity must describe values, not their Python numeric spelling.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def preview_day(state: CampaignState, plan: DailyPlan | None = None) -> DayReport:
    if state.book is None:
        raise GameError("朝の状況を読み込んでください。")
    plan = state.plan if plan is None else plan
    deliveries = route_plan(parcels(state), state.book.contacts, plan)
    by_parcel = {d.parcel: d for d in deliveries}
    contracts = []
    for c in accepted_contracts(state):
        results = [by_parcel[p.id] for p in c.parcels]
        on_time = sum(r.on_time for r in results)
        delivered = sum(r.arrival is not None for r in results)
        success = on_time >= c.target
        contracts.append(
            ContractResult(
                c.id,
                c.title,
                c.kind,
                len(results),
                on_time,
                delivered,
                success,
                on_time * c.payment,
                c.bonus if success else 0,
                0 if success else c.penalty,
            )
        )
    revenue = sum(c.payment + c.bonus for c in contracts)
    penalty = sum(c.penalty for c in contracts)
    credit_change = max(-3, min(3, sum(1 if c.success else -1 for c in contracts)))
    signature = json.dumps(
        _canonical(
            {
                "day": state.day,
                "seed": state.seed,
                "book": asdict(state.book),
                "accepted": state.accepted,
                "plan": asdict(plan),
            }
        ),
        sort_keys=True,
    )
    report_id = f"day-{state.day}-{hashlib.sha256(signature.encode()).hexdigest()[:16]}"
    return DayReport(
        report_id,
        state.day,
        deliveries,
        tuple(contracts),
        revenue,
        state.book.upkeep,
        penalty,
        revenue - penalty - state.book.upkeep,
        credit_change,
        sum(c.success for c in contracts) * 3,
        len(deliveries),
        sum(d.on_time for d in deliveries),
        sum(d.arrival is not None for d in deliveries),
    )


def commit_day(state: CampaignState, plan: DailyPlan | None = None) -> CampaignState:
    _planning(state)
    assert state.book is not None
    if not state.accepted:
        raise GameError("依頼を1件以上選んでください。")
    plan = state.plan if plan is None else plan
    return replace(state, plan=plan, report=preview_day(state, plan))


def claim_day(state: CampaignState, settlement_id: str) -> CampaignState:
    if settlement_id in state.claimed:
        return state
    if state.report is None or state.report.id != settlement_id:
        raise GameError("受け取る決算を確認してください。")
    report = state.report
    result_by_id = {r.id: r for r in report.contracts}
    ongoing = []
    completed = 0
    for c in accepted_contracts(state):
        if c.kind != "ongoing":
            continue
        done = c.completed_days + int(result_by_id[c.id].success)
        if c.days_left > 1:
            ongoing.append(replace(c, days_left=c.days_left - 1, completed_days=done))
        elif done == 3:
            completed += 1
    return replace(
        state,
        credits=state.credits + report.profit,
        credit=max(0, min(100, state.credit + report.credit_change)),
        points=state.points + report.research_points,
        successes=state.successes + sum(c.success for c in report.contracts),
        dispatches=state.dispatches + 1,
        delivered=state.delivered + report.delivered,
        on_time=state.on_time + report.on_time,
        ongoing_completed=state.ongoing_completed + completed,
        ongoing=tuple(ongoing),
        claimed=(*state.claimed[-63:], report.id),
        history=(*state.history[-29:], report),
    )


def next_day(state: CampaignState) -> CampaignState:
    if state.report is None or state.report.id not in state.claimed:
        raise GameError("今日の報酬を受け取ってから翌日へ進んでください。")
    # Keep recovery until the explicitly advertised 100 C restart fund is earned.
    return begin_day(
        replace(
            state,
            day=state.day + 1,
            book=None,
            accepted=(),
            plan=DailyPlan(),
            comparisons=(),
            report=None,
        ),
        recovering=bool(state.book and state.book.recovery),
    )


def _investment(state: CampaignState, cost: int) -> None:
    if state.report and state.report.id not in state.claimed:
        raise GameError("今日の報酬を受け取ってください。")
    if state.report is None and state.accepted:
        raise GameError("依頼を選ぶ前か、決算を受け取った後に設備を変更できます。")
    if state.credits < cost:
        raise GameError(f"資金が足りません。必要額は{cost} Cです。")


def _refresh(state: CampaignState) -> CampaignState:
    if state.book is None or state.report is not None:
        return state
    recovery = state.credits < _normal_upkeep(state) or (
        state.book.recovery and state.credits < 100
    )
    contacts = build_contacts(state.satellites, state.facilities, state.book.event, recovery)
    return replace(
        state,
        book=replace(
            state.book,
            contacts=contacts,
            recovery=recovery,
            upkeep=0 if recovery else _normal_upkeep(state),
        ),
        plan=DailyPlan(),
        comparisons=(),
    )


def buy_satellite(state: CampaignState, kind: str, orbit: str) -> CampaignState:
    if kind not in SATELLITE_TYPES or orbit not in ORBIT_PLANS:
        raise GameError("衛星の機種と軌道プランを選んでください。")
    if state.chapter < 2 or (kind != "small" and state.chapter < 4):
        raise GameError("小型衛星は第2章、全機種は第4章で開放します。")
    if len(state.satellites) >= 6:
        raise GameError("衛星は最大6機です。")
    cost = SATELLITE_TYPES[kind]["cost"]
    _investment(state, cost)
    # Never recycle ids after a sale.
    serial = max(int(s.id.split("-")[-1]) for s in state.satellites) + 1
    return _refresh(
        replace(
            state,
            credits=state.credits - cost,
            satellites=(*state.satellites, Satellite(f"sat-{serial}", kind, orbit)),
        )
    )


def sell_satellite(state: CampaignState, satellite_id: str) -> CampaignState:
    _investment(state, 0)
    if satellite_id == state.satellites[0].id:
        raise GameError("立て直し用の基本衛星は残します。")
    satellite = next((s for s in state.satellites if s.id == satellite_id), None)
    if satellite is None:
        raise GameError("衛星が見つかりません。")
    return _refresh(
        replace(
            state,
            credits=state.credits + SATELLITE_TYPES[satellite.kind]["cost"] * 60 // 100,
            satellites=tuple(s for s in state.satellites if s.id != satellite_id),
        )
    )


def unlock_station(state: CampaignState, station_id: str) -> CampaignState:
    if station_id not in STATIONS or any(f.id == station_id for f in state.facilities):
        raise GameError("開放する拠点を確認してください。")
    settings = STATIONS[station_id]
    if state.chapter < settings["chapter"]:
        raise GameError(f"第{settings['chapter']}章で開放します。")
    _investment(state, settings["cost"])
    return _refresh(
        replace(
            state,
            credits=state.credits - settings["cost"],
            facilities=(*state.facilities, Facility(station_id)),
        )
    )


def upgrade_station(state: CampaignState, station_id: str, equipment: str) -> CampaignState:
    facility = next((f for f in state.facilities if f.id == station_id), None)
    if facility is None or equipment not in ("antenna", "backhaul", "receivers"):
        raise GameError("強化する設備を確認してください。")
    level = getattr(facility, equipment)
    limit = {
        "antenna": 5 if state.research[0] >= 3 else 3,
        "backhaul": 2 + state.research[1],
        "receivers": 1 + min(2, state.research[0]),
    }[equipment]
    if equipment == "receivers" and state.chapter < 3:
        raise GameError("受信設備の増設は第3章で開放します。")
    if level >= limit:
        raise GameError("研究を進めると強化の上限が上がります。")
    cost = 100 * level**2 if equipment != "receivers" else 300 * level
    _investment(state, cost)
    updated = replace(facility, **{equipment: level + 1})
    return _refresh(
        replace(
            state,
            credits=state.credits - cost,
            upgrade_count=state.upgrade_count + 1,
            facilities=tuple(updated if f.id == station_id else f for f in state.facilities),
        )
    )


def toggle_asset(state: CampaignState, asset_id: str) -> CampaignState:
    _investment(state, 0)
    if asset_id in ("gs-sapporo", state.satellites[0].id):
        raise GameError("基本衛星と札幌局は運営を続けます。")
    if any(s.id == asset_id for s in state.satellites):
        return _refresh(
            replace(
                state,
                satellites=tuple(
                    replace(s, active=not s.active) if s.id == asset_id else s
                    for s in state.satellites
                ),
            )
        )
    if any(f.id == asset_id for f in state.facilities):
        return _refresh(
            replace(
                state,
                facilities=tuple(
                    replace(f, active=not f.active) if f.id == asset_id else f
                    for f in state.facilities
                ),
            )
        )
    raise GameError("設備が見つかりません。")


def research(state: CampaignState, branch: str) -> CampaignState:
    if branch not in RESEARCH:
        raise GameError("研究を選んでください。")
    index = tuple(RESEARCH).index(branch)
    level = state.research[index]
    if level >= 3:
        raise GameError("この研究は完了しています。")
    cost, points = 80 * (level + 1), 3 * (level + 1)
    _investment(state, cost)
    if state.points < points:
        raise GameError(f"研究ポイントが足りません。必要数は{points}です。")
    levels = list(state.research)
    levels[index] += 1
    return _refresh(
        replace(
            state,
            credits=state.credits - cost,
            points=state.points - points,
            research=(levels[0], levels[1], levels[2]),
        )
    )


def chapter_goals(state: CampaignState) -> tuple[tuple[str, int, int], ...]:
    if state.chapter == 1:
        return (("契約達成", state.successes, 5), ("設備強化", state.upgrade_count, 1))
    if state.chapter == 2:
        return (
            ("衛星", len(state.satellites), 2),
            ("地上拠点", len(state.facilities), 2),
            ("期限内到着", state.on_time, 20),
        )
    if state.chapter == 3:
        return (
            ("地上拠点", len(state.facilities), 3),
            ("継続契約達成", state.ongoing_completed, 1),
            ("信用", state.credit, 60),
        )
    if state.chapter == 4:
        recent = state.history[-5:]
        total, on_time = sum(r.total for r in recent), sum(r.on_time for r in recent)
        return (
            ("衛星", len(state.satellites), 4),
            ("地上拠点", len(state.facilities), 6),
            ("記録した営業日", len(recent), 5),
            ("直近5日の配送対象", total, 20),
            ("直近5日の期限内到着率（%）", int(on_time * 100 / total) if total else 0, 90),
        )
    return (("累計の契約達成", state.successes, state.successes),)


def advance_chapter(state: CampaignState) -> CampaignState:
    if state.chapter >= 5 or any(value < goal for _, value, goal in chapter_goals(state)):
        raise GameError("章の目標を達成すると次へ進めます。")
    return replace(state, chapter=state.chapter + 1)


def _text(command: dict, key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str):
        raise GameError("操作の項目を確認してください。")
    return value


def apply_command(state: CampaignState, command: dict) -> CampaignState:
    """Optimistic revision + command identity protect retried UI actions."""
    command_id = command.get("id")
    if not isinstance(command_id, str) or not 1 <= len(command_id) <= 100:
        raise GameError("操作番号を確認してください。")
    if command_id in state.command_ids:
        return state
    if type(command.get("revision")) is not int or command["revision"] != state.revision:
        raise GameError("別の画面で進行が変わりました。最新のセーブを読み込んでください。")
    action = command.get("action")
    if action == "accept":
        updated = accept(state, _text(command, "contract"))
    elif action == "cancel":
        updated = cancel(state, _text(command, "contract"))
    elif action == "auto":
        _planning(state)
        assert state.book is not None
        updated = set_plan(state, auto_plan(parcels(state), state.book.contacts))
    elif action == "plan":
        allocations = command.get("allocations")
        if not isinstance(allocations, list) or len(allocations) > 100:
            raise GameError("配送計画を確認してください。")
        updated = set_plan(
            state, DailyPlan(tuple(Assignment(a["parcel"], a["contact"]) for a in allocations))
        )
    elif action == "compare_save":
        _planning(state)
        assert state.book is not None
        slot = command.get("slot")
        if type(slot) is not int or slot not in (0, 1):
            raise GameError("比較案は2つまでです。")
        comparisons = list(state.comparisons)
        while len(comparisons) <= slot:
            comparisons.append(DailyPlan())
        comparisons[slot] = state.plan
        updated = replace(state, comparisons=tuple(comparisons))
    elif action == "compare_load":
        slot = command.get("slot")
        if type(slot) is not int or not 0 <= slot < len(state.comparisons):
            raise GameError("保存した比較案を選んでください。")
        updated = set_plan(state, state.comparisons[slot])
    elif action == "commit":
        updated = commit_day(state)
    elif action == "claim":
        updated = claim_day(state, _text(command, "settlement"))
    elif action == "next":
        updated = next_day(state)
    elif action == "buy":
        updated = buy_satellite(state, _text(command, "kind"), _text(command, "orbit"))
    elif action == "sell":
        updated = sell_satellite(state, _text(command, "asset"))
    elif action == "unlock":
        updated = unlock_station(state, _text(command, "asset"))
    elif action == "upgrade":
        updated = upgrade_station(state, _text(command, "asset"), _text(command, "equipment"))
    elif action == "toggle":
        updated = toggle_asset(state, _text(command, "asset"))
    elif action == "research":
        updated = research(state, _text(command, "branch"))
    elif action == "chapter":
        updated = advance_chapter(state)
    elif action == "tutorial":
        if type(command.get("open")) is not bool:
            raise GameError("案内の設定を確認してください。")
        updated = replace(state, tutorial=command["open"])
    else:
        raise GameError("操作を確認してください。")
    return replace(
        updated, revision=state.revision + 1, command_ids=(*state.command_ids[-63:], command_id)
    )


def goal_title(state: CampaignState) -> str:
    return CHAPTER_NAMES[state.chapter - 1]


def guaranteed_regular_feasible(state: CampaignState) -> bool:
    """Used by recovery/content acceptance checks, rather than assuming a rescue succeeds."""
    assert state.book is not None
    regular = next(c for c in state.book.offers if c.kind == "regular")
    return all(
        any(integrate(c, p.size_bytes, p.created) is not None for c in state.book.contacts)
        for p in regular.parcels
    )
