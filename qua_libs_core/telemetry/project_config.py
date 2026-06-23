"""
Project-wide telemetry configuration.

Telemetry is OFF by default. To turn it on, choose either:
  - Environment variables (no code change): set UPTRACE_ENABLED=true and
    UPTRACE_DSN=<your DSN>. Point the DSN at Uptrace Cloud or your self-hosted
    Uptrace server (see the self-host setup docs).
  - This file: pass enabled=True and dsn="..." below to turn telemetry on for
    all calibration nodes without environment variables.

No DSN is shipped by default, so an unconfigured install never sends telemetry.
"""

from .config import TelemetryConfig

PROJECT_CONFIG = TelemetryConfig(
    # dsn defaults to the UPTRACE_DSN env var when omitted. Set it explicitly here
    # to hard-code a destination (e.g. a self-hosted Uptrace) for all nodes.
    service_name="qua-libs",
    service_version="1.0.0",
    deployment_environment="production",
    # enabled defaults to the UPTRACE_ENABLED env var (off). Set enabled=True here
    # to force telemetry on from this file regardless of the environment.
)
