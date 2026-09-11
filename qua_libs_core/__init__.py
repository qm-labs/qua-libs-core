"""qua-libs-core importable package.

Ships shared ``telemetry`` (OpenTelemetry + Uptrace; off by default — see
``docs/telemetry/``) and ``qua_config`` (controller/logical QUA config split).
Import as::

    from qua_libs_core.telemetry import instrument_calibration_node
    from qua_libs_core.qua_config import merge_qua_config, split_qua_config
"""

__version__ = "0.1.0"
