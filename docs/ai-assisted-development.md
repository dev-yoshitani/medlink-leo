# AI-assisted development and engineering ownership

AI assistance was used to inspect the repository, propose changes, draft implementation and
documentation, and run automated checks for this portfolio improvement. This is disclosed
so generated code or prose is not mistaken for work independently reviewed by a human.

The repository demonstrates executable design choices and evidence. It does not establish
who personally authored or understood every line. Automated checks executed by an assistant
are automated verification, **not** an independent human review or a certification.

## Maintainer responsibility

Before presenting or merging the work, the maintainer should inspect the diff, reproduce the
key results and be able to explain the model, units, assumptions, failure modes and limitations.
The final decision to accept a model, claim a result or publish an application belongs to the
maintainer. A PR records which checks ran, which decisions were made and what remains unverified.
Do not mark a human review complete until it has actually occurred.

For this change, concrete review questions are:

1. Why is Pyorbital independent at implementation level but not a measurement reference?
2. Why does sharing a 1 s RF timestep motivate a sub-second contact-boundary check?
3. Why can rejecting late traffic halve a displayed mean latency without speeding up delivery?
4. Why are common-item and equal-condition latency averages different?
5. What does an installed-wheel test detect that editable-install tests miss?

AI-generated benchmark numbers, invented URLs and fabricated test outcomes are not accepted.
Evidence is produced by runnable code from committed inputs. Keep synthetic medical data only;
do not submit patient data or credentials to assistants, test fixtures or public issues.

At runtime, routing and its explanations are deterministic code. The demo has no LLM/API-key
dependency. Candidate comparisons and decision reasons come from the routing engine, not
generated natural-language judgments. See [ADRs](adr/001-preserve-model-boundary.md).
