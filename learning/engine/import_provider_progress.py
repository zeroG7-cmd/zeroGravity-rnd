"""Operator Zero Learning Engine — Provider Progress Importer v1.0.

Imports historical/current progress snapshots from external learning providers
(Boot.dev, Udemy, GitHub, manual sources) into an existing Operator track.

The importer:
- awards only newly discovered completions;
- supports completed unit IDs or a completed-unit count;
- distributes XP using the existing multi-competency XP engine;
- records permanent history events;
- updates competencies.json and generated stats.json;
- stores every provider snapshot for audit and future comparisons.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from history import record_completion
from concepts import distribute_concept_xp, resolve_concept_awards, update_concept_progress
from stats import update_operator_competencies
from xp import calculate_unit_xp, distribute_xp, resolve_competency_awards

LEARNING_ROOT = Path("learning")
TRACKS_ROOT = LEARNING_ROOT / "tracks"
SNAPSHOTS_ROOT = LEARNING_ROOT / "operator" / "provider_snapshots"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Required file not found:\n{path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path}: line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in: {path}")
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def discover_tracks() -> list[Path]:
    if not TRACKS_ROOT.exists():
        return []
    return sorted(
        metadata.parent
        for metadata in TRACKS_ROOT.rglob("metadata.json")
        if (metadata.parent / "progress.json").exists()
    )


def select_track() -> Path:
    tracks = discover_tracks()
    if not tracks:
        raise FileNotFoundError("No imported learning tracks were found.")

    print("\nAvailable learning tracks")
    print("-" * 68)
    for index, path in enumerate(tracks, start=1):
        metadata = load_json(path / "metadata.json")
        print(f"{index}. {metadata.get('title', path.name)}")
        print(f"   Provider: {metadata.get('provider', 'Unknown')}")

    while True:
        value = input("Select track number: ").strip()
        try:
            selected = int(value) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= selected < len(tracks):
            return tracks[selected]
        print(f"Choose a number from 1 to {len(tracks)}.")


def resolve_track_path(snapshot: dict[str, Any], explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not (path / "metadata.json").exists():
            raise FileNotFoundError(f"Track metadata not found:\n{path}")
        return path

    track_id = str(snapshot.get("track_id", "")).strip()
    resource_id = str(snapshot.get("resource_id", "")).strip()
    candidates: list[Path] = []

    for track in discover_tracks():
        metadata = load_json(track / "metadata.json")
        if track_id and str(metadata.get("id", "")) == track_id:
            candidates.append(track)
            continue
        if resource_id and str(metadata.get("resource_id", "")) == resource_id:
            candidates.append(track)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError("Snapshot matches more than one track. Use --track-path.")
    provider = str(snapshot.get("provider", "Unknown")).strip()
    raise FileNotFoundError(
        "No matching learning track exists for this provider snapshot.\n"
        f"Provider: {provider}\n"
        f"Resource ID: {resource_id or 'missing'}\n\n"
        "Import the matching course manifest first. Unrelated tracks were not changed."
    )


def normalise_unit_key(value: Any) -> str:
    return str(value).strip().lower()


def unit_keys(unit: dict[str, Any]) -> set[str]:
    keys = {
        normalise_unit_key(unit.get("id")),
        normalise_unit_key(unit.get("external_id")),
        normalise_unit_key(unit.get("provider_unit_id")),
    }
    return {key for key in keys if key}


def resolve_completed_units(
    snapshot: dict[str, Any],
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    progress = snapshot.get("progress", snapshot)
    if not isinstance(progress, dict):
        raise ValueError("snapshot.progress must be an object.")

    raw_ids = progress.get("completed_unit_ids", [])
    if raw_ids:
        if not isinstance(raw_ids, list):
            raise ValueError("completed_unit_ids must be a list.")
        requested = {normalise_unit_key(value) for value in raw_ids if str(value).strip()}
        matched: list[dict[str, Any]] = []
        remaining = set(requested)
        for unit in units:
            overlap = unit_keys(unit) & requested
            if overlap:
                matched.append(unit)
                remaining -= overlap
        if remaining:
            preview = ", ".join(sorted(remaining)[:10])
            raise ValueError(f"Snapshot contains unknown unit IDs: {preview}")
        return matched

    completed_count = progress.get("completed_units")
    if completed_count is None:
        completed_count = progress.get("completed_count")
    if completed_count is None:
        raise ValueError(
            "Provide progress.completed_unit_ids or progress.completed_units."
        )
    try:
        count = int(completed_count)
    except (TypeError, ValueError) as error:
        raise ValueError("completed_units must be an integer.") from error
    if count < 0 or count > len(units):
        raise ValueError(
            f"completed_units must be between 0 and {len(units)}."
        )
    return units[:count]


def ensure_progress(progress: dict[str, Any]) -> None:
    progress.setdefault("current_unit_index", 0)
    progress.setdefault("completed_units", [])
    progress.setdefault("total_xp", 0)
    progress.setdefault("status", "In Progress")
    progress.setdefault("provider_sync", {})


def update_track_progress(
    progress: dict[str, Any],
    units: list[dict[str, Any]],
) -> None:
    completed = set(str(value) for value in progress.get("completed_units", []))
    first_incomplete = next(
        (index for index, unit in enumerate(units) if str(unit["id"]) not in completed),
        len(units),
    )
    if first_incomplete >= len(units):
        progress["current_unit_index"] = max(0, len(units) - 1)
        progress["status"] = "Complete"
    else:
        progress["current_unit_index"] = first_incomplete
        progress["status"] = "In Progress"


def snapshot_identity(snapshot: dict[str, Any]) -> tuple[str, str]:
    provider = str(snapshot.get("provider", "manual")).strip() or "manual"
    resource_id = str(snapshot.get("resource_id", "unknown_resource")).strip()
    return provider, resource_id


def archive_snapshot(snapshot_path: Path, snapshot: dict[str, Any]) -> Path:
    provider, resource_id = snapshot_identity(snapshot)
    captured_at = str(snapshot.get("captured_at", "")).strip()
    if not captured_at:
        captured_at = datetime.now(timezone.utc).isoformat()
        snapshot["captured_at"] = captured_at
    safe_time = captured_at.replace(":", "-").replace("+", "_")
    destination = SNAPSHOTS_ROOT / provider.lower().replace(".", "_") / resource_id
    destination /= f"{safe_time}.json"
    snapshot["source_snapshot"] = snapshot_path.as_posix()
    save_json(destination, snapshot)
    return destination


def import_snapshot(
    snapshot_path: Path,
    track_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    snapshot = load_json(snapshot_path)
    metadata_path = track_path / "metadata.json"
    progress_path = track_path / "progress.json"
    metadata = load_json(metadata_path)
    progress = load_json(progress_path)
    ensure_progress(progress)

    units = metadata.get("units", [])
    if not isinstance(units, list) or not units:
        raise ValueError("Track metadata has no units.")

    provider = str(snapshot.get("provider", metadata.get("provider", "manual"))).strip()
    track_provider = str(metadata.get("provider", "")).strip()
    if provider and track_provider and provider.casefold() != track_provider.casefold():
        raise ValueError(
            f"Provider mismatch: snapshot is '{provider}' but track is '{track_provider}'. "
            "No files were changed."
        )
    snapshot["provider"] = provider
    snapshot.setdefault("resource_id", metadata.get("resource_id", metadata.get("id")))
    snapshot.setdefault("track_id", metadata.get("id"))

    provider_title = str(metadata.get("provider", "")).strip().lower()
    if provider and provider_title and provider.lower() != provider_title:
        print(
            f"WARNING: snapshot provider '{provider}' differs from "
            f"track provider '{metadata.get('provider')}'."
        )

    completed_units = resolve_completed_units(snapshot, units)
    already_completed = set(str(item) for item in progress["completed_units"])
    new_units = [
        unit for unit in completed_units if str(unit.get("id")) not in already_completed
    ]

    distributions: list[tuple[dict[str, Any], int, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]] = []
    total_new_xp = 0
    for unit in new_units:
        xp_award = calculate_unit_xp(metadata, unit)
        mappings = resolve_competency_awards(metadata, unit)
        if not mappings:
            raise ValueError(
                f"No competency mapping for unit: {unit.get('title', unit.get('id'))}"
            )
        distribution = distribute_xp(xp_award, mappings)
        concept_resolution = resolve_concept_awards(metadata, unit)
        concept_distribution = distribute_concept_xp(xp_award, concept_resolution["concept_awards"])
        distributions.append((unit, xp_award, distribution, concept_resolution, concept_distribution))
        total_new_xp += xp_award

    print("\nProvider progress import")
    print("-" * 68)
    print(f"Provider             : {provider}")
    print(f"Track                : {metadata.get('title')}")
    print(f"Provider completions : {len(completed_units)}/{len(units)}")
    print(f"Already imported     : {len(completed_units) - len(new_units)}")
    print(f"New completions      : {len(new_units)}")
    print(f"New Operator XP      : {total_new_xp}")

    if dry_run:
        print("DRY RUN: no files changed.")
        return {"new_units": len(new_units), "new_xp": total_new_xp}

    all_awards: list[dict[str, Any]] = []
    for unit, xp_award, distribution, concept_resolution, concept_distribution in distributions:
        progress["completed_units"].append(str(unit["id"]))
        progress["total_xp"] = int(progress.get("total_xp", 0)) + xp_award
        all_awards.extend(distribution)
        if concept_distribution:
            update_concept_progress(
                concept_resolution["capability_id"],
                concept_distribution,
                confidence=concept_resolution["mapping_confidence"],
                source=concept_resolution["mapping_source"],
            )
        record_completion(
            metadata=metadata,
            unit={
                **unit,
                "completion_source": "provider_import",
                "provider": provider,
            },
            xp_award=xp_award,
            xp_distribution=distribution,
            concept_distribution=concept_distribution,
            mapping_confidence=concept_resolution["mapping_confidence"],
        )

    operator_stats: dict[str, Any] | None = None
    if all_awards:
        operator_stats = update_operator_competencies(all_awards)

    captured_at = str(snapshot.get("captured_at", "")).strip() or datetime.now(
        timezone.utc
    ).isoformat()
    progress["provider_sync"][provider.lower()] = {
        "captured_at": captured_at,
        "completed_units": len(completed_units),
        "total_units": len(units),
        "external_xp": snapshot.get("external_xp")
        or snapshot.get("progress", {}).get("external_xp")
        if isinstance(snapshot.get("progress"), dict)
        else None,
    }
    update_track_progress(progress, units)
    save_json(progress_path, progress)
    archived_path = archive_snapshot(snapshot_path, snapshot)

    print(f"Snapshot archived     : {archived_path}")
    print(f"Track status          : {progress['status']}")
    if operator_stats:
        print(f"Operator total XP     : {operator_stats['total_xp']}")
        print(f"Operator level        : {operator_stats['level']}")
    else:
        print("No new XP was awarded; this snapshot was already synchronised.")

    return {"new_units": len(new_units), "new_xp": total_new_xp}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Boot.dev/Udemy/provider progress into Operator Zero."
    )
    parser.add_argument("snapshot", help="Path to a provider progress JSON snapshot.")
    parser.add_argument(
        "--track-path",
        help="Optional path to the existing imported learning track.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview detected completions and XP without changing files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    snapshot_path = Path(args.snapshot).expanduser()
    try:
        snapshot = load_json(snapshot_path)
        track_path = resolve_track_path(snapshot, args.track_path)
        import_snapshot(snapshot_path, track_path, dry_run=args.dry_run)
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError) as error:
        print("\nPROVIDER IMPORT ERROR")
        print("-" * 68)
        print(error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
