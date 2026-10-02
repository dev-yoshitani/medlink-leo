"""Immutable campaign snapshots; delivery results and settlements are saved in full."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from medlink.game import GameError


@dataclass(frozen=True)
class Satellite:
    id: str = "sat-1"
    kind: str = "small"
    orbit: str = "early"
    active: bool = True


@dataclass(frozen=True)
class Facility:
    id: str = "gs-sapporo"
    antenna: int = 1
    backhaul: int = 1
    receivers: int = 1
    active: bool = True


@dataclass(frozen=True)
class Parcel:
    id: str
    size_bytes: int
    created: float
    due: float


@dataclass(frozen=True)
class Contract:
    id: str
    kind: str
    title: str
    parcels: tuple[Parcel, ...]
    target: int
    payment: int
    bonus: int
    penalty: int
    minimum_credit: int = 0
    days_left: int = 1
    completed_days: int = 0


@dataclass(frozen=True)
class Contact:
    id: str
    satellite: str
    station: str
    start: float
    end: float
    delay: float
    receivers: int
    # start, end, RF rate, range. This frozen input survives content changes.
    intervals: tuple[tuple[float, float, float, float], ...]

    @property
    def capacity_mb(self) -> float:
        return sum((b - a) * rate for a, b, rate, _ in self.intervals) / 8_000_000


@dataclass(frozen=True)
class Assignment:
    parcel: str
    contact: str


@dataclass(frozen=True)
class DailyPlan:
    allocations: tuple[Assignment, ...] = ()


@dataclass(frozen=True)
class DayBook:
    day: int
    version: int
    event: str
    event_title: str
    event_body: str
    offers: tuple[Contract, ...]
    contacts: tuple[Contact, ...]
    recovery: bool = False
    upkeep: int = 0


@dataclass(frozen=True)
class Delivery:
    parcel: str
    contact: str | None
    satellite: str | None
    station: str | None
    departure: float | None
    completion: float | None
    arrival: float | None
    due: float
    on_time: bool
    reason: str
    receiver: int | None = None


@dataclass(frozen=True)
class ContractResult:
    id: str
    title: str
    kind: str
    total: int
    on_time: int
    delivered: int
    success: bool
    payment: int
    bonus: int
    penalty: int


@dataclass(frozen=True)
class DayReport:
    id: str
    day: int
    deliveries: tuple[Delivery, ...]
    contracts: tuple[ContractResult, ...]
    revenue: int
    upkeep: int
    penalty: int
    profit: int
    credit_change: int
    research_points: int
    total: int
    on_time: int
    delivered: int
    source: str = "synthetic-circular-game-v1"


@dataclass(frozen=True)
class CampaignState:
    save_version: int = 2
    seed: int = 1701
    day: int = 1
    revision: int = 0
    chapter: int = 1
    credits: int = 500
    credit: int = 40
    points: int = 0
    successes: int = 0
    dispatches: int = 0
    delivered: int = 0
    on_time: int = 0
    upgrade_count: int = 0
    ongoing_completed: int = 0
    satellites: tuple[Satellite, ...] = (Satellite(),)
    facilities: tuple[Facility, ...] = (Facility(),)
    research: tuple[int, int, int] = (0, 0, 0)
    book: DayBook | None = None
    accepted: tuple[str, ...] = ()
    ongoing: tuple[Contract, ...] = ()
    plan: DailyPlan = field(default_factory=DailyPlan)
    comparisons: tuple[DailyPlan, ...] = ()
    report: DayReport | None = None
    claimed: tuple[str, ...] = ()
    history: tuple[DayReport, ...] = ()
    command_ids: tuple[str, ...] = ()
    migrated: bool = False
    tutorial: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )


__all__ = ["GameError", "CampaignState", "DailyPlan"]
