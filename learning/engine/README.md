# Learning Engine

The Learning Engine owns learning-specific behaviour: resources, providers,
units, progress, evidence checks, and completion detection.

It does **not** own universal progression infrastructure. A completed unit is
translated by `completion_service.py` into a `learning_completed` Operator
event. `operator_core` then owns duplicate protection, XP distribution,
receipts, and shared history.

## Boundary

```text
Provider / manual tracker
        -> LearningCompletionService
        -> Operator Event Ledger
        -> XP Distribution Engine
        -> existing competency progression (compatibility layer)
```

The existing `stats.py`, `xp.py`, `level.py`, and `history.py` remain available
while callers are migrated. They are compatibility modules, not a second
Operator Core.
