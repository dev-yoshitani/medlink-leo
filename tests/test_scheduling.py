from __future__ import annotations

from medlink.models import MedicalData, Priority
from medlink.scheduling import select_edf, select_fifo, select_priority


def item(
    identifier: str,
    *,
    created: float = 0,
    deadline: float = 10,
    priority: Priority = Priority.NORMAL,
) -> MedicalData:
    return MedicalData(identifier, "synthetic", 1, priority, created, deadline)


def test_fifo_order_and_id_tie_break() -> None:
    items = [item("b"), item("a"), item("early", created=-0.0)]
    assert select_fifo(items, 0).id == "a"


def test_priority_order() -> None:
    items = [item("normal"), item("critical", priority=Priority.CRITICAL)]
    assert select_priority(items, 0).id == "critical"


def test_priority_tie_breaks_by_creation_then_id() -> None:
    items = [item("b"), item("a"), item("later", created=1)]
    assert select_priority(items, 1).id == "a"


def test_edf_order() -> None:
    items = [item("late", deadline=20), item("early", deadline=5)]
    assert select_edf(items, 0).id == "early"


def test_edf_tie_breaks_by_priority_creation_and_id() -> None:
    items = [
        item("normal", deadline=5),
        item("critical-b", deadline=5, priority=Priority.CRITICAL),
        item("critical-a", deadline=5, priority=Priority.CRITICAL),
    ]
    assert select_edf(items, 0).id == "critical-a"

