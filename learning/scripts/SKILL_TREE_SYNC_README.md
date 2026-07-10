# Operator Zero Skill Tree Synchronizer

This version supports a central competency registry and shared competency
references.

## Generated files

```text
learning/
├── skill_tree.md
├── config/
│   ├── skill_tree.json
│   ├── competencies.json
│   └── backups/
└── scripts/
    └── sync_skill_tree.py
```

## Markdown syntax

Ordinary competency:

```markdown
- Programming Languages
  - Python
```

Shared competency:

```markdown
- APIs & Backend
  - @HTTP

- Client/Server
  - @HTTP
```

Both `@HTTP` entries point to one registry record:

```json
"http": {
    "id": "http",
    "name": "HTTP",
    "xp": 0,
    "level": 0,
    "shared": true
}
```

Do not place children under an `@` competency.

## Test safely

From the repository root:

```cmd
python learning\scripts\sync_skill_tree.py --dry-run
```

The first migration may report removals because the old tree stored embedded
skills and the new tree stores competency references. Review the report.

If the reported removals are expected:

```cmd
python learning\scripts\sync_skill_tree.py --allow-removals
```

Then validate:

```cmd
python learning\scripts\sync_skill_tree.py --check
python -m json.tool learning\config\skill_tree.json
python -m json.tool learning\config\competencies.json
```

## Progress migration

Existing XP and levels are migrated from the old `skill_tree.json`.

For a shared competency that appears in multiple old locations, the script
preserves the highest XP and level instead of adding them together. This avoids
accidental XP inflation.

Timestamped backups are created before real writes.