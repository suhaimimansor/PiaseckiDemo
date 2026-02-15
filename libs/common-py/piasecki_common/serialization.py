"""Serialization utilities for telemetry data.

This module provides helper functions for reading and writing telemetry data
in various formats: JSON (human-readable, debugging) and Apache Parquet
(columnar, compressed, production time-series storage).

WHY THESE FORMATS?
------------------
JSON:
  - Human-readable, widely supported, easy to debug
  - Built-in to Python (json module)
  - Pydantic models have native JSON serialization (.model_dump_json())
  - Use cases: API responses, configuration, small datasets, debugging

Apache Parquet:
  - Columnar storage format designed for analytics
  - 10-100x compression vs CSV, typed columns, fast queries
  - Native support in Pandas, DuckDB, Spark, Polars
  - Ideal for time-series flight data (millions of sensor readings)
  - Use cases: Flight data logging, batch analysis, data lake storage

DESIGN DECISIONS:
-----------------
1. All functions accept `Path | str` for file paths (flexible, modern)
2. Parquet functions work with lists of Pydantic models or Pandas DataFrames
3. JSON functions handle both single objects and lists (line-delimited JSONL)
4. Compression is enabled by default (snappy for Parquet, gzip for JSONL)
5. Timestamps are preserved as float64 (no timezone confusion)

PARQUET SCHEMA MAPPING:
-----------------------
Pydantic model → Parquet column types:
  - float (timestamp, accel, gyro, etc.) → float64
  - int (num_satellites) → int64
  - Optional[T] → nullable column
  - Nested models (TelemetryFrame) → struct columns (nested schema)

Example:
    >>> from piasecki_common.models import IMUReading, TelemetryFrame
    >>> from piasecki_common.serialization import (
    ...     write_json, read_json, write_parquet, read_parquet
    ... )
    >>>
    >>> # Create sample data
    >>> readings = [
    ...     IMUReading(timestamp=t, accel_x=0.0, accel_y=0.0, accel_z=9.81,
    ...                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0)
    ...     for t in range(1707900000, 1707900010)
    ... ]
    >>>
    >>> # Write to JSON (human-readable)
    >>> write_json("imu_data.json", readings)
    >>>
    >>> # Write to Parquet (compressed, fast)
    >>> write_parquet("imu_data.parquet", readings)
    >>>
    >>> # Read back from Parquet
    >>> df = read_parquet("imu_data.parquet")
    >>> print(df.head())
"""

from pathlib import Path
from typing import Any, List, Type, TypeVar

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel

# Type variable for generic Pydantic models
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# JSON Serialization
# =============================================================================


def write_json(
    filepath: Path | str,
    data: BaseModel | List[BaseModel],
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> None:
    """Write Pydantic model(s) to a JSON file.

    This is a convenience wrapper around Pydantic's built-in JSON serialization.
    For single objects, writes a standard JSON object. For lists, writes a
    JSON array.

    Args:
        filepath: Output file path (overwrites if exists)
        data: Single Pydantic model or list of models
        indent: JSON indentation (2 spaces by default, None for compact)
        ensure_ascii: If True, escape non-ASCII chars (default False for UTF-8)

    Example:
        >>> from piasecki_common.models import IMUReading
        >>> reading = IMUReading(timestamp=1707900000.0, accel_x=0.0, ...)
        >>> write_json("imu.json", reading)
        >>> write_json("imu_batch.json", [reading, reading2, reading3])
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, list):
        # List of models → JSON array
        json_str = f"[{','.join(item.model_dump_json() for item in data)}]"
        # Re-parse and pretty-print if indent is specified
        if indent is not None:
            import json

            json_obj = json.loads(json_str)
            json_str = json.dumps(json_obj, indent=indent, ensure_ascii=ensure_ascii)
    else:
        # Single model → JSON object
        json_str = data.model_dump_json(indent=indent)

    filepath.write_text(json_str, encoding="utf-8")


def read_json(
    filepath: Path | str,
    model: Type[T],
    *,
    is_list: bool = False,
) -> T | List[T]:
    """Read JSON file into Pydantic model(s).

    Args:
        filepath: Input JSON file path
        model: Pydantic model class to deserialize into
        is_list: If True, expect a JSON array and return a list of models

    Returns:
        Single model instance or list of instances (depending on is_list)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If JSON doesn't match the model schema

    Example:
        >>> from piasecki_common.models import IMUReading
        >>> reading = read_json("imu.json", IMUReading)
        >>> readings = read_json("imu_batch.json", IMUReading, is_list=True)
    """
    filepath = Path(filepath)
    json_str = filepath.read_text(encoding="utf-8")

    if is_list:
        # Parse JSON array → list of models
        import json

        json_list = json.loads(json_str)
        return [model.model_validate(item) for item in json_list]
    else:
        # Parse single JSON object → single model
        return model.model_validate_json(json_str)


def write_jsonl(
    filepath: Path | str,
    data: List[BaseModel],
    *,
    compress: bool = True,
) -> None:
    """Write Pydantic models to line-delimited JSON (JSONL/NDJSON).

    JSONL is a streaming-friendly format where each line is a separate JSON
    object. This is ideal for large datasets that don't fit in memory, as you
    can process line-by-line.

    Advantages over standard JSON array:
      - Streamable (can read/write one line at a time)
      - Appendable (add new records without rewriting the entire file)
      - Common in data pipelines (used by BigQuery, Spark, etc.)

    Args:
        filepath: Output file path (.jsonl or .jsonl.gz)
        data: List of Pydantic models
        compress: If True, gzip compress the output (saves 70-90% space)

    Example:
        >>> readings = [IMUReading(...), IMUReading(...), ...]
        >>> write_jsonl("telemetry.jsonl.gz", readings)  # Compressed
        >>> write_jsonl("telemetry.jsonl", readings, compress=False)  # Plain
    """
    import gzip

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Generate line-delimited JSON
    lines = [item.model_dump_json() + "\n" for item in data]

    if compress:
        # Write compressed JSONL
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            f.writelines(lines)
    else:
        # Write plain JSONL
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)


def read_jsonl(
    filepath: Path | str,
    model: Type[T],
) -> List[T]:
    """Read line-delimited JSON (JSONL/NDJSON) into Pydantic models.

    Handles both plain (.jsonl) and gzip-compressed (.jsonl.gz) files
    automatically based on file extension.

    Args:
        filepath: Input JSONL file path
        model: Pydantic model class to deserialize into

    Returns:
        List of model instances (one per line)

    Example:
        >>> from piasecki_common.models import IMUReading
        >>> readings = read_jsonl("telemetry.jsonl.gz", IMUReading)
    """
    import gzip

    filepath = Path(filepath)

    # Auto-detect gzip compression by file extension
    if filepath.suffix == ".gz":
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Parse each line as a separate model
    return [model.model_validate_json(line.strip()) for line in lines if line.strip()]


# =============================================================================
# Parquet Serialization
# =============================================================================


def write_parquet(
    filepath: Path | str,
    data: List[BaseModel] | pd.DataFrame,
    *,
    compression: str = "snappy",
) -> None:
    """Write Pydantic models or DataFrame to Apache Parquet file.

    Parquet is a columnar storage format that provides:
      - Compression: 10-100x smaller than CSV
      - Typed columns: Preserves int/float/string types
      - Fast queries: Can read only the columns you need
      - Wide compatibility: Pandas, DuckDB, Spark, Polars, etc.

    Args:
        filepath: Output file path (.parquet)
        data: List of Pydantic models or Pandas DataFrame
        compression: Compression algorithm ('snappy', 'gzip', 'brotli', 'none')
                     snappy = fast, moderate compression (default)
                     gzip = slower, better compression
                     brotli = slowest, best compression

    Example:
        >>> readings = [IMUReading(...), IMUReading(...), ...]
        >>> write_parquet("imu_data.parquet", readings)
        >>>
        >>> # Or from a DataFrame
        >>> df = pd.DataFrame([r.model_dump() for r in readings])
        >>> write_parquet("imu_data.parquet", df)
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, pd.DataFrame):
        # DataFrame → Parquet (direct)
        df = data
    else:
        # List of Pydantic models → DataFrame → Parquet
        # model_dump() converts each model to a plain dict
        records = [item.model_dump() for item in data]
        df = pd.DataFrame(records)

    # Write to Parquet with compression
    df.to_parquet(
        filepath,
        engine="pyarrow",
        compression=compression,
        index=False,  # Don't write DataFrame index as a column
    )


def read_parquet(
    filepath: Path | str,
    *,
    columns: List[str] | None = None,
) -> pd.DataFrame:
    """Read Apache Parquet file into a Pandas DataFrame.

    Parquet supports efficient column pruning — you can read only the columns
    you need, which saves memory and speeds up queries.

    Args:
        filepath: Input Parquet file path
        columns: List of column names to read (None = read all)

    Returns:
        Pandas DataFrame with the telemetry data

    Example:
        >>> df = read_parquet("telemetry.parquet")
        >>> print(df.head())
        >>>
        >>> # Read only specific columns (faster)
        >>> df = read_parquet("telemetry.parquet", columns=["timestamp", "accel_z"])
    """
    filepath = Path(filepath)

    return pd.read_parquet(
        filepath,
        engine="pyarrow",
        columns=columns,
    )


def parquet_to_models(
    filepath: Path | str,
    model: Type[T],
    *,
    columns: List[str] | None = None,
) -> List[T]:
    """Read Parquet file and deserialize into Pydantic models.

    This combines read_parquet() with Pydantic validation. Useful when you
    need to work with validated model instances rather than raw DataFrames.

    WARNING: For large files (millions of rows), this will load all data into
    memory as Python objects. Consider using read_parquet() and processing the
    DataFrame in chunks instead.

    Args:
        filepath: Input Parquet file path
        model: Pydantic model class to deserialize into
        columns: List of column names to read (None = read all)

    Returns:
        List of Pydantic model instances

    Example:
        >>> from piasecki_common.models import IMUReading
        >>> readings = parquet_to_models("imu_data.parquet", IMUReading)
        >>> print(readings[0].accel_z)  # Validated Pydantic model
    """
    df = read_parquet(filepath, columns=columns)

    # Convert DataFrame rows → dict → Pydantic model
    # DataFrame.to_dict('records') → [{col: val, ...}, {col: val, ...}, ...]
    records = df.to_dict("records")
    return [model.model_validate(record) for record in records]


# =============================================================================
# Batch Processing Helpers
# =============================================================================


def write_parquet_batched(
    filepath: Path | str,
    data_iter: Any,
    *,
    batch_size: int = 10000,
    compression: str = "snappy",
) -> int:
    """Write large datasets to Parquet in batches (memory-efficient).

    For datasets too large to fit in memory, this function processes data in
    batches and appends to a single Parquet file.

    Args:
        filepath: Output Parquet file path
        data_iter: Iterator/generator yielding Pydantic models
        batch_size: Number of records per batch (10K default)
        compression: Compression algorithm ('snappy', 'gzip', 'brotli')

    Returns:
        Total number of records written

    Example:
        >>> def telemetry_stream():
        ...     for i in range(1000000):  # 1 million records
        ...         yield IMUReading(timestamp=float(i), ...)
        >>>
        >>> count = write_parquet_batched("huge_dataset.parquet", telemetry_stream())
        >>> print(f"Wrote {count} records")
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    writer = None
    total_count = 0
    batch = []

    for item in data_iter:
        batch.append(item.model_dump())

        if len(batch) >= batch_size:
            # Convert batch to DataFrame and write
            df = pd.DataFrame(batch)
            table = pa.Table.from_pandas(df)

            if writer is None:
                # First batch — create the file and writer
                writer = pq.ParquetWriter(filepath, table.schema, compression=compression)

            writer.write_table(table)
            total_count += len(batch)
            batch = []

    # Write remaining records (last partial batch)
    if batch:
        df = pd.DataFrame(batch)
        table = pa.Table.from_pandas(df)

        if writer is None:
            # Edge case: total data < batch_size
            writer = pq.ParquetWriter(filepath, table.schema, compression=compression)

        writer.write_table(table)
        total_count += len(batch)

    if writer is not None:
        writer.close()

    return total_count
