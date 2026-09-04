"""
Turn a QCA script's ``save_data_dict`` into typed, queryable span attributes.

Why this exists
---------------
The QCA (Quantum-Control-Applications) scripts are linear, pedagogical files with
module-level parameters -- there is no ``Parameters`` class to introspect the way
the QUAlibrate nodes have. What they *do* have is ``save_data_dict``, present in
38 of the 44 Single-Fixed-Transmon scripts, holding exactly the run parameters
and already persisted alongside the dataset by ``DataHandler``. Deriving span
attributes from it means the trace and the saved data describe the same run with
the same names, and cannot drift apart.

Design rules
------------
* **Typed, not stringified.** OpenTelemetry attributes may be str/bool/int/float
  (or homogeneous arrays). Numbers are emitted as numbers so Uptrace can range-
  filter and aggregate them. Stringifying is what blocks aggregation.
* **Flat with dotted prefixes.** OTel has no nested-object attribute. Dotted keys
  (``param.sweep.step_hz``) stay flat on the wire but render as a group in the
  Uptrace UI, which gives grouping without giving up queryability.
* **``config`` is hashed, not sent.** The QUA config is a large nested dict. Its
  *identity* is what's useful, so it becomes ``param.config.sha12`` -- enough to
  group every run that shared a config, for 12 bytes.
* **Arrays collapse to derived scalars.** A 401-point sweep vector is useless as
  an attribute and bloats every span. A uniform numeric sweep becomes
  points/start/stop/step/center/span; anything else becomes a count.
"""

from __future__ import annotations

import hashlib
import logging
import pprint
from typing import Any, Dict, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

# Keys that must never become attributes, mapped to how they are summarised instead.
_HASH_ONLY = {"config"}

# Result payloads that get merged into save_data_dict *after* the run. They should
# never appear as parameters -- see the snapshot-timing note in instrument_qca_script.
_RESULT_KEYS = {
    "I_data", "Q_data", "fig_live", "fig", "figure", "state_data", "adc_data",
}

# The same physical quantity is spelled differently across scripts. Normalise so a
# dashboard can compare runs from different files.
_ALIASES = {
    "amps": "amplitudes",
    "tau_vec": "taus",
    "IF_frequencies": "if_frequencies",
    "LO_frequencies": "lo_frequencies",
}

# save_data_dict keys carry no units, so units are supplied here. Unknown keys fall
# through with no suffix rather than guessing wrong.
_UNITS = {
    "frequencies": "hz",
    "if_frequencies": "hz",
    "lo_frequencies": "hz",
    "external_frequencies": "hz",
    "detuning": "hz",
    "taus": "ns",
    "durations": "ns",
    "readout_len": "ns",
    "saturation_len": "ns",
    "ringdown_len": "ns",
    "division_length": "ns",
    # dimensionless / counts -> deliberately absent
}

_SCALARS = (bool, int, float, str)


def config_fingerprint(config: Any, length: int = 12) -> str:
    """Stable short hash of a QUA config.

    ``pprint.pformat(sort_dicts=True)`` is used rather than ``json.dumps`` because
    QUA configs key elements by tuples (e.g. ``("con1", 1, 1)``), which JSON
    rejects outright.
    """
    canonical = pprint.pformat(config, sort_dicts=True, width=200)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:length]


def _unit_suffix(name: str) -> str:
    unit = _UNITS.get(name)
    return f"_{unit}" if unit else ""


def _as_number_list(value: Any) -> Optional[list]:
    """Return value as a list of numbers, or None if it isn't a numeric sequence."""
    if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
        return None
    # numpy arrays, lists, tuples -- anything sized and iterable
    if not isinstance(value, Sequence) and not hasattr(value, "__array__"):
        return None
    try:
        items = list(value)
    except TypeError:
        return None
    if not items:
        return None
    out = []
    for item in items:
        # numpy scalars are not int/float instances but do convert cleanly
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            try:
                item = float(item)
            except (TypeError, ValueError):
                return None
        out.append(float(item))
    return out


def _sweep_attributes(name: str, values: list, prefix: str) -> Dict[str, Any]:
    """Collapse a numeric sequence into the handful of scalars worth aggregating."""
    suffix = _unit_suffix(name)
    base = f"{prefix}.{name}"
    attrs: Dict[str, Any] = {f"{base}.points": len(values)}

    if len(values) < 2:
        attrs[f"{base}.start{suffix}"] = values[0]
        return attrs

    diffs = [b - a for a, b in zip(values, values[1:])]
    step = diffs[0]
    uniform = all(abs(d - step) <= 1e-9 * max(1.0, abs(step)) for d in diffs)

    attrs[f"{base}.start{suffix}"] = values[0]
    attrs[f"{base}.stop{suffix}"] = values[-1]
    attrs[f"{base}.span{suffix}"] = values[-1] - values[0]
    attrs[f"{base}.center{suffix}"] = (values[0] + values[-1]) / 2.0
    if uniform:
        attrs[f"{base}.step{suffix}"] = step
    else:
        # Non-uniform sweeps (log spacing, hand-built vectors) have no single step.
        attrs[f"{base}.uniform"] = False
    return attrs


def qca_param_attributes(
    params: Optional[Mapping[str, Any]],
    prefix: str = "param",
) -> Dict[str, Any]:
    """Flatten a QCA ``save_data_dict`` into typed span attributes.

    Args:
        params: The script's ``save_data_dict``, read *before* results are merged
            into it. ``None`` yields an empty dict.
        prefix: Attribute namespace. ``param`` groups these under one heading in
            the Uptrace span view.

    Returns:
        Flat ``{key: scalar}`` suitable for ``span.set_attribute``. Unsupported
        values are dropped (and logged at debug level) rather than stringified,
        so nothing unqueryable reaches the backend.

    Example:
        >>> attrs = qca_param_attributes({"n_avg": 1000, "config": {...}})
        >>> attrs["param.n_avg"]
        1000
    """
    if not params:
        return {}

    attrs: Dict[str, Any] = {}

    for raw_key, value in params.items():
        if raw_key in _HASH_ONLY:
            try:
                attrs[f"{prefix}.{raw_key}.sha12"] = config_fingerprint(value)
            except Exception as exc:  # noqa: BLE001 - telemetry must never break a run
                logger.debug("Could not fingerprint %r: %s", raw_key, exc)
            continue

        if raw_key in _RESULT_KEYS:
            # Result payload, not a parameter. Silently skip: this happens when the
            # dict is read after the run rather than before it.
            continue

        key = _ALIASES.get(raw_key, raw_key)

        if value is None:
            continue

        if isinstance(value, _SCALARS):
            attrs[f"{prefix}.{key}{_unit_suffix(key)}"] = value
            continue

        numbers = _as_number_list(value)
        if numbers is not None:
            attrs.update(_sweep_attributes(key, numbers, prefix))
            continue

        logger.debug("Skipping unsupported telemetry parameter %r (%s)", raw_key, type(value).__name__)

    return attrs
