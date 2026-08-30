# Implementation status

## Current Milestone

v0.2 — Static Satellite Link Budget

## Completed

- v0.1 scheduling core checkpointed and verified.
- Static RF link-budget model, explicit-unit equations, and reference cases implemented.

## Verification

- `python -m pip install -e ".[dev]"`: passed in the project virtual environment.
- `python -m pytest`: 39 passed.
- `python -m ruff check .`: passed.
- Hand-checkable FSPL, thermal-noise, SNR, capacity, efficiency, and margin cases: passed.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.
- Shannon capacity is named as an upper bound; effective rate uses explicit scenario efficiency.

## Known Limitations

- Orbit, intermittent contacts, benchmark, and Web Demo are later milestones.

## Git

- HEAD: 83d5b34
- working tree: ready for v0.2 checkpoint

## Next

- Verify v0.2 and implement deterministic orbit/contact modeling.
