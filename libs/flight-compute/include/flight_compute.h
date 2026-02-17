/**
 * @file flight_compute.h
 * @brief Flight data computation library for aerospace applications
 *
 * This library provides MISRA-C compliant implementations of common aerospace
 * calculations and sensor processing algorithms. Designed for use with Python
 * via ctypes FFI.
 *
 * DESIGN PRINCIPLES:
 * ------------------
 * 1. Pure C89/C99 with MISRA-C compliance (no dynamic memory, explicit types)
 * 2. No standard library dependencies in core compute functions
 * 3. All mathematical constants and formulas documented with references
 * 4. SI units throughout (meters, pascals, kelvin, radians, m/s)
 * 5. Defensive programming: NULL pointer guards, range validation
 * 6. Thread-safe: no global state, pure functions only
 *
 * USAGE FROM PYTHON (via ctypes):
 * --------------------------------
 * ```python
 * import ctypes
 * lib = ctypes.CDLL("./libflight_compute.so")
 *
 * # Define C function signature
 * lib.compute_indicated_airspeed.argtypes = [ctypes.c_double, ctypes.c_double]
 * lib.compute_indicated_airspeed.restype = ctypes.c_double
 *
 * # Call
 * ias = lib.compute_indicated_airspeed(101325.0, 1250.0)  # static_p, dynamic_p
 * ```
 *
 * AEROSPACE STANDARDS REFERENCES:
 * --------------------------------
 * - ICAO Standard Atmosphere (ISA): pressure/altitude/temperature model
 * - MIL-STD-1797A: Flight control system design guide
 * - DO-178C: Software considerations in airborne systems
 * - MISRA-C:2012: Safe C programming for embedded systems
 *
 * @author Suhaimi Mansor
 * @date February 2026
 * @version 0.1.0
 */

#ifndef FLIGHT_COMPUTE_H
#define FLIGHT_COMPUTE_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* INCLUDES                                                                   */
/* ========================================================================== */

#include <stdint.h>  /* uint8_t, int32_t, etc. — MISRA-required explicit types */
#include <stddef.h>  /* size_t, NULL */

/* ========================================================================== */
/* PHYSICAL CONSTANTS                                                         */
/* ========================================================================== */

/**
 * @brief Standard gravity acceleration (m/s²)
 * WGS84 reference ellipsoid standard: 9.80665 m/s²
 */
#define GRAVITY_MSL 9.80665

/**
 * @brief Standard sea-level air density (kg/m³)
 * ISA standard atmosphere at 15°C, 101325 Pa
 */
#define AIR_DENSITY_SL 1.225

/**
 * @brief Standard sea-level pressure (Pa)
 * 101325 Pa = 1013.25 hPa = 29.92 inHg
 */
#define PRESSURE_SL 101325.0

/**
 * @brief Standard sea-level temperature (K)
 * 288.15 K = 15°C
 */
#define TEMPERATURE_SL 288.15

/**
 * @brief Temperature lapse rate in troposphere (K/m)
 * Standard atmosphere: -0.0065 K/m (temperature decreases with altitude)
 */
#define LAPSE_RATE 0.0065

/**
 * @brief Specific gas constant for dry air (J/(kg·K))
 * R_specific = R_universal / M_air = 8314.32 / 28.9644
 */
#define GAS_CONSTANT_AIR 287.05

/* ========================================================================== */
/* TYPE DEFINITIONS (C Struct Representations of Python Models)              */
/* ========================================================================== */

/**
 * @brief IMU (Inertial Measurement Unit) sensor reading
 *
 * Coordinate system: NED (North-East-Down) aerospace standard
 *   X-axis: Forward (nose direction)
 *   Y-axis: Right (starboard wing)
 *   Z-axis: Down (belly)
 *
 * All fields use double (64-bit float) to match Python float precision.
 */
typedef struct {
    double timestamp;   /**< UNIX epoch time (seconds since 1970-01-01 UTC) */
    double accel_x;     /**< Linear acceleration X-axis (m/s²) */
    double accel_y;     /**< Linear acceleration Y-axis (m/s²) */
    double accel_z;     /**< Linear acceleration Z-axis (m/s²) */
    double gyro_x;      /**< Angular velocity X-axis (rad/s) */
    double gyro_y;      /**< Angular velocity Y-axis (rad/s) */
    double gyro_z;      /**< Angular velocity Z-axis (rad/s) */
} imu_reading_t;

/**
 * @brief Filtered IMU output (after complementary filter or Kalman filter)
 *
 * Provides attitude estimates by fusing accelerometer (gravity vector) and
 * gyroscope (angular velocity integration).
 */
typedef struct {
    double roll;        /**< Roll angle (rad), rotation about X-axis */
    double pitch;       /**< Pitch angle (rad), rotation about Y-axis */
    double yaw;         /**< Yaw angle (rad), rotation about Z-axis */
    double roll_rate;   /**< Roll rate (rad/s) */
    double pitch_rate;  /**< Pitch rate (rad/s) */
    double yaw_rate;    /**< Yaw rate (rad/s) */
} attitude_t;

/**
 * @brief Airspeed reading from pitot-static system
 */
typedef struct {
    double static_pressure;   /**< Ambient air pressure (Pa) */
    double dynamic_pressure;  /**< Pitot pressure - static pressure (Pa) */
    double temperature;       /**< Outside air temperature (K) */
} pitot_static_t;

/* ========================================================================== */
/* AIRSPEED CALCULATIONS                                                      */
/* ========================================================================== */

/**
 * @brief Compute indicated airspeed (IAS) from pitot-static pressures
 *
 * Uses the standard airspeed equation:
 *   IAS = sqrt(2 * (P_dynamic) / rho_sl)
 *
 * Where:
 *   - P_dynamic = P_pitot - P_static (dynamic pressure)
 *   - rho_sl = 1.225 kg/m³ (standard sea-level air density)
 *
 * IAS is what the pilot sees on the airspeed indicator. It's uncorrected for
 * altitude or temperature, making it the "felt" airspeed that determines stall
 * speed and structural limits.
 *
 * @param static_pressure Ambient static pressure (Pa), must be > 0
 * @param dynamic_pressure Dynamic pressure (Pa), must be >= 0
 * @return Indicated airspeed (m/s), or 0.0 on invalid input
 *
 * @note For safety: negative dynamic pressure returns 0.0 (invalid sensor reading)
 * @note At sea level with standard atmosphere, IAS ≈ TAS
 */
double compute_indicated_airspeed(double static_pressure, double dynamic_pressure);

/**
 * @brief Compute true airspeed (TAS) from IAS and altitude
 *
 * True airspeed is the actual speed of the aircraft through the air mass.
 * It differs from IAS due to decreasing air density with altitude:
 *
 *   TAS = IAS * sqrt(rho_sl / rho_altitude)
 *
 * Where rho_altitude is computed from pressure altitude using ISA model.
 *
 * @param indicated_airspeed IAS in m/s
 * @param pressure_altitude Pressure altitude (m)
 * @param temperature_celsius Outside air temperature (°C)
 * @return True airspeed (m/s)
 */
double compute_true_airspeed(
    double indicated_airspeed,
    double pressure_altitude,
    double temperature_celsius
);

/**
 * @brief Compute Mach number from TAS and temperature
 *
 * Mach number is the ratio of TAS to the local speed of sound:
 *   Mach = TAS / a
 *   where a = sqrt(gamma * R * T)
 *
 * Where:
 *   - gamma = 1.4 (specific heat ratio for air)
 *   - R = 287.05 J/(kg·K) (gas constant for air)
 *   - T = temperature (K)
 *
 * @param true_airspeed TAS in m/s
 * @param temperature_kelvin Outside air temperature (K), must be > 0
 * @return Mach number (dimensionless), or 0.0 on invalid input
 */
double compute_mach_number(double true_airspeed, double temperature_kelvin);

/* ========================================================================== */
/* ALTITUDE CALCULATIONS                                                      */
/* ========================================================================== */

/**
 * @brief Compute pressure altitude from static pressure
 *
 * Uses the barometric formula from ISA (International Standard Atmosphere):
 *
 *   H = (T0 / L) * [1 - (P / P0)^(R*L/g)]
 *
 * Where:
 *   - T0 = 288.15 K (standard temperature at sea level)
 *   - L = 0.0065 K/m (temperature lapse rate)
 *   - P = measured pressure
 *   - P0 = 101325 Pa (standard sea-level pressure)
 *   - R = 287.05 J/(kg·K) (gas constant)
 *   - g = 9.80665 m/s² (gravity)
 *
 * Pressure altitude is what ATC uses for flight levels (e.g., FL180 = 18000 ft).
 * All aircraft above 18,000 ft set altimeters to 29.92 inHg (1013.25 hPa).
 *
 * @param static_pressure Measured static pressure (Pa), must be > 0
 * @return Pressure altitude (meters), or 0.0 on invalid input
 *
 * @note Valid for troposphere only (up to ~11 km / 36,000 ft)
 * @note Returns 0 for invalid (non-positive) pressure
 */
double compute_pressure_altitude(double static_pressure);

/**
 * @brief Compute density altitude (performance altitude)
 *
 * Density altitude is the pressure altitude corrected for non-standard
 * temperature. It determines aircraft performance — higher density altitude
 * means thinner air, reduced lift, and longer takeoff rolls.
 *
 * Critical for hot-day/high-elevation takeoffs.
 *
 * @param pressure_altitude Pressure altitude (m)
 * @param temperature_celsius Outside air temperature (°C)
 * @return Density altitude (m)
 */
double compute_density_altitude(double pressure_altitude, double temperature_celsius);

/**
 * @brief Convert pressure altitude to indicated altitude using QNH
 *
 * Pilots use QNH (altimeter setting) to correct for local pressure variations.
 * The altimeter shows indicated altitude, which matches field elevation when
 * set correctly.
 *
 * @param pressure_altitude Pressure altitude (m)
 * @param qnh_setting Local altimeter setting (Pa or hPa * 100)
 * @return Indicated altitude (m)
 */
double compute_indicated_altitude(double pressure_altitude, double qnh_setting);

/* ========================================================================== */
/* IMU SENSOR PROCESSING                                                      */
/* ========================================================================== */

/**
 * @brief Simple complementary filter for IMU attitude estimation
 *
 * Fuses accelerometer (measures gravity vector) and gyroscope (measures
 * angular velocity) to estimate aircraft attitude (roll, pitch, yaw).
 *
 * Complementary filter is a lightweight alternative to Kalman filtering:
 *   - High-pass filter on gyro (tracks fast changes)
 *   - Low-pass filter on accel (rejects vibration)
 *   - Weighted blend: attitude = alpha * gyro_integrated + (1-alpha) * accel
 *
 * Typical alpha = 0.98 (98% gyro, 2% accel).
 *
 * @param imu Current IMU reading (accelerometer + gyroscope)
 * @param prev_attitude Previous attitude estimate
 * @param dt Time step since last reading (seconds)
 * @param alpha Filter weight (0.0 to 1.0, typically 0.98)
 * @param[out] output Updated attitude estimate
 * @return 0 on success, -1 on invalid input
 *
 * @note This is a simplified 6-DOF IMU. Real systems also integrate magnetometer
 *       (9-DOF) or GPS (10-DOF) for drift correction.
 */
int filter_imu_complementary(
    const imu_reading_t *imu,
    const attitude_t *prev_attitude,
    double dt,
    double alpha,
    attitude_t *output
);

/**
 * @brief Apply low-pass filter to IMU accelerometer to reduce noise
 *
 * Simple exponential moving average (EMA):
 *   filtered = alpha * new_sample + (1 - alpha) * previous_filtered
 *
 * Lower alpha = more smoothing, more lag
 *
 * @param raw_accel Raw accelerometer sample
 * @param prev_filtered Previous filtered value
 * @param alpha Filter coefficient (0.0 to 1.0)
 * @return Filtered accelerometer reading
 */
double filter_accelerometer(double raw_accel, double prev_filtered, double alpha);

/* ========================================================================== */
/* UTILITY FUNCTIONS                                                          */
/* ========================================================================== */

/**
 * @brief Convert Celsius to Kelvin
 * @param celsius Temperature in degrees Celsius
 * @return Temperature in Kelvin
 */
double celsius_to_kelvin(double celsius);

/**
 * @brief Convert Kelvin to Celsius
 * @param kelvin Temperature in Kelvin
 * @return Temperature in degrees Celsius
 */
double kelvin_to_celsius(double kelvin);

/**
 * @brief Convert meters per second to knots
 * @param mps Speed in m/s
 * @return Speed in nautical miles per hour (knots)
 */
double mps_to_knots(double mps);

/**
 * @brief Convert knots to meters per second
 * @param knots Speed in nautical miles per hour
 * @return Speed in m/s
 */
double knots_to_mps(double knots);

/**
 * @brief Convert radians to degrees
 * @param radians Angle in radians
 * @return Angle in degrees
 */
double rad_to_deg(double radians);

/**
 * @brief Convert degrees to radians
 * @param degrees Angle in degrees
 * @return Angle in radians
 */
double deg_to_rad(double degrees);

/* ========================================================================== */
/* VERSION INFO                                                               */
/* ========================================================================== */

/**
 * @brief Get library version string
 * @return Version string (e.g., "0.1.0")
 */
const char* flight_compute_version(void);

#ifdef __cplusplus
}
#endif

#endif /* FLIGHT_COMPUTE_H */
