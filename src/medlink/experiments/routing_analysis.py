"""Describe factorial routing results without confusing delivery selection with speed."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = [
    "offered_load_factor",
    "deadline_factor",
    "backhaul_factor",
    "minimum_elevation_deg",
    "rf_efficiency_factor",
]
CONDITION = ["config_id", "scheduler", "time_step_s", *FACTORS]
POLICIES = ["next-contact", "earliest-arrival", "deadline-aware"]


def analyze(raw: pd.DataFrame, items: pd.DataFrame) -> dict:
    if raw.empty or items.empty:
        raise ValueError("evidence must not be empty")
    for frame, keys in ((raw, CONDITION), (items, [*CONDITION, "item_id"])):
        if frame[[*keys, "routing_strategy"]].isna().any().any():
            raise ValueError("missing matching key")
        if frame.duplicated([*keys, "routing_strategy"]).any():
            raise ValueError("duplicate matched observation")
        groups = frame.groupby(keys, dropna=False)["routing_strategy"].agg(set)
        if not groups.map(lambda values: values == set(POLICIES)).all():
            raise ValueError("each condition/item requires all three policies")
    for column in ("delivered", "deadline_met"):
        if items[column].isna().any() or not items[column].isin([True, False]).all():
            raise ValueError("delivery flags must be boolean")
    if (items["deadline_met"] & ~items["delivered"]).any():
        raise ValueError("undelivered item cannot meet a deadline")
    delivered_latency = items.loc[items.delivered, "latency_s"]
    if not np.isfinite(delivered_latency).all() or (delivered_latency < 0).any():
        raise ValueError("delivered latency must be finite and nonnegative")
    if items.loc[~items.delivered, "latency_s"].notna().any():
        raise ValueError("failed item must not have a latency")
    keys = [*CONDITION, "routing_strategy"]
    counts = items.groupby(keys).agg(
        total_items=("item_id", "size"),
        delivered_count=("delivered", "sum"),
        deadline_met_items=("deadline_met", "sum"),
    )
    actual = raw.set_index(keys)[list(counts.columns)].sort_index()
    if not actual.equals(counts.sort_index().astype(actual.dtypes)):
        raise ValueError("run metrics do not agree with item evidence")
    for metric, numerator in (
        ("delivery_ratio", "delivered_count"),
        ("deadline_satisfaction_rate", "deadline_met_items"),
    ):
        expected = raw[numerator] / raw.total_items
        if not np.allclose(raw[metric], expected, rtol=0, atol=1e-12):
            raise ValueError("run rates do not agree with item evidence")
    factor_rows = []
    for factor in FACTORS:
        for (level, strategy), group in raw.groupby([factor, "routing_strategy"], sort=True):
            factor_rows.append(
                {
                    "factor": factor,
                    "level": float(level),
                    "strategy": strategy,
                    "n": len(group),
                    "deadline_rate": float(group.deadline_satisfaction_rate.mean()),
                    "delivery_ratio": float(group.delivery_ratio.mean()),
                }
            )
    paired_rows = []
    matched_conditions = []
    paired_factors = []
    for baseline, candidate in combinations(POLICIES, 2):
        runs = raw[raw.routing_strategy == baseline].merge(
            raw[raw.routing_strategy == candidate],
            on=CONDITION,
            suffixes=("_a", "_b"),
            validate="one_to_one",
        )
        pairs = items[items.routing_strategy == baseline].merge(
            items[items.routing_strategy == candidate],
            on=[*CONDITION, "item_id"],
            suffixes=("_a", "_b"),
            validate="one_to_one",
        )
        common = pairs[pairs.delivered_a & pairs.delivered_b].copy()
        common["delta_s"] = common.latency_s_b - common.latency_s_a
        deltas = runs.deadline_satisfaction_rate_b - runs.deadline_satisfaction_rate_a
        condition_means = common.groupby(CONDITION).delta_s.mean()
        runs["deadline_delta_pp"] = deltas * 100
        runs["delivery_delta_pp"] = (runs.delivery_ratio_b - runs.delivery_ratio_a) * 100
        runs = runs.join(condition_means.rename("common_latency_delta_s"), on=CONDITION)
        for record in runs[
            [*CONDITION, "deadline_delta_pp", "delivery_delta_pp", "common_latency_delta_s"]
        ].to_dict(orient="records"):
            matched_conditions.append({"baseline": baseline, "candidate": candidate, **record})
        for factor in FACTORS:
            for level, group in runs.groupby(factor):
                latency = group.common_latency_delta_s.dropna()
                paired_factors.append(
                    {
                        "baseline": baseline,
                        "candidate": candidate,
                        "factor": factor,
                        "level": float(level),
                        "matched_conditions": len(group),
                        "deadline_delta_mean_pp": float(group.deadline_delta_pp.mean()),
                        "delivery_delta_mean_pp": float(group.delivery_delta_pp.mean()),
                        "conditions_with_common_items": len(latency),
                        "condition_weighted_common_latency_delta_s": (
                            float(latency.mean()) if len(latency) else None
                        ),
                    }
                )
        paired_rows.append(
            {
                "baseline": baseline,
                "candidate": candidate,
                "matched_conditions": len(runs),
                "deadline_delta_mean_pp": float(deltas.mean() * 100),
                "deadline_wins_ties_losses": [
                    int((deltas > 1e-12).sum()),
                    int((deltas.abs() <= 1e-12).sum()),
                    int((deltas < -1e-12).sum()),
                ],
                "delivery_delta_mean_pp": float(
                    (runs.delivery_ratio_b - runs.delivery_ratio_a).mean() * 100
                ),
                "common_delivered_items": len(common),
                "baseline_only_items": int((pairs.delivered_a & ~pairs.delivered_b).sum()),
                "candidate_only_items": int((~pairs.delivered_a & pairs.delivered_b).sum()),
                "neither_delivered_items": int((~pairs.delivered_a & ~pairs.delivered_b).sum()),
                "common_item_latency_delta_mean_s": float(common.delta_s.mean())
                if len(common)
                else None,
                "common_item_latency_delta_median_s": float(common.delta_s.median())
                if len(common)
                else None,
                "common_item_latency_delta_min_s": float(common.delta_s.min())
                if len(common)
                else None,
                "common_item_latency_delta_max_s": float(common.delta_s.max())
                if len(common)
                else None,
                "conditions_with_common_items": len(condition_means),
                "condition_weighted_common_latency_delta_s": (
                    float(condition_means.mean()) if len(condition_means) else None
                ),
            }
        )
    return {
        "run_count": len(raw),
        "condition_count": len(raw) // len(POLICIES),
        "factors": factor_rows,
        "paired": paired_rows,
        "paired_factors": paired_factors,
        "matched_conditions": [
            {
                key: None if isinstance(value, float) and np.isnan(value) else value
                for key, value in row.items()
            }
            for row in matched_conditions
        ],
    }


def write_analysis(input_dir: Path, output_dir: Path) -> dict:
    raw_path, items_path = input_dir / "raw_results.csv", input_dir / "item_results.csv"
    report = analyze(pd.read_csv(raw_path), pd.read_csv(items_path))
    report["input_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (raw_path, items_path)
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    pd.DataFrame(report["factors"]).to_csv(output_dir / "factor_summary.csv", index=False)
    pd.DataFrame(report["paired"]).to_csv(output_dir / "matched_summary.csv", index=False)
    pd.DataFrame(report["paired_factors"]).to_csv(output_dir / "matched_factors.csv", index=False)
    pd.DataFrame(report["matched_conditions"]).to_csv(
        output_dir / "matched_conditions.csv", index=False
    )
    lines = [
        "# Generated matched routing analysis",
        "",
        "Deltas are candidate minus baseline. Negative latency means earlier delivery.",
        "Common-item latency includes only identical condition/item IDs "
        "delivered by both policies.",
        "These are deterministic scenario contrasts, not independent random trials; no p-values.",
        "",
        "| Baseline → candidate | Conditions | Deadline delta (pp) | Delivery delta (pp) | "
        "Common items | Common latency delta (s) | Baseline-only items |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["paired"]:
        delta = row["common_item_latency_delta_mean_s"]
        latency = "N/A" if delta is None else f"{delta:.6f}"
        lines.append(
            f"| {row['baseline']} → {row['candidate']} | {row['matched_conditions']} | "
            f"{row['deadline_delta_mean_pp']:.6f} | {row['delivery_delta_mean_pp']:.6f} | "
            f"{row['common_delivered_items']} | {latency} | {row['baseline_only_items']} |"
        )
    lines.extend(
        [
            "",
            "## Factor-stratified matched effects",
            "",
            "Each row averages the other factors. Latency here weights conditions equally.",
            "EA = Earliest Arrival; NC = Next Contact; DA = Deadline-Aware.",
            "",
            "| Factor | Level | Conditions | EA − NC common latency (s) | DA − EA delivery (pp) |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["paired_factors"]:
        if (row["baseline"], row["candidate"]) != ("next-contact", "earliest-arrival"):
            continue
        other = next(
            value
            for value in report["paired_factors"]
            if (value["baseline"], value["candidate"], value["factor"], value["level"])
            == ("earliest-arrival", "deadline-aware", row["factor"], row["level"])
        )
        delta = row["condition_weighted_common_latency_delta_s"]
        latency = "N/A" if delta is None else f"{delta:.6f}"
        lines.append(
            f"| {row['factor']} | {row['level']:g} | {row['matched_conditions']} | "
            f"{latency} | {other['delivery_delta_mean_pp']:.6f} |"
        )
    lines.extend(
        [
            "",
            "See factor_summary.csv for marginal factor levels (other factors averaged),",
            "matched_summary.csv for overlap counts and latency spread, "
            "and analysis.json for hashes.",
            "",
        ]
    )
    (output_dir / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_analysis(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
