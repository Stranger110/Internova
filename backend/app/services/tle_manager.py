"""
TLE (Two-Line Element) Manager with Automatic Multi-Mirror Ingestion and Offline Fallback.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Union
from app.config import TLE_CACHE_TTL_HOURS, TLE_FEEDS, FEATURED_SATELLITES
from app.services.resilient_client import resilient_client

logger = logging.getLogger("satellite.tle_manager")

# Bundled offline TLE baseline (guarantees zero-downtime even on cold start without internet)
OFFLINE_TLE_BACKUP = """
ISS (ZARYA)
1 25544U 98067A   26307.50000000  .00016717  00000+0  10270-3 0  9022
2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49815043445308
NOAA 19
1 33591U 09005A   26307.50000000  .00000120  00000+0  92000-4 0  9991
2 33591  99.1852 142.1203 0013894 185.3401 174.7502 14.12423011782341
NOAA 18
1 28654U 05018A   26307.50000000  .00000105  00000+0  85000-4 0  9992
2 28654  99.0123 150.3401 0014210 190.2301 169.8902 14.13100012984123
NOAA 15
1 25338U 98030A   26307.50000000  .00000095  00000+0  72000-4 0  9993
2 25338  98.7102 165.2301 0011502 170.1201 189.9102 14.26010015124102
METEOR-M2 3
1 57166U 23091A   26307.50000000  .00000085  00000+0  65000-4 0  9994
2 57166  98.6012 170.1201 0002102 120.3401 239.8102 14.22010012341201
METEOR-M2 4
1 59051U 24039A   26307.50000000  .00000090  00000+0  68000-4 0  9995
2 59051  98.6102 168.4501 0002201 115.2301 244.9102 14.21850011241501
TIANGONG
1 48274U 21035A   26307.50000000  .00021000  00000+0  12000-3 0  9996
2 48274  41.4721 210.5401 0004501 140.1201 220.1201 15.60120013451201
GOES 16
1 41866U 16071A   26307.50000000  .00000020  00000+0  00000+0 0  9997
2 41866   0.0215  75.2012 0001201  10.2301 350.1201  1.00270012034102
GOES 18
1 51850U 22022A   26307.50000000  .00000025  00000+0  00000+0 0  9998
2 51850   0.0350 137.2012 0001150  15.1201 345.2301  1.00268011985412
HST (HUBBLE)
1 20580U 90037B   26307.50000000  .00001500  00000+0  25000-4 0  9999
2 20580  28.4695 190.2301 0002801 110.1201 250.2301 15.08500014521021
"""


class TLEManager:
    def __init__(self):
        self.tles_by_norad: Dict[int, Dict[str, str]] = {}
        self.tles_by_name: Dict[str, Dict[str, str]] = {}
        self.last_update_time: float = 0
        self._load_fallback()

    def _load_fallback(self):
        """Parses baseline fallback data into memory."""
        self._parse_raw_tle_text(OFFLINE_TLE_BACKUP)
        logger.info(f"Loaded {len(self.tles_by_norad)} fallback baseline TLEs into memory.")

    def _parse_raw_tle_text(self, text: str):
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        i = 0
        while i < len(lines):
            # Format: Name, Line 1, Line 2
            if i + 2 < len(lines) and lines[i+1].startswith("1 ") and lines[i+2].startswith("2 "):
                name = lines[i]
                l1 = lines[i+1]
                l2 = lines[i+2]
                try:
                    norad = int(l1[2:7].strip())
                    tle_obj = {
                        "name": name,
                        "line1": l1,
                        "line2": l2,
                        "norad_id": norad,
                        "timestamp": time.time()
                    }
                    self.tles_by_norad[norad] = tle_obj
                    self.tles_by_name[name.upper()] = tle_obj
                except Exception as e:
                    logger.debug(f"Failed to parse TLE block: {e}")
                i += 3
            elif lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i+1].startswith("2 "):
                # 2-line format without name line
                l1 = lines[i]
                l2 = lines[i+1]
                try:
                    norad = int(l1[2:7].strip())
                    tle_obj = {
                        "name": f"SAT-{norad}",
                        "line1": l1,
                        "line2": l2,
                        "norad_id": norad,
                        "timestamp": time.time()
                    }
                    self.tles_by_norad[norad] = tle_obj
                except Exception:
                    pass
                i += 2
            else:
                i += 1

    async def refresh_all(self):
        """Fetch fresh TLEs from CelesTrak and backup mirrors."""
        logger.info("Initiating TLE refresh from upstream mirrors...")
        ttl_seconds = TLE_CACHE_TTL_HOURS * 3600

        for group, urls in TLE_FEEDS.items():
            try:
                raw_data = await resilient_client.get_with_failover(
                    urls, is_binary=False, cache_ttl_seconds=ttl_seconds
                )
                if raw_data and isinstance(raw_data, str):
                    self._parse_raw_tle_text(raw_data)
                    logger.info(f"Ingested TLE group '{group}' successfully.")
            except Exception as e:
                logger.warning(f"Error refreshing TLE group '{group}': {e}")

        self.last_update_time = time.time()
        logger.info(f"TLE database now holds {len(self.tles_by_norad)} total satellite orbits.")

    def get_tle(self, identifier: Union[int, str]) -> Optional[Dict[str, str]]:
        if isinstance(identifier, int):
            return self.tles_by_norad.get(identifier)
        if isinstance(identifier, str):
            if identifier.isdigit():
                return self.tles_by_norad.get(int(identifier))
            return self.tles_by_name.get(identifier.upper())
        return None

    def get_featured(self) -> List[Dict]:
        """Returns metadata & TLEs for all featured satellites."""
        results = []
        for feat in FEATURED_SATELLITES:
            tle = self.get_tle(feat["norad_id"])
            if tle:
                item = dict(feat)
                item["line1"] = tle["line1"]
                item["line2"] = tle["line2"]
                results.append(item)
            else:
                # If norad_id not found directly, check by name
                tle_name = self.get_tle(feat["name"])
                if tle_name:
                    item = dict(feat)
                    item["line1"] = tle_name["line1"]
                    item["line2"] = tle_name["line2"]
                    results.append(item)
        return results


# Global singleton
tle_manager = TLEManager()
