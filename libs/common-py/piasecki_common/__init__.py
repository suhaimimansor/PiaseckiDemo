"""Piasecki Common — Shared Python library for aerospace telemetry services.

This package provides the foundational data models, serialization utilities,
and configuration loaders used by all microservices in the Piasecki Aerospace
Skills Showcase project.

Modules:
    models          Pydantic data models for telemetry (IMU, GPS, Airspeed, Altitude)
    serialization   JSON and Parquet read/write helpers
    config          TOML and YAML configuration loader

Example:
    >>> from piasecki_common.models import IMUReading
    >>> reading = IMUReading(
    ...     timestamp=1707900000.0,
    ...     accel_x=0.01, accel_y=-0.02, accel_z=9.81,
    ...     gyro_x=0.001, gyro_y=0.002, gyro_z=-0.001,
    ... )
    >>> reading.accel_z
    9.81
"""

# ---------------------------------------------------------------------------
# Package version — kept in sync with pyproject.toml [project] version.
# Accessible at runtime via: piasecki_common.__version__
# ---------------------------------------------------------------------------
__version__ = "0.1.0"
