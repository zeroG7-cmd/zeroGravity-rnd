"""Canonical, machine-independent paths for the zeroGravity R&D repository."""
from __future__ import annotations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_ROOT = REPO_ROOT / "shared"
REPORTS_ROOT = REPO_ROOT / "reports"

OPERATOR_ROOT = REPO_ROOT / "operator_core"
OPERATOR_CAPABILITIES = OPERATOR_ROOT / "capabilities"
OPERATOR_EVENTS = OPERATOR_ROOT / "events"
OPERATOR_HUBS = OPERATOR_ROOT / "hubs"
OPERATOR_PROFILE = OPERATOR_ROOT / "profile"
OPERATOR_PROFILE_DATA = OPERATOR_PROFILE / "data"

LEARNING_ROOT = REPO_ROOT / "learning"
LEARNING_ENGINE = LEARNING_ROOT / "engine"
LEARNING_TRACKS = LEARNING_ROOT / "tracks"
LEARNING_RESOURCES = LEARNING_ROOT / "resources"
LEARNING_CATALOG = LEARNING_ROOT / "catalog"
LEARNING_CONFIG = LEARNING_ROOT / "config"

FITNESS_ROOT = REPO_ROOT / "fitness"
FITNESS_ENGINE = FITNESS_ROOT / "engine"
FITNESS_ROUTINES = FITNESS_ROOT / "routines"
FITNESS_HUB = OPERATOR_HUBS / "fitness"
FITNESS_STATS_DIR = FITNESS_HUB / "stats"
FITNESS_HISTORY_DIR = FITNESS_HUB / "history"
FITNESS_PROGRESS_DIR = FITNESS_HUB / "progress"
FITNESS_HISTORY_FILE = FITNESS_HISTORY_DIR / "fitness_history.json"
FITNESS_PROGRESS_FILE = FITNESS_PROGRESS_DIR / "fitness_progress.json"

LAB_ROOT = REPO_ROOT / "lab"
LAB_DATABASE = LAB_ROOT / "database"
LAB_DB = LAB_DATABASE / "zerogravity_rnd.db"
LAB_EXPERIMENTS = LAB_ROOT / "experiments"
LAB_ARCHIVE = LAB_ROOT / "archive"
LAB_REPORTS = LAB_ROOT / "reports"
LAB_DATASETS = LAB_ROOT / "datasets"

# Oct 24, 2026 - shadow_ws/src/shadow_drone/nodes/telemetry_publisher.py
# writes Shadow's live sim snapshot here at ~20Hz (connected/armed/mode,
# plus odometry/rc_out/imu when available), atomically (temp file +
# os.replace). This repo's own get_shadow() never actually read it -
# "telemetry.latest" was hardcoded to None - which is why Zero Command's
# Simulation Bay HUD was permanently stuck on "Awaiting live telemetry"
# and, since the FPV camera panel is gated on that same signal, the front
# camera never showed either, even though the camera stream itself was
# working fine on :5002/video the whole time. Matches
# ~/shadow_sim_runtime living as a sibling of this repo and shadow_ws
# under the user's home directory, not a guess - confirmed against
# telemetry_publisher.py's own DEFAULT_OUTPUT_PATH.
SHADOW_SIM_RUNTIME_ROOT = REPO_ROOT.parent / "shadow_sim_runtime"
SHADOW_TELEMETRY_JSON = SHADOW_SIM_RUNTIME_ROOT / "telemetry" / "latest.json"

JOURNAL_ROOT = REPO_ROOT / "journal"
JOURNAL_ENTRIES = JOURNAL_ROOT / "entries"
JOURNAL_ARCHIVE = JOURNAL_ROOT / "archive"
JOURNAL_INDEXES = JOURNAL_ROOT / "indexes"
JOURNAL_SUMMARIES = JOURNAL_ROOT / "summaries"
JOURNAL_LOGS = JOURNAL_ROOT / "logs"

PROJECTS_ROOT = REPO_ROOT / "projects"
SHADOW_ROOT = PROJECTS_ROOT / "shadow"
SHADOW_DATA = SHADOW_ROOT / "data"
SHADOW_HARDWARE_DATA = SHADOW_DATA / "hardware"
SHADOW_SIMULATION_DATA = SHADOW_DATA / "simulation"
SHADOW_SIMULATION_VIDEO = SHADOW_SIMULATION_DATA / "camera" / "Video.mov"
SHADOW_DOCS = SHADOW_ROOT / "docs"
SHADOW_CV = SHADOW_ROOT / "perception" / "computer_vision"
SHADOW_URDF = SHADOW_ROOT / "simulation" / "urdf"

REQUIRED_RUNTIME_DIRECTORIES = (
    LAB_DATABASE, LAB_EXPERIMENTS, LAB_REPORTS, LAB_DATASETS,
    JOURNAL_ENTRIES, JOURNAL_ARCHIVE, JOURNAL_INDEXES, JOURNAL_SUMMARIES, JOURNAL_LOGS,
    OPERATOR_EVENTS / "receipts",
    OPERATOR_PROFILE_DATA,
    FITNESS_STATS_DIR, FITNESS_HISTORY_DIR, FITNESS_PROGRESS_DIR,
    SHADOW_HARDWARE_DATA / "bags", SHADOW_HARDWARE_DATA / "camera",
    SHADOW_HARDWARE_DATA / "logs", SHADOW_HARDWARE_DATA / "results",
    SHADOW_SIMULATION_DATA / "bags", SHADOW_SIMULATION_DATA / "camera",
    SHADOW_SIMULATION_DATA / "logs", SHADOW_SIMULATION_DATA / "results",
)

def ensure_runtime_directories() -> None:
    for directory in REQUIRED_RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)

def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)

