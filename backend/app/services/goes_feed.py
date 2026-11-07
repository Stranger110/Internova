"""
NOAA GOES-16 & GOES-18 Real-Time Imagery Ingestor with Multi-Mirror Failover.
"""
import logging
import time
from typing import Dict, Optional, Union
from app.config import GOES_MIRRORS, IMAGERY_CACHE_TTL_MINUTES
from app.services.resilient_client import resilient_client

logger = logging.getLogger("satellite.goes_feed")


class GOESFeedManager:
    def __init__(self):
        self.cached_metadata: Dict[str, Dict] = {}

    async def get_latest_image_bytes(
        self,
        satellite: str = "GOES-16",
        channel: str = "geocolor"
    ) -> Optional[bytes]:
        """
        Fetches the latest satellite imagery bytes with automatic mirror failover.
        Supported satellites: GOES-16 (East), GOES-18 (West)
        Supported channels: geocolor, infrared, watervapor, mesoscale1
        """
        sat_key = satellite.upper()
        if sat_key not in GOES_MIRRORS:
            sat_key = "GOES-16"

        config = GOES_MIRRORS[sat_key]
        ttl_seconds = IMAGERY_CACHE_TTL_MINUTES * 60

        # Build mirror list according to requested channel
        if channel == "infrared":
            urls = [
                config["infrared"],
                f"https://cdn.star.nesdis.noaa.gov/{sat_key}/ABI/FD/13/1808x1808.jpg"
            ]
        elif channel == "watervapor":
            urls = [
                config["watervapor"],
                f"https://cdn.star.nesdis.noaa.gov/{sat_key}/ABI/FD/08/1808x1808.jpg"
            ]
        elif channel == "mesoscale1":
            urls = [
                config["mesoscale1"],
                f"https://cdn.star.nesdis.noaa.gov/{sat_key}/ABI/MESO/GEOCOLOR/latest.jpg"
            ]
        else:
            # Default GeoColor
            urls = [
                config["primary"],
                config["fallback"]
            ]

        data = await resilient_client.get_with_failover(
            urls, is_binary=True, cache_ttl_seconds=ttl_seconds
        )

        if isinstance(data, bytes) and len(data) > 1024:
            self.cached_metadata[f"{sat_key}_{channel}"] = {
                "satellite": sat_key,
                "channel": channel,
                "size_bytes": len(data),
                "timestamp": time.time(),
                "status": "online"
            }
            return data

        logger.warning(f"Could not retrieve GOES image for {sat_key} - {channel}")
        return None

    def get_feed_manifest(self) -> Dict:
        """Returns catalog of available GOES geostationary feeds."""
        return {
            "satellites": [
                {
                    "id": "GOES-16",
                    "name": "GOES-16 (East - 75.2° W)",
                    "orbital_slot": "Geostationary 35,786 km",
                    "coverage": "Americas, Atlantic Ocean, West Africa",
                    "channels": ["geocolor", "infrared", "watervapor", "mesoscale1"],
                    "refresh_interval": "5-10 minutes"
                },
                {
                    "id": "GOES-18",
                    "name": "GOES-18 (West - 137.2° W)",
                    "orbital_slot": "Geostationary 35,786 km",
                    "coverage": "Pacific Ocean, Hawaii, Western North America",
                    "channels": ["geocolor", "infrared", "watervapor", "mesoscale1"],
                    "refresh_interval": "5-10 minutes"
                }
            ]
        }


# Global singleton
goes_feed = GOESFeedManager()
