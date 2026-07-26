"""Process provider completion events through the shared Operator Core."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ENGINE = Path(__file__).resolve().parent
REPO_ROOT = ENGINE.parents[1]
for candidate in (str(REPO_ROOT), str(ENGINE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from completion_service import LearningCompletionService
from concepts import distribute_concept_xp, resolve_concept_awards, update_concept_progress
from history import record_completion
from stats import update_operator_competencies
from xp import calculate_unit_xp, resolve_competency_awards

ROOT = REPO_ROOT / "learning"
TRACKS = ROOT / "tracks"


def load(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", norm(value)).strip("_")


def find_track(event: dict[str, Any]) -> tuple[Path, dict[str, Any], Path]:
    provider = norm(event.get("provider"))
    resource_id = norm(event.get("resource_id") or event.get("course_id"))
    hits: list[tuple[Path, dict[str, Any], Path]] = []
    for metadata_path in TRACKS.rglob("metadata.json"):
        metadata = load(metadata_path, {})
        identifiers = {
            norm(metadata.get("id")),
            norm(metadata.get("resource_id")),
            norm(metadata.get("external_resource_id")),
        }
        if provider and norm(metadata.get("provider")) != provider:
            continue
        if resource_id and resource_id not in identifiers:
            continue
        hits.append((metadata_path.parent, metadata, metadata_path))
    if len(hits) != 1:
        raise ValueError(
            "No unique matching track for provider/resource "
            f"({event.get('provider')} / {event.get('resource_id')})."
        )
    return hits[0]


def existing_unit(metadata: dict[str, Any], event: dict[str, Any]):
    unit_id = norm(event.get("unit_id") or event.get("lesson_id"))
    url = norm(event.get("url"))
    title = norm(event.get("title"))
    for index, unit in enumerate(metadata.get("units", [])):
        values = {
            norm(unit.get("id")), norm(unit.get("external_id")),
            norm(unit.get("lesson_id")), norm(unit.get("source_url")),
        }
        if unit_id and unit_id in values:
            return index, unit
        if url and url in values:
            return index, unit
    if title:
        matches = [
            (index, unit) for index, unit in enumerate(metadata.get("units", []))
            if norm(unit.get("title")) == title
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def make_dynamic_unit(metadata: dict[str, Any], event: dict[str, Any]):
    if not metadata.get("dynamic_provider_units"):
        raise ValueError("Event unit could not be matched to the course manifest.")
    section = int(event.get("section_number") or 0)
    number = int(event.get("unit_number") or 0)
    title = str(event.get("lesson_title") or event.get("title") or "Provider lesson").strip()
    if not section or not number:
        raise ValueError("Dynamic provider events require section_number and unit_number.")
    url = str(event.get("url") or "").strip()
    unit_id = f"section_{section:02}_unit_{number:03}_{slug(title)[:48]}"
    unit = {
        "id": unit_id,
        "title": title,
        "section_number": section,
        "section_title": str(event.get("section_title") or f"Chapter {section}"),
        "unit_number": number,
        "source_type": "exercise",
        "source_url": url,
        "external_id": url or unit_id,
        "provider_unit_id": event.get("unit_id"),
        "mapping_confidence": "medium",
        "xp_value": int(event.get("xp_value") or metadata.get("xp_rules", {}).get("exercise", 20)),
    }
    metadata.setdefault("units", []).append(unit)
    return len(metadata["units"]) - 1, unit


def process(event: dict[str, Any], dry: bool = False) -> dict[str, Any]:
    external_event_id = str(event.get("event_id") or "").strip()
    if not external_event_id:
        raise ValueError("event_id is required")

    track, metadata, metadata_path = find_track(event)
    progress_path = track / "progress.json"
    progress = load(progress_path, {})
    progress.setdefault("completed_units", [])
    progress.setdefault("total_xp", 0)
    progress.setdefault("external_completed_units", 0)
    progress.setdefault("status", "In Progress")

    found = existing_unit(metadata, event)
    created = found is None
    if found is None:
        found = make_dynamic_unit(metadata, event)
    _, unit = found
    unit_id = str(unit["id"])

    total_xp = calculate_unit_xp(metadata, unit)
    competency_targets = resolve_competency_awards(metadata, unit)
    concept_resolution = resolve_concept_awards(metadata, unit)
    concept_distribution = distribute_concept_xp(
        total_xp, concept_resolution["concept_awards"]
    )

    if dry:
        return {
            "status": "preview",
            "external_event_id": external_event_id,
            "unit_id": unit_id,
            "unit_title": unit.get("title"),
            "xp": total_xp,
            "competency_targets": competency_targets,
            "concept_distribution": concept_distribution,
        }

    service = LearningCompletionService(progression_updater=update_operator_competencies)
    result = service.complete(
        source="learning.engine.provider",
        provider=str(event.get("provider") or metadata.get("provider") or "provider"),
        resource_id=str(metadata.get("resource_id") or metadata.get("id") or track.name),
        unit_id=unit_id,
        unit_title=str(unit.get("title", unit_id)),
        total_xp=total_xp,
        competency_targets=competency_targets,
        external_event_id=external_event_id,
        occurred_at=event.get("completed_at") or event.get("occurred_at"),
        payload={
            "track_title": metadata.get("title"),
            "chapter": unit.get("section_title"),
            "verification": event.get("verification", "provider_bridge"),
        },
    )

    already_completed = unit_id in progress["completed_units"]
    if created:
        save(metadata_path, metadata)
    if not already_completed:
        progress["completed_units"].append(unit_id)
        progress["total_xp"] += total_xp
        progress["external_completed_units"] = len(progress["completed_units"])
        progress["current_unit_index"] = progress["external_completed_units"]
        external_total = int(
            progress.get("external_total_units") or metadata.get("external_total_units") or 0
        )
        progress["status"] = (
            "Complete" if external_total and progress["external_completed_units"] >= external_total
            else "In Progress"
        )
        if concept_distribution:
            update_concept_progress(
                concept_resolution["capability_id"],
                concept_distribution,
                confidence=concept_resolution["mapping_confidence"],
                source="provider_event",
            )
        legacy_distribution = [
            {"competency_id": item.target_id, "weight": item.weight, "xp": item.xp}
            for item in result.receipt.allocations if item.target_type == "competency"
        ]
        record_completion(
            metadata, unit, total_xp, legacy_distribution, concept_distribution,
            concept_resolution["mapping_confidence"], "provider_event"
        )
        save(progress_path, progress)

    progression = dict(result.progression or {})
    return {
        "status": "duplicate" if already_completed else "completed",
        "external_event_id": external_event_id,
        "operator_event_id": result.event.event_id,
        "receipt_id": result.receipt.receipt_id,
        "provider": event.get("provider"),
        "track": metadata.get("title"),
        "resource_id": metadata.get("resource_id"),
        "unit_id": unit_id,
        "unit_title": unit.get("title"),
        "xp": result.receipt.total_xp,
        "operator_total_xp": progression.get("total_xp"),
        "operator_level": progression.get("level"),
        "verification": event.get("verification", "provider_bridge"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(process(load(Path(args.event)), args.dry_run), indent=2))


if __name__ == "__main__":
    main()
