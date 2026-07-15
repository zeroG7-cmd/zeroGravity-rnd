# Provider Progress Upgrade — 14 July 2026

## Added

- `engine/import_provider_progress.py`
  - Imports Boot.dev, Udemy, or manual provider snapshots.
  - Supports completion counts and exact provider unit IDs.
  - Awards only newly imported completions.
  - Uses weighted multi-competency XP mappings already present in the engine.
  - Updates track progress, competencies, operator stats, and history.
  - Archives provider snapshots under `operator/provider_snapshots/`.
  - Includes `--dry-run` preview mode.

- Provider progress templates for Boot.dev and the future Udemy API course.
- `PROVIDER_PROGRESS_README.md` with the operating workflow.

## Improved

- `engine/import_manifest.py` now preserves provider course IDs and provider unit IDs.
- `engine/history.py` now records whether completion came from the normal tracker or a provider import.

## Compatibility

Existing tracks and legacy single-competency mappings remain supported.
