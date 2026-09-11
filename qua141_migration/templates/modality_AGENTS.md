# AGENTS.md — MODALITY_PLACEHOLDER migration

```
export QCA_MODALITY="MODALITY_PLACEHOLDER"
uv run python ../qua-libs-core/qua141_migration/migrate_amp_to_amplitude_scale.py --repo . --modality "$QCA_MODALITY" --dry-run
```

See `../qua-libs-core/qua141_migration/docs/qua-1.4.0-migration-runbook.md`.
