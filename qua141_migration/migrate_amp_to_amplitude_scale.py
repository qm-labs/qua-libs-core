#!/usr/bin/env python3
"""Migrate deprecated QUA amp() to amplitude_scale on play/measure (Part 3 of docs/plans/qua-1.4.0-migration.md)."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_paths import add_target_args, is_ignored_path, qualibration_roots, resolve_qca_root, target_repo

# pulse_expr * amp(args) — pulse may be quoted string, identifier, or f-string / attribute
PULSE_AMP = re.compile(
    r"(?P<pulse>(?:[\w.]+|\"[^\"]*\"|'[^']*'|f\"[^\"]*\"))\s*\*\s*amp\((?P<args>[^)]*)\)"
)

PLAY_CALL = re.compile(
    r"play\(\s*(?P<pulse_amp>(?:[\w.\"']+|f\"[^\"]*\"|\{[^}]+\})\s*\*\s*amp\([^)]+\)),\s*(?P<tail>[^)]+)\)",
    re.DOTALL,
)

MEASURE_INLINE = re.compile(
    r"measure\(\s*(?P<pulse_amp>(?:[\w.\"']+|f\"[^\"]*\"|\{[^}]+\})\s*\*\s*amp\([^)]+\)),\s*(?P<tail>[^)]+)\)",
    re.DOTALL,
)

MEASURE_MULTILINE_FIRST = re.compile(
    r"(measure\(\s*\n\s*)(?P<pulse_amp>(?:[\w.\"']+|f\"[^\"]*\"|\{[^}]+\})\s*\*\s*amp\([^)]+\)),(\s*\n)",
    re.MULTILINE,
)


def _amplitude_scale_expr(args: str) -> str:
    args = args.strip()
    if args.startswith("*"):
        var = args[1:].strip()
        return f"({var}[0], {var}[1], {var}[2], {var}[3])"
    if "," in args:
        return f"({args})"
    return args


def _split_pulse_amp(pulse_amp: str) -> tuple[str, str]:
    m = PULSE_AMP.search(pulse_amp)
    if not m:
        raise ValueError(f"no pulse*amp in {pulse_amp!r}")
    return m.group("pulse"), _amplitude_scale_expr(m.group("args"))


def _append_amplitude_scale(tail: str, scale: str) -> str:
    tail = tail.strip()
    if tail.endswith(","):
        return f"{tail} amplitude_scale={scale}"
    return f"{tail}, amplitude_scale={scale}"


def _transform_play_measure_calls(text: str) -> str:
    def play_repl(m: re.Match[str]) -> str:
        pulse, scale = _split_pulse_amp(m.group("pulse_amp"))
        tail = _append_amplitude_scale(m.group("tail"), scale)
        return f"play({pulse}, {tail})"

    def measure_repl(m: re.Match[str]) -> str:
        pulse, scale = _split_pulse_amp(m.group("pulse_amp"))
        tail = _append_amplitude_scale(m.group("tail"), scale)
        return f"measure({pulse}, {tail})"

    text = PLAY_CALL.sub(play_repl, text)
    text = MEASURE_INLINE.sub(measure_repl, text)

    def measure_multiline(m: re.Match[str]) -> str:
        pulse, scale = _split_pulse_amp(m.group("pulse_amp"))
        return f"{m.group(1)}{pulse},{m.group(3)}        amplitude_scale={scale},"

    text = MEASURE_MULTILINE_FIRST.sub(measure_multiline, text)
    return text


def _transform_standalone_pulse_amp_in_measure(text: str) -> str:
    """Handle measure blocks where scaled pulse is first arg on its own line."""

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith("measure(") or (out and "measure(" in out[-1] and i > 0):
            block_start = i
            if stripped.startswith("measure("):
                block_lines = [line]
                i += 1
                depth = line.count("(") - line.count(")")
                while i < len(lines) and depth > 0:
                    block_lines.append(lines[i])
                    depth += lines[i].count("(") - lines[i].count(")")
                    i += 1
                block = "".join(block_lines)
                block = MEASURE_INLINE.sub(
                    lambda m: f"measure({_split_pulse_amp(m.group('pulse_amp'))[0]}, "
                    f"{_append_amplitude_scale(m.group('tail'), _split_pulse_amp(m.group('pulse_amp'))[1])})",
                    block,
                )
                if " * amp(" in block:
                    block = MEASURE_MULTILINE_FIRST.sub(
                        lambda m: f"{m.group(1)}{_split_pulse_amp(m.group('pulse_amp'))[0]},"
                        f"{m.group(3)}        amplitude_scale={_split_pulse_amp(m.group('pulse_amp'))[1]},",
                        block,
                    )
                out.append(block)
                continue
        out.append(line)
        i += 1
    return "".join(out)


def migrate_text(text: str) -> str:
    if " * amp(" not in text and "* amp(" not in text:
        return text
    text = _transform_play_measure_calls(text)
    # Remaining: first arg to play on multiple lines (qualibration style)
    text = re.sub(
        r"play\(\s*\n\s*(?P<pulse_amp>(?:[\w.\"']+|f\"[^\"]*\"|\{[^}]+\})\s*\*\s*amp\([^)]+\)),(\s*\n\s*)(?P<tail>[^)]+?\))",
        lambda m: f"play(\n            {_split_pulse_amp(m.group('pulse_amp'))[0]},"
        f"{m.group(2)}{_append_amplitude_scale(m.group('tail'), _split_pulse_amp(m.group('pulse_amp'))[1])})",
        text,
        flags=re.DOTALL,
    )
    # Dynamic operation * amp in play first arg (multiline qualibration)
    text = re.sub(
        r"play\(\s*\n\s*(?P<pulse_amp>[\w.]+\s*\*\s*amp\([^)]+\)),(\s*\n\s*)(?P<tail>[^)]+?\))",
        lambda m: f"play(\n                                        {_split_pulse_amp(m.group('pulse_amp'))[0]},"
        f"{m.group(2)}{_append_amplitude_scale(m.group('tail'), _split_pulse_amp(m.group('pulse_amp'))[1])})",
        text,
        flags=re.DOTALL,
    )
    # Multiline measure(... "pulse" * amp(...), ... dual_demod ...): replace pulse*amp and append amplitude_scale
    text = _transform_multiline_measure(text)
    return text


def _transform_multiline_measure(text: str) -> str:
    """Handle measure blocks where scaled pulse is on its own line."""

    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i : i + 8] != "measure(":
            result.append(text[i])
            i += 1
            continue
        start = i
        i += 8
        depth = 1
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        block = text[start:i]
        if " * amp(" not in block:
            result.append(block)
            continue
        m = PULSE_AMP.search(block)
        if not m:
            result.append(block)
            continue
        pulse = m.group("pulse")
        scale = _amplitude_scale_expr(m.group("args"))
        block = PULSE_AMP.sub(pulse, block, count=1)
        if "amplitude_scale=" not in block:
            block = block[:-1].rstrip() + f", amplitude_scale={scale})"
        result.append(block)
    return "".join(result)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def migrate_file(path: Path, dry_run: bool = False) -> bool:
    text = _read_text(path)
    if "amp(" not in text:
        return False
    new_text = migrate_text(text)
    if new_text == text:
        return False
    try:
        ast.parse(new_text)
    except SyntaxError as exc:
        print(f"SYNTAX ERROR after migrate {path}: {exc}")
        return False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    print(f"OK: {path}")
    return True


def iter_targets(qca_root: Path, repo: Path, *, include_qualibration: bool = True) -> list[Path]:
    roots = [qca_root]
    if include_qualibration:
        roots.extend(qualibration_roots(repo))
        roots.append(repo / "Tutorials")
    paths: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if is_ignored_path(path) or "migrate_amp" in path.name:
                continue
            paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_target_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-qualibration",
        action="store_true",
        help="Scan only the QCA modality tree (modality-only repos).",
    )
    args = parser.parse_args()
    repo = target_repo(args.repo)
    qca_root = resolve_qca_root(modality=args.modality, qca_root=args.qca_root, repo=repo)
    targets = iter_targets(qca_root, repo, include_qualibration=not args.skip_qualibration)
    count = sum(1 for p in targets if migrate_file(p, dry_run=args.dry_run))
    print(f"\nMigrated {count} files (scope: {qca_root.relative_to(repo)})")


if __name__ == "__main__":
    main()
