# zeroGravity R&D

The technical research environment for zeroGravity. The repository separates reusable R&D workflows from individual robotics projects and Operator progression.

## Main systems

- `projects/shadow/` — Shadow robot assets, software, simulation, data and documentation.
- `lab/` — reusable experiment, test, telemetry and research records.
- `learning/` — learning resources, tracks and Learning Engine.
- `operator_core/` — capability graph, XP, evidence and progression records.
- `journal/` — dated engineering journal entries and indexes.
- `zero_world/` — creative worldbuilding and design language.
- `shared/` — canonical paths and reusable platform libraries.

## First run

```powershell
python .\rnd.py init
python .\rnd.py status
python .\rnd.py verify
```

## Engines

```powershell
python -m lab.engine.cli status
python -m journal.engine.cli list
python .\\operator_core\\engine\\cli.py
python .\learning\engine\tracker.py
```

All platform-owned paths are defined in `shared/config/paths.py`. New scripts should import paths from there instead of hard-coding repository names or machine-specific absolute paths.

