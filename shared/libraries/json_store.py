from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    # newline="" stops Python's default universal-newline translation, which
    # on Windows silently turns every "\n" written here into "\r\n" on disk.
    # This repo's JSON was authored (and is always shipped) with plain LF -
    # without this, every file this function touches (competencies.json,
    # learning_stats.json, progress.json, etc.) comes out fully CRLF the
    # moment it's saved from a Windows checkout, so git sees every single
    # line as changed on the very next diff even when no value actually
    # changed - real edits become indistinguishable from line-ending noise.
    # indent=4 to match the convention already established across the rest
    # of the repo (learning/engine/*'s own JSON writers, and everything
    # already committed for competencies.json/learning_stats.json before
    # this module existed) - this used to be indent=2, which disagreed with
    # every one of those and was the actual cause of a real, live formatting
    # mismatch on competencies.json/learning_stats.json (the two files both
    # this module and learning/engine/stats.py write).
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)
