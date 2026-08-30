# Deployment

No public deployment URL is claimed. The application is locally runnable and configured for a
generic container host; publishing remains a manual action.

## Local execution

Requirements:

- Python 3.11 or 3.12;
- no environment variables for the bundled default;
- no API key and no live TLE download.

```powershell
python -m pip install -e ".[dev]"
streamlit run app/streamlit_app.py
```

The entry point is `app/streamlit_app.py`. Streamlit normally serves it at
`http://localhost:8501`.

## Container execution

When a Docker daemon is available:

```powershell
docker build -t medlink-leo:local .
docker run --rm -p 8501:8501 medlink-leo:local
```

The image launches Streamlit on `0.0.0.0:8501` and exposes a health check at
`/_stcore/health`.

## Generic hosted deployment

1. Select a Python or container host that supports Python 3.11+.
2. Build from the repository root with `Dockerfile`, or install the package from
   `pyproject.toml`.
3. Run `streamlit run app/streamlit_app.py --server.address=0.0.0.0`.
4. Expose the host-assigned port or set the Streamlit port to the platform-provided value.
5. Verify the safety notice, default run, contact plots, and all three scheduler rows.

The frozen fixture and default scenario are part of the installed repository, so default runtime
operation does not require outbound network access. Host-specific account setup, billing,
authentication, and publication are intentionally outside the local implementation.
