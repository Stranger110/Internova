"""
Resilient HTTP Client with Retries, Exponential Backoff, Circuit Breaker, and Disk Caching.
"""
import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import httpx

from app.config import CACHE_DIR, HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS

logger = logging.getLogger("satellite.resilient_client")


class CircuitBreakerOpenException(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker tripped OPEN after {self.failure_count} failures.")

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker entering HALF-OPEN state, testing probe.")
                return True
            return False
        # HALF-OPEN
        return True


class ResilientClient:
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.stats: Dict[str, Any] = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_hits": 0,
            "failures": 0,
            "last_request_time": None
        }

    def _get_cb(self, host: str) -> CircuitBreaker:
        if host not in self._circuit_breakers:
            self._circuit_breakers[host] = CircuitBreaker()
        return self._circuit_breakers[host]

    def _cache_path(self, key: str, ext: str = "dat") -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{h}.{ext}"

    async def get_with_failover(
        self,
        urls: List[str],
        is_binary: bool = False,
        cache_ttl_seconds: Optional[float] = None
    ) -> Optional[Union[str, bytes, Dict[str, Any]]]:
        """
        Attempts fetching from an ordered list of mirror URLs.
        Falls back to stale disk cache if all mirrors fail or timeout.
        """
        self.stats["total_requests"] += 1
        self.stats["last_request_time"] = time.time()

        primary_url = urls[0]
        cache_file = self._cache_path(primary_url, "bin" if is_binary else "txt")
        meta_file = self._cache_path(primary_url, "meta.json")

        # 1. Check if cache is fresh
        if cache_ttl_seconds and cache_file.exists() and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                age = time.time() - meta.get("timestamp", 0)
                if age < cache_ttl_seconds:
                    self.stats["cache_hits"] += 1
                    if is_binary:
                        return cache_file.read_bytes()
                    return cache_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Error reading cache for {primary_url}: {e}")

        # 2. Try mirrors in sequence
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SatelliteGroundStationHA/1.0; +https://github.com)"
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, headers=headers) as client:
            for idx, url in enumerate(urls):
                host = httpx.URL(url).host
                cb = self._get_cb(host)
                if not cb.can_attempt():
                    logger.warning(f"Skipping {url} because circuit breaker is OPEN for {host}")
                    continue

                for attempt in range(1, HTTP_MAX_RETRIES + 1):
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        if resp.status_code == 200:
                            cb.record_success()
                            content = resp.content if is_binary else resp.text

                            # Save to persistent cache
                            try:
                                if is_binary:
                                    cache_file.write_bytes(content)
                                else:
                                    cache_file.write_text(content, encoding="utf-8")
                                meta_file.write_text(
                                    json.dumps({"timestamp": time.time(), "url": url}),
                                    encoding="utf-8"
                                )
                            except Exception as save_err:
                                logger.error(f"Failed to write cache: {save_err}")

                            if idx > 0:
                                self.stats["fallback_hits"] += 1
                                logger.info(f"Fallback mirror succeeded: {url}")
                            return content

                        logger.warning(f"Mirror {url} returned status {resp.status_code}")
                    except (httpx.RequestError, httpx.TimeoutException) as err:
                        logger.warning(f"Attempt {attempt}/{HTTP_MAX_RETRIES} failed for {url}: {err}")
                        await asyncio.sleep(0.5 * attempt)

                cb.record_failure()

        # 3. All live attempts failed -> Use stale-while-revalidate disk cache
        if cache_file.exists():
            self.stats["fallback_hits"] += 1
            logger.warning(f"All live mirrors failed for {urls}. Serving STALE cached data.")
            if is_binary:
                return cache_file.read_bytes()
            return cache_file.read_text(encoding="utf-8")

        self.stats["failures"] += 1
        logger.error(f"Exhausted all live mirrors and no cache exists for {urls}")
        return None


# Global resilient client instance
resilient_client = ResilientClient()
