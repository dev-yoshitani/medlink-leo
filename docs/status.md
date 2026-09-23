# MedLink-LEO status

## Release versus development

- [v1.1.0 is already published](https://github.com/dev-yoshitani/medlink-leo/releases/tag/v1.1.0).
  Its tag resolves to `87d93d9c82ef94886ca545f67f6f08af14c2871f`; it is not a pending RC.
- Portfolio hardening was merged into `main` by [PR #4](https://github.com/dev-yoshitani/medlink-leo/pull/4)
  at `da5930df6a8bbf1f2d955c5884d61ebdac2f0b9d`. It remains unreleased; the package/model
  version is 1.1.0 and no newer tag or release is claimed.
- Historical v1.0 benchmark artifacts retain 1.0.0 provenance; v1.1 routing artifacts retain
  1.1.0. These are deliberate historical labels, not stale current-status claims.

## Portfolio improvements

- Streamlit result persistence across strategy/item/mode changes, explanatory guidance,
  delivered-only latency labeling, and downloadable routing JSON.
- Independent Pyorbital implementation comparison across 1,441 near-epoch samples, three
  stations, two masks and 27 contacts. See [validation](validation.md).
- Added per-item evidence and factor/condition/item matched analysis without changing the
  canonical experiment or original summary. See [interpretation](benchmark-analysis.md).
- Added ADRs, AI-assistance disclosure, review guidance, Issue/PR templates and contribution steps.
- Added mypy, dependency checks, wheel/sdist checks and Docker HTTP/AppTest CI.

## Verification observed locally

Environment: Windows, Python 3.12.14. This records actual checks, not future expectations.

- Full pytest suite: 103 passed.
- mypy: 32 source files passed; Ruff and `pip check`: passed.
- Independent comparison passed the predeclared tolerances; maximum rise/set discrepancy
  0.232256 s. Reference/library versions and all errors are in the committed JSON.
- 216-run raw CSV SHA-256 equals the released value:
  `e97e43f7c1e28e1a4300a32698b773f134a7c980a19868cfc39e5d1cfbd8ad24`.
- Original v1.0 and v1.1 summary files have not been edited.
- Isolated sdist/wheel build passed. Installing the wheel into a separate target and executing
  outside the checkout loaded the bundled TLE and ran the Deadline-Aware CLI successfully.
- Streamlit root/health returned HTTP 200; a browser check confirmed routing results, layout
  and strategy changes preserve the displayed results. AppTest covers both modes and item changes.

## External verification and remaining work

- Merged [PR #4](https://github.com/dev-yoshitani/medlink-leo/pull/4) links the implementation
  to engineering Issues #1, #2 and #3.
- [Post-merge `main` CI](https://github.com/dev-yoshitani/medlink-leo/actions/runs/35823073555)
  passed Python 3.11/3.12 (tests, typing, canonical reproduction and packaging) and Docker smoke
  for merge commit `da5930d`. The older release's CI is not used as evidence for this change.
- Docker CLI is unavailable locally. The remote job built the non-root container and passed
  HTTP health/root plus real Streamlit AppTest. The first run exposed a startup connection-reset
  race; bounded retry was corrected with regression tests while retaining all content assertions.
- [Public Streamlit demo](https://medlink-leo.streamlit.app/) was deployed from `main` at
  `da5930df6a8bbf1f2d955c5884d61ebdac2f0b9d` with Python 3.12 and no Secrets. Browser
  checks on 2026-09-24 JST confirmed the safety notice, three-policy routing comparison,
  station/candidate table, strategy and item switching with persistent results, a failure
  reason, and the Existing Simulation result. The JSON download triggered a browser download;
  its downloaded bytes were not separately inspected. An anonymous HTTP request that retained
  cookies through Streamlit's authentication redirect returned 200 at the public URL, with no
  login page. [Deployment details](deployment.md).
- Main protection was applied with the maintainer's explicit approval: PR required, current-base
  Python 3.11/3.12 and Docker smoke checks, conversation resolution and administrator enforcement;
  force pushes/deletion are prohibited. External approval count is zero for solo maintenance.
- The maintainer's human review and final acceptance are not represented by automated tests.
  [Review questions](ai-assisted-development.md).

## Model boundary retained

Synthetic data, frozen historical TLE, one satellite/radio, EDF ordering and greedy one-contact
routing are retained. No full DTN/BPv7, contact splitting, preemption, ISLs, adaptive RF/MCS,
real medical operations or measured satellite validation is claimed. The clinic uplink remains
abstracted; RF completion occupies the radio, while backhaul affects only hospital arrival.
