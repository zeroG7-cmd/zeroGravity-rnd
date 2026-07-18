"""Ingest Shadow hardware and simulation result files into the Lab database."""
from __future__ import annotations
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.engine.service import log_test
from shared.config.paths import SHADOW_HARDWARE_DATA, SHADOW_SIMULATION_DATA

FOLDERS = {
    "hardware": SHADOW_HARDWARE_DATA / "results",
    "simulation": SHADOW_SIMULATION_DATA / "results",
}

def parse_file(path: Path, source: str) -> dict[str, str]:
    data = {"Source": source}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data

def run_ingestion() -> int:
    count = 0
    for source, folder in FOLDERS.items():
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".txt", ".md"}:
                continue
            data = parse_file(path, source)
            log_test(
                data.get("Test", path.stem),
                data.get("Component", ""),
                data.get("Result", ""),
                data.get("Notes", ""),
                source,
                data.get("Time") or None,
            )
            print(f"Ingested ({source}): {path.name}")
            count += 1
    print(f"Ingestion complete: {count} file(s).")
    return count

if __name__ == "__main__":
    run_ingestion()
