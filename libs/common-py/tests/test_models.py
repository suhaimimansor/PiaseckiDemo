"""Unit tests for piasecki_common.models — Telemetry data models.

Tests cover:
  - Valid construction of all 5 model types
  - Field validation constraints (ranges, required vs optional)
  - Immutability (frozen models reject attribute assignment)
  - JSON serialization round-trip (model → JSON → model)
  - Dict serialization round-trip (model → dict → model)
  - Nested model composition (TelemetryFrame)
  - Edge cases (boundary values, optional fields as None)

WHY THESE TESTS?
----------------
Pydantic models are the foundation of the entire project. Every service
depends on them for data exchange. If a model silently accepts invalid data
(e.g., latitude=999) or fails to serialize correctly, bugs cascade through
the whole system. These tests ensure:

  1. Validation rules work as documented
  2. Serialization is lossless (no data corruption)
  3. Immutability is enforced (prevents accidental mutation)
  4. Refactoring doesn't break the data contract

RUN:
    pytest tests/test_models.py -v
"""

import pytest
from pydantic import ValidationError

from piasecki_common.models import (
    AirspeedReading,
    AltitudeReading,
    GPSPosition,
    IMUReading,
    TelemetryFrame,
)


# =============================================================================
# Test Fixtures — Reusable sample data
# =============================================================================
# Fixtures provide consistent test data across multiple test functions.
# pytest automatically injects these when a test function has a matching
# parameter name.


@pytest.fixture
def sample_imu() -> IMUReading:
    """Create a sample IMU reading (stationary on the ground)."""
    return IMUReading(
        timestamp=1707900000.0,
        accel_x=0.01,
        accel_y=-0.02,
        accel_z=9.81,  # Gravity
        gyro_x=0.001,
        gyro_y=0.002,
        gyro_z=-0.001,
    )


@pytest.fixture
def sample_gps() -> GPSPosition:
    """Create a sample GPS fix (Piasecki Aircraft HQ area, Essington PA)."""
    return GPSPosition(
        timestamp=1707900000.0,
        latitude=39.8583,
        longitude=-75.3002,
        altitude_msl=5.0,
        ground_speed=0.0,
        track=0.0,
        hdop=1.2,
        num_satellites=12,
    )


@pytest.fixture
def sample_airspeed() -> AirspeedReading:
    """Create a sample airspeed reading (cruising at ~100 knots)."""
    return AirspeedReading(
        timestamp=1707900000.0,
        indicated_airspeed=51.4,  # ~100 knots in m/s
        true_airspeed=55.0,
        static_pressure=101325.0,  # Standard sea level
        dynamic_pressure=1620.0,
    )


@pytest.fixture
def sample_altitude() -> AltitudeReading:
    """Create a sample altitude reading (3000m, standard atmosphere)."""
    return AltitudeReading(
        timestamp=1707900000.0,
        pressure_altitude=3000.0,
        indicated_altitude=3050.0,
        temperature=5.0,
        qnh_setting=1013.25,
    )


# =============================================================================
# IMUReading Tests
# =============================================================================


class TestIMUReading:
    """Tests for the IMUReading model."""

    def test_valid_construction(self, sample_imu: IMUReading) -> None:
        """IMUReading accepts valid sensor data."""
        assert sample_imu.timestamp == 1707900000.0
        assert sample_imu.accel_z == 9.81
        assert sample_imu.gyro_x == 0.001

    def test_timestamp_must_be_positive(self) -> None:
        """Timestamp must be > 0 (UNIX epoch is always positive)."""
        with pytest.raises(ValidationError):
            IMUReading(
                timestamp=0.0,  # Not > 0
                accel_x=0.0, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
            )

    def test_negative_timestamp_rejected(self) -> None:
        """Negative timestamps are invalid."""
        with pytest.raises(ValidationError):
            IMUReading(
                timestamp=-1.0,
                accel_x=0.0, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
            )

    def test_negative_acceleration_allowed(self) -> None:
        """Acceleration values can be negative (deceleration)."""
        imu = IMUReading(
            timestamp=1.0,
            accel_x=-5.0, accel_y=-3.0, accel_z=-9.81,
            gyro_x=-1.0, gyro_y=-2.0, gyro_z=-0.5,
        )
        assert imu.accel_x == -5.0

    def test_frozen_immutability(self, sample_imu: IMUReading) -> None:
        """Frozen models reject attribute assignment."""
        with pytest.raises(ValidationError):
            sample_imu.accel_z = 0.0  # type: ignore[misc]

    def test_json_round_trip(self, sample_imu: IMUReading) -> None:
        """Serialize to JSON and back without data loss."""
        json_str = sample_imu.model_dump_json()
        restored = IMUReading.model_validate_json(json_str)
        assert restored == sample_imu

    def test_dict_round_trip(self, sample_imu: IMUReading) -> None:
        """Serialize to dict and back without data loss."""
        data = sample_imu.model_dump()
        restored = IMUReading.model_validate(data)
        assert restored == sample_imu

    def test_missing_required_field_raises(self) -> None:
        """Omitting a required field raises ValidationError."""
        with pytest.raises(ValidationError):
            IMUReading(
                timestamp=1.0,
                accel_x=0.0,
                # Missing accel_y, accel_z, gyro_x, gyro_y, gyro_z
            )


# =============================================================================
# GPSPosition Tests
# =============================================================================


class TestGPSPosition:
    """Tests for the GPSPosition model."""

    def test_valid_construction(self, sample_gps: GPSPosition) -> None:
        """GPSPosition accepts valid GPS fix data."""
        assert sample_gps.latitude == 39.8583
        assert sample_gps.longitude == -75.3002
        assert sample_gps.num_satellites == 12

    def test_latitude_range(self) -> None:
        """Latitude must be between -90 and 90 degrees."""
        # Valid boundary values
        gps_north = GPSPosition(
            timestamp=1.0, latitude=90.0, longitude=0.0,
            altitude_msl=0.0, ground_speed=0.0, track=0.0,
        )
        assert gps_north.latitude == 90.0

        gps_south = GPSPosition(
            timestamp=1.0, latitude=-90.0, longitude=0.0,
            altitude_msl=0.0, ground_speed=0.0, track=0.0,
        )
        assert gps_south.latitude == -90.0

        # Invalid: out of range
        with pytest.raises(ValidationError):
            GPSPosition(
                timestamp=1.0, latitude=91.0, longitude=0.0,
                altitude_msl=0.0, ground_speed=0.0, track=0.0,
            )

    def test_longitude_range(self) -> None:
        """Longitude must be between -180 and 180 degrees."""
        with pytest.raises(ValidationError):
            GPSPosition(
                timestamp=1.0, latitude=0.0, longitude=181.0,
                altitude_msl=0.0, ground_speed=0.0, track=0.0,
            )

    def test_optional_fields_default_none(self) -> None:
        """Optional fields (hdop, num_satellites) default to None."""
        gps = GPSPosition(
            timestamp=1.0, latitude=0.0, longitude=0.0,
            altitude_msl=0.0, ground_speed=0.0, track=0.0,
        )
        assert gps.hdop is None
        assert gps.num_satellites is None

    def test_ground_speed_non_negative(self) -> None:
        """Ground speed cannot be negative."""
        with pytest.raises(ValidationError):
            GPSPosition(
                timestamp=1.0, latitude=0.0, longitude=0.0,
                altitude_msl=0.0, ground_speed=-1.0, track=0.0,
            )

    def test_track_range(self) -> None:
        """Track must be [0, 360)."""
        with pytest.raises(ValidationError):
            GPSPosition(
                timestamp=1.0, latitude=0.0, longitude=0.0,
                altitude_msl=0.0, ground_speed=0.0, track=360.0,  # lt=360
            )

    def test_json_round_trip(self, sample_gps: GPSPosition) -> None:
        """GPS data survives JSON serialization."""
        json_str = sample_gps.model_dump_json()
        restored = GPSPosition.model_validate_json(json_str)
        assert restored == sample_gps


# =============================================================================
# AirspeedReading Tests
# =============================================================================


class TestAirspeedReading:
    """Tests for the AirspeedReading model."""

    def test_valid_construction(self, sample_airspeed: AirspeedReading) -> None:
        """AirspeedReading accepts valid pitot-static data."""
        assert sample_airspeed.indicated_airspeed == 51.4
        assert sample_airspeed.static_pressure == 101325.0

    def test_airspeed_non_negative(self) -> None:
        """Airspeed values cannot be negative."""
        with pytest.raises(ValidationError):
            AirspeedReading(
                timestamp=1.0,
                indicated_airspeed=-10.0,  # Invalid
                true_airspeed=50.0,
                static_pressure=101325.0,
                dynamic_pressure=1000.0,
            )

    def test_static_pressure_must_be_positive(self) -> None:
        """Static pressure must be > 0 (vacuum is not valid)."""
        with pytest.raises(ValidationError):
            AirspeedReading(
                timestamp=1.0,
                indicated_airspeed=50.0,
                true_airspeed=55.0,
                static_pressure=0.0,  # Not > 0
                dynamic_pressure=1000.0,
            )

    def test_zero_airspeed_valid(self) -> None:
        """Zero airspeed is valid (aircraft parked on the ground)."""
        airspeed = AirspeedReading(
            timestamp=1.0,
            indicated_airspeed=0.0,
            true_airspeed=0.0,
            static_pressure=101325.0,
            dynamic_pressure=0.0,
        )
        assert airspeed.indicated_airspeed == 0.0

    def test_json_round_trip(self, sample_airspeed: AirspeedReading) -> None:
        """Airspeed reading survives JSON serialization."""
        json_str = sample_airspeed.model_dump_json()
        restored = AirspeedReading.model_validate_json(json_str)
        assert restored == sample_airspeed


# =============================================================================
# AltitudeReading Tests
# =============================================================================


class TestAltitudeReading:
    """Tests for the AltitudeReading model."""

    def test_valid_construction(self, sample_altitude: AltitudeReading) -> None:
        """AltitudeReading accepts valid barometric data."""
        assert sample_altitude.pressure_altitude == 3000.0
        assert sample_altitude.qnh_setting == 1013.25

    def test_qnh_must_be_positive(self) -> None:
        """QNH altimeter setting must be > 0."""
        with pytest.raises(ValidationError):
            AltitudeReading(
                timestamp=1.0,
                pressure_altitude=3000.0,
                indicated_altitude=3050.0,
                temperature=5.0,
                qnh_setting=0.0,  # Not > 0
            )

    def test_negative_altitude_valid(self) -> None:
        """Negative altitude is valid (below sea level, e.g., Dead Sea)."""
        alt = AltitudeReading(
            timestamp=1.0,
            pressure_altitude=-400.0,
            indicated_altitude=-395.0,
            temperature=35.0,
            qnh_setting=1013.25,
        )
        assert alt.pressure_altitude == -400.0

    def test_negative_temperature_valid(self) -> None:
        """Negative temperatures are valid (common at altitude)."""
        alt = AltitudeReading(
            timestamp=1.0,
            pressure_altitude=10000.0,
            indicated_altitude=10050.0,
            temperature=-50.0,  # Very cold at altitude
            qnh_setting=1013.25,
        )
        assert alt.temperature == -50.0

    def test_json_round_trip(self, sample_altitude: AltitudeReading) -> None:
        """Altitude reading survives JSON serialization."""
        json_str = sample_altitude.model_dump_json()
        restored = AltitudeReading.model_validate_json(json_str)
        assert restored == sample_altitude


# =============================================================================
# TelemetryFrame Tests (Composite Model)
# =============================================================================


class TestTelemetryFrame:
    """Tests for the TelemetryFrame composite model."""

    def test_valid_construction(
        self,
        sample_imu: IMUReading,
        sample_gps: GPSPosition,
        sample_airspeed: AirspeedReading,
        sample_altitude: AltitudeReading,
    ) -> None:
        """TelemetryFrame accepts all sensor readings together."""
        frame = TelemetryFrame(
            timestamp=1707900000.0,
            imu=sample_imu,
            gps=sample_gps,
            airspeed=sample_airspeed,
            altitude=sample_altitude,
        )
        assert frame.imu.accel_z == 9.81
        assert frame.gps is not None
        assert frame.gps.latitude == 39.8583

    def test_gps_optional(
        self,
        sample_imu: IMUReading,
        sample_airspeed: AirspeedReading,
        sample_altitude: AltitudeReading,
    ) -> None:
        """GPS can be omitted (None) — not always available in flight."""
        frame = TelemetryFrame(
            timestamp=1707900000.0,
            imu=sample_imu,
            gps=None,
            airspeed=sample_airspeed,
            altitude=sample_altitude,
        )
        assert frame.gps is None

    def test_json_round_trip_with_gps(
        self,
        sample_imu: IMUReading,
        sample_gps: GPSPosition,
        sample_airspeed: AirspeedReading,
        sample_altitude: AltitudeReading,
    ) -> None:
        """Full frame with GPS survives JSON round-trip."""
        frame = TelemetryFrame(
            timestamp=1707900000.0,
            imu=sample_imu,
            gps=sample_gps,
            airspeed=sample_airspeed,
            altitude=sample_altitude,
        )
        json_str = frame.model_dump_json()
        restored = TelemetryFrame.model_validate_json(json_str)
        assert restored == frame
        assert restored.gps is not None
        assert restored.gps.latitude == 39.8583

    def test_json_round_trip_without_gps(
        self,
        sample_imu: IMUReading,
        sample_airspeed: AirspeedReading,
        sample_altitude: AltitudeReading,
    ) -> None:
        """Frame without GPS survives JSON round-trip."""
        frame = TelemetryFrame(
            timestamp=1707900000.0,
            imu=sample_imu,
            airspeed=sample_airspeed,
            altitude=sample_altitude,
        )
        json_str = frame.model_dump_json()
        restored = TelemetryFrame.model_validate_json(json_str)
        assert restored == frame
        assert restored.gps is None

    def test_nested_validation(self) -> None:
        """Invalid nested model data is caught by validation."""
        with pytest.raises(ValidationError):
            TelemetryFrame(
                timestamp=1.0,
                imu={"timestamp": 1.0, "accel_x": 0.0},  # Missing fields
                airspeed={"timestamp": 1.0},  # Missing fields
                altitude={"timestamp": 1.0},  # Missing fields
            )

    def test_frozen_immutability(
        self,
        sample_imu: IMUReading,
        sample_airspeed: AirspeedReading,
        sample_altitude: AltitudeReading,
    ) -> None:
        """TelemetryFrame is also immutable."""
        frame = TelemetryFrame(
            timestamp=1707900000.0,
            imu=sample_imu,
            airspeed=sample_airspeed,
            altitude=sample_altitude,
        )
        with pytest.raises(ValidationError):
            frame.timestamp = 0.0  # type: ignore[misc]
