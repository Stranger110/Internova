"""
High-Availability Health, Readiness, and Node Status API endpoints.
Used by Load Balancers, Cloudflare Tunnels, Docker, and systemd Watchdogs.
"""
import time
from fastapi import APIRouter, Response, status
from app.config import NODE_ID
from app.services.resilient_client import resilient_client
from app.services.tle_manager import tle_manager

router = APIRouter(tags=["Health & HA"])
START_TIME = time.time()


@router.get("/healthz", summary="Liveness Probe")
async def healthz():
    """Returns 200 OK if process is alive and responsive."""
    return {
        "status": "healthy",
        "node_id": NODE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1)
    }


@router.get("/readyz", summary="Readiness Probe")
async def readyz(response: Response):
    """
    Returns 200 OK if satellite catalog and cache are initialized.
    Returns 503 if node is still starting or critical dependencies failed.
    """
    has_tles = len(tle_manager.tles_by_norad) > 0
    if not has_tles:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "reason": "TLE catalog not initialized"}

    return {
        "status": "ready",
        "node_id": NODE_ID,
        "tle_count": len(tle_manager.tles_by_norad)
    }


@router.get("/api/ha/status", summary="Cluster & Circuit Breaker Metrics")
async def ha_status():
    """Detailed High Availability metrics, cache statistics, and circuit breakers."""
    cb_states = {}
    for host, cb in resilient_client._circuit_breakers.items():
        cb_states[host] = {
            "state": cb.state,
            "failure_count": cb.failure_count,
            "last_failure": cb.last_failure_time
        }

    return {
        "node_id": NODE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_satellites_indexed": len(tle_manager.tles_by_norad),
        "client_metrics": resilient_client.stats,
        "circuit_breakers": cb_states,
        "tle_last_refreshed": tle_manager.last_update_time
    }
