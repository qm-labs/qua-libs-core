"""Portable grep gates for QUA 1.3.1 / 1.4.0 migration under Quantum-Control-Applications."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]


def _target_repo() -> Path:
    env = os.environ.get("QCA_REPO")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd().resolve()


REPO_ROOT = _target_repo()
_qca_apps = REPO_ROOT / "Quantum-Control-Applications"
_found = sorted(p.name for p in _qca_apps.iterdir() if p.is_dir()) if _qca_apps.is_dir() else []
if os.environ.get("QCA_MODALITY"):
    MODALITY = os.environ["QCA_MODALITY"]
elif len(_found) == 1:
    MODALITY = _found[0]
else:
    MODALITY = None
QCA_ROOT = (
    REPO_ROOT / "Quantum-Control-Applications" / MODALITY
    if MODALITY
    else REPO_ROOT / "Quantum-Control-Applications" / "__unset_modality__"
)

if not QCA_ROOT.is_dir():
    pytest.skip(
        f"QCA root not found: {QCA_ROOT} (set QCA_REPO and QCA_MODALITY)",
        allow_module_level=True,
    )

CONTROLLER_KEYS = frozenset({"controllers", "octaves", "mixers"})
LOGICAL_KEYS = frozenset(
    {"oscillators", "elements", "integration_weights", "waveforms", "digital_waveforms", "pulses"}
)
DEPRECATED_AMP_PATTERN = re.compile(r"\*\s*amp\s*\(")
DECLARE_WITH_STREAM_TAG_PATTERN = re.compile(r'declare_with_stream\s*\([^,]+,\s*"([^"]+)"')
MANUAL_SAVE_TAG_PATTERN = re.compile(r'\.save\s*\(\s*"([^"]+)"\s*\)')
BOOL_AVERAGE_AXES_PATTERN = re.compile(
    r'declare_with_stream\s*\(\s*bool\s*,[^)]*average_axes\s*='
)


def _skip_if_no_qca_root() -> None:
    if not QCA_ROOT.is_dir():
        pytest.skip(f"QCA root not found: {QCA_ROOT} (set QCA_MODALITY)")


def discover_configuration_files() -> list[Path]:
    _skip_if_no_qca_root()
    files: list[Path] = []
    for path in sorted(QCA_ROOT.rglob("*.py")):
        if not path.name.startswith("config"):
            continue
        if any(part in {".venv", ".git", "__pycache__", "site-packages"} for part in path.parts):
            continue
        files.append(path)
    return files


def discover_qca_python_files() -> list[Path]:
    _skip_if_no_qca_root()
    files: list[Path] = []
    for path in sorted(QCA_ROOT.rglob("*.py")):
        if path.name == "qua_config_split.py" or any(
            part in {".venv", ".git", "__pycache__", "site-packages"} for part in path.parts
        ):
            continue
        files.append(path)
    return files


def discover_qca_scripts_with_execute_or_simulate() -> list[Path]:
    files: list[Path] = []
    for path in discover_qca_python_files():
        if path.name.startswith("config"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "open_qm" in text or "qmm.simulate" in text:
            files.append(path)
    return files


def _top_level_assigned_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _active_lines(text: str) -> list[tuple[int, str]]:
    active: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        active.append((line_no, line))
    return active


@pytest.mark.parametrize(
    "config_file",
    discover_configuration_files(),
    ids=lambda path: str(path.relative_to(REPO_ROOT)),
)
def test_configuration_file_defines_split_exports(config_file: Path) -> None:
    source = config_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(config_file))
    top_level_names = _top_level_assigned_names(tree)
    assert "controller_config" in top_level_names, f"{config_file} missing controller_config"
    assert "logical_config" in top_level_names, f"{config_file} missing logical_config"
    assert "config" in top_level_names, f"{config_file} missing transitional config alias"
    assert "merge_qua_config" in source or "split_qua_config" in source


def test_no_declare_stream_in_qca() -> None:
    violations: list[str] = []
    for path in discover_qca_python_files():
        text = path.read_text(encoding="utf-8")
        if "declare_stream(" in text:
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, f"declare_stream() still used in: {violations}"


def test_no_open_qm_with_merged_config() -> None:
    violations: list[str] = []
    for path in discover_qca_scripts_with_execute_or_simulate():
        text = path.read_text(encoding="utf-8")
        if re.search(r"open_qm\s*\(\s*config\s*\)", text):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, f"open_qm(config) still used in: {violations}"


def test_qca_execute_passes_logical_config() -> None:
    violations: list[str] = []
    for path in discover_qca_scripts_with_execute_or_simulate():
        text = path.read_text(encoding="utf-8")
        if "qm.execute" not in text:
            continue
        for match in re.finditer(r"qm\.execute\s*\(([^)]*)\)", text):
            args = match.group(1)
            if "config=" not in args and "**" not in args:
                violations.append(f"{path.relative_to(REPO_ROOT)}: qm.execute({args[:80]})")
    assert not violations, f"qm.execute without config= in: {violations}"


def test_no_deprecated_amp_in_qca() -> None:
    violations: list[str] = []
    for path in discover_qca_python_files():
        if "migrate_amp" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in _active_lines(text):
            if DEPRECATED_AMP_PATTERN.search(line):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {line.strip()}")
    assert not violations, "Deprecated `* amp(` usage found:\n" + "\n".join(violations)


def test_no_duplicate_stream_tags_in_qca() -> None:
    """declare_with_stream auto tags must not overlap manual stream_processing .save() tags."""
    violations: list[str] = []
    for path in discover_qca_python_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "declare_with_stream" not in text:
            continue
        auto_tags = set(DECLARE_WITH_STREAM_TAG_PATTERN.findall(text))
        manual_tags = set(MANUAL_SAVE_TAG_PATTERN.findall(text))
        collisions = sorted(auto_tags & manual_tags)
        if collisions:
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}: duplicate tags {collisions}")
    assert not violations, (
        "declare_with_stream tags collide with manual .save() tags:\n" + "\n".join(violations)
    )


def test_no_bool_average_axes_in_declare_with_stream() -> None:
    """Bool streams cannot use average_axes — use int (equivalent to boolean_to_int().average())."""
    violations: list[str] = []
    for path in discover_qca_python_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in _active_lines(text):
            if BOOL_AVERAGE_AXES_PATTERN.search(line):
                rel = path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {line.strip()}")
    assert not violations, (
        "declare_with_stream(bool, ..., average_axes=...) is invalid — use int instead "
        "(see https://docs.quantum-machines.co/1.3.1/docs/Guides/qua_iterables/):\n"
        + "\n".join(violations)
    )


def test_no_measure_none_adc_placeholder_in_qca() -> None:
    """measure(..., None, ...) ADC placeholder is deprecated in qm-qua 1.4.0 — omit None."""
    import sys

    sys.path.insert(0, str(KIT_ROOT))
    try:
        from migrate_measure_none import migrate_text  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    violations: list[str] = []
    for path in discover_qca_python_files():
        if "migrate_measure_none" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _, count = migrate_text(text)
        if count:
            violations.append(f"{path.relative_to(REPO_ROOT)} ({count} placeholder(s))")
    assert not violations, (
        "Deprecated measure(..., None, ...) ADC placeholder found — remove literal None:\n"
        + "\n".join(violations)
    )


def test_simulation_wait_until_before_samples_in_opx1000_qca() -> None:
    """OPX1000 async simulate jobs need wait_until('Done') before get_simulated_samples()."""
    import sys

    sys.path.insert(0, str(KIT_ROOT))
    try:
        from migrate_simulation_wait_until import script_uses_opx1000_config  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    wait_pattern = re.compile(r"""wait_until\s*\(\s*['"]Done['"]\s*\)""")
    violations: list[str] = []
    for path in discover_qca_python_files():
        if path.name.startswith("config"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "get_simulated_samples" not in text:
            continue
        if not script_uses_opx1000_config(path, text):
            continue
        samples_idx = text.find("get_simulated_samples")
        wait_match = wait_pattern.search(text)
        if wait_match is None or wait_match.start() >= samples_idx:
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, (
        "Missing job.wait_until('Done') before get_simulated_samples() in OPX1000 scripts — "
        "run qua141_migration/migrate_simulation_wait_until.py from qua-libs-core:\n" + "\n".join(violations)
    )


def test_simulate_uses_manager_not_open_qm() -> None:
    violations: list[str] = []
    for path in discover_qca_scripts_with_execute_or_simulate():
        text = path.read_text(encoding="utf-8")
        if "qmm.simulate" not in text:
            continue
        if re.search(r"open_qm\s*\([^)]*\)[\s\S]{0,200}qmm\.simulate", text):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, f"open_qm before qmm.simulate in: {violations}"


def test_qua_config_split_at_modality_root() -> None:
    _skip_if_no_qca_root()
    helper = QCA_ROOT / "qua_config_split.py"
    uses_pkg = False
    for path in discover_configuration_files()[:5]:
        src = path.read_text(encoding="utf-8")
        if "qua_libs_core.qua_config" in src or "qua_config_split" in src:
            uses_pkg = True
            break
    assert helper.is_file() or uses_pkg, (
        f"Missing {helper} and no qua_libs_core.qua_config / qua_config_split import in configs"
    )


def test_split_merge_round_trip() -> None:
    import sys

    _skip_if_no_qca_root()
    try:
        from qua_libs_core.qua_config import merge_qua_config, split_qua_config  # noqa: PLC0415
    except ImportError:
        sys.path.insert(0, str(QCA_ROOT))
        try:
            from qua_config_split import merge_qua_config, split_qua_config  # noqa: PLC0415
        finally:
            sys.path.pop(0)

    sample = {
        "controllers": {"con1": {"type": "opx1000", "fems": {}}},
        "elements": {"q1": {"operations": {}}},
        "pulses": {"const": {"operation": "control"}},
        "waveforms": {"wf": {"type": "constant", "sample": 0.1}},
        "digital_waveforms": {"ON": {"samples": [(1, 0)]}},
        "integration_weights": {"cos": {"cosine": [(1.0, 0)]}},
    }
    controller, logical = split_qua_config(sample)
    merged = merge_qua_config(controller, logical)
    assert merged == sample
    assert set(controller.keys()).issubset(CONTROLLER_KEYS)
    assert set(logical.keys()).issubset(LOGICAL_KEYS)
