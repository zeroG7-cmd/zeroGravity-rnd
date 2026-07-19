"""Models for immutable journal entries and their structured manifests."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

JOURNAL_SCHEMA_VERSION = 1
ALLOWED_ENTRY_TYPES = {
    "reflection",
    "insight",
    "epiphany",
    "technical",
    "business",
    "test_log",
    "learning",
    "planning",
    "spiritual",
    "creative",
    "decision",
    "problem",
    "personal",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalise_string_list(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class JournalEvidence:
    """A lightweight reference to evidence stored elsewhere."""

    evidence_type: str
    reference: str
    label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_type.strip():
            raise ValueError("evidence_type must not be empty")
        if not self.reference.strip():
            raise ValueError("reference must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class JournalEntryRequest:
    """User-authored content plus explicit structured mapping selections."""

    title: str
    body: str
    entry_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    xp_targets: tuple[Mapping[str, Any], ...] = ()
    evidence: tuple[JournalEvidence, ...] = ()
    entry_date: date | None = None
    base_xp: int = 0

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.body.strip():
            raise ValueError("body must not be empty")
        unknown = set(self.entry_types) - ALLOWED_ENTRY_TYPES
        if unknown:
            raise ValueError(f"Unsupported journal entry types: {sorted(unknown)}")
        if self.base_xp < 0:
            raise ValueError("base_xp cannot be negative")
        if self.base_xp and not self.xp_targets:
            raise ValueError("xp_targets are required when base_xp is greater than zero")


@dataclass(frozen=True, slots=True)
class JournalManifest:
    """Structured companion to the untouched Markdown entry."""

    entry_id: str
    title: str
    entry_date: str
    created_at: str
    markdown_path: str
    manifest_path: str
    entry_types: tuple[str, ...]
    tags: tuple[str, ...]
    projects: tuple[str, ...]
    domains: tuple[str, ...]
    concepts: tuple[str, ...]
    capabilities: tuple[str, ...]
    evidence: tuple[JournalEvidence, ...]
    base_xp: int
    xp_targets: tuple[Mapping[str, Any], ...]
    event_id: str | None = None
    receipt_id: str | None = None
    status: str = "recorded"
    schema_version: int = JOURNAL_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: JournalEntryRequest,
        markdown_path: str,
        manifest_path: str,
    ) -> "JournalManifest":
        day = request.entry_date or date.today()
        return cls(
            entry_id=f"journal_{uuid4().hex}",
            title=request.title.strip(),
            entry_date=day.isoformat(),
            created_at=utc_now_iso(),
            markdown_path=markdown_path,
            manifest_path=manifest_path,
            entry_types=normalise_string_list(request.entry_types),
            tags=normalise_string_list(request.tags),
            projects=normalise_string_list(request.projects),
            domains=normalise_string_list(request.domains),
            concepts=normalise_string_list(request.concepts),
            capabilities=normalise_string_list(request.capabilities),
            evidence=request.evidence,
            base_xp=request.base_xp,
            xp_targets=request.xp_targets,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload
