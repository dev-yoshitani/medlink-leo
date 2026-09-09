"""Shared deterministic orbit-to-capacity integration utilities."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from medlink.link import LinkBudgetResult, RFLinkTemplate, calculate_link_budget
from medlink.models import ensure_finite
from medlink.orbit import (
    ContactWindow,
    FrozenTLE,
    GroundStation,
    OrbitSample,
    find_contact_windows,
    propagate_orbit_many,
)
from medlink.orbit.models import require_utc


@dataclass(frozen=True, slots=True)
class CapacityInterval:
    """One midpoint-sampled interval with an optional RF link budget."""

    start_s: float
    end_s: float
    sample: OrbitSample
    link_budget: LinkBudgetResult | None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def effective_rate_bps(self) -> float:
        return self.link_budget.effective_rate_bps if self.link_budget is not None else 0.0

    @property
    def capacity_bits(self) -> float:
        return self.effective_rate_bps * self.duration_s


@dataclass(frozen=True, slots=True)
class CapacityTransferEstimate:
    """Capacity and completion estimate for a non-preemptive transfer."""

    departure_s: float | None
    completed_s: float | None
    transmission_time_s: float
    capacity_available_bits: float

    @property
    def feasible(self) -> bool:
        return self.completed_s is not None


def _boundaries(
    *,
    start_utc: datetime,
    end_utc: datetime,
    time_step_s: float,
    windows: tuple[ContactWindow, ...],
    extra_boundaries_s: Iterable[float],
) -> tuple[float, ...]:
    horizon_s = (end_utc - start_utc).total_seconds()
    values = {0.0, horizon_s}
    count = int(math.ceil(horizon_s / time_step_s))
    values.update(min(index * time_step_s, horizon_s) for index in range(1, count + 1))
    for value in extra_boundaries_s:
        checked = ensure_finite("extra boundary", value)
        if 0 <= checked <= horizon_s:
            values.add(checked)
    for window in windows:
        values.add(max(0.0, (window.start_utc - start_utc).total_seconds()))
        values.add(min(horizon_s, (window.end_utc - start_utc).total_seconds()))
    return tuple(sorted(values))


def build_station_capacity_trace(
    *,
    tle: FrozenTLE,
    ground_station: GroundStation,
    rf_link: RFLinkTemplate,
    start_utc: datetime,
    end_utc: datetime,
    time_step_s: float,
    contact_windows: tuple[ContactWindow, ...] | None = None,
    extra_boundaries_s: Iterable[float] = (),
    propagate_many: Callable[..., tuple[OrbitSample, ...]] | None = None,
) -> tuple[CapacityInterval, ...]:
    """Build a deterministic midpoint capacity trace for one station."""
    start = require_utc(start_utc, "start_utc")
    end = require_utc(end_utc, "end_utc")
    if end <= start:
        raise ValueError("end_utc must be after start_utc")
    step = ensure_finite("time_step_s", time_step_s)
    if step <= 0:
        raise ValueError("time_step_s must be > 0")
    windows = (
        contact_windows
        if contact_windows is not None
        else find_contact_windows(tle, ground_station, start, end)
    )
    boundaries = _boundaries(
        start_utc=start,
        end_utc=end,
        time_step_s=step,
        windows=windows,
        extra_boundaries_s=extra_boundaries_s,
    )
    pairs = tuple(zip(boundaries[:-1], boundaries[1:], strict=True))
    midpoints = [start + timedelta(seconds=(left + right) / 2.0) for left, right in pairs]
    propagator = propagate_many or propagate_orbit_many
    samples = propagator(tle, ground_station, midpoints)
    return tuple(
        CapacityInterval(
            left,
            right,
            sample,
            calculate_link_budget(rf_link.at_range(sample.range_m))
            if sample.in_contact
            else None,
        )
        for (left, right), sample in zip(pairs, samples, strict=True)
    )


def estimate_capacity_transfer(
    intervals: Iterable[CapacityInterval],
    *,
    earliest_start_s: float,
    required_bits: float,
) -> CapacityTransferEstimate:
    """Estimate a full transfer over the supplied intervals without mutating them."""
    earliest = ensure_finite("earliest_start_s", earliest_start_s)
    required = ensure_finite("required_bits", required_bits)
    if earliest < 0:
        raise ValueError("earliest_start_s must be >= 0")
    if required <= 0:
        raise ValueError("required_bits must be > 0")

    usable: list[tuple[CapacityInterval, float, float]] = []
    available = 0.0
    for interval in intervals:
        left = max(interval.start_s, earliest)
        right = interval.end_s
        rate = interval.effective_rate_bps
        if right <= left or rate <= 0:
            continue
        usable.append((interval, left, right))
        available += rate * (right - left)

    remaining = required
    departure: float | None = None
    transmission_time = 0.0
    for interval, left, right in usable:
        rate = interval.effective_rate_bps
        if departure is None:
            departure = left
        interval_bits = rate * (right - left)
        if remaining <= interval_bits + 1e-9:
            used_s = remaining / rate
            transmission_time += used_s
            return CapacityTransferEstimate(
                departure_s=departure,
                completed_s=left + used_s,
                transmission_time_s=transmission_time,
                capacity_available_bits=available,
            )
        remaining -= interval_bits
        transmission_time += right - left

    return CapacityTransferEstimate(
        departure_s=departure,
        completed_s=None,
        transmission_time_s=transmission_time,
        capacity_available_bits=available,
    )
