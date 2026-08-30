# Implementation status

## Current Milestone

v0.5 — Reproducible Benchmark Experiments

## Completed

- v0.1 through v0.4 checkpointed and verified.
- Deterministic benchmark matrix, artifacts, summaries, plots, and methodology implemented.

## Verification

- `python -m pytest`: 65 passed.
- `python -m ruff check .`: passed.
- Canonical benchmark: 108 runs generated from code.
- Independent second run: raw CSV and all deterministic summaries matched SHA-256 hashes.
- Benchmark plots: rendered and visually inspected.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.
- Shannon capacity is named as an upper bound; effective rate uses explicit scenario efficiency.
- UTC-aware time only; frozen orbit fixture is evaluated near its epoch.
- Single-hop resumable transfer with no scheduler preemption; midpoint timestep is explicit.
- Benchmark jitter uses a recorded seed and shares each physical trace across schedulers.

## Known Limitations

- Web Demo is a later milestone; protocol-level DTN remains out of scope.

## Git

- HEAD: cf769eb
- working tree: ready for v0.5 checkpoint

## Next

- Verify and generate the canonical benchmark, then implement the Web Demo.
