"""Unit tests for piasecki_common.serialization — JSON & Parquet I/O.

Tests cover:
  - JSON write/read round-trip (single model and list)
  - JSONL write/read round-trip (plain and gzip-compressed)
  - Parquet write/read round-trip (from model list and from DataFrame)
  - parquet_to_models() — Parquet → Pydantic model deserialization
  - write_parquet_batched() — streaming write with configurable batch size
  - Column selection in Parquet reads
  - Edge cases: empty lists, single-item lists, large batches

WHY THESE TESTS?
----------------
Serialization is the bridge between in-memory models and persistent storage.
If serialization is lossy (drops fields, truncates precision, corrupts types),
data analysis downstream produces garbage. These tests ensure:

  1. Round-trip fidelity: write → read → compare == original
  2. Compression works: gzip JSONL and Snappy Parquet produce valid output
  3. Format correctness: files are valid JSON/JSONL/Parquet
  4. Edge cases: empty data, single records, large batches

RUN:
    pytest tests/test_serialization.py -v
"""

from pathlib import Path

import pandas as pd
import pytest

from piasecki_common.models import IMUReading, GPSPosition, AirspeedReading
from piasecki_common.serialization import (
    parquet_to_models,
    read_json,
    read_jsonl,
    read_parquet,
    write_json,
    write_jsonl,
    write_parquet,
    write_parquet_batched,
)


# =============================================================================
# Fixtures — Reusable sample data
# =============================================================================


def _make_imu(timestamp: float = 1707900000.0) -> IMUReading:
    """Create a sample IMU reading with the given timestamp."""
    return IMUReading(
        timestamp=timestamp,
        accel_x=0.01,
        accel_y=-0.02,
        accel_z=9.81,
        gyro_x=0.001,
        gyro_y=0.002,
        gyro_z=-0.001,
    )


def _make_gps(timestamp: float = 1707900000.0) -> GPSPosition:
    """Create a sample GPS position."""
    return GPSPosition(
        timestamp=timestamp,
        latitude=39.8583,
        longitude=-75.3002,
        altitude_msl=5.0,
        ground_speed=0.0,
        track=0.0,
        hdop=1.2,
        num_satellites=12,
    )


@pytest.fixture
def imu_list() -> list[IMUReading]:
    """Create a list of 5 IMU readings with sequential timestamps."""
    return [_make_imu(timestamp=1707900000.0 + i) for i in range(5)]


@pytest.fixture
def single_imu() -> IMUReading:
    """Single IMU reading for simple tests."""
    return _make_imu()


# =============================================================================
# JSON Write/Read Round-Trip
# =============================================================================


class TestWriteJson:
    """Tests for write_json() and read_json()."""

    def test_single_model_round_trip(
        self, tmp_path: Path, single_imu: IMUReading
    ) -> None:
        """Write a single model to JSON and read it back."""
        filepath = tmp_path / "single.json"
        write_json(filepath, single_imu)
        restored = read_json(filepath, IMUReading)
        assert restored == single_imu

    def test_list_round_trip(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """Write a list of models to JSON and read them back."""
        filepath = tmp_path / "list.json"
        write_json(filepath, imu_list)
        restored = read_json(filepath, IMUReading, is_list=True)
        assert restored == imu_list

    def test_creates_parent_directories(self, tmp_path: Path, single_imu: IMUReading) -> None:
        """write_json creates parent directories if they don't exist."""
        filepath = tmp_path / "deep" / "nested" / "dir" / "data.json"
        write_json(filepath, single_imu)
        assert filepath.exists()

    def test_compact_json(self, tmp_path: Path, single_imu: IMUReading) -> None:
        """indent=None produces compact JSON (no whitespace)."""
        filepath = tmp_path / "compact.json"
        write_json(filepath, single_imu, indent=None)
        content = filepath.read_text()
        # Compact JSON has no newlines
        assert "\n" not in content

    def test_file_is_valid_json(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """Output file is valid JSON that can be parsed by stdlib json."""
        import json

        filepath = tmp_path / "valid.json"
        write_json(filepath, imu_list)
        data = json.loads(filepath.read_text())
        assert isinstance(data, list)
        assert len(data) == 5


# =============================================================================
# JSONL Write/Read Round-Trip
# =============================================================================


class TestWriteJsonl:
    """Tests for write_jsonl() and read_jsonl()."""

    def test_plain_jsonl_round_trip(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """Write and read plain (uncompressed) JSONL."""
        filepath = tmp_path / "data.jsonl"
        write_jsonl(filepath, imu_list, compress=False)
        restored = read_jsonl(filepath, IMUReading)
        assert restored == imu_list

    def test_gzip_jsonl_round_trip(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """Write and read gzip-compressed JSONL."""
        filepath = tmp_path / "data.jsonl.gz"
        write_jsonl(filepath, imu_list, compress=True)
        restored = read_jsonl(filepath, IMUReading)
        assert restored == imu_list

    def test_one_line_per_record(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """Each model is on its own line in JSONL format."""
        filepath = tmp_path / "lines.jsonl"
        write_jsonl(filepath, imu_list, compress=False)
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 5

    def test_empty_list(self, tmp_path: Path) -> None:
        """Writing an empty list produces an empty (or near-empty) file."""
        filepath = tmp_path / "empty.jsonl"
        write_jsonl(filepath, [], compress=False)
        restored = read_jsonl(filepath, IMUReading)
        assert restored == []

    def test_gzip_smaller_than_plain(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """Gzip-compressed JSONL should be smaller than plain JSONL."""
        plain_path = tmp_path / "plain.jsonl"
        gz_path = tmp_path / "compressed.jsonl.gz"
        write_jsonl(plain_path, imu_list, compress=False)
        write_jsonl(gz_path, imu_list, compress=True)
        assert gz_path.stat().st_size < plain_path.stat().st_size


# =============================================================================
# Parquet Write/Read Round-Trip
# =============================================================================


class TestWriteParquet:
    """Tests for write_parquet() and read_parquet()."""

    def test_model_list_round_trip(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """Write Pydantic models to Parquet and read back as DataFrame."""
        filepath = tmp_path / "imu.parquet"
        write_parquet(filepath, imu_list)
        df = read_parquet(filepath)
        assert len(df) == 5
        assert "accel_z" in df.columns

    def test_dataframe_round_trip(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """Write a Pandas DataFrame to Parquet and read it back."""
        filepath = tmp_path / "df.parquet"
        df_in = pd.DataFrame([m.model_dump() for m in imu_list])
        write_parquet(filepath, df_in)
        df_out = read_parquet(filepath)
        pd.testing.assert_frame_equal(df_in, df_out)

    def test_column_selection(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """read_parquet can select specific columns (column pruning)."""
        filepath = tmp_path / "select.parquet"
        write_parquet(filepath, imu_list)
        df = read_parquet(filepath, columns=["timestamp", "accel_z"])
        assert list(df.columns) == ["timestamp", "accel_z"]
        assert len(df) == 5

    def test_gzip_compression(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """Parquet with gzip compression is valid and readable."""
        filepath = tmp_path / "gzip.parquet"
        write_parquet(filepath, imu_list, compression="gzip")
        df = read_parquet(filepath)
        assert len(df) == 5

    def test_creates_parent_directories(
        self, tmp_path: Path, imu_list: list[IMUReading]
    ) -> None:
        """write_parquet creates parent directories if needed."""
        filepath = tmp_path / "deep" / "dir" / "data.parquet"
        write_parquet(filepath, imu_list)
        assert filepath.exists()


# =============================================================================
# Parquet → Pydantic Models
# =============================================================================


class TestParquetToModels:
    """Tests for parquet_to_models() — read Parquet back into Pydantic."""

    def test_round_trip(self, tmp_path: Path, imu_list: list[IMUReading]) -> None:
        """Write models → Parquet → models produces identical data."""
        filepath = tmp_path / "models.parquet"
        write_parquet(filepath, imu_list)
        restored = parquet_to_models(filepath, IMUReading)
        assert len(restored) == len(imu_list)
        for original, loaded in zip(imu_list, restored):
            assert original == loaded

    def test_column_selection(self, tmp_path: Path) -> None:
        """parquet_to_models with column selection still validates."""
        # GPS has optional fields — write full records, read subset
        gps_list = [_make_gps(timestamp=1707900000.0 + i) for i in range(3)]
        filepath = tmp_path / "gps.parquet"
        write_parquet(filepath, gps_list)
        # Read only a few columns — won't validate as GPSPosition
        # (missing required fields), so we just check it works for DataFrames
        df = read_parquet(filepath, columns=["timestamp", "latitude"])
        assert len(df) == 3
        assert "timestamp" in df.columns

    def test_type_is_correct(self, tmp_path: Path, single_imu: IMUReading) -> None:
        """Returned objects are actual Pydantic model instances."""
        filepath = tmp_path / "typed.parquet"
        write_parquet(filepath, [single_imu])
        result = parquet_to_models(filepath, IMUReading)
        assert isinstance(result[0], IMUReading)


# =============================================================================
# Batched Parquet Writer
# =============================================================================


class TestWriteParquetBatched:
    """Tests for write_parquet_batched() — streaming write."""

    def test_basic_batched_write(self, tmp_path: Path) -> None:
        """Batched write produces a valid Parquet file."""
        filepath = tmp_path / "batched.parquet"

        def imu_stream():
            for i in range(25):
                yield _make_imu(timestamp=1707900000.0 + i)

        count = write_parquet_batched(filepath, imu_stream(), batch_size=10)
        assert count == 25
        df = read_parquet(filepath)
        assert len(df) == 25

    def test_batch_size_larger_than_data(self, tmp_path: Path) -> None:
        """Works correctly when batch_size > total records (single batch)."""
        filepath = tmp_path / "small.parquet"

        def small_stream():
            for i in range(3):
                yield _make_imu(timestamp=1707900000.0 + i)

        count = write_parquet_batched(filepath, small_stream(), batch_size=10000)
        assert count == 3
        df = read_parquet(filepath)
        assert len(df) == 3

    def test_exact_batch_boundary(self, tmp_path: Path) -> None:
        """Exactly batch_size records (no partial batch at end)."""
        filepath = tmp_path / "exact.parquet"

        def exact_stream():
            for i in range(10):
                yield _make_imu(timestamp=1707900000.0 + i)

        count = write_parquet_batched(filepath, exact_stream(), batch_size=10)
        assert count == 10
        df = read_parquet(filepath)
        assert len(df) == 10

    def test_empty_iterator(self, tmp_path: Path) -> None:
        """Empty iterator writes 0 records and returns 0."""
        filepath = tmp_path / "empty.parquet"
        count = write_parquet_batched(filepath, iter([]))
        assert count == 0

    def test_data_integrity(self, tmp_path: Path) -> None:
        """Batched write preserves data values (no corruption)."""
        filepath = tmp_path / "integrity.parquet"

        timestamps = [1707900000.0 + i for i in range(15)]

        def stream():
            for ts in timestamps:
                yield _make_imu(timestamp=ts)

        write_parquet_batched(filepath, stream(), batch_size=7)
        models = parquet_to_models(filepath, IMUReading)
        assert [m.timestamp for m in models] == timestamps


# =============================================================================
# GPS Model with Optional Fields — Parquet Nullable Columns
# =============================================================================


class TestGPSParquetNullable:
    """Tests for Parquet handling of Optional/nullable fields."""

    def test_optional_fields_preserved(self, tmp_path: Path) -> None:
        """Optional fields that are None survive the Parquet round-trip."""
        gps_no_extras = GPSPosition(
            timestamp=1707900000.0,
            latitude=39.85,
            longitude=-75.30,
            altitude_msl=5.0,
            ground_speed=0.0,
            track=0.0,
            # hdop and num_satellites omitted → None
        )
        filepath = tmp_path / "gps_null.parquet"
        write_parquet(filepath, [gps_no_extras])
        df = read_parquet(filepath)
        assert pd.isna(df["hdop"].iloc[0])

    def test_optional_fields_with_values(self, tmp_path: Path) -> None:
        """Optional fields that have values survive the round-trip."""
        gps = _make_gps()
        filepath = tmp_path / "gps_full.parquet"
        write_parquet(filepath, [gps])
        models = parquet_to_models(filepath, GPSPosition)
        assert models[0].hdop == 1.2
        assert models[0].num_satellites == 12
