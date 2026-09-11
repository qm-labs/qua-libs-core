"""Unit tests for qua_libs_core.qua_config."""

from qua_libs_core.qua_config import CONTROLLER_KEYS, LOGICAL_KEYS, merge_qua_config, split_qua_config


def test_split_merge_round_trip() -> None:
    sample = {
        "controllers": {"con1": {"type": "opx1000", "fems": {}}},
        "octaves": {},
        "mixers": {},
        "elements": {"q1": {"operations": {}}},
        "pulses": {"const": {"operation": "control"}},
        "waveforms": {"wf": {"type": "constant", "sample": 0.1}},
        "digital_waveforms": {"ON": {"samples": [(1, 0)]}},
        "integration_weights": {"cos": {"cosine": [(1.0, 0)]}},
        "oscillators": {},
    }
    controller, logical = split_qua_config(sample)
    merged = merge_qua_config(controller, logical)
    assert merged == sample
    assert set(controller.keys()).issubset(CONTROLLER_KEYS)
    assert set(logical.keys()).issubset(LOGICAL_KEYS)


def test_split_omits_missing_keys() -> None:
    controller, logical = split_qua_config({"controllers": {"c": {}}, "elements": {"e": {}}})
    assert controller == {"controllers": {"c": {}}}
    assert logical == {"elements": {"e": {}}}
