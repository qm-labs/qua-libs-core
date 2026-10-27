# Compatibility matrix

Tested package combinations for QUA Libraries releases. Use this table when
planning an install or validating your environment.

| qua-libs-core | qm-qua | Python | Notes |
|---------------|--------|--------|-------|
| 0.4.4 | 1.3.1 | 3.10–3.14 | Installer also ships an Apple Silicon macOS build. |
| 0.4.3 | 1.3.1 | 3.10–3.14 | Installer always writes telemetry.toml (enabled or not). |
| 0.4.0 | 1.3.1 | 3.10–3.14 | Installer reports stage-specific errors. Fix superconducting git repo path. |
| 0.3.0 | 1.3.1 | 3.10–3.14 | Installer artifact included in release. |
| 0.2.1 | 1.3.1 | 3.10–3.14 | Package metadata allows 3.13 and 3.14. Installer default remains 3.12. |
| 0.2.0 | 1.3.1 | 3.10, 3.11, 3.12 | Local-first telemetry; optional Uptrace. Same SDK combo as 0.1.0. |
| 0.1.0 | 1.3.1 | 3.10, 3.11, 3.12 | Tested combination for superconducting and NV workspace installs. |

After installation, the complete summary shows the **QUA SDK version actually
installed** in your environment.

## Manual installs

Use the installer when possible. For advanced setups, clone the modality
repository and follow its README.

## Release notes

QUA SDK release notes:
https://docs.quantum-machines.co/latest/docs/Release_notes/release_notes/
