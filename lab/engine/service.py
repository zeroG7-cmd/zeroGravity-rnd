from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .database import initialize_database, session

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def create_experiment(
    experiment_id: str,
    title: str,
    project: str = "shadow",
    domain: str = "",
    hypothesis: str = "",
    method: str = "",
) -> None:
    initialize_database()
    stamp = now()
    with session() as database:
        database.execute(
            """
            INSERT INTO experiments (
                experiment_id, title, project, domain, status,
                hypothesis, method, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id, title, project, domain, "planned",
                hypothesis, method, stamp, stamp,
            ),
        )

def list_experiments() -> list[dict[str, Any]]:
    initialize_database()
    with session() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC"
            )
        ]

def log_test(
    test_name: str,
    component: str = "",
    result: str = "",
    notes: str = "",
    source: str = "simulation",
    timestamp: str | None = None,
) -> None:
    initialize_database()
    with session() as database:
        database.execute(
            """
            INSERT INTO test_logs (
                test_name, component, result, notes, source, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                test_name, component, result, notes,
                source, timestamp or now(),
            ),
        )

def counts() -> dict[str, int]:
    initialize_database()
    tables = (
        "experiments", "test_logs", "telemetry_logs",
        "mission_logs", "perception_logs", "sensor_logs",
    )
    with session() as database:
        return {
            table: int(
                database.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )
            for table in tables
        }
