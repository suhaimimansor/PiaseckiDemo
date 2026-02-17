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

### Telemetry Data Models

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

# Pydantic built-in serialization
print(imu.model_dump_json())  # JSON string
print(gps.model_dump())       # Python dict
```

### Serialization Utilities

The `serialization` module provides helpers for reading/writing telemetry data in JSON and Apache Parquet formats.

#### JSON Serialization

```python
from piasecki_common.serialization import write_json, read_json, write_jsonl, read_jsonl
from piasecki_common.models import IMUReading

# Write single model to JSON
reading = IMUReading(timestamp=1707900000.0, accel_x=0.0, accel_y=0.0, accel_z=9.81,
                     gyro_x=0.0, gyro_y=0.0, gyro_z=0.0)
write_json("imu.json", reading)

# Write multiple models to JSON array
readings = [reading1, reading2, reading3]
write_json("imu_batch.json", readings)

# Read back
single = read_json("imu.json", IMUReading)
batch = read_json("imu_batch.json", IMUReading, is_list=True)

# Line-delimited JSON (JSONL) — ideal for streaming large datasets
write_jsonl("telemetry.jsonl.gz", readings, compress=True)
readings = read_jsonl("telemetry.jsonl.gz", IMUReading)
```

#### Apache Parquet Serialization

Parquet is the recommended format for flight data storage — it provides 10-100x compression vs CSV, typed columns, and fast queries.

```python
from piasecki_common.serialization import write_parquet, read_parquet, parquet_to_models
from piasecki_common.models import IMUReading

# Write models to Parquet
readings = [IMUReading(...), IMUReading(...), ...]
write_parquet("telemetry.parquet", readings)

# Read as Pandas DataFrame (fast, memory-efficient)
df = read_parquet("telemetry.parquet")
print(df.head())

# Read specific columns only (column pruning)
df = read_parquet("telemetry.parquet", columns=["timestamp", "accel_z"])

# Read back as validated Pydantic models
readings = parquet_to_models("telemetry.parquet", IMUReading)
```

#### Batch Processing for Large Datasets

For datasets too large to fit in memory:

```python
from piasecki_common.serialization import write_parquet_batched

def telemetry_generator():
    """Generator that yields IMU readings one at a time."""
    for i in range(1_000_000):  # 1 million records
        yield IMUReading(timestamp=float(i), accel_x=0.0, ...)

# Write in batches (memory-efficient)
count = write_parquet_batched("huge_dataset.parquet", telemetry_generator())
print(f"Wrote {count:,} records")
```

### Configuration Loading

The `config` module provides a unified interface for loading TOML, YAML, and JSON configuration files — with optional Pydantic validation.

#### Loading Config Files

```python
from piasecki_common.config import load_toml, load_yaml, load_json

# TOML (uses Python 3.11+ built-in tomllib)
portal_config = load_toml("services/portal/config.toml")
print(portal_config["service"]["name"])  # "Portal"

# YAML (uses pyyaml with safe_load for security)
gcs_config = load_yaml("services/gcs/config.yaml")
print(gcs_config["redis"]["host"])  # "localhost"

# JSON (uses Python built-in json module)
sim_config = load_json("services/simulation/config.json")
print(sim_config["update_rate_hz"])  # 50
```

#### Pydantic-Validated Config

```python
from pydantic import BaseModel
from piasecki_common.config import load_toml_as, load_yaml_as

class ServiceConfig(BaseModel):
    name: str
    port: int
    debug: bool = False

# Raises ValidationError at startup if config is invalid
config = load_toml_as("config.toml", ServiceConfig)
print(config.port)  # Type-safe access
```

#### Safe Nested Access & Config Merging

```python
from piasecki_common.config import get_nested, merge_configs

# Safe nested access (no KeyError chains)
config = {"database": {"connection": {"pool": {"max_size": 10}}}}
get_nested(config, "database", "connection", "pool", "max_size")  # 10
get_nested(config, "missing", "key", default="fallback")          # "fallback"

# Deep-merge layered configs (base → env → CLI overrides)
base = {"db": {"host": "localhost", "port": 5432}, "debug": False}
prod = {"db": {"host": "prod-server"}, "debug": True}
merged = merge_configs(base, prod)
# {'db': {'host': 'prod-server', 'port': 5432}, 'debug': True}
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=piasecki_common --cov-report=term-missing
```

**91 tests** covering models, serialization, and configuration:

| Test Module | Tests | Coverage |
|---|---|---|
| `test_models.py` | 22 | Model validation, immutability, JSON round-trips |
| `test_serialization.py` | 34 | JSON, JSONL, Parquet read/write, batched writes |
| `test_config.py` | 35 | TOML/YAML/JSON loading, `get_nested`, `merge_configs` |

## Dependencies

| Package | Purpose |
|---|---|
| pydantic | Data validation and serialization for telemetry models |
| pyarrow | Apache Parquet file support for flight data |
| pyyaml | YAML configuration parsing |
| structlog | Structured JSON logging for containerized services |
