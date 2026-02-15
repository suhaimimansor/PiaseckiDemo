"""Telemetry data models for aerospace applications.

This module defines Pydantic models for various sensor readings and telemetry
data used throughout the flight simulation and ground control systems.

WHY PYDANTIC?
-------------
Pydantic provides:
  - Runtime data validation (catches bad data before it causes bugs)
  - Type checking integration with mypy/pyright
  - Fast serialization to JSON, dict, and other formats
  - Automatic documentation generation from type hints
  - Immutability (frozen models prevent accidental mutation)

All models inherit from `pydantic.BaseModel` and use type hints for field
definitions. Pydantic validates data at instantiation time and when
deserializing from JSON/dict.

DESIGN PRINCIPLES:
------------------
1. All timestamps are UNIX epoch time (float, seconds since 1970-01-01 UTC)
   - Universal, timezone-independent
   - Easy to sort, compare, and compute time deltas
   - Standard in aerospace and scientific computing

2. All units are SI base units or aerospace-standard units:
   - Acceleration: m/s² (meters per second squared)
   - Angular velocity: rad/s (radians per second)
   - Position: decimal degrees (latitude/longitude), meters (altitude)
   - Speed: m/s (meters per second) or knots (nautical miles per hour)
   - Pressure: Pa (Pascals) or hPa (hectopascals/millibars)

3. Models are frozen by default (immutable) via `frozen=True` config
   - Prevents accidental modification
   - Makes instances hashable (can be dict keys or set members)
   - Thread-safe

4. All models have a `model_config` for Pydantic v2 configuration

Example:
    >>> from piasecki_common.models import IMUReading
    >>> reading = IMUReading(
    ...     timestamp=1707900000.0,
    ...     accel_x=0.01, accel_y=-0.02, accel_z=9.81,
    ...     gyro_x=0.001, gyro_y=0.002, gyro_z=-0.001
    ... )
    >>> reading.accel_z
    9.81
    >>> reading.model_dump_json()
    '{"timestamp":1707900000.0,...}'
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# IMU (Inertial Measurement Unit) Reading
# =============================================================================
class IMUReading(BaseModel):
    """Inertial Measurement Unit sensor reading.

    An IMU combines an accelerometer (measures linear acceleration) and a
    gyroscope (measures angular velocity). IMUs are the backbone of flight
    control systems, providing attitude and motion data at high rates (typically
    50-1000 Hz).

    Coordinate system (standard aerospace NED - North-East-Down):
        X-axis: Forward (nose direction)
        Y-axis: Right (starboard wing)
        Z-axis: Down (belly direction)

    Attributes:
        timestamp: UNIX epoch time when the reading was taken (seconds)
        accel_x: Linear acceleration along X-axis (m/s²). Positive = forward.
        accel_y: Linear acceleration along Y-axis (m/s²). Positive = right.
        accel_z: Linear acceleration along Z-axis (m/s²). Positive = down.
                 At rest on the ground, expect accel_z ≈ 9.81 (gravity).
        gyro_x: Angular velocity around X-axis (rad/s). Positive = roll right.
        gyro_y: Angular velocity around Y-axis (rad/s). Positive = pitch up.
        gyro_z: Angular velocity around Z-axis (rad/s). Positive = yaw right.

    Example:
        >>> imu = IMUReading(
        ...     timestamp=1707900000.0,
        ...     accel_x=0.1, accel_y=0.0, accel_z=9.81,
        ...     gyro_x=0.01, gyro_y=0.02, gyro_z=-0.005
        ... )
        >>> imu.accel_z  # Gravity component when stationary
        9.81
    """

    model_config = ConfigDict(frozen=True)  # Immutable

    timestamp: float = Field(
        ...,
        description="UNIX epoch timestamp (seconds since 1970-01-01 UTC)",
        gt=0.0,  # Must be positive
    )
    accel_x: float = Field(..., description="Acceleration X-axis (m/s²)")
    accel_y: float = Field(..., description="Acceleration Y-axis (m/s²)")
    accel_z: float = Field(..., description="Acceleration Z-axis (m/s²)")
    gyro_x: float = Field(..., description="Angular velocity X-axis (rad/s)")
    gyro_y: float = Field(..., description="Angular velocity Y-axis (rad/s)")
    gyro_z: float = Field(..., description="Angular velocity Z-axis (rad/s)")


# =============================================================================
# GPS Position
# =============================================================================
class GPSPosition(BaseModel):
    """GPS (Global Positioning System) position fix.

    Standard GPS provides position (lat/lon/alt), velocity, and a quality
    metric. Modern systems can achieve 1-5m accuracy (civilian) or centimeter-
    level with RTK (Real-Time Kinematic) corrections.

    Attributes:
        timestamp: UNIX epoch time of the GPS fix (seconds)
        latitude: Latitude in decimal degrees. Range: [-90, 90].
                  Positive = North, Negative = South.
        longitude: Longitude in decimal degrees. Range: [-180, 180].
                   Positive = East, Negative = West.
        altitude_msl: Altitude above Mean Sea Level (meters). Can be negative
                      (e.g., Death Valley, Dead Sea).
        ground_speed: Speed over ground (m/s). Horizontal velocity magnitude.
        track: Ground track / course angle (degrees, 0-360). 0° = North,
               90° = East, 180° = South, 270° = West.
        hdop: Horizontal Dilution of Precision. Quality metric. Lower is better.
              <1 = ideal, 1-2 = excellent, 2-5 = good, 5-10 = moderate, >10 = poor.
        num_satellites: Number of satellites used for the fix. 4+ required for 3D fix.

    Example:
        >>> gps = GPSPosition(
        ...     timestamp=1707900000.0,
        ...     latitude=40.7128,  # New York City
        ...     longitude=-74.0060,
        ...     altitude_msl=10.0,
        ...     ground_speed=25.0,
        ...     track=90.0,
        ...     hdop=1.2,
        ...     num_satellites=12
        ... )
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(..., description="UNIX epoch timestamp", gt=0.0)
    latitude: float = Field(
        ..., description="Latitude (decimal degrees)", ge=-90.0, le=90.0
    )
    longitude: float = Field(
        ..., description="Longitude (decimal degrees)", ge=-180.0, le=180.0
    )
    altitude_msl: float = Field(
        ..., description="Altitude above Mean Sea Level (meters)"
    )
    ground_speed: float = Field(
        ..., description="Ground speed (m/s)", ge=0.0
    )
    track: float = Field(
        ..., description="Ground track/course (degrees, 0-360)", ge=0.0, lt=360.0
    )
    hdop: Optional[float] = Field(
        None, description="Horizontal Dilution of Precision", ge=0.0
    )
    num_satellites: Optional[int] = Field(
        None, description="Number of satellites used", ge=0, le=50
    )


# =============================================================================
# Airspeed Reading
# =============================================================================
class AirspeedReading(BaseModel):
    """Airspeed measurement from a pitot-static system.

    Airspeed is critical for aircraft control. Too slow = stall, too fast =
    structural damage. Pilots monitor indicated airspeed (IAS) which is affected
    by altitude and temperature. True airspeed (TAS) is the actual speed through
    the air mass.

    Types of airspeed:
        - IAS (Indicated Airspeed): Raw reading from the pitot tube
        - CAS (Calibrated Airspeed): IAS corrected for instrument/position error
        - TAS (True Airspeed): CAS corrected for altitude and temperature
        - GS (Ground Speed): Speed over the ground (from GPS, not pitot)

    Attributes:
        timestamp: UNIX epoch time of the reading (seconds)
        indicated_airspeed: IAS in m/s or knots (specify in field validation).
                            This is what the pilot sees on the gauge.
        true_airspeed: TAS in m/s. The actual speed through the air. Calculated
                       from IAS using altitude and temperature corrections.
        static_pressure: Ambient air pressure from the static port (Pa or hPa).
                         Used to compute altitude and airspeed.
        dynamic_pressure: Pitot pressure minus static pressure (Pa). Proportional
                          to airspeed squared: q = 0.5 * ρ * V²

    Example:
        >>> airspeed = AirspeedReading(
        ...     timestamp=1707900000.0,
        ...     indicated_airspeed=50.0,  # m/s
        ...     true_airspeed=55.0,       # Higher at altitude
        ...     static_pressure=101325.0, # Pa (sea level standard)
        ...     dynamic_pressure=1250.0   # Pa
        ... )
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(..., description="UNIX epoch timestamp", gt=0.0)
    indicated_airspeed: float = Field(
        ..., description="Indicated airspeed (m/s)", ge=0.0
    )
    true_airspeed: float = Field(
        ..., description="True airspeed (m/s)", ge=0.0
    )
    static_pressure: float = Field(
        ..., description="Static pressure (Pa)", gt=0.0
    )
    dynamic_pressure: float = Field(
        ..., description="Dynamic pressure (Pa)", ge=0.0
    )


# =============================================================================
# Altitude Reading
# =============================================================================
class AltitudeReading(BaseModel):
    """Barometric altitude measurement.

    Altitude can be measured multiple ways:
        1. Barometric (pressure-based, this class) — standard for aircraft
        2. GPS altitude — less accurate than barometric, but absolute
        3. Radar altimeter — measures height above ground (AGL), used for landing

    The barometric altimeter measures static air pressure and converts it to
    altitude using the standard atmosphere model. Pilots adjust the "altimeter
    setting" (QNH) to account for local pressure variations.

    Attributes:
        timestamp: UNIX epoch time of the reading (seconds)
        pressure_altitude: Altitude computed from pressure assuming standard
                           atmosphere (29.92 inHg / 1013.25 hPa at sea level).
                           Used for flight levels above 18,000 ft.
        indicated_altitude: Altitude shown on the altimeter after QNH correction.
                            This is what ATC expects you to report.
        temperature: Outside air temperature (°C). Used for density altitude
                     and true airspeed calculations.
        qnh_setting: Altimeter setting (hPa or inHg). Corrects for local pressure.
                     Standard is 1013.25 hPa (29.92 inHg).

    Example:
        >>> altitude = AltitudeReading(
        ...     timestamp=1707900000.0,
        ...     pressure_altitude=3000.0,    # meters
        ...     indicated_altitude=3050.0,   # meters
        ...     temperature=5.0,             # °C
        ...     qnh_setting=1013.25          # hPa (standard)
        ... )
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(..., description="UNIX epoch timestamp", gt=0.0)
    pressure_altitude: float = Field(
        ..., description="Pressure altitude (meters)"
    )
    indicated_altitude: float = Field(
        ..., description="Indicated altitude (meters)"
    )
    temperature: float = Field(
        ..., description="Outside air temperature (°C)"
    )
    qnh_setting: float = Field(
        ..., description="Altimeter setting (hPa)", gt=0.0
    )


# =============================================================================
# Composite Telemetry Frame
# =============================================================================
class TelemetryFrame(BaseModel):
    """Complete telemetry snapshot from all sensors.

    In real flight systems, sensor data arrives asynchronously at different
    rates (e.g., IMU at 100 Hz, GPS at 10 Hz). This model represents a
    synchronized "frame" where all sensor readings are timestamped to the same
    moment (or interpolated to a common time).

    This is useful for:
        - Ground control displays (show all data together)
        - Data logging (one row per frame)
        - Simulation output (publish all sensor states together)

    Attributes:
        timestamp: Frame timestamp (seconds). All sensor readings are synchronized
                   to this time.
        imu: IMU reading (accelerometer + gyroscope)
        gps: GPS position fix (optional — may not be available indoors or at low update rates)
        airspeed: Airspeed reading from pitot-static system
        altitude: Barometric altitude reading

    Example:
        >>> frame = TelemetryFrame(
        ...     timestamp=1707900000.0,
        ...     imu=IMUReading(...),
        ...     gps=GPSPosition(...),
        ...     airspeed=AirspeedReading(...),
        ...     altitude=AltitudeReading(...)
        ... )
        >>> frame.model_dump_json()  # Serialize entire frame to JSON
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(..., description="Frame timestamp", gt=0.0)
    imu: IMUReading = Field(..., description="IMU sensor reading")
    gps: Optional[GPSPosition] = Field(None, description="GPS position (optional)")
    airspeed: AirspeedReading = Field(..., description="Airspeed reading")
    altitude: AltitudeReading = Field(..., description="Altitude reading")
