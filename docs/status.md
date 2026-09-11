# MedLink-LEO v1.1 Release Candidate status

## Current Milestone

v1.1 — implementation-complete Release Candidate

## Completed

- Preserved all v1.0 schedulers, fixed/intermittent simulation, orbit/RF behavior, benchmark
  evidence, and Web mode.
- Added a shared orbit-to-capacity integrator and deterministic three-station Contact Plan.
- Added separate Next Contact, Earliest Arrival, and Deadline-Aware routing over the existing item
  scheduler, with single-radio contention and four explicit failure reasons.
- Added route/route-compare CLI JSON, a synthetic example, a separate 216-run benchmark, and
  committed generated evidence.
- Added a routing-first Streamlit experience with route explanations and a Ground Station
  comparison table, while preserving Existing Simulation mode.
- Updated package metadata to 1.1.0 and prepared root dependencies, theme configuration,
  Docker context, and deployment instructions for Streamlit Community Cloud.

## Verification

- `python -m pip install -e ".[dev]"`: passed; editable 1.1.0 installed.
- `python -m pip check`: no broken requirements.
- `python -m pytest`: 89 passed on Python 3.12.14.
- `python -m ruff check .`: passed.
- Fixed and intermittent CLI commands: passed; each JSON comparison matched across two runs.
- Next Contact, Earliest Arrival, Deadline-Aware, and route comparison CLI: passed; routing JSON
  matched across two runs.
- v1.0 canonical benchmark: 108 runs completed twice; raw and summary outputs matched. Raw
  SHA-256 remains `501C2A32BC426E44A2E68F38D47CAEEBC701D16CE676B1AA4943143D4B46129E`.
- v1.1 canonical routing benchmark: 216 runs completed twice; raw and summary outputs matched.
  Raw SHA-256 is `E97E43F7C1E28E1A4300A32698B773F134A7C980A19868CFC39E5D1CFBD8AD24`.
- Committed v1.0 and v1.1 summary evidence matches the final regenerated files byte-for-byte.
- Streamlit: routing and existing-simulation AppTests passed; bounded headless health/root checks
  returned HTTP 200 and the process stopped; local browser review verified layout, labels, units,
  Ground Station comparison, and Why this route?.
- Markdown relative-link test: passed for README and top-level docs.
- Security: no tracked `.env`, PEM, or key files; no hard secret pattern in the tree or reachable
  Git history; no machine-specific path; scenario records are explicitly synthetic.
- GitHub Actions retains `permissions: contents: read` and official pinned actions. Remote run
  `34598054420` passed install, Ruff, and pytest on Python 3.11 and 3.12.
- Docker CLI is unavailable; Dockerfile and build context were reviewed, but build/runtime were not
  executed.

## Assumptions Added

- Synthetic items are available on the satellite at `created_at_s`; clinic uplink is abstracted.
- One satellite radio serves one item at a time. A selected route uses one contact and does not
  split or resume the item across stations.
- RF completion advances the radio clock; terrestrial backhaul changes hospital arrival but does
  not occupy the radio.
- EDF is held constant in the v1.1 routing benchmark so route policies receive matched item order.

## Known Limitations

- Routing is deterministic and greedy rather than globally optimal.
- Full DTN/BPv7, store-carry-forward contact splitting, preemptive scheduling, multi-satellite
  routing, inter-satellite links, and adaptive RF/MCS remain out of scope.
- Docker runtime verification is unavailable in this environment.
- The repository is public at `https://github.com/dev-yoshitani/medlink-leo`; `origin/main` and the
  v1.1 feature branch point to the same verified release-candidate history.
- Public Streamlit deployment has not been performed because it requires interactive Streamlit
  Community Cloud authentication and app creation.

## Git

- Base v1.0 RC HEAD: `d754d13`
- Branch: `feat/medlink-leo-v1.1-routing`
- Routing-core checkpoint: `d18c7e7`
- UI/evidence checkpoint: `8e62be3`
- Final RC checkpoint: this commit
- Working tree: expected clean after the final checkpoint

## Next

1. Create the authorized `v1.1.0` tag and GitHub Release after this publication checkpoint passes
   remote CI.
2. Sign in to Streamlit Community Cloud, deploy `app/streamlit_app.py` from `main`, and verify the
   deployed URL before adding a Live Demo link to README.
