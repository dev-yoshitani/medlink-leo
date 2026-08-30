# Assumptions and limitations

## Workload and safety

- All medical workloads are synthetic and illustrative.
- Priority labels are scenario classes, not clinical recommendations.
- No real patient data, diagnosis, treatment, or clinical recommendation is represented.
- Synthetic sizes, deadlines, arrivals, and priority labels are not clinically validated.

## Orbit and contact

- One frozen 2014 ISS TLE is propagated only near its documented epoch.
- Results are historical engineering examples, not current satellite tracking.
- The Tokyo reference ground station is illustrative and is not an operational facility claim.
- The v1.0 scope uses one satellite and one ground station.
- All internal datetimes are timezone-aware UTC values.

## Link and channel

- v0.1 fixed mode uses a constant bandwidth in bits per second.
- Dynamic mode uses free-space path loss, ideal thermal noise, and a Shannon capacity upper bound.
- `implementation_efficiency` is an explicit scenario abstraction, not a measured modem constant.
- Atmospheric absorption, rain, fading, shadowing, interference, pointing loss, polarization loss,
  protocol headers, retransmissions, and propagation delay are omitted.
- Optional `required_snr_db` is an input; the project never invents a modem threshold.

## Scheduling and transfer

- One link carries one active medical-data item at a time.
- Scheduling and queue behavior are deterministic and non-preemptive.
- Transfer progress is retained across contact loss; this is not a DTN or Bundle Protocol model.
- A newly created higher-priority item waits until the active item completes.
- `undelivered` means unfinished at the finite horizon; `deferred` is the subset whose deadline
  lies after that horizon.

## Numerical method

- Orbit range and dynamic rate are sampled at deterministic interval midpoints.
- The maximum interval width is the scenario `time_step_s`; arrival and contact boundaries split
  intervals further.
- The canonical example uses 1 s, and the test suite compares it with a 0.5 s result.

## Fixed-mode omissions

- Protocol headers, retransmissions, propagation delay, contact loss, and orbital motion are not
  modeled in the fixed-link v0.1 mode.

MedLink-LEO is an engineering simulation project. It is not intended for diagnosis, treatment,
clinical decision-making, or real-world medical operations.
