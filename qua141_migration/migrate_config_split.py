#!/usr/bin/env python3
"""Migrate QUA configs and scripts to controller/logical split (Part 2 of docs/plans/qua-1.4.0-migration.md)."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_paths import add_target_args, is_ignored_path, qualibration_roots, resolve_qca_root, target_repo

CONTROLLER_KEYS = frozenset({"controllers", "octaves", "mixers"})
LOGICAL_KEYS = frozenset({"oscillators", "elements", "integration_weights", "waveforms", "digital_waveforms", "pulses"})
SKIP_CONFIG_KEYS = frozenset({"version"})


def _import_block(config_path: Path) -> str:
    return "from qua_libs_core.qua_config import merge_qua_config\n\n"


def _dict_entry_source(source: str, key_node: ast.expr, value_node: ast.expr) -> str:
    key_src = ast.get_source_segment(source, key_node)
    val_src = ast.get_source_segment(source, value_node)
    return f"    {key_src}: {val_src},\n"


def split_configuration_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "controller_config" in text and "logical_config" in text:
        return False

    try:
        tree = ast.parse(text)
    except SyntaxError:
        print(f"SKIP (syntax): {path}")
        return False

    config_assign: ast.Assign | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    config_assign = node
                    break

    if config_assign is None or not isinstance(config_assign.value, ast.Dict):
        print(f"SKIP (no config dict): {path}")
        return False

    d = config_assign.value
    controller_lines: list[str] = []
    logical_lines: list[str] = []
    for key_node, value_node in zip(d.keys, d.values):
        if key_node is None:
            continue
        key = ast.literal_eval(key_node) if isinstance(key_node, ast.Constant) else None
        if key in SKIP_CONFIG_KEYS:
            continue
        entry = _dict_entry_source(text, key_node, value_node)
        if key in CONTROLLER_KEYS:
            controller_lines.append(entry)
        elif key in LOGICAL_KEYS:
            logical_lines.append(entry)
        else:
            print(f"WARN unknown config key {key!r} in {path}")

    if not controller_lines or not logical_lines:
        print(f"SKIP (empty split): {path}")
        return False

    assign_src = ast.get_source_segment(text, config_assign)
    assert assign_src is not None
    start, end = config_assign.lineno - 1, config_assign.end_lineno
    lines = text.splitlines(keepends=True)
    prefix = "".join(lines[:start])
    suffix = "".join(lines[end:])

    import_block = _import_block(path)
    if "from qua_libs_core.qua_config import merge_qua_config" not in text and "from qua_config_split import merge_qua_config" not in text:
        # Insert after module docstring / first imports block
        insert_at = 0
        if prefix.lstrip().startswith('"""') or prefix.lstrip().startswith("'''"):
            quote = '"""' if '"""' in prefix[:10] else "'''"
            end_doc = prefix.find(quote, prefix.find(quote) + 3) + 3
            insert_at = end_doc
            while insert_at < len(prefix) and prefix[insert_at] in "\n\r":
                insert_at += 1
        else:
            insert_at = 0
        prefix = prefix[:insert_at] + import_block + prefix[insert_at:]

    replacement = (
        "controller_config = {\n"
        + "".join(controller_lines)
        + "}\n"
        "logical_config = {\n"
        + "".join(logical_lines)
        + "}\n"
        "config = merge_qua_config(controller_config, logical_config)\n"
    )

    new_text = prefix + replacement + suffix
    path.write_text(new_text, encoding="utf-8")
    print(f"OK config: {path}")
    return True


def migrate_qca_scripts(qca_root: Path) -> int:
    count = 0
    for py in qca_root.rglob("*.py"):
        if is_ignored_path(py) or py.name.startswith("config") or py.name == "qua_config_split.py":
            continue
        text = py.read_text(encoding="utf-8")
        original = text

        text = re.sub(r"\bqmm\.open_qm\(config\b", "qmm.open_qm(controller_config", text)
        text = re.sub(r"\bqmm\.open_qm_from_file\(", "qmm.open_qm(controller_config)  # was open_qm_from_file(", text)

        # qm.execute(prog) -> qm.execute(prog, config=logical_config) when no config= yet
        text = re.sub(
            r"\bqm\.execute\(([^,)]+)\)(?!\s*,\s*config=)",
            r"qm.execute(\1, config=logical_config)",
            text,
        )
        text = re.sub(
            r"\bqm\.compile\(([^,)]+)\)(?!\s*,\s*config=)",
            r"qm.compile(\1, config=logical_config)",
            text,
        )

        if text != original:
            py.write_text(text, encoding="utf-8")
            count += 1
    return count


def migrate_qualibration_nodes(repo: Path) -> int:
    count = 0
    cal_dirs = [root / "calibrations" for root in qualibration_roots(repo)]
    if not cal_dirs:
        return 0
    import_line = "from calibration_utils.qua_config_split import split_qua_config\n"
    for cal_dir in cal_dirs:
        if not cal_dir.is_dir():
            continue
        for py in sorted(cal_dir.rglob("*.py")):
            if is_ignored_path(py):
                continue
            text = py.read_text(encoding="utf-8")
            if "execute_qua_program" not in text and "simulate_qua_program" not in text:
                continue
            original = text
    
            if "split_qua_config" not in text and "generate_config()" in text:
                if "from calibration_utils.qua_config_split import split_qua_config" not in text:
                    # Insert after the last closed parenthesis of calibration_utils import blocks
                    m = re.search(
                        r"from calibration_utils\.\w+ import \([\s\S]*?\)\n",
                        text,
                    )
                    if m:
                        text = text[: m.end()] + import_line + text[m.end() :]
                    elif re.search(r"from calibration_utils[^\n]+\n", text):
                        m = re.search(r"(from calibration_utils[^\n]+\n)", text)
                        if m:
                            text = text[: m.end()] + import_line + text[m.end() :]
                    elif "from qualibration_libs" in text:
                        m2 = re.search(r"(from qualibration_libs[^\n]+\n)", text)
                        if m2:
                            text = text[: m2.end()] + import_line + text[m2.end() :]
                    else:
                        text = import_line + text
    
            text = re.sub(
                r"(\n\s+)config = node\.machine\.generate_config\(\)\n(\s+)with qm_session\(qmm, config,",
                r"\1config = node.machine.generate_config()\n\1controller_config, logical_config = split_qua_config(config)\n\2with qm_session(qmm, controller_config,",
                text,
            )
            text = re.sub(
                r"(\n\s+)with qm_session\(qmm, config,",
                r"\1controller_config, logical_config = split_qua_config(config)\n\1with qm_session(qmm, controller_config,",
                text,
            )
            text = re.sub(
                r"job = qm\.execute\((node\.namespace\[\"qua_program\"\])\)(?!\s*,\s*config=)",
                r"job = qm.execute(\1, config=logical_config)",
                text,
            )
            text = re.sub(
                r"job = qm\.execute\((node\.namespace\['qua_program'\])\)(?!\s*,\s*config=)",
                r"job = qm.execute(\1, config=logical_config)",
                text,
            )
    
            if text != original:
                py.write_text(text, encoding="utf-8")
                count += 1
                print(f"OK node: {py}")
    return count


def migrate_tutorial(repo: Path) -> None:
    path = repo / "Tutorials" / "intro-to-QUAlibrate" / "calibrations" / "time_of_flight.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    original = text
    import_line = "from calibration_utils.qua_config_split import split_qua_config\n"
    if "split_qua_config" not in text:
        text = text.replace("from qualibration_libs.runtime import simulate_and_plot\n", import_line + "from qualibration_libs.runtime import simulate_and_plot\n")
    text = re.sub(
        r"with qm_session\(qmm, config,",
        "controller_config, logical_config = split_qua_config(config)\n    with qm_session(qmm, controller_config,",
        text,
    )
    text = re.sub(
        r"job = qm\.execute\(node\.namespace\[\"qua_program\"\]\)(?!\s*,\s*config=)",
        "job = qm.execute(node.namespace[\"qua_program\"], config=logical_config)",
        text,
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"OK tutorial: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_target_args(parser)
    parser.add_argument(
        "--skip-qualibration",
        action="store_true",
        help="Do not migrate qualibration_graphs nodes (modality-only repos).",
    )
    args = parser.parse_args()
    repo = target_repo(args.repo)
    qca_root = resolve_qca_root(modality=args.modality, qca_root=args.qca_root, repo=repo)

    config_paths = [
        p
        for p in qca_root.rglob("*.py")
        if not is_ignored_path(p) and p.name.startswith("config") and p.suffix == ".py"
    ]
    tutorial_cfg = repo / "Tutorials" / "intro-to-QUAlibrate" / "configuration" / "configuration_with_lf_fem_and_mw_fem.py"
    if tutorial_cfg.exists():
        config_paths.append(tutorial_cfg)

    n_cfg = sum(split_configuration_file(p) for p in sorted(config_paths))
    n_scripts = migrate_qca_scripts(qca_root)
    n_nodes = 0 if args.skip_qualibration else migrate_qualibration_nodes(repo)
    if not args.skip_qualibration:
        migrate_tutorial(repo)
    print(f"\nDone ({qca_root.relative_to(repo)}): {n_cfg} configs, {n_scripts} QCA scripts, {n_nodes} qualibration nodes")


if __name__ == "__main__":
    main()
