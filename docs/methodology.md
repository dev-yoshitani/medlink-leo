# Benchmark methodology

## Research question

How do FIFO, illustrative medical-priority scheduling, and earliest-deadline-first scheduling
differ in deadline-constrained synthetic medical-data delivery over intermittent LEO links?

No scheduler is assumed to win before the experiment is run.

## Canonical matrix

The committed configuration identifier is `canonical-v1.0`.

The canonical configuration evaluates the full Cartesian product of:

- three offered-load factors: 0.75, 1.0, and 1.5;
- three deadline factors: 0.5, 1.0, and 1.5;
- two minimum-elevation masks: 10° and 20°;
- two RF presets: constrained and nominal;
- three schedulers: FIFO, Priority, and EDF.

This produces 108 scheduler runs. Every scheduler receives the same generated workload and the
same precomputed orbit/link-capacity trace for a given physical scenario.

## Synthetic workload

The source workload is repeated twice with a fixed 2400 s separation. A pseudorandom arrival
jitter of at most 30 s is generated with seed `20260830`. Offered-load factors multiply item size;
deadline factors multiply the scenario deadline. These values are illustrative engineering
inputs and are not clinically validated.

## Held-constant variables

The frozen historical ISS TLE, propagation interval, reference ground-station coordinates,
carrier frequency, transmit power, antenna gains, losses, noise temperature, and simulator
semantics remain fixed except where the matrix explicitly names an RF or elevation factor.

## Metrics

Each run records deadline and critical-class deadline satisfaction, delivered/undelivered/deferred
counts, average and maximum delivered-item latency, transferred bits, integrated available
capacity, contact time, and link utilization. The committed summary reports unweighted means
across all 36 physical/workload scenarios for each scheduler and aggregate counts.

## Numerical method

Orbit and range are evaluated with Skyfield/SGP4. Effective link rate is sampled at the midpoint
of deterministic intervals whose maximum width is `time_step_s = 1.0`. Data-arrival and contact
boundaries split intervals. A 0.5 s comparison is covered by the test suite.

## Reproduction

```powershell
python -m medlink benchmark `
  --config experiments/canonical_benchmark.json `
  --output-dir artifacts/benchmark `
  --publish-dir docs/assets/benchmark
```

`raw_results.csv`, deterministic summaries, plots, and variable run metadata are generated.
The timestamp and absolute config path occur only in `run_metadata.json`; deterministic checks
compare the raw and summary files.

## Interpretation limits

The experiment is a single-satellite, single-ground-station, single-hop abstraction. It omits
packet protocols, retransmissions, atmospheric fading, interference, multi-hop routing, and
clinical validation. Results support comparison inside the documented simulation assumptions;
they do not predict clinical or operational performance.
