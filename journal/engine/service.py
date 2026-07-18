from __future__ import annotations
import re
from datetime import date, datetime, timezone
from pathlib import Path
from shared.config.paths import JOURNAL_ENTRIES, JOURNAL_INDEXES
from shared.libraries.json_store import load_json, save_json

INDEX_PATH = JOURNAL_INDEXES / "entries.json"

def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "entry"

def create_entry(
    title: str,
    body: str = "",
    tags: list[str] | None = None,
    entry_date: date | None = None,
) -> Path:
    day = entry_date or date.today()
    folder = JOURNAL_ENTRIES / f"{day:%Y}" / f"{day:%m}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day.isoformat()}-{slugify(title)}.md"
    created = datetime.now(timezone.utc).isoformat()
    tag_list = tags or []
    path.write_text(
        "---\n"
        f'title: "{title}"\n'
        f"date: {day.isoformat()}\n"
        f"created_at: {created}\n"
        f'tags: {", ".join(tag_list)}\n'
        "---\n\n"
        f"# {title}\n\n"
        f"{body.strip()}\n",
        encoding="utf-8",
    )
    rebuild_index()
    return path

def rebuild_index() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(JOURNAL_ENTRIES.rglob("*.md"), reverse=True):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem
        match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.MULTILINE)
        if match:
            title = match.group(1)
        tags: list[str] = []
        tag_match = re.search(r"^tags:\s*(.*?)\s*$", text, re.MULTILINE)
        if tag_match:
            tags = [
                tag.strip()
                for tag in tag_match.group(1).split(",")
                if tag.strip()
            ]
        entries.append(
            {
                "title": title,
                "path": path.relative_to(JOURNAL_ENTRIES).as_posix(),
                "tags": tags,
            }
        )
    save_json(
        INDEX_PATH,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        },
    )
    return entries

def list_entries() -> list[dict[str, object]]:
    payload = load_json(INDEX_PATH)
    if isinstance(payload, dict):
        return payload.get("entries", [])
    return rebuild_index()
