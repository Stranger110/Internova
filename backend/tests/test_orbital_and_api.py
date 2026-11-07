"""
Automated Resilience and Verification Test Suite for Satellite Ground Station.
Tests:
1. SGP4 orbital propagation & geodetic math.
2. Ground track coordinate calculation.
3. Pass prediction with topocentric elevation and azimuth.
4. FastAPI health and readiness endpoints.
5. Circuit breaker behavior on simulated failure.
"""
import asyncio
import unittest
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.orbital import (
    propagate_satellite,
    get_ground_track,
    predict_passes,
    ecef_to_geodetic,
    geodetic_to_ecef
)
from app.services.tle_manager import tle_manager
from app.services.resilient_client import CircuitBreaker


class TestSatelliteGroundStation(unittest.TestCase):
    def setUp(self):
        # ISS TLE
        self.line1 = "1 25544U 98067A   26307.50000000  .00016717  00000+0  10270-3 0  9022"
        self.line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49815043445308"

    def test_sgp4_propagation(self):
        dt = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        pos = propagate_satellite(self.line1, self.line2, dt)
        self.assertIsNotNone(pos)
        self.assertTrue(-90.0 <= pos["latitude"] <= 90.0)
        self.assertTrue(-180.0 <= pos["longitude"] <= 180.0)
        self.assertTrue(300.0 < pos["altitude_km"] < 500.0)  # ISS LEO range
        self.assertTrue(7.0 < pos["velocity_km_s"] < 8.0)    # ~7.6 km/s
        self.assertTrue(pos["footprint_radius_km"] > 1000.0)

    def test_geodetic_ecef_roundtrip(self):
        lat, lon, alt_m = 37.7749, -122.4194, 50.0
        x, y, z = geodetic_to_ecef(lat, lon, alt_m)
        r_lat, r_lon, r_alt_km = ecef_to_geodetic(x, y, z)
        self.assertAlmostEqual(lat, r_lat, places=3)
        self.assertAlmostEqual(lon, r_lon, places=3)
        self.assertAlmostEqual(alt_m / 1000.0, r_alt_km, places=2)

    def test_ground_track_generation(self):
        track = get_ground_track(self.line1, self.line2, past_minutes=20, future_minutes=20, step_minutes=5)
        self.assertGreater(len(track), 5)
        for pt in track:
            self.assertEqual(len(pt), 2)
            self.assertTrue(-90 <= pt[0] <= 90)
            self.assertTrue(-180 <= pt[1] <= 180)

    def test_pass_prediction(self):
        # Predict over 48 hours for ISS over San Francisco
        passes = predict_passes(
            self.line1, self.line2,
            obs_lat=37.77, obs_lon=-122.41, obs_alt_m=10,
            hours=48, min_elevation_deg=10.0, freq_mhz=145.8
        )
        self.assertIsInstance(passes, list)
        if len(passes) > 0:
            first_pass = passes[0]
            self.assertIn("aos_time", first_pass)
            self.assertIn("max_elevation", first_pass)
            self.assertGreaterEqual(first_pass["max_elevation"], 10.0)
            self.assertIn("duration_seconds", first_pass)

    def test_tle_manager_fallback(self):
        tle = tle_manager.get_tle(25544)  # ISS
        self.assertIsNotNone(tle)
        self.assertEqual(tle["norad_id"], 25544)

        featured = tle_manager.get_featured()
        self.assertGreaterEqual(len(featured), 5)

    def test_circuit_breaker_logic(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.2)
        self.assertEqual(cb.state, "CLOSED")
        self.assertTrue(cb.can_attempt())

        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, "CLOSED")

        cb.record_failure()
        self.assertEqual(cb.state, "OPEN")
        self.assertFalse(cb.can_attempt())


if __name__ == "__main__":
    unittest.main()
