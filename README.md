# MedLink-LEO

Reliable medical-data delivery over constrained LEO satellite links.

MedLink-LEO is an engineering simulation project for comparing deterministic scheduling
strategies for deadline-constrained synthetic medical-data delivery. Version 0.1 provides a
fixed-bandwidth, single-link scheduling core; satellite and orbit models are added in later
milestones.

> **Safety notice:** MedLink-LEO uses synthetic medical data only. It is an engineering
> simulation project and is not intended for diagnosis, treatment, clinical decision-making,
> or real-world medical operations. Priority labels are illustrative simulation inputs, not
> clinical guidance.

## Quick start

```powershell
python -m pip install -e ".[dev]"
python -m medlink compare --scenario examples/basic_scenario.json
python -m medlink compare --scenario examples/basic_scenario.json --json
```

Run one strategy:

```powershell
python -m medlink simulate --scenario examples/basic_scenario.json --strategy edf
```

## Implemented in v0.1

- FIFO, illustrative medical-priority, and earliest-deadline-first scheduling
- Deterministic release times and tie-breaking
- Fixed-bandwidth, single-link, non-preemptive simulation
- Deadline, latency, and utilization metrics
- Human-readable and stable JSON CLI output

See [docs/assumptions.md](docs/assumptions.md) for the current model boundary.

