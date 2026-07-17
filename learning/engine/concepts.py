"""Operator Zero concept graph engine â€” Manifest v3.

Concept mappings are optional precision beneath a capability. Existing
competency/capability XP remains the source of truth for operator totals.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

GRAPH_PATH = Path("operator/capabilities/capability_graph.json")
CONFIDENCE = {"high", "medium", "low"}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _normalise(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    merged: dict[str, float] = {}
    order: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("concept_id", "")).strip()
        try:
            weight = float(item.get("weight", 0))
        except (TypeError, ValueError):
            continue
        if not concept_id or weight <= 0:
            continue
        if concept_id not in merged:
            merged[concept_id] = 0.0
            order.append(concept_id)
        merged[concept_id] += weight
    total = sum(merged.values())
    if total <= 0:
        return []
    return [{"concept_id": cid, "weight": merged[cid] / total} for cid in order]


def validate_concept_ids(capability_id: str, mappings: list[dict[str, Any]]) -> None:
    graph = load_json(GRAPH_PATH, {"capabilities": {}})
    capability = graph.get("capabilities", {}).get(capability_id, {})
    concepts = capability.get("concepts", {}) if isinstance(capability, dict) else {}
    unknown = [m["concept_id"] for m in mappings if m["concept_id"] not in concepts]
    if unknown:
        raise ValueError(
            f"Unknown concept IDs for capability '{capability_id}': " + ", ".join(unknown)
        )


def resolve_concept_awards(metadata: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    """Resolve unit -> section -> track defaults -> capability-only fallback."""
    capability_id = str(
        unit.get("capability_id")
        or metadata.get("capability_id")
        or metadata.get("competency_id")
        or ""
    ).strip()

    candidates: list[tuple[Any, str, str]] = [
        (unit.get("concept_awards"), str(unit.get("mapping_confidence", "high")), "unit"),
    ]
    sections = metadata.get("section_concept_awards", {})
    if isinstance(sections, dict):
        for key in (
            str(unit.get("section_number", "")),
            str(unit.get("section_title", "")),
            str(unit.get("section_id", "")),
        ):
            if key and key in sections:
                entry = sections[key]
                if isinstance(entry, dict):
                    candidates.append((entry.get("concept_awards", []), str(entry.get("mapping_confidence", "medium")), "section"))
                else:
                    candidates.append((entry, "medium", "section"))
                break
    candidates.append((metadata.get("default_concept_awards"), str(metadata.get("mapping_confidence", "low")), "track"))

    for raw, confidence, source in candidates:
        mappings = _normalise(raw)
        if mappings:
            confidence = confidence.lower() if confidence.lower() in CONFIDENCE else "medium"
            if capability_id:
                validate_concept_ids(capability_id, mappings)
            return {
                "capability_id": capability_id,
                "concept_awards": mappings,
                "mapping_confidence": confidence,
                "mapping_source": source,
            }

    return {
        "capability_id": capability_id,
        "concept_awards": [],
        "mapping_confidence": "low",
        "mapping_source": "capability_only",
    }


def distribute_concept_xp(total_xp: int, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    awards = _normalise(mappings)
    if not awards:
        return []
    exact = [total_xp * item["weight"] for item in awards]
    values = [math.floor(value) for value in exact]
    remainder = total_xp - sum(values)
    ranked = sorted(range(len(awards)), key=lambda i: (exact[i] - values[i], -i), reverse=True)
    for index in ranked[:remainder]:
        values[index] += 1
    return [
        {"concept_id": item["concept_id"], "weight": round(item["weight"], 6), "xp": values[index]}
        for index, item in enumerate(awards)
        if values[index] > 0 or total_xp == 0
    ]


def calculate_level(xp: int) -> int:
    return 0 if xp <= 0 else (xp // 100) + 1


def update_concept_progress(
    capability_id: str,
    distribution: list[dict[str, Any]],
    *,
    confidence: str,
    source: str,
) -> dict[str, Any]:
    if not distribution:
        return {"updated": 0, "capability_only": True}
    graph = load_json(GRAPH_PATH, {"schema_version": 2, "capabilities": {}, "concept_progress": {}})
    capability = graph.get("capabilities", {}).get(capability_id)
    if not isinstance(capability, dict):
        raise ValueError(f"Capability is not defined in capability_graph.json: {capability_id}")
    progress = graph.setdefault("concept_progress", {})
    for award in distribution:
        concept_id = award["concept_id"]
        record = progress.setdefault(concept_id, {"xp": 0, "level": 0, "status": "Not Started"})
        record["xp"] = int(record.get("xp", 0)) + int(award["xp"])
        record["level"] = calculate_level(record["xp"])
        record["status"] = "Developing" if record["xp"] > 0 else "Not Started"
        record["last_mapping_confidence"] = confidence
        record["last_source"] = source
    save_json(GRAPH_PATH, graph)
    return {"updated": len(distribution), "capability_only": False}

