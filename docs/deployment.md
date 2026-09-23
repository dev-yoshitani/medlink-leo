# Deployment

The [public Streamlit demo](https://medlink-leo.streamlit.app/) runs on Streamlit Community Cloud
from `dev-yoshitani/medlink-leo`, branch `main`, entry point `app/streamlit_app.py`. At deployment
on 2026-09-24 JST, `main` was `da5930df6a8bbf1f2d955c5884d61ebdac2f0b9d`.

## Compatibility summary

- Python: 3.11+; Python 3.12 is the verified release environment.
- Entry point: `app/streamlit_app.py`.
- Dependencies: root `requirements.txt` installs the local package with `-e .`; package runtime
  dependencies remain authoritative in `pyproject.toml`.
- Environment variables: none for the bundled default.
- External services: no database, daemon, API key, live TLE, persistent writable disk, or Docker
  runtime is required.
- Default data: a bundled synthetic scenario and frozen historical TLE.

## Local execution

```powershell
python -m pip install -e ".[dev]"
streamlit run app/streamlit_app.py
```

Streamlit normally serves the app at `http://localhost:8501`. Contact-Plan Routing is the default
mode; Existing Simulation preserves the v1.0 demo.

## Streamlit Community Cloud

Using the public `dev-yoshitani/medlink-leo` repository:

1. In Streamlit Community Cloud, create an app from this repository and the intended release
   branch.
2. Set the main file path to `app/streamlit_app.py`.
3. In Advanced settings, select Python 3.12.
4. Leave Secrets empty; the default demo needs no environment variables.
5. Deploy, then verify the safety notice, Contact-Plan Routing comparison, Ground Station table,
   Why this route? explanation, and Existing Simulation mode.

The public URL was opened after deployment. The browser showed the synthetic-data/non-clinical
notice, the three-strategy comparison, contact and ground-station candidates, and a Why this
route? explanation. Switching to Deadline-Aware and selecting a failed item kept the comparison
visible and showed `INSUFFICIENT_CAPACITY`. Existing Simulation ran and displayed FIFO, Priority,
and EDF results. The routing JSON button triggered a browser download; downloaded bytes were not
separately inspected. Cloud logs showed Python 3.12.14 and installation from root
`requirements.txt`. No Secrets were configured. An anonymous HTTP request retaining cookies
through Streamlit's redirect returned 200 at the same app URL without a login page.

## Container execution

When a Docker daemon is available:

```powershell
docker build -t medlink-leo:1.1.0 .
docker run --rm -p 8501:8501 medlink-leo:1.1.0
```

The image launches Streamlit on `0.0.0.0:8501` and exposes `/_stcore/health`. Docker is optional
for Community Cloud and is not a default-demo dependency.

The container runs as an unprivileged `demo` user. The `Docker smoke` CI job builds it,
checks HTTP readiness within 60 seconds, and actually executes the routing app and strategy
switching with AppTest. A startup connection reset is retried within that deadline; invalid
health content, application exceptions or missing results fail the job. See [verified status](status.md).

For later deployments, record the actual source branch/commit and repeat the browser checks,
including changing the routing strategy and selected item without rerunning, downloading the JSON,
and switching to Existing Simulation. Use only the bundled synthetic data and leave Secrets empty.

## Known host constraints

Community Cloud executes from the repository root, so all runtime paths are derived from the app
file rather than the current working directory. Ephemeral storage is sufficient because the app
reads bundled fixtures and writes no required persistent state. Maintaining the public deployment
requires access to its Streamlit Cloud account.
