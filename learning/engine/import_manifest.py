"""
Operator Zero Learning Engine
Manifest Importer v1.0

Imports provider-generated JSON manifests (Udemy, YouTube, books, etc.)
and generates tracker-compatible learning tracks.

Keep import_resource.py for repository/local-folder scanning.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEARNING_ROOT = Path("learning")
TRACKS_ROOT = LEARNING_ROOT / "tracks"
CATALOG_PATH = LEARNING_ROOT / "catalog" / "resources.json"
SKILL_TREE_PATH = LEARNING_ROOT / "config" / "skill_tree.json"

DEFAULT_EVIDENCE = [
    {"name": "Notes", "path": "notes.md"},
    {"name": "Reflection", "path": "reflection.md"},
    {"name": "Practical Evidence", "path": "evidence/practical_evidence.md"},
]


def ask_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field cannot be empty.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        value = input(prompt + suffix).strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter y or n.")


def slugify(value: str) -> str:
    value = value.strip().lower().replace("c++", "cpp").replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path}: line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def choose_manifest() -> Path:
    supplied = Path(
        ask_required("Manifest file or resource directory: ")
    ).expanduser()

    if not supplied.exists():
        raise FileNotFoundError(f"Path does not exist:\n{supplied}")

    if supplied.is_file():
        if supplied.suffix.lower() != ".json":
            raise ValueError("Manifest must be a .json file.")
        return supplied

    candidates = sorted(supplied.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(f"No JSON manifest found in:\n{supplied}")
    if len(candidates) == 1:
        return candidates[0]

    print("\nMultiple JSON files found")
    print("-" * 68)
    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. {candidate.name}")

    while True:
        raw = input("Select manifest number: ").strip()
        try:
            selection = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= selection < len(candidates):
            return candidates[selection]
        print("Selection is out of range.")


def validate_manifest(manifest: dict[str, Any]) -> None:
    for key in ("resource", "operator_mapping", "course"):
        if not isinstance(manifest.get(key), dict):
            raise ValueError(f"Manifest field '{key}' must be an object.")

    resource = manifest["resource"]
    mapping = manifest["operator_mapping"]
    course = manifest["course"]

    if not str(resource.get("title", "")).strip():
        raise ValueError("resource.title is required.")

    if not str(mapping.get("stat", "")).strip():
        raise ValueError("operator_mapping.stat is required.")

    hierarchy = mapping.get("hierarchy")
    if not isinstance(hierarchy, list) or not hierarchy:
        raise ValueError(
            "operator_mapping.hierarchy must be a non-empty list."
        )

    sections = course.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("course.sections must be a non-empty list.")

    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            raise ValueError(f"Section {index} must be an object.")
        lectures = section.get("lectures")
        if not isinstance(lectures, list) or not lectures:
            raise ValueError(f"Section {index} has no lectures/units.")


def validate_skill_path(stat: str, hierarchy: list[str]) -> None:
    tree = load_json(SKILL_TREE_PATH, {"stats": {}})
    stats = tree.get("stats", {})

    if stat not in stats:
        raise ValueError(f"Main stat not found: {stat}")

    current = stats[stat]
    for level in hierarchy:
        children = current.get("children", {}) if isinstance(current, dict) else {}
        if level not in children:
            raise ValueError(
                "Knowledge path does not exist:\n"
                + " > ".join([stat, *hierarchy])
                + f"\nMissing level: {level}"
            )
        current = children[level]

    if current.get("node_type") != "competency_reference":
        raise ValueError(
            "Knowledge path must end at an XP-earning competency:\n"
            + " > ".join([stat, *hierarchy])
        )


def normalise(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    resource = manifest["resource"]
    mapping = manifest["operator_mapping"]
    course = manifest["course"]

    hierarchy = [
        str(item).strip()
        for item in mapping["hierarchy"]
        if str(item).strip()
    ]

    return {
        "manifest_path": path,
        "resource_root": path.parent,
        "title": str(resource["title"]).strip(),
        "provider": str(resource.get("provider", "Unknown Provider")).strip(),
        "instructor": str(resource.get("instructor", "")).strip(),
        "source_url": str(resource.get("source_url", "")).strip(),
        "stat": str(mapping["stat"]).strip(),
        "hierarchy": hierarchy,
        "competency_id": str(mapping.get("competency_id", "")).strip(),
        "difficulty": str(course.get("difficulty", "Unspecified")).strip(),
        "sections": course["sections"],
    }


def classify_unit(lecture: dict[str, Any]) -> str:
    declared = str(lecture.get("source_type", "")).strip().lower()
    if declared:
        return declared

    title = str(lecture.get("title", ""))
    if re.search(r"\bquiz\b|practice test", title, re.IGNORECASE):
        return "quiz"
    if re.search(r"\barticle\b", title, re.IGNORECASE):
        return "article"
    return "video"


def build_units(data: dict[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []

    for section_number, section in enumerate(data["sections"], start=1):
        section_title = str(
            section.get("title", f"Section {section_number}")
        ).strip()
        section_slug = (
            str(section.get("slug", "")).strip()
            or slugify(section_title)
            or f"section_{section_number:02}"
        )
        section_folder = f"section_{section_number:02}_{section_slug}"

        for unit_number, lecture in enumerate(
            section.get("lectures", []), start=1
        ):
            if not isinstance(lecture, dict):
                continue

            title = str(
                lecture.get("title", f"Unit {unit_number}")
            ).strip()
            title_slug = slugify(title) or f"unit_{unit_number:03}"
            unit_folder = f"unit_{unit_number:03}_{title_slug}"

            units.append(
                {
                    "id": (
                        f"section_{section_number:02}_"
                        f"unit_{unit_number:03}_{title_slug}"
                    ),
                    "title": (
                        f"Section {section_number}: "
                        f"{section_title} - {title}"
                    ),
                    "section_number": section_number,
                    "section_title": section_title,
                    "unit_number": unit_number,
                    "path": (
                        f"sections/{section_folder}/{unit_folder}"
                    ),
                    "source": data["manifest_path"].name,
                    "source_type": classify_unit(lecture),
                    "duration": lecture.get("duration"),
                    "duration_minutes": lecture.get("duration_minutes"),
                    "source_url": data["source_url"],
                }
            )

    if not units:
        raise ValueError("No units could be generated from the manifest.")

    return units


def build_track_path(data: dict[str, Any]) -> Path:
    path = TRACKS_ROOT / slugify(data["stat"])
    for level in data["hierarchy"]:
        path /= slugify(level)
    return path / slugify(data["title"])


def create_evidence_files(unit_path: Path) -> None:
    for requirement in DEFAULT_EVIDENCE:
        path = unit_path / requirement["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            if path.suffix.lower() == ".md":
                path.write_text(
                    f"# {requirement['name']}\n\n",
                    encoding="utf-8",
                )
            else:
                path.touch()


def create_track(
    data: dict[str, Any],
    units: list[dict[str, Any]],
    track_path: Path,
) -> dict[str, Any]:
    skill = data["hierarchy"][-1]

    metadata = {
        "id": f"{slugify(skill)}_{slugify(data['title'])}",
        "title": data["title"],
        "provider": data["provider"],
        "instructor": data["instructor"],
        "stat": data["stat"],
        "hierarchy": data["hierarchy"],
        "domain": data["hierarchy"][0],
        "skill": skill,
        "difficulty": data["difficulty"],
        "resource": data["resource_root"].as_posix(),
        "manifest": data["manifest_path"].as_posix(),
        "source_url": data["source_url"],
        "competency_id": data["competency_id"],
        "import_method": "manifest",
        "structure_type": "imported",
        "section_count": len(data["sections"]),
        "unit_count": len(units),
        "units": units,
        "evidence_requirements": DEFAULT_EVIDENCE,
    }

    save_json(track_path / "metadata.json", metadata)
    save_json(
        track_path / "progress.json",
        {
            "current_unit_index": 0,
            "completed_units": [],
            "total_xp": 0,
            "status": "In Progress",
        },
    )

    knowledge_path = " > ".join(
        [metadata["stat"], *metadata["hierarchy"]]
    )
    provider = metadata["provider"]
    if metadata["instructor"]:
        provider += f" — {metadata['instructor']}"

    (track_path / "README.md").write_text(
        f"""# {metadata["title"]}

## Operator Zero Manifest Learning Track

- **Knowledge path:** {knowledge_path}
- **Provider:** {provider}
- **Difficulty:** {metadata["difficulty"]}
- **Sections:** {metadata["section_count"]}
- **Imported units:** {metadata["unit_count"]}
- **Manifest:** `{metadata["manifest"]}`
- **Status:** In Progress

The original course remains external. Zero Command stores the course structure,
your progress, notes, reflections, and evidence.
""",
        encoding="utf-8",
    )

    for unit in units:
        unit_path = track_path / unit["path"]
        unit_path.mkdir(parents=True, exist_ok=True)
        create_evidence_files(unit_path)
        save_json(
            unit_path / "source.json",
            {
                "source_type": unit["source_type"],
                "provider": data["provider"],
                "instructor": data["instructor"],
                "manifest": data["manifest_path"].as_posix(),
                "source_url": data["source_url"],
                "section_number": unit["section_number"],
                "section_title": unit["section_title"],
                "unit_number": unit["unit_number"],
                "duration": unit.get("duration"),
                "duration_minutes": unit.get("duration_minutes"),
            },
        )

    return metadata


def register_resource(metadata: dict[str, Any], track_path: Path) -> None:
    catalog = load_json(CATALOG_PATH, {"resources": []})
    resources = catalog.setdefault("resources", [])

    if not isinstance(resources, list):
        raise ValueError("resources.json field 'resources' must be a list.")

    if any(
        isinstance(item, dict) and item.get("id") == metadata["id"]
        for item in resources
    ):
        print("\nResource already exists in the catalog.")
        return

    resources.append(
        {
            "id": metadata["id"],
            "title": metadata["title"],
            "provider": metadata["provider"],
            "instructor": metadata["instructor"],
            "stat": metadata["stat"],
            "hierarchy": metadata["hierarchy"],
            "skill": metadata["skill"],
            "difficulty": metadata["difficulty"],
            "resource": metadata["resource"],
            "manifest": metadata["manifest"],
            "track_path": track_path.as_posix(),
            "import_method": "manifest",
            "date_added": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_json(CATALOG_PATH, catalog)


def display_summary(data: dict[str, Any], units: list[dict[str, Any]]) -> None:
    print("\nManifest detected")
    print("-" * 68)
    print(f"Title       : {data['title']}")
    print(f"Provider    : {data['provider']}")
    print(f"Instructor  : {data['instructor'] or 'Not supplied'}")
    print(f"Difficulty  : {data['difficulty']}")
    print(
        "Knowledge   : "
        + " > ".join([data["stat"], *data["hierarchy"]])
    )
    print(f"Sections    : {len(data['sections'])}")
    print(f"Units       : {len(units)}")
    print(f"Manifest    : {data['manifest_path']}")
    print("-" * 68)
    print("\nEvidence templates")
    for requirement in DEFAULT_EVIDENCE:
        print(f"- {requirement['name']}: {requirement['path']}")


def main() -> None:
    print("=" * 68)
    print("        OPERATOR ZERO MANIFEST IMPORTER")
    print("=" * 68)

    try:
        manifest_path = choose_manifest()
        manifest = load_json(manifest_path, {})
        validate_manifest(manifest)
        data = normalise(manifest_path, manifest)
        validate_skill_path(data["stat"], data["hierarchy"])
        units = build_units(data)
    except (FileNotFoundError, ValueError, OSError) as error:
        print("\nIMPORT ERROR")
        print("-" * 68)
        print(error)
        return

    display_summary(data, units)

    if not ask_yes_no("\nUse these detected values?", default=True):
        print("Import cancelled. Edit the manifest and run again.")
        return

    track_path = build_track_path(data)

    print("\nTrack destination")
    print("-" * 68)
    print(track_path)

    if track_path.exists():
        print("\nERROR: This track already exists.")
        print("No files were changed.")
        return

    if not ask_yes_no("Generate this manifest track?", default=True):
        print("Import cancelled.")
        return

    try:
        track_path.mkdir(parents=True, exist_ok=False)
        metadata = create_track(data, units, track_path)
        register_resource(metadata, track_path)
    except Exception:
        if track_path.exists():
            shutil.rmtree(track_path)
        raise

    print("\nMANIFEST IMPORTED SUCCESSFULLY")
    print("-" * 68)
    print(f"Track title : {metadata['title']}")
    print(f"Provider    : {metadata['provider']}")
    print(f"Skill       : {metadata['skill']}")
    print(f"Sections    : {metadata['section_count']}")
    print(f"Units       : {metadata['unit_count']}")
    print(f"Track path  : {track_path}")
    print(f"Catalog     : {CATALOG_PATH}")
    print("\nRun tracker.py to confirm the course is discovered.")


if __name__ == "__main__":
    main()
