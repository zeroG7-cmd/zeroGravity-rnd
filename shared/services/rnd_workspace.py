"""Read-only workspace service for Zero Command.

This module is the public integration boundary between ``zeroGravity-rnd`` and
external interfaces.  It returns plain dictionaries so callers do not need to
know the repository's database schemas or directory layout.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from shared.config.paths import (
    JOURNAL_ENTRIES,
    LAB_DB,
    OPERATOR_CAPABILITIES,
    OPERATOR_ROOT,
    PROJECTS_ROOT,
    REPO_ROOT,
    SHADOW_DATA,
    SHADOW_ROOT,
    SHADOW_URDF,
)
from shared.libraries.json_store import load_json

CAD_EXTENSIONS = {".step", ".stp", ".stl", ".iges", ".igs", ".f3d", ".f3z", ".sldprt"}
URDF_EXTENSIONS = {".urdf", ".xacro", ".xml"}


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(LAB_DB)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _scalar(query: str, parameters: tuple[Any, ...] = ()) -> int:
    if not LAB_DB.exists():
        return 0
    try:
        with _connect() as connection:
            row = connection.execute(query, parameters).fetchone()
            return int(row[0]) if row else 0
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return 0


def _rows(query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if not LAB_DB.exists():
        return []
    try:
        with _connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]
    except (sqlite3.Error, OSError):
        return []


def _count_files(root: Path, extensions: set[str] | None = None) -> int:
    if not root.exists():
        return 0
    return sum(
        1
        for path in root.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
        and (extensions is None or path.suffix.lower() in extensions)
    )


def _latest_file(roots: Iterable[Path]) -> dict[str, str] | None:
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(
                path for path in root.rglob("*")
                if path.is_file() and path.name != ".gitkeep"
            )
    if not files:
        return None
    try:
        latest = max(files, key=lambda path: path.stat().st_mtime)
        stamp = datetime.fromtimestamp(latest.stat().st_mtime)
        return {
            "name": latest.name,
            "relative_path": latest.relative_to(REPO_ROOT).as_posix(),
            "modified": stamp.strftime("%d %b %Y · %H:%M"),
        }
    except (OSError, ValueError):
        return None


def _normalise_result(value: Any) -> str:
    result = str(value or "").strip().lower()
    return result if result in {"pass", "fail"} else "pending"


def get_tests(limit: int = 6) -> dict[str, Any]:
    total = _scalar("SELECT COUNT(*) FROM test_runs")
    passed = _scalar("SELECT COUNT(*) FROM test_runs WHERE LOWER(TRIM(result))='pass'")
    failed = _scalar("SELECT COUNT(*) FROM test_runs WHERE LOWER(TRIM(result))='fail'")
    recent = _rows(
        """
        SELECT id, test_name, component, source, result, notes, timestamp
        FROM test_runs ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )
    for item in recent:
        item["result_class"] = _normalise_result(item.get("result"))
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pending": max(total - passed - failed, 0),
        "success_rate": round((passed / total) * 100) if total else 0,
        "recent": recent,
    }


def get_experiments(limit: int = 8) -> dict[str, Any]:
    items = _rows(
        """
        SELECT id, experiment_name, category, status, hypothesis,
               conclusion, created_at, updated_at
        FROM experiments
        ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT ?
        """,
        (limit,),
    )
    return {
        "total": _scalar("SELECT COUNT(*) FROM experiments"),
        "active": _scalar(
            "SELECT COUNT(*) FROM experiments WHERE LOWER(TRIM(status)) IN ('active','running','in progress')"
        ),
        "recent": items,
    }


def get_simulation() -> dict[str, int]:
    return {
        "runs": _scalar("SELECT COUNT(*) FROM simulation_runs"),
        "completed_runs": _scalar(
            "SELECT COUNT(*) FROM simulation_runs WHERE LOWER(TRIM(status))='completed'"
        ),
        "telemetry_samples": _scalar("SELECT COUNT(*) FROM simulated_telemetry"),
    }


def get_operator() -> dict[str, Any]:
    stats_candidates = [
        OPERATOR_ROOT / "hubs" / "learning" / "stats" / "learning_stats.json",
        REPO_ROOT / "learning" / "operator" / "stats.json",
    ]
    stats: dict[str, Any] = {}
    for candidate in stats_candidates:
        payload = load_json(candidate, {}) or {}
        if isinstance(payload, dict) and payload:
            stats = payload
            break
    capabilities = load_json(OPERATOR_CAPABILITIES / "competencies.json", {}) or {}
    payload = capabilities.get("competencies", capabilities) if isinstance(capabilities, dict) else {}
    return {
        "online": OPERATOR_ROOT.exists(),
        "level": int(stats.get("level", stats.get("operator_level", 0)) or 0),
        "xp": int(stats.get("total_xp", stats.get("xp", 0)) or 0),
        "competencies": len(payload) if isinstance(payload, (dict, list)) else 0,
    }


def get_journal() -> dict[str, Any]:
    entries = [
        path for path in JOURNAL_ENTRIES.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ] if JOURNAL_ENTRIES.exists() else []
    latest = _latest_file([JOURNAL_ENTRIES])
    return {"entries": len(entries), "latest": latest}


def get_projects() -> list[dict[str, Any]]:
    if not PROJECTS_ROOT.exists():
        return []
    projects = []
    for path in sorted(PROJECTS_ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        projects.append({
            "id": path.name,
            "name": path.name.replace("_", " ").replace("-", " ").title(),
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "files": _count_files(path),
            "status": "online",
        })
    return projects


def get_shadow() -> dict[str, Any]:
    return {
        "database_online": LAB_DB.exists(),
        "vehicle": {
            "name": "Shadow MK1",
            "type": "Companion Aerial Robot",
            "model": "MK1",
            "status": "Development" if SHADOW_ROOT.exists() else "Unavailable",
            "last_seen": None,
        },
        "telemetry": {
            "samples": _scalar("SELECT COUNT(*) FROM telemetry_logs"),
            "latest": None,
        },
        "missions": {
            "total": _scalar("SELECT COUNT(*) FROM mission_logs"),
            "completed": _scalar(
                "SELECT COUNT(*) FROM mission_logs WHERE LOWER(TRIM(result)) IN ('completed','pass','success')"
            ),
        },
        "faults": {"open": 0},
        "maintenance": {"records": 0},
        "camera_files": _count_files(SHADOW_DATA / "hardware" / "camera"),
        "sensor_records": _scalar("SELECT COUNT(*) FROM sensor_logs"),
    }


def get_repository() -> dict[str, Any]:
    required = [LAB_DB, OPERATOR_ROOT, PROJECTS_ROOT, SHADOW_ROOT]
    available = sum(path.exists() for path in required)
    return {
        "repo_online": REPO_ROOT.exists(),
        "healthy": available == len(required),
        "health_score": round((available / len(required)) * 100),
        "repo_path": str(REPO_ROOT),
        "hardware_files": _count_files(SHADOW_DATA / "hardware"),
        "simulation_files": _count_files(SHADOW_DATA / "simulation"),
        "archived_experiments": _count_files(REPO_ROOT / "lab" / "archive"),
        "cad_assets": _count_files(SHADOW_ROOT / "cad", CAD_EXTENSIONS),
        "urdf_assets": _count_files(SHADOW_URDF, URDF_EXTENSIONS),
        "latest_artifact": _latest_file([REPO_ROOT / "lab", SHADOW_DATA, JOURNAL_ENTRIES]),
    }


def get_workspace_data() -> dict[str, Any]:
    """Return the complete, read-only payload consumed by Zero Command."""
    tests = get_tests()
    experiments = get_experiments()
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "research": {
            "database_online": LAB_DB.exists(),
            "database_path": str(LAB_DB),
            "tests": tests,
            "experiments": experiments["recent"],
            "experiment_summary": {
                "total": experiments["total"],
                "active": experiments["active"],
            },
            "simulation": get_simulation(),
        },
        "repository": get_repository(),
        "operator": get_operator(),
        "journal": get_journal(),
        "projects": get_projects(),
        "shadow": get_shadow(),
    }
