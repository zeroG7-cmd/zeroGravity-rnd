"""SQLite schema and connection management for the reusable R&D Lab."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from shared.config.paths import LAB_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 experiment_id TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL,
 project TEXT,
 domain TEXT,
 status TEXT NOT NULL DEFAULT 'planned',
 hypothesis TEXT,
 method TEXT,
 result TEXT,
 notes TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS test_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 test_name TEXT,
 component TEXT,
 result TEXT,
 notes TEXT,
 source TEXT,
 timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telemetry_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project TEXT NOT NULL DEFAULT 'shadow',
 battery REAL, altitude REAL, speed REAL, flight_mode TEXT,
 timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project TEXT NOT NULL DEFAULT 'shadow',
 mission_name TEXT, start_time TEXT, end_time TEXT,
 result TEXT, notes TEXT, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS perception_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project TEXT NOT NULL DEFAULT 'shadow',
 object_name TEXT, confidence REAL, camera_source TEXT,
 timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sensor_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project TEXT NOT NULL DEFAULT 'shadow',
 sensor_name TEXT, status TEXT, value REAL,
 timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 experiment_id TEXT, journal_entry TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

def connect() -> sqlite3.Connection:
    LAB_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(LAB_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def initialize_database() -> None:
    with session() as connection:
        connection.executescript(SCHEMA)
