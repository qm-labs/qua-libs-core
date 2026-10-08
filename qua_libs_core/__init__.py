"""qua-libs-core importable package.

Currently ships the shared ``telemetry`` subpackage — OpenTelemetry with a local
SQLite store (Uptrace optional). Telemetry is off by default; see
``docs/telemetry/`` for usage. Typical imports::

    from qua_libs_core.telemetry import start_qca_telemetry, instrument_calibration_node
"""

__version__ = "0.4.1"
