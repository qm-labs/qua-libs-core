#!/usr/bin/env bash
# Seed a modality repo with qua141_migration/ local files (not the shared CLI).
# Usage: ./qua141_migration/bootstrap_modality_repo.sh TARGET_DIR [MODALITY]
set -euo pipefail

TARGET="${1:?Usage: $0 TARGET_DIR [MODALITY]}"
MODALITY="${2:-}"
SOURCE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$TARGET/qua141_migration" "$TARGET/.github/workflows"

cp "$SOURCE/templates/validation_matrix.py" "$TARGET/qua141_migration/validation_matrix.py"
cp "$SOURCE/templates/VALIDATION.md" "$TARGET/qua141_migration/VALIDATION.md"
cp "$SOURCE/templates/modality_AGENTS.md" "$TARGET/qua141_migration/AGENTS.md"
cp "$SOURCE/templates/root_AGENTS.md" "$TARGET/AGENTS.md"
cp "$SOURCE/templates/gitignore" "$TARGET/qua141_migration/.gitignore"
cp "$SOURCE/templates/ci-qca-migration-gates.yml" "$TARGET/.github/workflows/qca-migration-gates.yml"

if [[ -n "$MODALITY" ]]; then
  export BOOTSTRAP_TARGET="$TARGET"
  export BOOTSTRAP_MODALITY="$MODALITY"
  python3 - << 'END'
from pathlib import Path
import os

t = Path(os.environ["BOOTSTRAP_TARGET"])
m = os.environ["BOOTSTRAP_MODALITY"]
for rel in (
    "qua141_migration/validation_matrix.py",
    "AGENTS.md",
    "qua141_migration/AGENTS.md",
    ".github/workflows/qca-migration-gates.yml",
):
    path = t / rel
    path.write_text(path.read_text(encoding="utf-8").replace("MODALITY_PLACEHOLDER", m), encoding="utf-8")
END
fi

echo
echo "Seeded $TARGET/qua141_migration (matrix + VALIDATION.md only)."
echo "Shared migrators stay in qua-libs-core/qua141_migration/."
