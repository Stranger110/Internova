"""
Orbital Mechanics Engine: SGP4 Propagation, Ground Tracks, Radio Footprints, and Topocentric Pass Prediction.
"""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sgp4.api import Satrec, jday

# WGS84 Constants
WGS84_A = 6378.137          # Semi-major axis (Earth radius in km)
WGS84_F = 1.0 / 298.257223563 # Flattening factor
WGS84_E2 = WGS84_F * (2.0 - WGS84_F) # First eccentricity squared
SPEED_OF_LIGHT_KM_S = 299792.458


def get_gmst(jd: float, fr: float) -> float:
    """Calculate Greenwich Mean Sidereal Time (GMST) in radians."""
    d = (jd - 2451545.0) + fr
    gmst_hours = 18.697374558 + 24.06570982441908 * d
    return (gmst_hours % 24.0) * (2.0 * math.pi / 24.0)


def teme_to_ecef(r_teme: Tuple[float, float, float], gmst: float) -> Tuple[float, float, float]:
    """Rotates position vector from TEME to ECEF using GMST."""
    x, y, z = r_teme
    cos_g = math.cos(gmst)
    sin_g = math.sin(gmst)
    x_ecef = x * cos_g + y * sin_g
    y_ecef = -x * sin_g + y * cos_g
    z_ecef = z
    return (x_ecef, y_ecef, z_ecef)


def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """
    Converts ECEF Cartesian coordinates (km) to Geodetic (Lat deg, Lon deg, Alt km)
    using Bowring's method for sub-millimeter precision.
    """
    lon = math.degrees(math.atan2(y, x))
    p = math.sqrt(x * x + y * y)
    if p < 1e-6:
        lat = 90.0 if z > 0 else -90.0
        alt = abs(z) - WGS84_A * (1.0 - WGS84_F)
        return (lat, lon, alt)

    theta = math.atan2(z * WGS84_A, p * (WGS84_A * (1.0 - WGS84_F)))
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)
    b = WGS84_A * (1.0 - WGS84_F)
    e_prime2 = (WGS84_A * WGS84_A - b * b) / (b * b)

    lat_rad = math.atan2(
        z + e_prime2 * b * (sin_t ** 3),
        p - WGS84_E2 * WGS84_A * (cos_t ** 3)
    )
    sin_phi = math.sin(lat_rad)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi * sin_phi)
    alt = p / math.cos(lat_rad) - n
    return (math.degrees(lat_rad), lon, alt)


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[float, float, float]:
    """Converts observer geodetic (deg, deg, m) to ECEF (km)."""
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    h_km = alt_m / 1000.0
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi * sin_phi)
    x = (n + h_km) * cos_phi * math.cos(lam)
    y = (n + h_km) * cos_phi * math.sin(lam)
    z = (n * (1.0 - WGS84_E2) + h_km) * sin_phi
    return (x, y, z)


def calculate_az_el_range(
    sat_ecef: Tuple[float, float, float],
    sat_vel: Tuple[float, float, float],
    obs_lat: float,
    obs_lon: float,
    obs_alt_m: float
) -> Tuple[float, float, float, float]:
    """
    Computes topocentric Azimuth (deg), Elevation (deg), Slant Range (km),
    and Range Rate (km/s) for Doppler shift calculation.
    """
    obs_ecef = geodetic_to_ecef(obs_lat, obs_lon, obs_alt_m)
    dx = sat_ecef[0] - obs_ecef[0]
    dy = sat_ecef[1] - obs_ecef[1]
    dz = sat_ecef[2] - obs_ecef[2]

    phi = math.radians(obs_lat)
    lam = math.radians(obs_lon)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)

    # Transform to East, North, Up (ENU)
    east = -sin_lam * dx + cos_lam * dy
    north = -sin_phi * cos_lam * dx - sin_phi * sin_lam * dy + cos_phi * dz
    up = cos_phi * cos_lam * dx + cos_phi * sin_lam * dy + sin_phi * dz

    slant_range = math.sqrt(east * east + north * north + up * up)
    if slant_range < 1e-6:
        return (0.0, 90.0, 0.0, 0.0)

    elevation = math.degrees(math.asin(max(-1.0, min(1.0, up / slant_range))))
    azimuth = (math.degrees(math.atan2(east, north)) + 360.0) % 360.0

    # Range rate (v_relative . delta_r / |delta_r|)
    # Approximate range rate along the line-of-sight
    vx, vy, vz = sat_vel
    range_rate = (dx * vx + dy * vy + dz * vz) / slant_range

    return (azimuth, elevation, slant_range, range_rate)


def propagate_satellite(line1: str, line2: str, dt: Optional[datetime] = None) -> Optional[Dict]:
    """Calculates instantaneous satellite position, footprint, and velocity."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    try:
        sat = Satrec.twoline2rv(line1, line2)
        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond * 1e-6)
        e, r, v = sat.sgp4(jd, fr)
        if e != 0:
            return None

        gmst = get_gmst(jd, fr)
        r_ecef = teme_to_ecef(r, gmst)
        lat, lon, alt = ecef_to_geodetic(r_ecef[0], r_ecef[1], r_ecef[2])
        velocity = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)

        # Radio Horizon Footprint Circle
        # cos(theta) = R_E / (R_E + h)
        re = WGS84_A
        if alt > 0:
            cos_theta = re / (re + alt)
            theta_rad = math.acos(max(0.0, min(1.0, cos_theta)))
            footprint_angle_deg = math.degrees(theta_rad)
            footprint_radius_km = re * theta_rad
        else:
            footprint_angle_deg = 0.0
            footprint_radius_km = 0.0

        return {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "altitude_km": round(alt, 2),
            "velocity_km_s": round(velocity, 3),
            "footprint_radius_km": round(footprint_radius_km, 1),
            "footprint_angle_deg": round(footprint_angle_deg, 2),
            "timestamp": dt.isoformat(),
            "ecef_pos": r_ecef,
            "ecef_vel": v
        }
    except Exception:
        return None


def get_ground_track(
    line1: str,
    line2: str,
    center_dt: Optional[datetime] = None,
    past_minutes: int = 45,
    future_minutes: int = 45,
    step_minutes: int = 2
) -> List[List[float]]:
    """Generates continuous [[lat, lon], ...] trajectory points for map overlay."""
    if center_dt is None:
        center_dt = datetime.now(timezone.utc)

    points = []
    total_steps = (past_minutes + future_minutes) // step_minutes

    start_dt = center_dt - timedelta(minutes=past_minutes)
    for i in range(total_steps + 1):
        step_dt = start_dt + timedelta(minutes=i * step_minutes)
        pos = propagate_satellite(line1, line2, step_dt)
        if pos:
            points.append([pos["latitude"], pos["longitude"]])

    return points


def predict_passes(
    line1: str,
    line2: str,
    obs_lat: float,
    obs_lon: float,
    obs_alt_m: float = 0.0,
    hours: int = 24,
    min_elevation_deg: float = 10.0,
    freq_mhz: Optional[float] = None
) -> List[Dict]:
    """
    Finds all satellite passes visible from the ground station in the next N hours.
    Returns AOS, Max Elevation (Culmination), LOS, Azimuth, and Doppler shift.
    """
    start_dt = datetime.now(timezone.utc)
    sat = Satrec.twoline2rv(line1, line2)

    passes = []
    in_pass = False
    current_pass = {}

    # Sample every 30 seconds for quick scan
    step_seconds = 30
    total_steps = int((hours * 3600) / step_seconds)

    for step in range(total_steps):
        t = start_dt + timedelta(seconds=step * step_seconds)
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond * 1e-6)
        e, r, v = sat.sgp4(jd, fr)
        if e != 0:
            continue

        gmst = get_gmst(jd, fr)
        r_ecef = teme_to_ecef(r, gmst)
        az, el, rng, r_rate = calculate_az_el_range(r_ecef, v, obs_lat, obs_lon, obs_alt_m)

        if el >= min_elevation_deg:
            if not in_pass:
                # AOS (Acquisition of Signal)
                in_pass = True
                current_pass = {
                    "aos_time": t.isoformat(),
                    "aos_timestamp": t.timestamp(),
                    "aos_azimuth": round(az, 1),
                    "max_elevation": round(el, 1),
                    "max_elevation_time": t.isoformat(),
                    "culmination_azimuth": round(az, 1),
                    "min_range_km": round(rng, 1),
                    "freq_mhz": freq_mhz
                }
            else:
                # Track max elevation
                if el > current_pass["max_elevation"]:
                    current_pass["max_elevation"] = round(el, 1)
                    current_pass["max_elevation_time"] = t.isoformat()
                    current_pass["culmination_azimuth"] = round(az, 1)
                    current_pass["min_range_km"] = round(rng, 1)
        else:
            if in_pass:
                # LOS (Loss of Signal)
                in_pass = False
                current_pass["los_time"] = t.isoformat()
                current_pass["los_timestamp"] = t.timestamp()
                current_pass["los_azimuth"] = round(az, 1)
                duration = current_pass["los_timestamp"] - current_pass["aos_timestamp"]
                current_pass["duration_seconds"] = int(duration)

                # Doppler shift calculation: delta_f = -f0 * (v_r / c)
                if freq_mhz and current_pass.get("min_range_km"):
                    max_doppler_hz = round(freq_mhz * 1e6 * (7.5 / SPEED_OF_LIGHT_KM_S))
                    current_pass["max_doppler_hz"] = max_doppler_hz

                passes.append(current_pass)
                current_pass = {}

    return passes
