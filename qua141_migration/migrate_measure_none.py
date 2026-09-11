#!/usr/bin/env python3
"""Remove deprecated literal None as the ADC-stream placeholder in QUA measure() calls."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_paths import add_target_args, is_ignored_path, resolve_qca_root, target_repo

MEASURE_START = re.compile(r"\bmeasure\s*\(")
_NONE_BEFORE_MORE = re.compile(r",\s*None\s*,")
_NONE_BEFORE_CLOSE = re.compile(r",\s*None\s*\)")
_NONE_ON_OWN_LINE = re.compile(r"\n\s*None\s*,\s*\n")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _find_measure_call_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    search_from = 0
    while search_from < len(text):
        match = MEASURE_START.search(text, search_from)
        if not match:
            break
        paren_open = match.end() - 1
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
                    spans.append((match.start(), idx + 1))
                    break
            idx += 1
        search_from = paren_open + 1
    return spans


def _transform_measure_call(call: str) -> tuple[str, int]:
    new = call
    replacements = 0
    for pattern, repl in (
        (_NONE_BEFORE_MORE, ","),
        (_NONE_BEFORE_CLOSE, ")"),
        (_NONE_ON_OWN_LINE, "\n"),
    ):
        new, count = pattern.subn(repl, new)
        replacements += count
    return new, replacements


def migrate_text(text: str) -> tuple[str, int]:
    if "measure(" not in text or "None" not in text:
        return text, 0

    spans = _find_measure_call_spans(text)
    if not spans:
        return text, 0

    parts: list[str] = []
    total = 0
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        call = text[start:end]
        new_call, count = _transform_measure_call(call)
        total += count
        parts.append(new_call)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), total


def migrate_file(path: Path, dry_run: bool = False) -> tuple[bool, int]:
    text = _read_text(path)
    if "measure(" not in text:
        return False, 0
    new_text, replacements = migrate_text(text)
    if replacements == 0:
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
    print(f"OK ({replacements}): {rel}")
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True, replacements


def iter_targets(qca_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(qca_root.rglob("*.py")):
        if is_ignored_path(path) or path.name == "qua_config_split.py" or "migrate_measure_none" in path.name:
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
    replacement_count = 0
    for path in targets:
        changed, count = migrate_file(path, dry_run=args.dry_run)
        if changed:
            file_count += 1
            replacement_count += count

    scope = qca_root.relative_to(repo)
    action = "Would migrate" if args.dry_run else "Migrated"
    print(f"\n{action} {file_count} files, {replacement_count} measure(None) removals (scope: {scope})")


if __name__ == "__main__":
    main()
