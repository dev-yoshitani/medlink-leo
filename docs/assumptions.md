# Assumptions and limitations

## v0.1 model boundary

- All medical workloads are synthetic and illustrative.
- Priority labels are scenario classes, not clinical recommendations.
- One link transmits one complete item at a time.
- Bandwidth is fixed and measured in bits per second.
- Scheduling is non-preemptive.
- Transmission and queue behavior are deterministic.
- Protocol headers, retransmissions, propagation delay, contact loss, and orbital motion are not
  modeled in the fixed-link v0.1 mode.
- Orbit examples use a frozen 2014 ISS TLE only near its documented epoch.
- The Tokyo reference ground station is illustrative and is not an operational facility claim.

MedLink-LEO is an engineering simulation project. It is not intended for diagnosis, treatment,
clinical decision-making, or real-world medical operations.
