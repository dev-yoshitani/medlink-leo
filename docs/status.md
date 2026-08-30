# Release Candidate status

## Current Milestone

v1.0 — Release Candidate / Publication Preparation

## Completed

- v1.0 implementation remains scope-frozen; no product feature was added during RC preparation.
- Reachable Git history was rewritten with explicit authorization so all author/committer metadata
  uses the GitHub noreply identifier. Commit order, subjects, count, and the final tree were
  preserved; a verified recovery bundle is retained under ignored `work/`.
- Pre-public scans cover the current tree and every reachable commit. No secret pattern, private
  key, content email, machine-specific path, sensitive filename, private URL, or patient data was
  found.
- MIT License added for copyright holder `yoshitani-dev`; README, package metadata, wheel, Docker
  build context, and license-integrity test agree.
- GitHub Actions retains read-only contents permission and official actions are pinned to verified
  full commit SHAs.

## Verification

- `python -m pip install -e ".[dev]"`: passed; editable 1.0.0 installed.
- `python -m pytest`: 72 passed on Python 3.12.13.
- `python -m ruff check .`: passed.
- `python -m pip check`: no broken requirements.
- Fixed and intermittent CLI simulate/compare commands: passed.
- Fixed and intermittent JSON comparisons: exact output matched across two runs.
- Canonical benchmark: 108 runs completed twice; raw CSV and CSV/JSON/Markdown summaries matched
  SHA-256 across runs; regenerated summaries and plots matched committed evidence byte-for-byte.
- Canonical raw CSV SHA-256: `501C2A32BC426E44A2E68F38D47CAEEBC701D16CE676B1AA4943143D4B46129E`.
- Numerical suite: 35 passed; two contacts, 6,904 intervals, positive range, and finite non-negative
  effective rate confirmed for the default scenario.
- Web: supported AppTest passed; bounded headless health and root checks returned HTTP 200, and the
  process was stopped.
- Packaging: editable install passed; isolated wheel build passed; wheel metadata reports MIT and
  contains `dist-info/licenses/LICENSE`.
- README evidence test: benchmark values match the committed v1.0 summary.
- README relative links: 0 broken; five external technical references responded; required
  documents, synthetic example data, image metadata, and placeholder scan passed.
- GitHub Actions: Python 3.11/3.12 workflow configured with `contents: read`; remote run not yet
  observed for this RC checkpoint.
- Docker: CLI unavailable; Dockerfile inspected, build not executed.

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
- Docker runtime verification remains unavailable in this environment.
- GitHub CLI identifies `yoshitani-dev` as the active account, but its saved token is invalid.
  Reauthentication is required before the same-name collision check, private repository creation,
  push, remote CI, or GitHub rendering audit. No remote mutation has occurred.
- Remote repository, CI, rendering, and deployment verification therefore remain pending.

## Git

- Pre-RC rewritten HEAD: `a3f59f7`
- RC audit checkpoint: `cccd989`
- authentication-blocker checkpoint: this commit
- working tree: expected clean after checkpoint

## Next

- Reauthenticate GitHub CLI for `yoshitani-dev`, then check for a same-name collision. If none
  exists, create the authorized private repository, push only `feat/medlink-leo-v1`, and observe
  remote CI/rendering. Do not merge, publicize, tag, or release.
