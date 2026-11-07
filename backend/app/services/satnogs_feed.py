"""
SatNOGS Global Open Ground Station Network Feed.
Ingests real-time observations, downlinks, and decoded image payloads from amateur ground stations worldwide.
"""
import json
import logging
import time
from typing import Dict, List
from app.config import SATNOGS_OBS_API
from app.services.resilient_client import resilient_client

logger = logging.getLogger("satellite.satnogs_feed")


class SatNOGSFeed:
    def __init__(self):
        self.cached_observations: List[Dict] = []
        self.last_sync: float = 0

    async def get_latest_downlinks(self, limit: int = 15) -> List[Dict]:
        """
        Retrieves real-time satellite pass observations with decoded payload imagery
        and radio waterfall spectrograms from the SatNOGS open ground station network.
        """
        raw_json = await resilient_client.get_with_failover(
            [SATNOGS_OBS_API], is_binary=False, cache_ttl_seconds=1800
        )

        if not raw_json or not isinstance(raw_json, str):
            logger.warning("SatNOGS API response empty or unavailable. Using cached downlinks.")
            return self.cached_observations

        try:
            items = json.loads(raw_json)
            downlinks = []
            for obs in items[:limit]:
                obs_id = obs.get("id")
                sat_name = obs.get("tle", {}).get("tle0", obs.get("norad_cat_id", "Satellite"))
                waterfall = obs.get("waterfall")
                demoddata = obs.get("demoddata", [])
                station_id = obs.get("ground_station")

                # Payload images if present
                payloads = []
                for p in demoddata:
                    p_url = p.get("payload_url")
                    if p_url:
                        payloads.append(p_url)

                downlinks.append({
                    "observation_id": obs_id,
                    "satellite": sat_name,
                    "norad_cat_id": obs.get("norad_cat_id"),
                    "station_id": station_id,
                    "station_lat": obs.get("station_lat"),
                    "station_lng": obs.get("station_lng"),
                    "start_time": obs.get("start"),
                    "end_time": obs.get("end"),
                    "waterfall_url": waterfall,
                    "payload_urls": payloads,
                    "frequency_hz": obs.get("frequency"),
                    "status": obs.get("status")
                })

            if downlinks:
                self.cached_observations = downlinks
                self.last_sync = time.time()

            return self.cached_observations
        except Exception as e:
            logger.error(f"Error parsing SatNOGS observations: {e}")
            return self.cached_observations


# Global singleton
satnogs_feed = SatNOGSFeed()
