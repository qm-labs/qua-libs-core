"""Headless QCA script simulation — emits waveform report JSON on stdout."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return str(obj)


def _find_program_name(source: str) -> str | None:
    match = re.search(r"with\s+program\s*\(\s*\)\s+as\s+(\w+)\s*:", source)
    return match.group(1) if match else None


def load_program_namespace(script_path: Path) -> tuple[Any, Any, Any]:
    import matplotlib

    matplotlib.use("Agg")

    source = script_path.read_text(encoding="utf-8")
    marker = "qmm = QuantumMachinesManager"
    if marker not in source:
        raise RuntimeError(f"{script_path}: could not find '{marker}'")
    prelude = source.split(marker, 1)[0]

    ns: dict[str, Any] = {
        "__name__": "__simulate_runner__",
        "__file__": str(script_path.resolve()),
    }
    exec(compile(prelude, str(script_path), "exec"), ns)  # noqa: S102

    prog_name = _find_program_name(source)
    program = ns.get(prog_name) if prog_name else None
    if program is None:
        for key, value in ns.items():
            if key.startswith("_"):
                continue
            if hasattr(value, "is_reversed"):
                program = value
                break
    if program is None:
        raise RuntimeError(f"{script_path}: QUA program not found (expected '{prog_name}')")

    if "config" not in ns:
        raise RuntimeError(f"{script_path}: configuration did not define 'config'")
    if "qop_ip" not in ns or "cluster_name" not in ns:
        raise RuntimeError(f"{script_path}: configuration missing qop_ip / cluster_name")

    return ns["config"], program, ns


def _config_uses_opx1000(config: dict[str, Any]) -> bool:
    return any(
        controller.get("type") == "opx1000" or "fems" in controller
        for controller in config.get("controllers", {}).values()
    )


def simulate_script(script_path: Path, duration: int) -> dict[str, Any]:
    import logging

    from qm import QuantumMachinesManager, SimulationConfig

    # qm logs to stdout by default; keep stdout clean for JSON payload
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)

    config, program, ns = load_program_namespace(script_path)
    qop_ip = ns["qop_ip"]
    qop_port = ns.get("qop_port")
    cluster_name = ns["cluster_name"]

    qmm = QuantumMachinesManager(host=qop_ip, port=qop_port, cluster_name=cluster_name)
    job = qmm.simulate(config, program, SimulationConfig(duration=duration))
    if _config_uses_opx1000(config):
        job.wait_until("Done")
    return job.get_simulated_waveform_report().to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path, help="QCA script path (run from its directory context)")
    parser.add_argument("--duration", type=int, default=10_000, help="Simulation duration in clock cycles")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this file (default: stdout)",
    )
    args = parser.parse_args()

    script_path = args.script.resolve()
    if not script_path.is_file():
        print(f"Script not found: {script_path}", file=sys.stderr)
        return 1

    import os

    os.chdir(script_path.parent)
    sys.path.insert(0, str(script_path.parent))

    try:
        report = simulate_script(script_path, args.duration)
    except Exception as exc:  # noqa: BLE001 — surface runner failures to orchestrator
        print(str(exc), file=sys.stderr)
        return 1

    payload = json.dumps(report, default=_json_default, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
