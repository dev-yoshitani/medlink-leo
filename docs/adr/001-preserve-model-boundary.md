# ADR 001: Preserve the v1.1 routing model and canonical experiments

Status: accepted for the portfolio improvement branch (2026-09-23).

## Context

The engineering question is how contact capacity, backhaul and deadlines affect routing
under a shared satellite radio. Adding satellites, protocols or live TLE feeds would change
that question and invalidate comparisons with the published v1.1.0 evidence.

## Decision

Keep the single-satellite, single-radio, greedy routing model, frozen 2014 TLE, synthetic
workload, EDF ordering and canonical factor matrix unchanged. Add observation and analysis
around the existing engine. Retain the package/model version 1.1.0 until a separately reviewed
release; describe these changes as unreleased, not as an existing new release.

## Alternatives and consequences

A global optimizer could establish an optimality gap, but would introduce a new algorithm and
evaluation question. Full DTN/BPv7 or multi-satellite support would be a separate milestone.
The current choice keeps old evidence comparable while exposing selection bias in latency.
It does not prove routing optimality, RF realism, clinical usefulness or operational readiness.

Verification: unchanged canonical raw SHA-256, summary reproduction, existing routing tests,
and [matched analysis](../benchmark-analysis.md).
