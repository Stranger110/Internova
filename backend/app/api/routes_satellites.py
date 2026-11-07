"""
Satellite Tracking, Orbit Propagation, Ground Tracks, and Pass Prediction API.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.tle_manager import tle_manager
from app.services.orbital import propagate_satellite, get_ground_track, predict_passes

router = APIRouter(prefix="/api/satellites", tags=["Satellites & Orbits"])


@router.get("", summary="Get Real-Time Coordinates for All Tracked Satellites")
async def get_all_satellites():
    """Returns current real-time coordinates, footprint, and velocity for all featured satellites."""
    featured = tle_manager.get_featured()
    results = []

    for sat in featured:
        coords = propagate_satellite(sat["line1"], sat["line2"])
        if coords:
            results.append({
                "norad_id": sat["norad_id"],
                "name": sat["name"],
                "category": sat.get("category", "general"),
                "freq_mhz": sat.get("freq_mhz"),
                "position": coords
            })

    return {
        "count": len(results),
        "satellites": results
    }


@router.get("/{norad_id}", summary="Get Detailed Telemetry for a Specific Satellite")
async def get_satellite_details(norad_id: int):
    tle = tle_manager.get_tle(norad_id)
    if not tle:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")

    coords = propagate_satellite(tle["line1"], tle["line2"])
    if not coords:
        raise HTTPException(status_code=500, detail="Orbital propagation failed for this epoch.")

    return {
        "norad_id": norad_id,
        "name": tle["name"],
        "line1": tle["line1"],
        "line2": tle["line2"],
        "telemetry": coords
    }


@router.get("/{norad_id}/track", summary="Get Ground Track (Past and Future Path)")
async def get_satellite_track(
    norad_id: int,
    past_min: int = Query(45, ge=5, le=180),
    future_min: int = Query(45, ge=5, le=180),
    step_min: int = Query(2, ge=1, le=10)
):
    tle = tle_manager.get_tle(norad_id)
    if not tle:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")

    track_points = get_ground_track(
        tle["line1"],
        tle["line2"],
        past_minutes=past_min,
        future_minutes=future_min,
        step_minutes=step_min
    )

    return {
        "norad_id": norad_id,
        "name": tle["name"],
        "point_count": len(track_points),
        "track": track_points
    }


@router.get("/{norad_id}/passes", summary="Predict Passes Over a Ground Station")
async def get_satellite_passes(
    norad_id: int,
    lat: float = Query(..., ge=-90.0, le=90.0, description="Observer latitude in degrees"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Observer longitude in degrees"),
    alt_m: float = Query(0.0, ge=-500.0, le=10000.0, description="Observer altitude in meters"),
    hours: int = Query(24, ge=1, le=72, description="Prediction window in hours"),
    min_el: float = Query(10.0, ge=0.0, le=80.0, description="Minimum elevation horizon in degrees")
):
    tle = tle_manager.get_tle(norad_id)
    if not tle:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")

    # Find satellite's downlink frequency if available
    freq = None
    for feat in tle_manager.get_featured():
        if feat["norad_id"] == norad_id:
            freq = feat.get("freq_mhz")
            break

    passes = predict_passes(
        tle["line1"],
        tle["line2"],
        obs_lat=lat,
        obs_lon=lon,
        obs_alt_m=alt_m,
        hours=hours,
        min_elevation_deg=min_el,
        freq_mhz=freq
    )

    return {
        "norad_id": norad_id,
        "name": tle["name"],
        "observer": {"latitude": lat, "longitude": lon, "altitude_m": alt_m},
        "pass_count": len(passes),
        "passes": passes
    }
