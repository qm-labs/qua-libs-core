#!/usr/bin/env python3
"""Insert job.wait_until('Done') after qmm.simulate() for OPX1000/FEM configs only."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_paths import add_target_args, is_ignored_path, resolve_qca_root, target_repo

CONFIG_IMPORT = re.compile(r"^\s*from\s+(configuration[\w_]*)\s+import", re.MULTILINE)
OPX1000_CONFIG = re.compile(r'"type"\s*:\s*"opx1000"|"fems"\s*:')
SIMULATE_ASSIGN = re.compile(r"^(\s*)job\s*=\s*qmm\.simulate\s*\(", re.MULTILINE)
WAIT_UNTIL = re.compile(r"""wait_until\s*\(\s*['"]Done['"]\s*\)""")
OLD_SIMULATE_COMMENT = "# Simulate blocks python until the simulation is done"
NEW_SIMULATE_COMMENT = "# Start simulation (non-blocking on OPX1000; wait before pulling results)"
WAIT_BLOCK = (
    "{indent}# Wait until the simulation is done\n"
    '{indent}job.wait_until("Done")\n'
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def resolve_config_import(script_path: Path, text: str) -> Path | None:
    match = CONFIG_IMPORT.search(text)
    if not match:
        return None
    config_path = script_path.parent / f"{match.group(1)}.py"
    return config_path if config_path.is_file() else None


def is_opx1000_config(config_path: Path) -> bool:
    return bool(OPX1000_CONFIG.search(_read_text(config_path)))


def script_uses_opx1000_config(script_path: Path, text: str | None = None) -> bool:
    source = text if text is not None else _read_text(script_path)
    config_path = resolve_config_import(script_path, source)
    return config_path is not None and is_opx1000_config(config_path)


def _find_simulate_line_end(text: str, start: int) -> int | None:
    paren_open = text.find("(", start)
    if paren_open == -1:
        return None
    depth = 0
    in_string: str | None = None
    escape = False
    idx = paren_open
    while idx < len(text):
        char = text[idx]
        if in_string is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
        elif char in ("'", '"'):
            in_string = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                line_end = text.find("\n", idx)
                return len(text) if line_end == -1 else line_end + 1
        idx += 1
    return None


def _needs_migration(text: str) -> bool:
    if "get_simulated_samples" not in text:
        return False
    samples_idx = text.find("get_simulated_samples")
    wait_match = WAIT_UNTIL.search(text)
    if wait_match is None:
        return True
    return wait_match.start() >= samples_idx


def migrate_text(text: str) -> tuple[str, int]:
    if not _needs_migration(text):
        return text, 0

    new_text = text.replace(OLD_SIMULATE_COMMENT, NEW_SIMULATE_COMMENT)
    comment_replacements = 1 if new_text != text else 0

    match = SIMULATE_ASSIGN.search(new_text)
    if not match:
        return text, 0

    insert_at = _find_simulate_line_end(new_text, match.start())
    if insert_at is None:
        return text, 0

    indent = match.group(1)
    block = WAIT_BLOCK.format(indent=indent)
    updated = new_text[:insert_at] + block + new_text[insert_at:]
    return updated, 1 + comment_replacements


def migrate_file(path: Path, dry_run: bool = False) -> tuple[bool, int]:
    text = _read_text(path)
    if "get_simulated_samples" not in text:
        return False, 0
    if not script_uses_opx1000_config(path, text):
        return False, 0
    new_text, changes = migrate_text(text)
    if changes == 0:
        return False, 0
    try:
        ast.parse(text)
        original_parses = True
    except SyntaxError:
        original_parses = False
    if original_parses:
        try:
            ast.parse(new_text)
        except SyntaxError as exc:
            print(f"SYNTAX ERROR after migrate {path}: {exc}")
            return False, 0
    rel = path
    print(f"OK ({changes}): {rel}")
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True, changes


def iter_targets(qca_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(qca_root.rglob("*.py")):
        if is_ignored_path(path):
            continue
        if path.name.startswith("config") or path.name in {
            "macros.py",
            "qua_config_split.py",
        }:
            continue
        if "migrate_simulation_wait_until" in path.name:
            continue
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_target_args(parser)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()
    repo = target_repo(args.repo)
    qca_root = resolve_qca_root(modality=args.modality, qca_root=args.qca_root, repo=repo)
    targets = iter_targets(qca_root)

    file_count = 0
    change_count = 0
    for path in targets:
        changed, count = migrate_file(path, dry_run=args.dry_run)
        if changed:
            file_count += 1
            change_count += count

    scope = qca_root.relative_to(repo)
    action = "Would migrate" if args.dry_run else "Migrated"
    print(f"\n{action} {file_count} OPX1000 files, {change_count} wait_until insertions (scope: {scope})")


if __name__ == "__main__":
    main()
