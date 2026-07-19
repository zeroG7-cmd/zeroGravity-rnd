# zeroGravity R&D Architecture

## Core rule

Domain engines describe what happened. `operator_core` owns the shared mechanics
that every domain needs.

```text
Learning Engine ─┐
Journal Engine ──┤
Lab Engine ──────┼──> Operator Event Ledger ──> XP Distribution ──> Progression
Execution Engine ┤
Business Engine ─┘
```

## Learning

`learning/engine/` owns courses, providers, lessons, imports, progress positions,
and learning completion semantics. It should not permanently own universal XP,
level, evidence, or history behaviour.

## Operator Core

`operator_core/` owns cross-domain infrastructure:

- immutable events;
- XP distribution and receipts;
- progression and level updates;
- evidence;
- Operator profile state;
- unified history.

## Incremental migration

Existing Learning modules remain operational while their shared responsibilities
move behind compatibility wrappers. No working feature is deleted before all of
its callers have migrated and tests confirm equivalent behaviour.
