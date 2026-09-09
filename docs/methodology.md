# Benchmark methodology

MedLink-LEO retains the v1.0 scheduler benchmark unchanged and adds a separate v1.1 routing
benchmark. Results from the two matrices are not pooled.

## v1.0 scheduler benchmark

### Research question

How do FIFO, illustrative medical-priority scheduling, and EDF differ in deadline-constrained
synthetic medical-data delivery over one intermittent LEO link?

The `canonical-v1.0` matrix contains three offered-load factors, three deadline factors, two
elevation masks, two RF presets, and three schedulers: 108 runs. It repeats the source workload
twice, uses seed `20260830` for arrival jitter, and shares each orbit/capacity trace across the
three schedulers.

```powershell
python -m medlink benchmark `
  --config experiments/canonical_benchmark.json `
  --output-dir artifacts/benchmark `
  --publish-dir docs/assets/benchmark
```

The v1.0 deterministic project-version field remains `1.0.0` so the published evidence and raw
SHA-256 remain a stable compatibility artifact after the package advances to v1.1.

## v1.1 contact-plan routing benchmark

### Research question

How do Next Available Contact, Earliest Arrival, and Deadline-Aware Medical Routing differ when
several ground-station contacts have different RF capacity and terrestrial backhaul delay?

No routing policy is assumed to win. The canonical configuration identifier is
`canonical-contact-plan-routing-v1.1`.

### Matrix

The full Cartesian product contains:

- offered-load factors: 0.75, 1.0, and 1.25;
- deadline factors: 0.75, 1.0, and 1.5;
- backhaul-delay factors: 0.5 and 1.5;
- minimum-elevation masks: 10° and 20°;
- RF-efficiency factors: 0.75 and 1.25;
- routing policies: Next Contact, Earliest Arrival, and Deadline-Aware.

This produces 216 runs, or 72 matched conditions per routing policy. EDF is held constant as the
item scheduler. The routing matrix introduces no randomness.

### Held-constant variables

The frozen TLE, simulation interval, station coordinates, carrier frequency, transmit power,
antenna gains, system losses, noise temperature, 1 s timestep, item arrival times, and single-radio
semantics remain fixed unless a named factor changes them. One contact plan is reused across all
routing policies for each matched orbit/RF condition.

### Metrics

Each run records deadline satisfaction, critical-class satisfaction, delivery ratio, mean and
maximum delivered-item end-to-end latency, contact utilization, delivered/failed counts, explicit
failure counts, and ground-station selection distribution.

### Reproduction

```powershell
python -m medlink routing-benchmark `
  --config experiments/canonical_routing_benchmark.json `
  --output-dir artifacts/routing-benchmark `
  --publish-dir docs/assets/routing-benchmark
```

`raw_results.csv`, deterministic CSV/JSON/Markdown summaries, and three plots are generated.
Timestamp and absolute config path occur only in `run_metadata.json`, which is excluded from
byte-for-byte determinism comparisons.

### Interpretation

Across this documented matrix, Next Contact and Earliest Arrival both deliver 216 of 288 items
and achieve 68.06% mean deadline satisfaction. Earliest Arrival reduces mean delivered latency
from 1063.56 s to 1048.20 s. Deadline-Aware also achieves 68.06% deadline satisfaction but
delivers 196 items because it refuses routes estimated to arrive late; its 529.17 s mean latency
is therefore conditional on a smaller delivered set. These findings are scenario-specific
tradeoffs, not universal claims about routing-policy superiority.

## Shared numerical method and limits

Skyfield/SGP4 supplies range and visibility. The existing RF model supplies effective rate at each
deterministic midpoint. Workloads and priorities are illustrative, not clinically validated.
Neither benchmark models packet protocols, fading, interference, multi-hop DTN behavior, or
operational performance.
