# Portfolio walkthrough and interview preparation

Use the repository to explain an engineering problem, a bounded design, a reproducible
experiment and an honest limitation. Do not claim flight experience or clinical deployment.

| Review question | Evidence to open | Point to explain |
| --- | --- | --- |
| Can you design a system? | [Architecture](architecture.md), [ADR 001](adr/001-preserve-model-boundary.md) | Separate item ordering, contact selection, shared radio occupancy and backhaul arrival. |
| Can you validate engineering code? | [Orbit validation](validation.md), RF reference tests | Compare independent implementations, align units/frames, predeclare tolerances and state what is not validated. |
| Can you reason about results? | [Matched analysis](benchmark-analysis.md) | Delivery selection can bias the mean; compare the same conditions and item IDs. |
| Can you maintain quality? | [Contribution process](../CONTRIBUTING.md), CI, PR diff | Regressions, typing, packaging and container execution each cover different failure modes. |
| How was AI used? | [AI assistance](ai-assisted-development.md) | Identify generated work, reproduce it and make the acceptance decision yourself. |

Suggested three-minute demo: state the single-radio problem, run the bundled comparison,
switch route policies, inspect one item's candidate table, and explain why a late item is
rejected. Then open the matched benchmark table and identify the population-selection effect.

Before using first-person claims in an application, actually reproduce the validation command,
inspect one routing decision in code and review the associated PR. This document is preparation
material, not a statement that these personal review activities have already occurred.
