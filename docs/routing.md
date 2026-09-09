# Contact-Plan-Aware Medical Routing

## Contact Plan

A contact-plan entry records who can transmit to whom, when the opportunity begins and ends, how
many bits the RF model integrates across it, and its one-way propagation delay. IDs and ordering
are stable for identical inputs.

| Field | Meaning |
| --- | --- |
| `contact_id` | Stable satellite/station/opportunity identifier |
| `source`, `destination` | Network node IDs |
| `start_s`, `end_s` | Seconds from the UTC simulation start |
| `available_capacity_bits` | Midpoint-integrated effective RF capacity |
| `propagation_delay_s` | Capacity-weighted one-way range divided by light speed |

The builder reuses `simulation.capacity`, which also supplies the v1.0 intermittent simulator.
No RF equation is reimplemented in the routing package.

## Strategies

### Next Available Contact

Reject contacts that cannot finish the item. Rank remaining candidates by RF departure, RF
completion, remaining capacity (descending), station ID, and contact ID.

### Earliest Arrival

Estimate hospital arrival as waiting plus dynamic-rate RF transfer, propagation, and station
backhaul. Rank by arrival, departure, completion, remaining capacity (descending), and stable IDs.

### Deadline-Aware Medical Routing

First keep only candidates arriving by the item's absolute deadline. Then rank by arrival,
remaining capacity (descending), departure, and stable IDs. If capacity-feasible candidates exist
but all are late, report `DEADLINE_INFEASIBLE` and leave the shared radio time unchanged.

## Contention semantics

An existing scheduler first selects a ready item. Routing then chooses one contact. The item must
fit completely in the unelapsed portion of that contact. Successful RF completion advances one
shared satellite-radio clock, so later items cannot reuse elapsed capacity. Backhaul proceeds
off-radio and only changes hospital arrival.

This is a deterministic greedy abstraction, not full DTN, BPv7, or a global optimizer. One item's
bits are never split across contacts or stations.

## Result transparency

Each result includes the selected station/contact, departure, RF completion, hospital arrival,
deadline and margin, required/available capacity, decision reason, and every evaluated candidate.
Failures distinguish no remaining contact, insufficient capacity, deadline infeasibility, and the
finite simulation horizon. CLI JSON and the Web Demo present the same result objects.
