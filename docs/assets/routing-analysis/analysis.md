# Generated matched routing analysis

Deltas are candidate minus baseline. Negative latency means earlier delivery.
Common-item latency includes only identical condition/item IDs delivered by both policies.
These are deterministic scenario contrasts, not independent random trials; no p-values.

| Baseline → candidate | Conditions | Deadline delta (pp) | Delivery delta (pp) | Common items | Common latency delta (s) | Baseline-only items |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| next-contact → earliest-arrival | 72 | 0.000000 | 0.000000 | 216 | -17.658672 | 0 |
| next-contact → deadline-aware | 72 | 0.000000 | -6.944444 | 196 | -18.846428 | 20 |
| earliest-arrival → deadline-aware | 72 | 0.000000 | -6.944444 | 196 | 0.000000 | 20 |

## Factor-stratified matched effects

Each row averages the other factors. Latency here weights conditions equally.
EA = Earliest Arrival; NC = Next Contact; DA = Deadline-Aware.

| Factor | Level | Conditions | EA − NC common latency (s) | DA − EA delivery (pp) |
| --- | ---: | ---: | ---: | ---: |
| offered_load_factor | 0.75 | 24 | -31.455152 | -2.083333 |
| offered_load_factor | 1 | 24 | -8.340136 | -12.500000 |
| offered_load_factor | 1.25 | 24 | -6.290192 | -6.250000 |
| deadline_factor | 0.75 | 24 | -15.361827 | -8.333333 |
| deadline_factor | 1 | 24 | -15.361827 | -6.250000 |
| deadline_factor | 1.5 | 24 | -15.361827 | -6.250000 |
| backhaul_factor | 0.5 | 36 | -8.809496 | -6.944444 |
| backhaul_factor | 1.5 | 36 | -21.914158 | -6.944444 |
| minimum_elevation_deg | 10 | 36 | -21.567120 | -9.722222 |
| minimum_elevation_deg | 20 | 36 | -9.156534 | -4.166667 |
| rf_efficiency_factor | 0.75 | 36 | -5.308029 | -12.500000 |
| rf_efficiency_factor | 1.25 | 36 | -25.415625 | -1.388889 |

See factor_summary.csv for marginal factor levels (other factors averaged),
matched_summary.csv for overlap counts and latency spread, and analysis.json for hashes.
