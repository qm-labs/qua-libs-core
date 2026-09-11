# Simulation validation

Fill this file as you compare migrated scripts against the qua-libs baseline (`QL-1212-validation`).

```
uv run python ../qua-libs-core/qua141_migration/validate_simulation_baseline.py --repo . --list-folders
uv run python ../qua-libs-core/qua141_migration/validate_simulation_baseline.py --repo . --folder FOLDER --print-notes
```

Folder presets live in `validation_matrix.py`.
