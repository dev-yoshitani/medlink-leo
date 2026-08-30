# Implementation status

## Current Milestone

v0.1 — Medical Data Scheduling Core

## Completed

- Project package, scenario schema, schedulers, simulator, metrics, CLI, and synthetic example.

## Verification

- `python -m pip install -e ".[dev]"`: passed in the project virtual environment.
- `python -m pytest`: 26 passed.
- `python -m ruff check .`: passed.
- CLI simulate/compare and deterministic JSON: passed.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.

## Known Limitations

- Satellite orbit, link budget, intermittent contacts, benchmark, and Web Demo are later milestones.

## Git

- HEAD: pending first checkpoint
- working tree: ready for v0.1 checkpoint

## Next

- Implement v0.2 static satellite link budget.
