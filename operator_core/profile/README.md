# Operator Profile and Progression

This package owns the canonical Operator identity, main-stat totals, total XP,
level progress, preferences, goals, and the record of applied XP receipts.

The progression path is:

```text
Operator Event -> XP Distribution Receipt -> Operator Profile
```

A receipt is applied exactly once. Retrying the same receipt returns the current
profile without adding XP again.

## Canonical data

- `data/identity.json` — Operator identity.
- `data/stats.json` — main-stat XP totals.
- `data/progression.json` — total XP, level, thresholds, and applied receipts.
- `data/awards.json` — totals for every target type, including competencies.
- `data/preferences.json` — profile behaviour and display preferences.
- `data/active_goals.json` — active Operator goals.

Learning-specific competency files remain in place during migration. They are
compatibility data, while this package becomes the authoritative cross-system
profile.
