# Operator XP Distribution Engine

This package owns one responsibility: split a single XP reward pool across the
correct Operator destinations and preserve an auditable receipt.

It is shared by Learning, Journal, Lab, Execution, Business, and future systems.
Those systems emit facts; they do not implement their own rounding or duplicate
protection.

## Event payload

A source event may carry its own reward pool and targets:

```json
{
  "base_xp": 40,
  "xp_targets": [
    {"target_type": "stat", "target_id": "INT", "weight": 0.6},
    {"target_type": "stat", "target_id": "DISC", "weight": 0.2},
    {"target_type": "stat", "target_id": "SPIRIT", "weight": 0.2}
  ]
}
```

The resulting integer allocations always add up to exactly 40 XP. A receipt is
stored once per source event and ruleset. Reprocessing the same event returns
the original receipt rather than awarding a second distribution.

## Boundary

This commit calculates and records distributions. Applying those allocations to
the Operator competency registry/profile is the responsibility of the shared
progression service introduced during the next integration step. Existing
Learning stats remain untouched until the compatibility refactor.
