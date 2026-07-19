# Universal Journal Engine

The journal captures technical work, business thinking, test observations,
learning, personal reflection, spiritual insight, planning, decisions, and
creative ideas through one consistent pipeline.

```text
Markdown entry (original writing)
        ↓
JSON manifest (structured metadata)
        ↓
journal_created Operator event
        ↓
optional shared XP distribution receipt
```

## Storage

Each entry is stored under `journal/entries/YYYY/MM/` as a pair:

```text
2026-07-19-ground-control-realisation.md
2026-07-19-ground-control-realisation.json
```

The Markdown body is the authoritative original writing. Later processing may
update the JSON manifest, but must not rewrite the Markdown entry.

## Entry types

Supported first-version types are:

`reflection`, `insight`, `epiphany`, `technical`, `business`, `test_log`,
`learning`, `planning`, `spiritual`, `creative`, `decision`, `problem`, and
`personal`.

## XP boundary

The journal never mutates stats. It emits a `journal_created` event containing
one reward pool and weighted targets. `operator_core.distribution` calculates
and records the receipt.

A journal entry can be saved with `base_xp=0` when it is only a record. This
prevents ordinary writing from automatically farming XP.

## CLI examples

Create an entry without XP:

```powershell
python -m journal.engine.cli create "Camera stream insight" `
  --body "I understood how the Pi stream connects to Ground Control." `
  --types "technical,insight" `
  --projects "Shadow Ground Control" `
  --concepts "Camera Systems,REST APIs"
```

Create an evidenced entry with a controlled 20 XP pool:

```powershell
python -m journal.engine.cli create "Camera pipeline test" `
  --body-file .\notes\camera_test.txt `
  --types "technical,test_log,reflection" `
  --projects "Shadow" `
  --base-xp 20 `
  --target "stat:INT:0.70" `
  --target "stat:DISC:0.20" `
  --target "stat:SPIRIT:0.10" `
  --evidence "git_commit:6e11d18:Event ledger commit"
```

Rebuild or inspect the index:

```powershell
python -m journal.engine.cli index
python -m journal.engine.cli list
```
