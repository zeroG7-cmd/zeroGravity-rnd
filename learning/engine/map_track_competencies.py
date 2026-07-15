"""Operator Zero automatic competency mapper v1.0.

Uses transparent keyword rules to suggest weighted competency mappings for each
unit. The generated mappings are deterministic and reviewable in metadata.json.
They can be edited manually after generation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACKS_ROOT = Path("learning/tracks")
RULES_PATH = Path("learning/config/competency_mapping_rules.json")
COMPETENCIES_PATH = Path("learning/config/competencies.json")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def discover_tracks() -> list[Path]:
    return sorted(
        path.parent
        for path in TRACKS_ROOT.rglob("metadata.json")
        if (path.parent / "progress.json").exists()
    )


def choose_track(paths: list[Path]) -> Path | None:
    if not paths:
        print("No tracks found.")
        return None
    for index, path in enumerate(paths, start=1):
        metadata = load_json(path / "metadata.json")
        print(f"{index}. {metadata.get('title', path.name)}")
    while True:
        value = input("Select a track, or Q to quit: ").strip()
        if value.lower() == "q":
            return None
        try:
            index = int(value) - 1
        except ValueError:
            print("Enter a number or Q.")
            continue
        if 0 <= index < len(paths):
            return paths[index]
        print("Selection is out of range.")


def map_unit(
    unit: dict[str, Any],
    rules: list[dict[str, Any]],
    valid_ids: set[str],
) -> list[dict[str, Any]]:
    text = " ".join(
        str(value)
        for value in (
            unit.get("section_title", ""),
            unit.get("title", ""),
            unit.get("source_type", ""),
        )
    ).lower()

    scores: dict[str, float] = {}
    for rule in rules:
        competency_id = str(rule.get("competency_id", "")).strip()
        if competency_id not in valid_ids:
            continue
        keywords = rule.get("keywords", [])
        if not isinstance(keywords, list):
            continue
        matches = sum(1 for keyword in keywords if str(keyword).lower() in text)
        if not matches:
            continue
        try:
            score = float(rule.get("score", 1)) * matches
        except (TypeError, ValueError):
            score = float(matches)
        scores[competency_id] = scores.get(competency_id, 0.0) + score

    total = sum(scores.values())
    if total <= 0:
        return []

    return [
        {
            "competency_id": competency_id,
            "weight": round(score / total, 4),
        }
        for competency_id, score in sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


def main() -> None:
    print("=" * 68)
    print("OPERATOR ZERO AUTOMATIC COMPETENCY MAPPER")
    print("=" * 68)

    track_path = choose_track(discover_tracks())
    if track_path is None:
        return

    metadata_path = track_path / "metadata.json"
    metadata = load_json(metadata_path)
    rules_data = load_json(RULES_PATH)
    registry = load_json(COMPETENCIES_PATH).get("competencies", {})
    rules = rules_data.get("rules", [])

    mapped = 0
    unmatched = 0
    existing = 0

    for unit in metadata.get("units", []):
        if unit.get("competency_awards"):
            existing += 1
            continue
        awards = map_unit(unit, rules, set(registry))
        if awards:
            unit["competency_awards"] = awards
            mapped += 1
        else:
            unmatched += 1

    print(f"Mapped units    : {mapped}")
    print(f"Existing maps   : {existing}")
    print(f"Fallback units  : {unmatched}")
    print()
    print("Unmatched units continue using the track default or legacy competency.")

    if input("Save these mappings? [Y/n]: ").strip().lower() not in {"n", "no"}:
        save_json(metadata_path, metadata)
        print(f"Saved: {metadata_path}")
    else:
        print("No files changed.")


if __name__ == "__main__":
    main()
