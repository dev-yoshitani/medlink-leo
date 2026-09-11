# Deployment

The Streamlit application is prepared for Streamlit Community Cloud and local/container use from
the public repository at `https://github.com/dev-yoshitani/medlink-leo`. No public demo URL is
claimed because Streamlit deployment still requires interactive service authentication.

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

Do not add a Live Demo link until the deployed URL has been opened and those checks pass.

## Container execution

When a Docker daemon is available:

```powershell
docker build -t medlink-leo:1.1.0 .
docker run --rm -p 8501:8501 medlink-leo:1.1.0
```

The image launches Streamlit on `0.0.0.0:8501` and exposes `/_stcore/health`. Docker is optional
for Community Cloud and is not a default-demo dependency.

## Known host constraints

Community Cloud executes from the repository root, so all runtime paths are derived from the app
file rather than the current working directory. Ephemeral storage is sufficient because the app
reads bundled fixtures and writes no required persistent state. Public deployment still depends
on interactive Streamlit service authentication and app creation.
