"""
NASA EPIC (DSCOVR) Deep Space Earth Imagery Service.
Ingests real-time imagery from the Earth-Sun Lagrange-1 point (~1,000,000 miles in deep space).
"""
import json
import logging
import time
from typing import Dict, List, Optional
from app.config import NASA_EPIC_API, NASA_EPIC_ARCHIVE
from app.services.resilient_client import resilient_client

logger = logging.getLogger("satellite.epic_feed")


class NASAEPICFeed:
    def __init__(self):
        self.cached_images: List[Dict] = []
        self.last_sync: float = 0

    async def get_latest_images(self, limit: int = 12) -> List[Dict]:
        """
        Fetches the latest natural-color Earth photos taken from Lagrange Point 1.
        Returns array of images with high-res URLs, date taken, Earth coordinates, and DSCOVR position.
        """
        urls = [NASA_EPIC_API]
        raw_json = await resilient_client.get_with_failover(
            urls, is_binary=False, cache_ttl_seconds=3600
        )

        if not raw_json or not isinstance(raw_json, str):
            logger.warning("NASA EPIC API response empty or invalid.")
            return self.cached_images

        try:
            items = json.loads(raw_json)
            parsed_list = []
            for item in items[:limit]:
                # Format: YYYY/MM/DD/png/epic_1b_YYYYMMDDHHMMSS.png or jpg
                image_name = item.get("image")
                date_str = item.get("date", "")
                if not image_name or not date_str:
                    continue

                date_part = date_str.split(" ")[0].replace("-", "/")
                hires_url = f"{NASA_EPIC_ARCHIVE}/{date_part}/jpg/{image_name}.jpg"
                thumb_url = f"{NASA_EPIC_ARCHIVE}/{date_part}/thumbs/{image_name}.jpg"

                centroid = item.get("centroid_coordinates", {})
                dscovr_pos = item.get("dscovr_j2000_position", {})

                parsed_list.append({
                    "identifier": item.get("identifier"),
                    "caption": item.get("caption", "Earth from Lagrange-1 Point (DSCOVR EPIC)"),
                    "image_name": image_name,
                    "date": date_str,
                    "hires_url": hires_url,
                    "thumb_url": thumb_url,
                    "sun_lat": centroid.get("lat"),
                    "sun_lon": centroid.get("lon"),
                    "distance_km": 1500000,  # ~1.5 million km L1 point
                    "attitude": dscovr_pos
                })

            self.cached_images = parsed_list
            self.last_sync = time.time()
            return parsed_list
        except Exception as e:
            logger.error(f"Failed to parse NASA EPIC payload: {e}")
            return self.cached_images


# Global singleton
epic_feed = NASAEPICFeed()
