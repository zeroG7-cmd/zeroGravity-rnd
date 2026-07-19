"""Universal Journal Engine.

The engine preserves the author's Markdown, writes a structured manifest,
emits an Operator event, and optionally requests a shared XP distribution.
It does not own progression rules or mutate Operator stats directly.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from journal.engine.models import (
    JournalEntryRequest,
    JournalEvidence,
    JournalManifest,
    normalise_string_list,
)
from operator_core.distribution.service import DistributionService
from operator_core.events.models import OperatorEvent
from operator_core.events.service import EventLedger
from shared.config.paths import JOURNAL_ENTRIES, JOURNAL_INDEXES, REPO_ROOT
from shared.libraries.json_store import load_json, save_json

INDEX_PATH = JOURNAL_INDEXES / "entries.json"


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "entry"


class JournalService:
    """Create and query journal entries using injectable storage services."""

    def __init__(
        self,
        *,
        entries_root: Path = JOURNAL_ENTRIES,
        index_path: Path = INDEX_PATH,
        repo_root: Path = REPO_ROOT,
        ledger: EventLedger | None = None,
        distributor: DistributionService | None = None,
    ) -> None:
        self.entries_root = Path(entries_root)
        self.index_path = Path(index_path)
        self.repo_root = Path(repo_root)
        self.ledger = ledger or EventLedger()
        self.distributor = distributor or DistributionService(ledger=self.ledger)

    def create(self, request: JournalEntryRequest) -> JournalManifest:
        day = request.entry_date or date.today()
        folder = self.entries_root / f"{day:%Y}" / f"{day:%m}"
        folder.mkdir(parents=True, exist_ok=True)

        stem = self._available_stem(folder, day.isoformat(), slugify(request.title))
        markdown_path = folder / f"{stem}.md"
        manifest_path = folder / f"{stem}.json"

        manifest = JournalManifest.create(
            request=request,
            markdown_path=self._relative(markdown_path),
            manifest_path=self._relative(manifest_path),
        )
        self._write_markdown(markdown_path, request, manifest)
        save_json(manifest_path, manifest.to_dict())

        event = self._emit_created_event(manifest)
        manifest = replace(manifest, event_id=event.event_id)
        save_json(manifest_path, manifest.to_dict())

        if request.base_xp > 0:
            receipt = self.distributor.distribute_event(event)
            manifest = replace(manifest, receipt_id=receipt.receipt_id, status="processed")
            save_json(manifest_path, manifest.to_dict())

        self.rebuild_index()
        return manifest

    def get(self, entry_id: str) -> dict[str, Any] | None:
        for record in self.list_entries():
            if record.get("entry_id") != entry_id:
                continue
            manifest_path = self.repo_root / str(record["manifest_path"])
            payload = load_json(manifest_path, None)
            return payload if isinstance(payload, dict) else None
        return None

    def list_entries(self) -> list[dict[str, Any]]:
        payload = load_json(self.index_path, None)
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            return list(payload["entries"])
        return self.rebuild_index()

    def rebuild_index(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.entries_root.rglob("*.json"), reverse=True):
            payload = load_json(path, None)
            if not isinstance(payload, dict) or "entry_id" not in payload:
                continue
            entries.append(
                {
                    "entry_id": payload["entry_id"],
                    "title": payload.get("title", path.stem),
                    "entry_date": payload.get("entry_date"),
                    "created_at": payload.get("created_at"),
                    "entry_types": payload.get("entry_types", []),
                    "tags": payload.get("tags", []),
                    "projects": payload.get("projects", []),
                    "domains": payload.get("domains", []),
                    "concepts": payload.get("concepts", []),
                    "capabilities": payload.get("capabilities", []),
                    "markdown_path": payload.get("markdown_path"),
                    "manifest_path": payload.get("manifest_path"),
                    "event_id": payload.get("event_id"),
                    "receipt_id": payload.get("receipt_id"),
                    "status": payload.get("status", "recorded"),
                }
            )
        entries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        save_json(self.index_path, {"schema_version": 1, "entries": entries})
        return entries

    def _emit_created_event(self, manifest: JournalManifest) -> OperatorEvent:
        payload = {
            "entry_id": manifest.entry_id,
            "title": manifest.title,
            "entry_date": manifest.entry_date,
            "entry_types": list(manifest.entry_types),
            "tags": list(manifest.tags),
            "projects": list(manifest.projects),
            "domains": list(manifest.domains),
            "concepts": list(manifest.concepts),
            "capabilities": list(manifest.capabilities),
            "evidence": [item.to_dict() for item in manifest.evidence],
            "markdown_path": manifest.markdown_path,
            "manifest_path": manifest.manifest_path,
            "base_xp": manifest.base_xp,
            "xp_targets": [dict(item) for item in manifest.xp_targets],
        }
        return self.ledger.append(
            OperatorEvent(
                event_type="journal_created",
                source="journal.engine",
                payload=payload,
                occurred_at=manifest.created_at,
                idempotency_key=f"journal_created:{manifest.entry_id}",
                correlation_id=manifest.entry_id,
            )
        )

    @staticmethod
    def _available_stem(folder: Path, day: str, slug: str) -> str:
        base = f"{day}-{slug}"
        candidate = base
        counter = 2
        while (folder / f"{candidate}.md").exists() or (folder / f"{candidate}.json").exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _write_markdown(
        path: Path,
        request: JournalEntryRequest,
        manifest: JournalManifest,
    ) -> None:
        # The body is written once and is never rewritten during later processing.
        metadata_lines = [
            "---",
            f'entry_id: "{manifest.entry_id}"',
            f'title: "{manifest.title.replace(chr(34), chr(39))}"',
            f"date: {manifest.entry_date}",
            f"created_at: {manifest.created_at}",
            f"types: {', '.join(manifest.entry_types)}",
            f"tags: {', '.join(manifest.tags)}",
            "---",
            "",
            f"# {manifest.title}",
            "",
            request.body.strip(),
            "",
        ]
        path.write_text("\n".join(metadata_lines), encoding="utf-8", newline="\n")


_default_service = JournalService()


def create_entry(
    title: str,
    body: str = "",
    tags: list[str] | None = None,
    entry_date: date | None = None,
    *,
    entry_types: list[str] | None = None,
    projects: list[str] | None = None,
    domains: list[str] | None = None,
    concepts: list[str] | None = None,
    capabilities: list[str] | None = None,
    xp_targets: Iterable[Mapping[str, Any]] | None = None,
    evidence: Iterable[JournalEvidence | Mapping[str, Any]] | None = None,
    base_xp: int = 0,
) -> Path:
    """Compatibility entry point returning the Markdown path as before."""
    evidence_items: list[JournalEvidence] = []
    for item in evidence or ():
        if isinstance(item, JournalEvidence):
            evidence_items.append(item)
        else:
            evidence_items.append(
                JournalEvidence(
                    evidence_type=str(item["evidence_type"]),
                    reference=str(item["reference"]),
                    label=str(item.get("label", "")),
                    metadata=dict(item.get("metadata", {})),
                )
            )
    request = JournalEntryRequest(
        title=title,
        body=body,
        entry_types=normalise_string_list(entry_types),
        tags=normalise_string_list(tags),
        projects=normalise_string_list(projects),
        domains=normalise_string_list(domains),
        concepts=normalise_string_list(concepts),
        capabilities=normalise_string_list(capabilities),
        xp_targets=tuple(dict(item) for item in (xp_targets or ())),
        evidence=tuple(evidence_items),
        entry_date=entry_date,
        base_xp=base_xp,
    )
    manifest = _default_service.create(request)
    return REPO_ROOT / manifest.markdown_path


def rebuild_index() -> list[dict[str, Any]]:
    return _default_service.rebuild_index()


def list_entries() -> list[dict[str, Any]]:
    return _default_service.list_entries()
