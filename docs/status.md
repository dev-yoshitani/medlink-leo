# Implementation status

## Current Milestone

v0.7 — Interactive Web Demo

## Completed

- v0.1 through v0.5 checkpointed and verified.
- Offline Streamlit demo implemented as a thin UI over the scenario and simulation APIs.
- Default workload, frozen TLE, link trace, delivery detail, and three-scheduler comparison exposed.

## Verification

- `python -m pip install -e ".[dev]"`: editable package installed with Streamlit 1.62.0.
- `python -m pytest tests/test_streamlit_app.py -q`: 1 passed.
- `python -m pytest`: 66 passed.
- `python -m ruff check .`: passed.
- The AppTest run loaded the default scenario, clicked `Run Simulation`, and verified the
  deterministic FIFO/Priority/EDF comparison without a live network dependency.

## Assumptions Added

- Fixed-bandwidth, single-link, non-preemptive deterministic model.
- Synthetic medical workload and illustrative priority labels only.
- Shannon capacity is named as an upper bound; effective rate uses explicit scenario efficiency.
- UTC-aware time only; frozen orbit fixture is evaluated near its epoch.
- Single-hop resumable transfer with no scheduler preemption; midpoint timestep is explicit.
- Benchmark jitter uses a recorded seed and shares each physical trace across schedulers.

## Known Limitations

- Protocol-level DTN remains out of scope.
- No public demo URL is claimed; local and deployment-ready execution are the target.

## Git

- HEAD before checkpoint: f988036
- working tree: ready for v0.7 checkpoint

## Next

- Checkpoint v0.7, then add CI, container configuration, deployment notes, and final engineering
  documentation for v0.9.
