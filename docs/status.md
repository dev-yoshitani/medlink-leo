# v1.1 development status

## Current Milestone

v1.1 — Contact-Plan-Aware Medical Routing (implementation in progress)

## Completed

- Created the isolated `feat/medlink-leo-v1.1-routing` branch from the verified v1.0 RC.
- Added a shared orbit-to-capacity integrator and kept the v1.0 intermittent simulator on that
  implementation.
- Added deterministic multi-ground-station contact-plan construction with RF-integrated capacity
  and one-way propagation delay.
- Separated existing medical-item scheduling from three routing strategies: next contact,
  earliest hospital arrival, and deadline-aware routing.
- Added explicit route candidates, decision explanations, capacity contention, end-to-end metrics,
  and four machine-readable failure reasons.
- Added a three-station synthetic example, `route` / `route-compare` CLI commands, and a separate
  routing benchmark runner.

## Verification

- Baseline before v1.1 changes: 72 tests passed; Ruff and `pip check` passed on Python 3.12.13.
- Routing unit suite: 8 passed.
- Scenario and routing integration suite: 15 passed.
- CLI suite including deterministic routing JSON: 7 passed.
- Benchmark suite including two identical routing smoke runs: 5 passed.
- Real frozen-TLE example: five contacts generated across Seoul, Sapporo, and Tokyo; strategy
  selection differs when terrestrial backhaul is included.

## Assumptions Added

- Synthetic items are available on the satellite at `created_at_s`; the clinic uplink is not
  modeled in v1.1.
- One satellite radio serves one item at a time. A selected route uses one ground-station contact;
  v1.1 does not split one item across contacts or stations.
- RF completion advances the shared radio clock; terrestrial backhaul delay affects hospital
  arrival but does not occupy the satellite radio.
- Routing is greedy and deterministic, while item ordering remains the responsibility of an
  existing FIFO, Priority, or EDF scheduler.

## Known Limitations

- Full DTN/BPv7, store-carry-forward contact splitting, multi-satellite routing, inter-satellite
  links, preemptive scheduling, and adaptive RF/MCS remain out of scope.
- GitHub authentication remains unavailable; no remote mutation, merge, tag, release, or public
  deployment has been attempted.
- Docker runtime availability will be rechecked during final verification.

## Git

- Base v1.0 RC HEAD: `d754d13`
- Branch: `feat/medlink-leo-v1.1-routing`
- v1.1 checkpoint: pending this development checkpoint
- Working tree: expected clean after checkpoint commit

## Next

- Run the 216-case canonical routing benchmark twice, publish the small evidence set, add the
  recruiter-facing routing UI, update documentation/package version, and run full RC verification.
