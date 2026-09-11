"""Split and merge QUA configuration dicts (controller vs logical)."""

from __future__ import annotations

from typing import Any

CONTROLLER_KEYS = ("controllers", "octaves", "mixers")
LOGICAL_KEYS = ("oscillators", "elements", "integration_weights", "waveforms", "digital_waveforms", "pulses")


def split_qua_config(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a full QUA config into controller and logical parts."""
    controller_config = {key: config[key] for key in CONTROLLER_KEYS if key in config}
    logical_config = {key: config[key] for key in LOGICAL_KEYS if key in config}
    return controller_config, logical_config


def merge_qua_config(controller_config: dict[str, Any], logical_config: dict[str, Any]) -> dict[str, Any]:
    """Merge controller and logical configs into a full QUA config."""
    return {**controller_config, **logical_config}
