"""Synthetic circular orbits, RF integration, and resource-reserving game routing.

This is a game model on a spherical rotating Earth, not a TLE/SGP4 prediction.
Every displayed completion is integrated from the RF rates; no outcome bonuses.
"""

from __future__ import annotations

import math
from dataclasses import replace
from functools import lru_cache

import numpy as np

from medlink.link import RFLinkTemplate, calculate_link_budget

from .content import HORIZON, ORBIT_PLANS, SATELLITE_TYPES, STATIONS, STEP
from .models import Assignment, Contact, DailyPlan, Delivery, Facility, Parcel, Satellite

EARTH_RADIUS = 6_371_000.0
EARTH_MU = 3.986004418e14
EARTH_ROTATION = 2 * math.pi / 86164


@lru_cache(maxsize=192)
def _pair(satellite: Satellite, facility: Facility, event: str) -> tuple[Contact, ...]:
    station = STATIONS[facility.id]
    orbit = ORBIT_PLANS[satellite.orbit]
    kind = SATELLITE_TYPES[satellite.kind]
    inclination = math.radians(orbit["inclination"])
    # Calibrate the first orbit to pass Sapporo near 10 minutes into the shift.
    reference_lat = math.radians(STATIONS["gs-sapporo"]["lat"])
    reference_u = math.asin(math.sin(reference_lat) / math.sin(inclination))
    angular_rate = math.sqrt(EARTH_MU / (EARTH_RADIUS + orbit["altitude_km"] * 1000) ** 3)
    node = (
        math.radians(STATIONS["gs-sapporo"]["lon"])
        + EARTH_ROTATION * 600
        - math.atan2(math.cos(inclination) * math.sin(reference_u), math.cos(reference_u))
        + math.radians(orbit["node_offset"])
    )
    times = np.arange(STEP / 2, HORIZON, STEP, dtype=float)
    u = reference_u + angular_rate * (times - 600) + math.radians(orbit["phase_offset"])
    radius = EARTH_RADIUS + orbit["altitude_km"] * 1000
    x = radius * (math.cos(node) * np.cos(u) - math.sin(node) * np.sin(u) * math.cos(inclination))
    y = radius * (math.sin(node) * np.cos(u) + math.cos(node) * np.sin(u) * math.cos(inclination))
    z = radius * np.sin(u) * math.sin(inclination)
    theta = times * EARTH_ROTATION
    ecef = np.stack(
        (x * np.cos(theta) + y * np.sin(theta), -x * np.sin(theta) + y * np.cos(theta), z), axis=1
    )
    lat, lon = math.radians(station["lat"]), math.radians(station["lon"])
    normal = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    delta = ecef - normal * EARTH_RADIUS
    ranges = np.linalg.norm(delta, axis=1)
    elevations = np.degrees(np.arcsin(np.clip(delta @ normal / ranges, -1, 1)))
    template = RFLinkTemplate(
        frequency_hz=2_200_000_000,
        tx_power_dbm=kind["power"],
        tx_antenna_gain_dbi=2,
        rx_antenna_gain_dbi=22 + 2.5 * (facility.antenna - 1),
        system_losses_db=3 + (3 if event == "weather" else 0),
        noise_temperature_k=500,
        channel_bandwidth_hz=kind["bandwidth"],
        implementation_efficiency=0.035,
        required_snr_db=3,
    )
    groups: list[list[tuple[float, float, float, float]]] = []
    current: list[tuple[float, float, float, float]] = []
    for time, distance, elevation in zip(times, ranges, elevations, strict=True):
        if elevation >= 10:
            budget = calculate_link_budget(template.at_range(float(distance)))
            current.append(
                (
                    float(time - STEP / 2),
                    float(time + STEP / 2),
                    budget.effective_rate_bps,
                    float(distance),
                )
            )
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    delay = station["delay"] * 0.6 ** (facility.backhaul - 1)
    if event == "backhaul" and facility.id == "gs-sapporo":
        delay += 120
    return tuple(
        Contact(
            id=f"{satellite.id}:{facility.id}:{i}",
            satellite=satellite.id,
            station=facility.id,
            start=group[0][0],
            end=group[-1][1],
            delay=delay,
            receivers=facility.receivers,
            intervals=tuple(group),
        )
        for i, group in enumerate(groups)
        if not (event == "maintenance" and facility.id == "gs-sapporo" and i == 0)
    )


def build_contacts(
    satellites: tuple[Satellite, ...],
    facilities: tuple[Facility, ...],
    event: str = "",
    recovery: bool = False,
) -> tuple[Contact, ...]:
    if recovery:
        satellites = (replace(satellites[0], active=True, orbit="early"),)
        facilities = (replace(next(f for f in facilities if f.id == "gs-sapporo"), active=True),)
        event = ""
    return tuple(
        sorted(
            (
                contact
                for satellite in satellites
                if satellite.active
                for facility in facilities
                if facility.active
                for contact in _pair(satellite, facility, event)
            ),
            key=lambda c: (c.start, c.satellite, c.station, c.id),
        )
    )


def integrate(
    contact: Contact, size_bytes: int, earliest: float, latest: float | None = None
) -> tuple[float, float, float] | None:
    """Integrate a complete non-preemptive item in one contact/free resource gap."""
    needed = size_bytes * 8.0
    limit = min(contact.end, latest if latest is not None else contact.end)
    departure = None
    for start, end, rate, distance in contact.intervals:
        a, b = max(start, earliest), min(end, limit)
        if b <= a or rate <= 0:
            continue
        if departure is None:
            departure = a
        bits = (b - a) * rate
        if bits >= needed - 1e-6:
            completion = a + needed / rate
            return departure, completion, completion + distance / 299_792_458 + contact.delay
        needed -= bits
    return None


def _free_gaps(
    start: float, end: float, reservations: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    cursor = start
    gaps = []
    for a, b in sorted(reservations):
        if b <= cursor or a >= end:
            continue
        if a > cursor:
            gaps.append((cursor, min(a, end)))
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append((cursor, end))
    return gaps


def _candidate(
    item: Parcel, contact: Contact, reservations: dict[str, list[tuple[float, float]]]
) -> Delivery:
    best = None
    start = max(item.created, contact.start)
    if start >= contact.end:
        reason = "荷物の生成後にこの通信機会は残っていません。"
    elif integrate(contact, item.size_bytes, start) is None:
        reason = "この通信機会に荷物全体を収める容量がありません。"
    else:
        reason = "衛星の送信枠または地上局の受信枠が競合しています。"
        for receiver in range(contact.receivers):
            occupied = reservations.get(f"sat:{contact.satellite}", []) + reservations.get(
                f"gs:{contact.station}:{receiver}", []
            )
            for a, b in _free_gaps(start, contact.end, occupied):
                result = integrate(contact, item.size_bytes, a, b)
                if result is not None and result[2] <= HORIZON:
                    if best is None or result[2] < best[0][2]:
                        best = (result, receiver)
                    break
        if best:
            (departure, completion, arrival), receiver = best
            return Delivery(
                item.id,
                contact.id,
                contact.satellite,
                contact.station,
                departure,
                completion,
                arrival,
                item.due,
                arrival <= item.due + 1e-6,
                "期限内に到着"
                if arrival <= item.due + 1e-6
                else "容量は足りますが期限を過ぎます。",
                receiver,
            )
    return Delivery(
        item.id,
        contact.id,
        contact.satellite,
        contact.station,
        None,
        None,
        None,
        item.due,
        False,
        reason,
    )


def _reserve(result: Delivery, reservations: dict[str, list[tuple[float, float]]]) -> None:
    if result.departure is None or result.completion is None:
        return
    interval = (result.departure, result.completion)
    reservations.setdefault(f"sat:{result.satellite}", []).append(interval)
    reservations.setdefault(f"gs:{result.station}:{result.receiver}", []).append(interval)


def route_plan(
    items: tuple[Parcel, ...], contacts: tuple[Contact, ...], plan: DailyPlan
) -> tuple[Delivery, ...]:
    by_item = {item.id: item for item in items}
    by_contact = {contact.id: contact for contact in contacts}
    seen = set()
    results = []
    reservations: dict[str, list[tuple[float, float]]] = {}
    for assignment in plan.allocations:
        if (
            assignment.parcel not in by_item
            or assignment.contact not in by_contact
            or assignment.parcel in seen
        ):
            raise ValueError("荷物や通信枠の割り当てを確認してください。")
        seen.add(assignment.parcel)
        result = _candidate(
            by_item[assignment.parcel], by_contact[assignment.contact], reservations
        )
        results.append(result)
        _reserve(result, reservations)
    results.extend(
        Delivery(
            item.id,
            None,
            None,
            None,
            None,
            None,
            None,
            item.due,
            False,
            "通信枠が割り当てられていません。",
        )
        for item in items
        if item.id not in seen
    )
    return tuple(results)


def auto_plan(items: tuple[Parcel, ...], contacts: tuple[Contact, ...]) -> DailyPlan:
    allocations = []
    reservations: dict[str, list[tuple[float, float]]] = {}
    for item in sorted(items, key=lambda p: (p.due, p.size_bytes, p.id)):
        candidates = [_candidate(item, contact, reservations) for contact in contacts]
        feasible = [candidate for candidate in candidates if candidate.arrival is not None]
        if not feasible:
            continue
        selected = min(feasible, key=lambda r: (not r.on_time, r.arrival, r.contact))
        assert selected.contact is not None
        allocations.append(Assignment(item.id, selected.contact))
        _reserve(selected, reservations)
    return DailyPlan(tuple(allocations))


def remaining_capacity_mb(
    contacts: tuple[Contact, ...], deliveries: tuple[Delivery, ...]
) -> dict[str, float]:
    """Largest contiguous RF capacity left after the whole current plan.

    Satellite occupancy and each receiver lane apply across overlapping contacts.
    Generation time and deadline still need the normal item-specific prediction.
    """
    reservations: dict[str, list[tuple[float, float]]] = {}
    for delivery in deliveries:
        _reserve(delivery, reservations)
    capacities = {}
    for contact in contacts:
        largest = 0.0
        for receiver in range(contact.receivers):
            occupied = reservations.get(f"sat:{contact.satellite}", []) + reservations.get(
                f"gs:{contact.station}:{receiver}", []
            )
            for a, b in _free_gaps(contact.start, contact.end, occupied):
                bits = sum(
                    max(0.0, min(b, end) - max(a, start)) * rate
                    for start, end, rate, _ in contact.intervals
                )
                largest = max(largest, bits)
        capacities[contact.id] = largest / 8_000_000
    return capacities


def orbit_overlap(existing: tuple[Contact, ...], proposed: tuple[Contact, ...]) -> float:
    duration = sum(c.end - c.start for c in proposed)
    overlap = 0.0
    # Union overlapping existing windows so several ground sites do not double-count.
    union: list[list[float]] = []
    for start, end in sorted((c.start, c.end) for c in existing):
        if union and start <= union[-1][1]:
            union[-1][1] = max(union[-1][1], end)
        else:
            union.append([start, end])
    for contact in proposed:
        overlap += sum(max(0, min(contact.end, b) - max(contact.start, a)) for a, b in union)
    return overlap / duration if duration else 0.0
