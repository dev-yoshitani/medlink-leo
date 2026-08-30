# MedLink-LEO

Reliable medical-data delivery over constrained LEO satellite links.

MedLink-LEO is an engineering simulation project for comparing deterministic scheduling
strategies for deadline-constrained synthetic medical-data delivery. The current implementation
provides a fixed-bandwidth scheduling core, a documented RF link budget, offline SGP4
orbit/contact modeling, and a resumable intermittent-link simulator.

> **Safety notice:** MedLink-LEO uses synthetic medical data only. It is an engineering
> simulation project and is not intended for diagnosis, treatment, clinical decision-making,
> or real-world medical operations. Priority labels are illustrative simulation inputs, not
> clinical guidance.

## Quick start

```powershell
python -m pip install -e ".[dev]"
python -m medlink compare --scenario examples/basic_scenario.json
python -m medlink compare --scenario examples/basic_scenario.json --json
python -m medlink compare --scenario examples/end_to_end_scenario.json
python -m medlink benchmark --config experiments/canonical_benchmark.json --output-dir artifacts/benchmark
```

Run one strategy:

```powershell
python -m medlink simulate --scenario examples/basic_scenario.json --strategy edf
```

Launch the offline Web Demo:

```powershell
streamlit run app/streamlit_app.py
```

The bundled default needs no API key or live network access.

## Implemented through v0.7

- FIFO, illustrative medical-priority, and earliest-deadline-first scheduling
- Deterministic release times and tie-breaking
- Fixed-bandwidth, single-link, non-preemptive simulation
- Deadline, latency, and utilization metrics
- Human-readable and stable JSON CLI output
- Static free-space link budget with explicit units
- Thermal-noise, SNR, Shannon upper-bound, and effective-rate calculations
- Frozen historical TLE fixture and Skyfield/SGP4 propagation
- Ground-station azimuth, elevation, range, and contact-window detection
- Midpoint-sampled dynamic link rate driven by propagated range
- Non-preemptive transfer pause/resume across intermittent contacts
- Finite-horizon delivered, undelivered, deferred, deadline, latency, and utilization metrics
- Reproducible 108-run scheduler benchmark with raw data, summaries, and generated plots
- Offline Streamlit demo over the same tested simulation core

See [docs/assumptions.md](docs/assumptions.md) for the current model boundary.
