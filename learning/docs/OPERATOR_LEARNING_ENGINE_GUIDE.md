# Operator Learning Engine Command Guide

Run commands from the `zeroGravity-rnd` repository root.

## Skill tree

```powershell
python learning\scripts\sync_skill_tree.py --dry-run
python learning\scripts\sync_skill_tree.py
python learning\scripts\sync_skill_tree.py --check
```

The source of truth is `operator_core/capabilities/skill_tree.md`.

## Provider maintenance

```powershell
python learning\engine\reconcile_bootdev_progress.py bootdev_learn_python 44 --dry-run
python learning\engine\repair_learning_pipeline.py
python learning\engine\backfill_concepts.py --dry-run
```

## Execution records

```powershell
python operator_core\execution\cli.py add operator_core\execution\templates\execution_record.json
python operator_core\execution\cli.py list
python operator_core\execution\cli.py summary
```

## Repository verification

```powershell
python scripts\verify_repository.py
python -m compileall learning operator_core shared
```

## Zero Command

Set the R&D path before starting Flask:

```powershell
$env:ZERO_GRAVITY_RND_ROOT = "C:\Users\Zero\zero Gravity\zeroGravity-rnd"
python app.py
```
