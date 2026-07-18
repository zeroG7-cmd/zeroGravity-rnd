"""
Operator Zero Skill Tree Synchronizer — Knowledge Graph Edition
===============================================================

The Markdown file is the human-editable source of truth.

This tool generates:

1. operator_core/capabilities/skill_tree.json
   - Stores the hierarchy.
   - Leaf nodes contain competency references, not XP.

2. operator_core/capabilities/competencies.json
   - Stores each competency's XP and level exactly once.

Markdown syntax
---------------
Ordinary competency:

    - Python

Explicitly shared competency:

    - @HTTP

Repeated @HTTP entries anywhere in the tree point to the same competency ID.

ID rules
--------
- Shared competency:
      @HTTP -> "http"

- Ordinary competency:
      Python under INT > Software Engineering > Programming Languages
      -> "int.software_engineering.programming_languages.python"

This prevents unrelated competencies with the same display name from being
merged accidentally.

Migration
---------
The script can migrate progression from the previous embedded-XP format:

    "Python": {
        "name": "Python",
        "node_type": "skill",
        "xp": 100,
        "level": 1
    }

For shared competencies found in several old locations, the migration preserves
the highest XP and level instead of summing them, which avoids accidental
double-counting.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MARKDOWN_PATH = PROJECT_ROOT / "operator_core" / "capabilities" / "skill_tree.md"
DEFAULT_TREE_PATH = PROJECT_ROOT / "operator_core" / "capabilities" / "skill_tree.json"
DEFAULT_COMPETENCIES_PATH = (
    PROJECT_ROOT / "operator_core" / "capabilities" / "competencies.json"
)
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "operator_core" / "capabilities" / "backups"

BULLET_PATTERN = re.compile(r"^(?P<indent>[ \t]*)[-*+]\s+(?P<name>.+?)\s*$")
SUSPICIOUS_ENDING_PATTERN = re.compile(r"[#:]$")
NON_ID_CHARACTER_PATTERN = re.compile(r"[^a-z0-9]+")


class SkillTreeError(Exception):
    """Raised when source or generated skill-tree data is invalid."""


@dataclass
class TreeNode:
    """One node parsed from the Markdown hierarchy."""

    name: str
    line_number: int
    is_shared: bool = False
    children: list["TreeNode"] = field(default_factory=list)


@dataclass
class Progress:
    """Stored progression for one competency."""

    xp: int = 0
    level: int = 0


@dataclass
class ChangeReport:
    """Human-readable synchronization report."""

    added_tree_paths: list[str] = field(default_factory=list)
    preserved_tree_paths: list[str] = field(default_factory=list)
    removed_tree_paths: list[str] = field(default_factory=list)

    added_competencies: list[str] = field(default_factory=list)
    preserved_competencies: list[str] = field(default_factory=list)
    removed_competencies: list[str] = field(default_factory=list)

    shared_references: list[str] = field(default_factory=list)
    migrated_progress: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize Markdown into skill_tree.json and competencies.json."
        )
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=DEFAULT_MARKDOWN_PATH,
        help=f"Markdown source (default: {DEFAULT_MARKDOWN_PATH})",
    )
    parser.add_argument(
        "--tree-json",
        type=Path,
        default=DEFAULT_TREE_PATH,
        help=f"Tree JSON destination (default: {DEFAULT_TREE_PATH})",
    )
    parser.add_argument(
        "--competencies-json",
        type=Path,
        default=DEFAULT_COMPETENCIES_PATH,
        help=(
            "Competency registry destination "
            f"(default: {DEFAULT_COMPETENCIES_PATH})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed changes without writing files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 only when both generated files are synchronized.",
    )
    parser.add_argument(
        "--allow-removals",
        action="store_true",
        help=(
            "Allow tree paths or competencies missing from Markdown "
            "to be removed."
        ),
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create timestamped backups before writing.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    """Create a stable lowercase identifier component."""

    replacements = {
        "c++": "cpp",
        "c#": "csharp",
        "ci/cd": "ci_cd",
        "&": " and ",
    }

    normalized = value.strip().lower()
    normalized = replacements.get(normalized, normalized)
    normalized = normalized.replace("+", " plus ")
    normalized = normalized.replace("#", " sharp ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("&", " and ")
    normalized = NON_ID_CHARACTER_PATTERN.sub("_", normalized)
    normalized = normalized.strip("_")

    if not normalized:
        raise SkillTreeError(
            f"Could not create a competency ID from name: {value!r}"
        )

    return normalized


def competency_id_for(path: tuple[str, ...], node: TreeNode) -> str:
    """Return the stable competency ID for a leaf node."""

    if node.is_shared:
        return slugify(node.name)

    return ".".join(slugify(component) for component in (*path, node.name))


def leading_indent_width(raw_indent: str, line_number: int) -> int:
    if "\t" in raw_indent:
        raise SkillTreeError(
            f"Line {line_number}: tabs are not allowed. Use spaces only."
        )

    width = len(raw_indent)
    if width % 2 != 0:
        raise SkillTreeError(
            f"Line {line_number}: indentation must use multiples of 2 spaces; "
            f"found {width}."
        )

    return width


def validate_node_name(name: str, line_number: int) -> list[str]:
    warnings: list[str] = []

    if not name:
        raise SkillTreeError(f"Line {line_number}: empty bullet name.")

    if SUSPICIOUS_ENDING_PATTERN.search(name):
        warnings.append(
            f"Line {line_number}: '{name}' ends with punctuation that may "
            "be accidental."
        )

    if "  " in name:
        warnings.append(
            f"Line {line_number}: '{name}' contains repeated spaces."
        )

    common_corrections = {
        "algorithoms": "Algorithms",
        "complexity": "Complexity",
        "linux": "Linux",
        "mechanics of materials": "Mechanics of Materials",
    }
    corrected = common_corrections.get(name.lower())
    if corrected is not None and name != corrected:
        warnings.append(
            f"Line {line_number}: consider renaming '{name}' to '{corrected}'."
        )

    return warnings


def parse_markdown(markdown_path: Path) -> tuple[list[TreeNode], list[str]]:
    """Parse nested Markdown bullets at arbitrary depth."""

    if not markdown_path.exists():
        raise SkillTreeError(f"Markdown file not found: {markdown_path}")

    roots: list[TreeNode] = []
    stack: list[tuple[int, TreeNode]] = []
    warnings: list[str] = []
    seen_paths: set[tuple[str, ...]] = set()

    text = markdown_path.read_text(encoding="utf-8")

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        match = BULLET_PATTERN.match(raw_line)
        if match is None:
            raise SkillTreeError(
                f"Line {line_number}: unsupported content:\n"
                f"    {raw_line}\n"
                "Use headings, blank lines, and nested Markdown bullets only."
            )

        indent = leading_indent_width(match.group("indent"), line_number)
        depth = indent // 2
        raw_name = match.group("name").strip()

        is_shared = raw_name.startswith("@")
        name = raw_name[1:].strip() if is_shared else raw_name

        if is_shared and not name:
            raise SkillTreeError(
                f"Line {line_number}: '@' must be followed by a competency name."
            )

        warnings.extend(validate_node_name(name, line_number))

        if depth > len(stack):
            raise SkillTreeError(
                f"Line {line_number}: indentation jumped more than one level."
            )

        while len(stack) > depth:
            stack.pop()

        node = TreeNode(
            name=name,
            line_number=line_number,
            is_shared=is_shared,
        )

        if depth == 0:
            if is_shared:
                raise SkillTreeError(
                    f"Line {line_number}: a main stat cannot be a shared "
                    "competency reference."
                )
            roots.append(node)
        else:
            if not stack:
                raise SkillTreeError(
                    f"Line {line_number}: '{name}' has no parent."
                )
            stack[-1][1].children.append(node)

        stack.append((depth, node))

        identity_name = f"@{name}" if is_shared else name
        current_path = tuple(
            (f"@{item[1].name}" if item[1].is_shared else item[1].name)
            for item in stack
        )
        if current_path in seen_paths:
            raise SkillTreeError(
                f"Line {line_number}: duplicate hierarchy path: "
                f"{' > '.join(current_path)}"
            )
        seen_paths.add(current_path)

    if not roots:
        raise SkillTreeError("No main-stat bullets were found.")

    def validate_shape(node: TreeNode, path: tuple[str, ...]) -> None:
        current_path = (*path, node.name)

        if node.is_shared and node.children:
            raise SkillTreeError(
                f"Line {node.line_number}: shared competency "
                f"'{' > '.join(current_path)}' cannot have children."
            )

        for child in node.children:
            validate_shape(child, current_path)

    for root in roots:
        validate_shape(root, ())

    top_names = [node.name for node in roots]
    duplicate_top_names = sorted(
        name for name in set(top_names) if top_names.count(name) > 1
    )
    if duplicate_top_names:
        raise SkillTreeError(
            "Duplicate main stats: " + ", ".join(duplicate_top_names)
        )

    return roots, warnings


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SkillTreeError(
            f"Invalid JSON in {path}: line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error

    if not isinstance(data, dict):
        raise SkillTreeError(f"JSON root must be an object: {path}")

    return data


def flatten_tree_nodes(
    stats: dict[str, Any],
) -> dict[tuple[str, ...], dict[str, Any]]:
    """Flatten both old and new skill-tree formats by display path."""

    flattened: dict[tuple[str, ...], dict[str, Any]] = {}

    def walk(
        nodes: dict[str, Any],
        parent_path: tuple[str, ...],
    ) -> None:
        for key, value in nodes.items():
            if not isinstance(value, dict):
                continue

            name = str(value.get("name", key))
            path = (*parent_path, name)
            flattened[path] = value

            children = value.get("children")
            if isinstance(children, dict):
                walk(children, path)

    walk(stats, ())
    return flattened


def flatten_markdown_paths(
    roots: Iterable[TreeNode],
) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()

    def walk(node: TreeNode, parent_path: tuple[str, ...]) -> None:
        current_path = (*parent_path, node.name)
        paths.add(current_path)
        for child in node.children:
            walk(child, current_path)

    for root in roots:
        walk(root, ())

    return paths


def load_registry_progress(
    competencies_data: dict[str, Any],
) -> dict[str, Progress]:
    registry = competencies_data.get("competencies", {})
    if not isinstance(registry, dict):
        raise SkillTreeError(
            "competencies.json must contain a 'competencies' object."
        )

    result: dict[str, Progress] = {}

    for competency_id, value in registry.items():
        if not isinstance(value, dict):
            continue

        result[competency_id] = Progress(
            xp=int(value.get("xp", 0)),
            level=int(value.get("level", 0)),
        )

    return result


def extract_old_embedded_progress(
    old_tree_nodes: dict[tuple[str, ...], dict[str, Any]],
) -> dict[tuple[str, ...], Progress]:
    """Read progression from the previous embedded leaf-node format."""

    result: dict[tuple[str, ...], Progress] = {}

    for path, node in old_tree_nodes.items():
        children = node.get("children")
        is_leaf = not isinstance(children, dict) or not children

        if not is_leaf:
            continue

        if "xp" in node or "level" in node:
            result[path] = Progress(
                xp=int(node.get("xp", 0)),
                level=int(node.get("level", 0)),
            )

    return result


def collect_leaf_definitions(
    roots: list[TreeNode],
) -> list[tuple[tuple[str, ...], TreeNode, str]]:
    leaves: list[tuple[tuple[str, ...], TreeNode, str]] = []

    def walk(node: TreeNode, parent_path: tuple[str, ...]) -> None:
        if node.children:
            current_path = (*parent_path, node.name)
            for child in node.children:
                walk(child, current_path)
            return

        competency_id = competency_id_for(parent_path, node)
        leaves.append((parent_path, node, competency_id))

    for root in roots:
        walk(root, ())

    return leaves


def determine_progress(
    competency_id: str,
    display_name: str,
    paths: list[tuple[str, ...]],
    existing_registry: dict[str, Progress],
    old_embedded: dict[tuple[str, ...], Progress],
    report: ChangeReport,
) -> Progress:
    """Preserve registry progress first, then migrate old embedded progress."""

    if competency_id in existing_registry:
        return existing_registry[competency_id]

    migrated_candidates = [
        old_embedded[path]
        for path in paths
        if path in old_embedded
    ]

    if not migrated_candidates:
        return Progress()

    progress = Progress(
        xp=max(item.xp for item in migrated_candidates),
        level=max(item.level for item in migrated_candidates),
    )

    path_list = ", ".join(" > ".join(path) for path in paths)
    report.migrated_progress.append(
        f"{display_name} [{competency_id}] -> XP {progress.xp}, "
        f"Level {progress.level} from {path_list}"
    )

    if len(migrated_candidates) > 1:
        unique_values = {(item.xp, item.level) for item in migrated_candidates}
        if len(unique_values) > 1:
            report.warnings.append(
                f"Shared competency '{display_name}' had different old progress "
                f"values. Preserved the highest XP and level: "
                f"XP {progress.xp}, Level {progress.level}."
            )

    return progress


def build_outputs(
    roots: list[TreeNode],
    existing_tree_data: dict[str, Any],
    existing_competencies_data: dict[str, Any],
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any], ChangeReport]:
    report = ChangeReport(warnings=list(warnings))

    old_stats = existing_tree_data.get("stats", {})
    if not isinstance(old_stats, dict):
        raise SkillTreeError("skill_tree.json must contain a 'stats' object.")

    old_tree_nodes = flatten_tree_nodes(old_stats)
    old_paths = set(old_tree_nodes)
    new_paths = flatten_markdown_paths(roots)

    report.removed_tree_paths = [
        " > ".join(path)
        for path in sorted(old_paths - new_paths, key=lambda p: (len(p), p))
    ]

    existing_registry = load_registry_progress(existing_competencies_data)
    old_embedded = extract_old_embedded_progress(old_tree_nodes)

    leaf_definitions = collect_leaf_definitions(roots)

    leaves_by_id: dict[
        str,
        list[tuple[tuple[str, ...], TreeNode]],
    ] = {}

    for parent_path, node, competency_id in leaf_definitions:
        full_path = (*parent_path, node.name)
        leaves_by_id.setdefault(competency_id, []).append(
            (full_path, node)
        )

    # Guard against accidental ID collisions.
    for competency_id, definitions in leaves_by_id.items():
        names = {node.name for _, node in definitions}
        if len(names) > 1:
            details = ", ".join(
                f"{' > '.join(path)} ({node.name})"
                for path, node in definitions
            )
            raise SkillTreeError(
                f"Competency ID collision for '{competency_id}': {details}"
            )

    new_registry: dict[str, Any] = {}

    for competency_id, definitions in sorted(leaves_by_id.items()):
        display_name = definitions[0][1].name
        paths = [path for path, _ in definitions]
        is_shared = definitions[0][1].is_shared

        progress = determine_progress(
            competency_id=competency_id,
            display_name=display_name,
            paths=paths,
            existing_registry=existing_registry,
            old_embedded=old_embedded,
            report=report,
        )

        new_registry[competency_id] = {
            "id": competency_id,
            "name": display_name,
            "xp": progress.xp,
            "level": progress.level,
            "shared": is_shared,
        }

        label = f"{display_name} [{competency_id}]"
        if competency_id in existing_registry:
            report.preserved_competencies.append(label)
        else:
            report.added_competencies.append(label)

        if is_shared:
            report.shared_references.append(
                f"{label}: {len(definitions)} tree reference(s)"
            )

    report.removed_competencies = [
        f"{competency_id}"
        for competency_id in sorted(
            set(existing_registry) - set(new_registry)
        )
    ]

    def build_tree_node(
        node: TreeNode,
        parent_path: tuple[str, ...],
    ) -> dict[str, Any]:
        current_path = (*parent_path, node.name)
        path_text = " > ".join(current_path)

        if current_path in old_tree_nodes:
            report.preserved_tree_paths.append(path_text)
        else:
            report.added_tree_paths.append(path_text)

        if node.children:
            result: dict[str, Any] = {
                "name": node.name,
                "node_type": "parent",
                "average_level": float(
                    old_tree_nodes.get(current_path, {}).get(
                        "average_level",
                        0.0,
                    )
                ),
                "children": {},
            }

            for child in node.children:
                result["children"][child.name] = build_tree_node(
                    child,
                    current_path,
                )

            return result

        competency_id = competency_id_for(parent_path, node)
        return {
            "name": node.name,
            "node_type": "competency_reference",
            "competency_id": competency_id,
            "shared": node.is_shared,
        }

    new_stats: dict[str, Any] = {}
    for root in roots:
        new_stats[root.name] = build_tree_node(root, ())

    tree_output: dict[str, Any] = {
        "schema_version": 2,
        "stats": new_stats,
        "total_xp": int(existing_tree_data.get("total_xp", 0)),
        "level": int(existing_tree_data.get("level", 0)),
    }

    for key, value in existing_tree_data.items():
        if key not in tree_output and key != "stats":
            tree_output[key] = value

    competencies_output: dict[str, Any] = {
        "schema_version": 1,
        "competencies": new_registry,
    }

    for key, value in existing_competencies_data.items():
        if key not in competencies_output and key != "competencies":
            competencies_output[key] = value

    return tree_output, competencies_output, report


def normalized_json(data: dict[str, Any]) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        indent=4,
        sort_keys=True,
    )


def print_section(
    title: str,
    entries: list[str],
    prefix: str,
    limit: int = 40,
) -> None:
    print()
    print(title)
    print("-" * len(title))

    if not entries:
        print("  None")
        return

    for entry in entries[:limit]:
        print(f"  {prefix} {entry}")

    hidden = len(entries) - limit
    if hidden > 0:
        print(f"  ... and {hidden} more")


def print_report(report: ChangeReport) -> None:
    print("=" * 76)
    print("OPERATOR ZERO SKILL TREE — KNOWLEDGE GRAPH SYNCHRONIZATION")
    print("=" * 76)

    print_section("Tree paths added", report.added_tree_paths, "+")
    print_section("Tree paths removed", report.removed_tree_paths, "-")
    print_section("Competencies added", report.added_competencies, "+")
    print_section("Competencies removed", report.removed_competencies, "-")
    print_section("Shared references", report.shared_references, "@")
    print_section("Progress migrated", report.migrated_progress, ">")
    print_section("Warnings", report.warnings, "!")

    print()
    print("Summary")
    print("-------")
    print(f"  Tree paths added          : {len(report.added_tree_paths)}")
    print(f"  Tree paths preserved      : {len(report.preserved_tree_paths)}")
    print(f"  Tree paths removed        : {len(report.removed_tree_paths)}")
    print(f"  Competencies added        : {len(report.added_competencies)}")
    print(
        f"  Competencies preserved    : "
        f"{len(report.preserved_competencies)}"
    )
    print(
        f"  Competencies removed      : "
        f"{len(report.removed_competencies)}"
    )
    print(f"  Shared references         : {len(report.shared_references)}")
    print(f"  Progress records migrated : {len(report.migrated_progress)}")
    print(f"  Warnings                  : {len(report.warnings)}")


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def create_backups(paths: Iterable[Path]) -> list[Path]:
    existing_paths = [path for path in paths if path.exists()]
    if not existing_paths:
        return []

    DEFAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups: list[Path] = []

    for source in existing_paths:
        backup = (
            DEFAULT_BACKUP_DIR
            / f"{source.stem}_{timestamp}{source.suffix}"
        )
        shutil.copy2(source, backup)
        backups.append(backup)

    return backups


def main() -> int:
    args = parse_arguments()

    markdown_path = args.markdown.resolve()
    tree_path = args.tree_json.resolve()
    competencies_path = args.competencies_json.resolve()

    try:
        roots, warnings = parse_markdown(markdown_path)
        existing_tree = load_json(
            tree_path,
            {"stats": {}, "total_xp": 0, "level": 0},
        )
        existing_competencies = load_json(
            competencies_path,
            {"competencies": {}},
        )

        new_tree, new_competencies, report = build_outputs(
            roots=roots,
            existing_tree_data=existing_tree,
            existing_competencies_data=existing_competencies,
            warnings=warnings,
        )
    except SkillTreeError as error:
        print()
        print("SKILL TREE ERROR")
        print("----------------")
        print(error)
        return 1

    print_report(report)

    tree_matches = normalized_json(existing_tree) == normalized_json(new_tree)
    competencies_match = (
        normalized_json(existing_competencies)
        == normalized_json(new_competencies)
    )
    everything_matches = tree_matches and competencies_match

    if args.check:
        print()
        if everything_matches:
            print("CHECK PASSED: both JSON files match the Markdown source.")
            return 0

        print("CHECK FAILED: generated files do not match the Markdown.")
        if not tree_matches:
            print(f"  Out of sync: {tree_path}")
        if not competencies_match:
            print(f"  Out of sync: {competencies_path}")
        return 1

    has_removals = bool(
        report.removed_tree_paths or report.removed_competencies
    )
    if has_removals and not args.allow_removals:
        print()
        print("SYNC BLOCKED")
        print("------------")
        print(
            "Existing tree paths or competencies would be removed.\n"
            "No files were changed. Review the removal sections above.\n"
            "When the removals are intentional, run:\n\n"
            "    python learning\\scripts\\sync_skill_tree.py "
            "--allow-removals"
        )
        return 1

    if args.dry_run:
        print()
        print("DRY RUN COMPLETE: no files were changed.")
        return 0

    if everything_matches:
        print()
        print("No synchronization needed. Both JSON files are current.")
        return 0

    backups: list[Path] = []
    if not args.no_backup:
        backups = create_backups([tree_path, competencies_path])

    write_json_atomic(tree_path, new_tree)
    write_json_atomic(competencies_path, new_competencies)

    print()
    print("SYNCHRONIZATION COMPLETE")
    print("------------------------")
    print(f"Markdown       : {markdown_path}")
    print(f"Skill tree JSON: {tree_path}")
    print(f"Competencies   : {competencies_path}")

    for backup in backups:
        print(f"Backup         : {backup.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

