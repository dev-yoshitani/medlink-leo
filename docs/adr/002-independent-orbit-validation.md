# ADR 002: Cross-check propagation with Pyorbital

Status: accepted for the portfolio improvement branch (2026-09-23).

## Context

Scalar/vector Skyfield agreement tests establish internal consistency only. They cannot
independently validate Skyfield's propagation, coordinate conversion or event-search path.

## Decision

Use development-only Pyorbital 1.12.1, whose `_SGDP4` implementation is separate from
Skyfield's `python-sgp4` backend. Compare near-epoch TEME position/velocity, topocentric
angles/range and rise/set contacts at three stations and two elevation masks. Keep the
production dependency path unchanged. Pass TLE lines explicitly; the check must work offline.

Predeclare tolerances: position 100 m, velocity 0.1 m/s, angles 0.05 degrees, range 500 m,
contact boundaries 0.5 s. These are gross implementation-error detection bounds, with the
contact bound below the canonical 1 s integration timestep, not flight requirements.
Do not tune tolerances automatically from measured errors. A tolerance failure produces evidence and
a nonzero exit code. Changes to reference versions or tolerances require a reviewed explanation.

## Alternatives and consequences

Direct `sgp4` plus a different coordinate transform would still share the production propagator.
Astropy alone is a frame-conversion check. Neither would supply an independent propagation
implementation. Measured ephemerides would test physical accuracy but are outside this frozen
fixture's evidence base. Pyorbital shares the SGP4 theory and TLE inputs; this is implementation
agreement, not independent physical truth. See [scope and measured errors](../validation.md).
