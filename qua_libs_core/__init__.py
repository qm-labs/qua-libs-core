"""qua-libs-core importable package.

Currently ships the shared ``telemetry`` subpackage — OpenTelemetry + Uptrace
instrumentation used by the per-modality qua-libs repos. Telemetry is off by
default; see ``docs/telemetry/`` for usage. Import as::

    from qua_libs_core.telemetry import instrument_calibration_node
"""

__version__ = "0.1.0"
