# What the 216-run routing benchmark actually shows

The canonical grid is unchanged: 3 loads × 3 deadline factors × 2 backhaul factors ×
2 elevation masks × 2 RF-efficiency factors = 72 conditions, each with three policies.
EDF, workload IDs, frozen TLE, RF equations and the 1 s timestep remain fixed.

The original raw-results SHA-256 is still
`e97e43f7c1e28e1a4300a32698b773f134a7c980a19868cfc39e5d1cfbd8ad24`.
Original v1.0 and v1.1 published summaries have not been edited.

## Reproduce and inspect

```sh
python -m medlink routing-benchmark --config experiments/canonical_routing_benchmark.json --output-dir artifacts/routing-benchmark
python -m medlink.experiments.routing_analysis --input-dir artifacts/routing-benchmark --output-dir artifacts/routing-analysis
python scripts/check_evidence.py
```

- [Original run metrics](assets/routing-analysis/raw_results.csv)
- [New item-level records](assets/routing-analysis/item_results.csv)
- [Generated matched table](assets/routing-analysis/analysis.md)
- [Marginal factor results](assets/routing-analysis/factor_summary.csv)
- [Matched effects by factor](assets/routing-analysis/matched_factors.csv)
- [Every matched condition](assets/routing-analysis/matched_conditions.csv)
- [Overlap counts and latency spread](assets/routing-analysis/matched_summary.csv)
- [Analysis JSON and source hashes](assets/routing-analysis/analysis.json)

## Interpretation

All three policies have the same deadline-satisfaction rate **in every matched condition**.
Earliest Arrival and Next Contact deliver the same 216 condition/item pairs; Earliest Arrival
reduces their item-weighted mean latency by 17.659 s. The old difference of run-averaged means
is about 15.36 s because runs with different delivered counts receive equal weight there.
Both statistics are valid only with their weighting stated.

Deadline-Aware and Earliest Arrival share 196 delivered condition/item pairs. Their latency
difference is exactly zero for every shared pair in this matrix. Earliest Arrival delivers
20 additional late items; Deadline-Aware rejects them. Therefore the large difference between
their published overall mean latencies is **selection of delivered items**, not a measured
speed improvement on the same traffic. The delivery-ratio difference is -6.944 percentage
points, while the deadline-rate difference is zero.

The generated factor tables expose load, deadline, backhaul, elevation-mask and RF-efficiency
effects. Marginals average the other factors and can hide interactions: use the paired factor
table and individual matched conditions to inspect a specific engineering claim. No causal
effect beyond the deterministic simulator or random-sample uncertainty is inferred. There are
only four synthetic items per condition; this is a deliberately small engineering experiment.

For example, increasing the backhaul factor from 0.5 to 1.5 increases the condition-weighted
Earliest Arrival advantage over Next Contact from 8.809 s to 21.914 s, while deadline rates
remain unchanged. Under the lower RF-efficiency factor, Deadline-Aware's delivery penalty
relative to Earliest Arrival is 12.5 percentage points; under the higher factor it is 1.389.
Capacity and route timing interact with deadlines, so offered-load effects are not necessarily
monotone. These are descriptive contrasts within the published grid, not extrapolations.

Tests use a hand-computable toy example to detect the selection-bias mistake, reject missing
or duplicate matches and inconsistent counts/rates, and keep absent common-item latency as
null. CI regenerates the full 216 runs and compares numeric evidence at small floating-point
tolerances across Python/platform versions; local byte hashes record exact provenance.
