"""Runtime bootstrap helpers."""
from __future__ import annotations
import sys
from pathlib import Path
from .paths import REPO_ROOT, ensure_runtime_directories

def bootstrap() -> Path:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    ensure_runtime_directories()
    return REPO_ROOT
