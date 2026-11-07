"""
Configuration settings for High-Availability Satellite Ground Station Dashboard.
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SATELLITE_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Upstream Satellite TLE Feeds (with mirrors)
TLE_FEEDS = {
    "weather": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
        "https://raw.githubusercontent.com/brownpau/tle/master/weather.txt",
    ],
    "stations": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    ],
    "active": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
    ]
}

# Satellites of interest to track by default
FEATURED_SATELLITES = [
    {"name": "ISS (ZARYA)", "category": "station", "norad_id": 25544, "freq_mhz": 145.800},
    {"name": "NOAA 19", "category": "weather-leo", "norad_id": 33591, "freq_mhz": 137.100},
    {"name": "NOAA 18", "category": "weather-leo", "norad_id": 28654, "freq_mhz": 137.912},
    {"name": "NOAA 15", "category": "weather-leo", "norad_id": 25338, "freq_mhz": 137.620},
    {"name": "METEOR-M2 3", "category": "weather-leo", "norad_id": 57166, "freq_mhz": 137.900},
    {"name": "METEOR-M2 4", "category": "weather-leo", "norad_id": 59051, "freq_mhz": 137.100},
    {"name": "TIANGONG", "category": "station", "norad_id": 48274, "freq_mhz": 145.000},
    {"name": "GOES 16", "category": "weather-geo", "norad_id": 41866, "freq_mhz": 1694.1},
    {"name": "GOES 18", "category": "weather-geo", "norad_id": 51850, "freq_mhz": 1694.1},
    {"name": "HST (HUBBLE)", "category": "science", "norad_id": 20580, "freq_mhz": 2255.5},
]

# NOAA GOES Imagery Mirrors
GOES_MIRRORS = {
    "GOES-16": {
        "title": "GOES-16 (East) Full Disk GeoColor",
        "primary": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/GEOCOLOR/latest.jpg",
        "fallback": "https://rammb-slider.cira.colostate.edu/data/imagery/goes-16/full_disk/geocolor/latest.jpg",
        "mesoscale1": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/MESO/GEOCOLOR/latest.jpg",
        "infrared": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/13/1808x1808.jpg",
        "watervapor": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/08/1808x1808.jpg"
    },
    "GOES-18": {
        "title": "GOES-18 (West) Full Disk GeoColor",
        "primary": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/GEOCOLOR/latest.jpg",
        "fallback": "https://rammb-slider.cira.colostate.edu/data/imagery/goes-18/full_disk/geocolor/latest.jpg",
        "mesoscale1": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/MESO/GEOCOLOR/latest.jpg",
        "infrared": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/13/1808x1808.jpg",
        "watervapor": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/08/1808x1808.jpg"
    }
}

# NASA EPIC DSCOVR API (Lagrange-1 Earth View)
NASA_EPIC_API = "https://epic.gsfc.nasa.gov/api/natural"
NASA_EPIC_ARCHIVE = "https://epic.gsfc.nasa.gov/archive/natural"

# SatNOGS Network API (Amateur Ground Station Downlinks)
SATNOGS_OBS_API = "https://network.satnogs.org/api/observations/?vetted_status=good&has_vetted_payload=true&format=json"

# NASA EONET v3 (Earth Observatory Natural Event Tracker)
NASA_EONET_API = "https://eonet.gsfc.nasa.gov/api/v3/events"
EONET_CACHE_TTL_MINUTES = 20

# Resiliency & Timeouts
HTTP_TIMEOUT_SECONDS = 12.0
HTTP_MAX_RETRIES = 3
TLE_CACHE_TTL_HOURS = 12
IMAGERY_CACHE_TTL_MINUTES = 8
NODE_ID = os.getenv("NODE_ID", "ground-station-alpha-01")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
