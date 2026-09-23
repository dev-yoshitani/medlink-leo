from __future__ import annotations

import pandas as pd
import pytest

from medlink.experiments.routing_analysis import POLICIES, analyze


def evidence():
    condition = {
        "config_id": "toy",
        "scheduler": "edf",
        "time_step_s": 1,
        "offered_load_factor": 1,
        "deadline_factor": 1,
        "backhaul_factor": 1,
        "minimum_elevation_deg": 10,
        "rf_efficiency_factor": 1,
    }
    rows, items = [], []
    for policy, latencies in zip(POLICIES, ((10, 100), (8, 90), (8, None)), strict=True):
        delivered = sum(value is not None for value in latencies)
        rows.append(
            {
                **condition,
                "routing_strategy": policy,
                "total_items": 2,
                "delivered_count": delivered,
                "deadline_met_items": 1,
                "delivery_ratio": delivered / 2,
                "deadline_satisfaction_rate": 0.5,
            }
        )
        for i, value in enumerate(latencies):
            items.append(
                {
                    **condition,
                    "routing_strategy": policy,
                    "item_id": f"item-{i}",
                    "latency_s": value,
                    "delivered": value is not None,
                    "deadline_met": i == 0,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(items)


def test_matched_items_separate_censoring_from_speed() -> None:
    result = analyze(*evidence())
    row = result["paired"][2]
    assert row["baseline"] == "earliest-arrival"
    assert row["common_delivered_items"] == 1
    assert row["baseline_only_items"] == 1
    assert row["common_item_latency_delta_mean_s"] == 0
    assert row["delivery_delta_mean_pp"] == -50
    assert row["deadline_wins_ties_losses"] == [0, 1, 0]
    assert len(result["paired_factors"]) == 15


@pytest.mark.parametrize("fault", ["duplicate", "missing", "counts", "rate", "latency"])
def test_corrupt_or_unmatched_evidence_is_rejected(fault) -> None:
    raw, items = evidence()
    if fault == "duplicate":
        items = pd.concat([items, items.iloc[[0]]])
    elif fault == "missing":
        items = items.iloc[:-1]
    elif fault == "counts":
        raw.loc[0, "delivered_count"] = 1
    elif fault == "rate":
        raw.loc[0, "delivery_ratio"] = 0
    else:
        items.loc[0, "latency_s"] = float("nan")
    with pytest.raises(ValueError):
        analyze(raw, items)


def test_no_common_delivery_is_missing_not_zero_latency() -> None:
    raw, items = evidence()
    items["delivered"] = False
    items["deadline_met"] = False
    items["latency_s"] = float("nan")
    for column in (
        "delivered_count",
        "deadline_met_items",
        "delivery_ratio",
        "deadline_satisfaction_rate",
    ):
        raw[column] = 0
    result = analyze(raw, items)
    assert result["paired"][0]["common_item_latency_delta_mean_s"] is None
    assert result["paired"][0]["neither_delivered_items"] == 2
