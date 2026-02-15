# piasecki-common

Shared Python library for the Piasecki Aerospace Skills Showcase project.

## What This Package Provides

- **Telemetry Data Models** — Pydantic dataclasses for IMU, GPS, Airspeed, and Altitude readings
- **Serialization Utilities** — JSON and Apache Parquet read/write helpers
- **Configuration Loaders** — TOML and YAML config file parsers

## Installation

```bash
# Development (editable — changes reflect immediately)
pip install -e libs/common-py/

# Production
pip install libs/common-py/
```

## Usage

```python
from piasecki_common.models import IMUReading, GPSPosition, TelemetryFrame

# Create individual sensor readings
imu = IMUReading(
    timestamp=1707900000.0,
    accel_x=0.01, accel_y=-0.02, accel_z=9.81,
    gyro_x=0.001, gyro_y=0.002, gyro_z=-0.001,
)

gps = GPSPosition(
    timestamp=1707900000.0,
    latitude=40.7128,
    longitude=-74.0060,
    altitude_msl=10.0,
    ground_speed=25.0,
    track=90.0,
    hdop=1.2,
    num_satellites=12,
)

# Serialize to JSON
print(imu.model_dump_json())
print(gps.model_dump_json())
```

## Dependencies

| Package | Purpose |
|---|---|
| pydantic | Data validation and serialization for telemetry models |
| pyarrow | Apache Parquet file support for flight data |
| pyyaml | YAML configuration parsing |
| structlog | Structured JSON logging for containerized services |
