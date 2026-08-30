"""Small, composable scheduler functions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum

from medlink.models import MedicalData

Scheduler = Callable[[Sequence[MedicalData], float], MedicalData]


class Strategy(StrEnum):
    FIFO = "fifo"
    PRIORITY = "priority"
    EDF = "edf"

    @classmethod
    def parse(cls, value: Strategy | str) -> Strategy:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).lower())
        except ValueError as error:
            choices = ", ".join(strategy.value for strategy in cls)
            raise ValueError(f"strategy must be one of: {choices}") from error


def _require_ready(items: Sequence[MedicalData], now_s: float) -> None:
    if not items:
        raise ValueError("scheduler requires at least one ready item")
    if any(item.created_at_s > now_s for item in items):
        raise ValueError("scheduler received an item that is not ready")


def select_fifo(items: Sequence[MedicalData], now_s: float) -> MedicalData:
    _require_ready(items, now_s)
    return min(items, key=lambda item: (item.created_at_s, item.id))


def select_priority(items: Sequence[MedicalData], now_s: float) -> MedicalData:
    _require_ready(items, now_s)
    return min(items, key=lambda item: (item.priority, item.created_at_s, item.id))


def select_edf(items: Sequence[MedicalData], now_s: float) -> MedicalData:
    _require_ready(items, now_s)
    return min(
        items,
        key=lambda item: (item.due_at_s, item.priority, item.created_at_s, item.id),
    )


_SCHEDULERS: dict[Strategy, Scheduler] = {
    Strategy.FIFO: select_fifo,
    Strategy.PRIORITY: select_priority,
    Strategy.EDF: select_edf,
}

SCHEDULER_ORDER: tuple[Strategy, ...] = (
    Strategy.FIFO,
    Strategy.PRIORITY,
    Strategy.EDF,
)


def get_scheduler(strategy: Strategy | str) -> Scheduler:
    return _SCHEDULERS[Strategy.parse(strategy)]

