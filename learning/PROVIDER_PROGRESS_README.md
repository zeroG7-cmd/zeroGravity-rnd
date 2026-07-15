# External Learning Provider Progress

Operator Zero can now import existing progress from Boot.dev, Udemy, and future providers without awarding the same work twice.

## Workflow

1. Import the course manifest with `import_manifest.py`.
2. Open the provider `progress_snapshot.json` file.
3. Enter either:
   - `completed_units`: the number completed from the beginning of the imported course; or
   - `completed_unit_ids`: exact provider lecture/unit IDs.
4. Preview the import:

```cmd
python learning\engine\import_provider_progress.py path\to\progress_snapshot.json --dry-run
```

5. Apply it:

```cmd
python learning\engine\import_provider_progress.py path\to\progress_snapshot.json
```

The importer updates the track progress, competency XP, generated operator stats, completion history, and an archived provider snapshot.

## Important

- Historical progress is marked through permanent completion events and awarded once.
- Re-importing the same total awards no extra XP.
- Increasing the completed count later awards only the new difference.
- Provider XP is retained as external evidence; Operator XP is calculated by your own XP rules.
- Use `--track-path` when the snapshot cannot identify a unique track automatically.
