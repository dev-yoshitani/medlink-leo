# Implementation status

## Current Milestone

v0.4 — End-to-End Intermittent-Link Simulator

## Completed

- v0.1 through v0.3 checkpointed and verified.
- Dynamic link trace, pause/resume transfers, finite-horizon classification, and E2E scenario
  implemented.

## Verification

- `python -m pytest`: 62 passed.
- `python -m ruff check .`: passed.
- End-to-end CLI and scheduler comparison: passed.
- 1.0 s versus 0.5 s dynamic-capacity convergence: passed.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.
- Shannon capacity is named as an upper bound; effective rate uses explicit scenario efficiency.
- UTC-aware time only; frozen orbit fixture is evaluated near its epoch.
- Single-hop resumable transfer with no scheduler preemption; midpoint timestep is explicit.

## Known Limitations

- Benchmark and Web Demo are later milestones; protocol-level DTN remains out of scope.

## Git

- HEAD: fa5847d
- working tree: ready for v0.4 checkpoint

## Next

- Verify v0.4 and add reproducible benchmark experiments.
