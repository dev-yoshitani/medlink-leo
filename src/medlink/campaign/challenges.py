"""Twelve fixed practice cases computed by the same RF and reservation engine.

Practice uses explicit synthetic starting equipment and never pays campaign money.
Cases are generated from geometric contacts, rather than prescribed outcomes.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from .flight import auto_plan, build_contacts, integrate, route_plan
from .models import Assignment, Contact, DailyPlan, Facility, GameError, Parcel, Satellite

CATALOG = (
    ("1-priority", 1, "大きな便か、急ぎの便か", "同じ通信枠で、収入と期限内件数を比べよう。"),
    ("1-late", 1, "後から届く荷物の枠", "生成される前の荷物のために、通信時間を残そう。"),
    ("1-batch", 1, "小さな荷物をまとめて", "大きな1件と小さな3件の送信順を比べよう。"),
    ("2-overlap", 2, "衛星の時間を補い合う", "朝の便と補完の便の到着時刻を比較しよう。"),
    ("2-backhaul", 2, "どの地上局に届けるか", "通過時刻と地上回線の両方が到着に効く。"),
    ("2-parallel", 2, "地上局を分けて使う", "2機の衛星を使っても、同じ受信設備は競合する。"),
    ("3-receiver", 3, "受信設備を使い切る", "受信設備2台と衛星2機を組み合わせよう。"),
    ("3-maintenance", 3, "点検の日の計画", "使えない最初の通信枠の代わりを早めに選ぼう。"),
    ("3-ongoing", 3, "継続便の枠を守る", "継続便と臨時の大容量便を両立できるか比べよう。"),
    ("4-weather", 4, "通信条件が悪い日", "高出力衛星の通信容量と小型衛星を比較しよう。"),
    ("4-wide", 4, "広域の便を使う", "通過時刻が違う衛星から、期限に合う便を選ぼう。"),
    (
        "4-network",
        4,
        "広域通信網の混雑",
        "同じ枠に集める計画と、通信網全体に分ける計画を比べよう。",
    ),
)


def _plan(items: tuple[Parcel, ...], contacts: tuple[Contact, ...], index: int = 0) -> DailyPlan:
    return DailyPlan(tuple(Assignment(p.id, contacts[index].id) for p in items))


def _timing_case(contacts: tuple[Contact, ...]) -> tuple[tuple[Parcel, ...], DailyPlan, DailyPlan]:
    pairs = [
        (a, b)
        for a in contacts
        for b in contacts
        if a.id != b.id and a.capacity_mb > 0.1 and b.capacity_mb > 0.1
    ]
    for a, b in pairs:
        size = round(min(a.capacity_mb, b.capacity_mb) * 0.25 * 1_000_000)
        first, second = integrate(a, size, 0), integrate(b, size, 0)
        if first and second and abs(first[2] - second[2]) > 30:
            due = min(21599.0, (first[2] + second[2]) / 2)
            items = (Parcel("choice", size, 0.0, due),)
            return items, _plan(items, (a,)), _plan(items, (b,))
    raise ValueError("practice case needs two distinct arrival opportunities")


@lru_cache(maxsize=12)
def exercise(exercise_id: str) -> dict:
    metadata = next((row for row in CATALOG if row[0] == exercise_id), None)
    if metadata is None:
        raise GameError("練習課題を選んでください。")
    _, chapter, title, body = metadata
    satellites: tuple[Satellite, ...] = (Satellite(),)
    facilities: tuple[Facility, ...] = (Facility(),)
    event = ""
    if chapter >= 2:
        satellites = (Satellite(), Satellite("sat-2", orbit="relay"))
    if exercise_id == "2-backhaul":
        facilities = (Facility(), Facility("gs-tokyo"))
    if exercise_id == "2-parallel":
        satellites = (Satellite(), Satellite("sat-2"))
        facilities = (Facility(), Facility("gs-tokyo"))
    if exercise_id == "3-receiver":
        satellites = (Satellite(), Satellite("sat-2"))
        facilities = (Facility(receivers=2),)
    if exercise_id == "3-maintenance":
        event = "maintenance"
    if exercise_id == "4-weather":
        satellites = (Satellite(), Satellite("sat-2", kind="power"))
        event = "weather"
    if exercise_id == "4-wide":
        satellites = (Satellite(), Satellite("sat-2", orbit="wide"))
    if exercise_id == "4-network":
        satellites = (
            Satellite(),
            Satellite("sat-2", orbit="relay"),
            Satellite("sat-3", orbit="wide"),
            Satellite("sat-4", kind="bulk"),
        )
        facilities = (Facility(), Facility("gs-tokyo"), Facility("gs-seoul"))
    contacts = build_contacts(satellites, facilities, event)
    positive = tuple(c for c in contacts if c.capacity_mb > 0.1)
    first = positive[0]
    if exercise_id in ("2-overlap", "2-backhaul", "3-maintenance", "4-wide"):
        items, a, b = _timing_case(positive)
    elif exercise_id in ("2-parallel", "3-receiver"):
        first = next(c for c in positive if c.satellite == "sat-1" and c.station == "gs-sapporo")
        second = next(
            c
            for c in positive
            if c.satellite == "sat-2"
            and c.station == ("gs-tokyo" if exercise_id == "2-parallel" else "gs-sapporo")
        )
        size = round(min(first.capacity_mb, second.capacity_mb) * 0.70 * 1_000_000)
        due = max(first.end + first.delay, second.end + second.delay) + 1
        items = (Parcel("one", size, 0.0, due), Parcel("two", size, 0.0, due))
        a = _plan(items, (first,))
        b = DailyPlan((Assignment("one", first.id), Assignment("two", second.id)))
    elif exercise_id == "4-weather":
        small = max((c for c in positive if c.satellite == "sat-1"), key=lambda c: c.capacity_mb)
        powerful = max((c for c in positive if c.satellite == "sat-2"), key=lambda c: c.capacity_mb)
        size = round((small.capacity_mb + powerful.capacity_mb) / 2 * 1_000_000)
        items = (Parcel("large", size, 0.0, 21599.0),)
        a, b = _plan(items, (small,)), _plan(items, (powerful,))
    elif exercise_id == "4-network":
        items = tuple(
            Parcel(f"packet-{i}", round(first.capacity_mb * 0.4 * 1_000_000), 0.0, 21599.0)
            for i in range(12)
        )
        a, b = _plan(items, (first,)), auto_plan(items, contacts)
    else:
        capacity = first.capacity_mb * 1_000_000
        due = first.end + first.delay + 1
        if exercise_id == "1-batch":
            items = (
                Parcel("large", round(capacity * 0.78), 0.0, due),
                *(Parcel(f"small-{i}", round(capacity * 0.35), 0.0, due) for i in range(3)),
            )
        elif exercise_id == "1-late":
            items = (
                Parcel("archive", round(capacity * 0.7), 0.0, due),
                Parcel("new", round(capacity * 0.5), first.start + 70, due),
            )
        else:
            items = (
                Parcel("large", round(capacity * 0.92), 0.0, due),
                Parcel("urgent-1", round(capacity * 0.22), first.start + 70, due),
                Parcel("urgent-2", round(capacity * 0.22), first.start + 90, due),
            )
        a = _plan(items, (first,))
        b = _plan((*items[1:], items[0]), (first,))
    return {
        "id": exercise_id,
        "chapter": chapter,
        "title": title,
        "body": body,
        "items": items,
        "contacts": contacts,
        "plans": (a, b),
    }


def exercise_model(exercise_id: str, plan: DailyPlan | None = None) -> dict:
    case = exercise(exercise_id)
    plan = plan if plan is not None else case["plans"][0]
    results = route_plan(case["items"], case["contacts"], plan)
    return {
        "id": case["id"],
        "title": case["title"],
        "body": case["body"],
        "parcels": [asdict(p) for p in case["items"]],
        "plan": asdict(plan),
        "contacts": [
            {
                "id": c.id,
                "satellite": c.satellite,
                "station": c.station,
                "start": c.start,
                "end": c.end,
                "capacity_mb": c.capacity_mb,
            }
            for c in case["contacts"]
        ],
        "deliveries": [asdict(d) for d in results],
        "on_time": sum(d.on_time for d in results),
        "total": len(results),
        "score": sum(
            (120 if d.parcel in ("large", "archive") else 60) for d in results if d.on_time
        ),
        "examples": [
            {"on_time": sum(d.on_time for d in route_plan(case["items"], case["contacts"], p))}
            for p in case["plans"]
        ],
    }


def daily_challenge(state) -> dict:
    chapter = min(4, state.chapter)
    choices = [row for row in CATALOG if row[1] == chapter]
    row = choices[(state.seed + state.day) % 3]
    return {"id": row[0], "title": row[2], "body": row[3]}
