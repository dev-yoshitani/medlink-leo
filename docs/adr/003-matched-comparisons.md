# ADR 003: Separate policy effects from delivered-population selection

Status: accepted for the portfolio improvement branch (2026-09-23).

## Context

The old benchmark averages delivered-item latency within each run and then across runs.
Deadline-Aware can reject late items, so a lower mean does not establish faster delivery.

## Decision

Keep the published metrics and add per-item evidence. Match policies on all five factors,
config ID, EDF scheduler and numerical timestep. For latency, additionally match item IDs
and retain only items delivered by both policies. Report overlap, policy-only and neither
counts. Report both item-weighted and condition-weighted latency deltas; they need not agree.
Also expose each matched condition and factor-stratified deltas. Reject duplicate, missing
or inconsistent records rather than silently merging them.

## Alternatives and consequences

Replacing failures with zero latency rewards dropping traffic. Replacing them with a chosen
penalty mixes delivery and latency preferences. Neither is used. Deadline rate keeps all offered
items in its denominator, while common-item latency answers the narrower speed question.
Factor marginals average other factors; inspect matched conditions before inferring interactions.
The 72 conditions are a deterministic factorial grid, not 72 independent stochastic replications.
No confidence intervals, p-values or universal policy ranking are claimed.
