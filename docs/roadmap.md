# Roadmap

## Implemented in v1.0 scope

- Deterministic fixed-link simulation with FIFO, illustrative Priority, and EDF scheduling.
- Explicit RF link budget with FSPL, received power, thermal noise, SNR, capacity upper bound,
  implementation efficiency, and optional margin.
- Frozen historical TLE propagation through Skyfield/SGP4.
- Ground-station range, azimuth/elevation, and contact-window detection.
- Single-hop, non-preemptive, resumable transfer across intermittent contacts.
- Reproducible scheduler benchmark with raw outputs, summaries, and plots.
- Offline Streamlit demo over the tested package.
- Pytest, Ruff, GitHub Actions configuration, packaging, and Docker configuration.

## Deliberately out of scope

- Multi-satellite or multi-ground-station routing.
- Full Delay/Disruption Tolerant Networking or Bundle Protocol behavior.
- Packet-level TCP, QUIC, retransmission, congestion-control, or protocol-overhead models.
- Adaptive coding and modulation, atmospheric/rain fading, interference, or weather models.
- Scheduler preemption or chunk-based queue selection.
- Authentication, databases, real patient data, or clinical workflows.
- Constellation optimization and operational mission planning.

## Promising future engineering work

- Add validated propagation-loss components and modem/coding profiles.
- Study preemptive or chunked scheduling under the same reproducible workload framework.
- Generalize capacity providers for controlled multi-contact experiments.
- Add statistically designed sensitivity analysis without changing the deterministic canonical run.
- Validate container and CI configuration on an authorized remote service.
