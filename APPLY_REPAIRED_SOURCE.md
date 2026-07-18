# Applying the repaired source bundle

This bundle intentionally excludes large CAD/media assets and SQLite databases.

From the parent folder containing both the repaired extracted folder and your real `zeroGravity-rnd` repository, copy the repaired source over the repository:

```powershell
robocopy `
    ".\zeroGravity-rnd-repaired-source" `
    ".\zeroGravity-rnd" `
    /E `
    /XD __pycache__ `
    /XF *.db
```

Then enter the real repository and verify:

```powershell
cd ".\zeroGravity-rnd"
python .\rnd.py init
python .\rnd.py status
python .\rnd.py verify
git status
```

The existing `lab/database/zerogravity_rnd.db` is not replaced. The Lab Engine creates it only when no database exists.
