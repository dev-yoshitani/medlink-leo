# Roadmap

## Implemented in v1.0

- Deterministic fixed-link and intermittent-link simulation with FIFO, Priority, and EDF.
- RF link budget with FSPL, received power, thermal noise, SNR, capacity upper bound, explicit
  efficiency, and optional margin.
- Frozen historical TLE propagation, station geometry, and contact windows.
- Non-preemptive pause/resume transfer across intermittent contacts.
- Reproducible 108-run scheduler benchmark, offline Streamlit demo, packaging, tests, Ruff, CI
  configuration, and Docker configuration.

## Implemented in v1.1

- One-satellite, three-ground-station Contact Plan with RF-integrated capacity and propagation
  delay.
- Strict separation between existing item scheduling and route selection.
- Next Available Contact, Earliest Arrival, and Deadline-Aware Medical Routing.
- Configurable station-to-hospital backhaul delay and deterministic candidate explanations.
- Capacity contention on one satellite-radio timeline and four explicit failure reasons.
- Route JSON, CLI comparison, 216-run deterministic routing benchmark, and generated evidence.
- Recruiter-facing Streamlit routing mode with Ground Station comparison and Why this route?
- Streamlit Community Cloud-ready dependency and entry-point configuration.

## Deliberately out of scope for v1.1

- Full DTN or BPv7 and store-carry-forward contact splitting.
- Multi-satellite routing and inter-satellite links.
- Packet-level TCP/QUIC, retransmission, congestion control, or protocol overhead.
- Adaptive coding/modulation, weather attenuation, interference, and operational link validation.
- Preemptive scheduling, chunk-based route changes, or a global multi-item optimizer.
- Authentication, databases, real patient data, diagnosis, or clinical workflows.

## Promising future engineering work

- Add validated propagation-loss components and modem/coding profiles.
- Compare greedy routing with a clearly bounded global capacity-allocation formulation.
- Extend the Contact Plan to multiple satellites and explicit store-carry-forward semantics.
- Add statistically designed sensitivity analysis without changing either canonical benchmark.
