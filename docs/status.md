# Implementation status

## Current Milestone

v0.3 — TLE / SGP4 / Contact Windows

## Completed

- v0.1 and v0.2 checkpointed and verified.
- Frozen historical TLE, SGP4 propagation, reference station, and contact windows implemented.

## Verification

- `python -m pip install -e ".[dev]"`: passed in the project virtual environment.
- `python -m pytest`: 50 passed.
- `python -m ruff check .`: passed.
- Frozen TLE epoch, fixed propagation values, UTC handling, contact/no-contact, and range: passed.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.
- Shannon capacity is named as an upper bound; effective rate uses explicit scenario efficiency.
- UTC-aware time only; frozen orbit fixture is evaluated near its epoch.

## Known Limitations

- Intermittent transfer, benchmark, and Web Demo are later milestones.

## Git

- HEAD: 4a2255a
- working tree: ready for v0.3 checkpoint

## Next

- Verify v0.3 and integrate intermittent transfer simulation.
