# Assumptions and limitations

## Workload and safety

- All medical workloads are synthetic and illustrative.
- Priority labels are scenario classes, not clinical recommendations.
- Synthetic sizes, deadlines, arrivals, and priorities are not clinically validated.
- No real patient data, diagnosis, treatment, or clinical recommendation is represented.

## Orbit and contact

- One frozen 2014 ISS TLE is propagated only near its documented epoch.
- Results are historical engineering examples, not current satellite tracking.
- Seoul, Sapporo, and Tokyo stations are illustrative reference coordinates, not claims about
  operational facilities.
- v1.1 uses one satellite, three ground stations, one abstract remote clinic, and one hospital
  gateway. All internal datetimes are timezone-aware UTC values.
- Contact capacity is independently integrated for each station. The single-radio transfer clock
  prevents simultaneous downlinks, but total-plan capacity and utilization include overlapping
  station opportunities and should be interpreted as planning metrics.

## Link and channel

- Dynamic modes use free-space path loss, ideal thermal noise, and a Shannon capacity upper bound.
- `implementation_efficiency` is an explicit scenario abstraction, not measured modem throughput.
- Atmospheric absorption, rain, fading, shadowing, interference, pointing loss, polarization loss,
  protocol headers, retransmissions, and adaptive modulation/coding are omitted.
- Optional `required_snr_db` is an input; the project never invents a modem threshold.
- One-way free-space propagation delay is included in v1.1 route arrival estimates. The original
  fixed and intermittent scheduling simulators retain their v1.0 timing definitions.

## Routing and backhaul

- A synthetic item is assumed to be available on the satellite at `created_at_s`; the clinic
  uplink is outside the v1.1 model.
- An item is assigned to one station contact and must fit in that contact's remaining capacity.
  It is not split or resumed across contacts or stations.
- The satellite radio handles one item at a time. RF completion advances the radio clock;
  terrestrial `backhaul_delay_s` affects hospital arrival but does not occupy the radio.
- Next Contact and Earliest Arrival may deliver an item after its deadline. Deadline-Aware Routing
  rejects all late candidates and reports `DEADLINE_INFEASIBLE` without consuming a contact.
- Explicit failures are `NO_CONTACT`, `INSUFFICIENT_CAPACITY`, `DEADLINE_INFEASIBLE`, and
  `OUTSIDE_SIMULATION_HORIZON`.
- Route selection is greedy and deterministic, not a globally optimal multi-item assignment.

## Scheduling and transfer

- Item scheduling and route selection are separate. The canonical v1.1 benchmark holds the item
  scheduler at EDF while changing only the routing policy.
- Existing FIFO, Priority, and EDF scheduling are deterministic and non-preemptive.
- The v1.0 intermittent simulator retains transfer progress across contact loss. That behavior is
  not a DTN or Bundle Protocol implementation.

## Numerical method

- Orbit range and dynamic rate are sampled at deterministic interval midpoints.
- Maximum interval width is scenario `time_step_s`; contact boundaries split intervals further.
- Canonical examples use 1 s. Existing convergence coverage compares 1 s and 0.5 s results.

## Explicitly not implemented

Full DTN/BPv7, store-carry-forward contact splitting, multi-satellite routing, inter-satellite
links, scheduler preemption, packet-level TCP/QUIC, authentication, databases, real clinical data,
and operational mission planning remain outside v1.1.

MedLink-LEO is an engineering simulation project. It is not intended for diagnosis, treatment,
clinical decision-making, or real-world medical operations.
