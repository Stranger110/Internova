"""
NASA EONET Real-Time Natural Disaster Tracking API Endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Query
from app.services.eonet_feed import eonet_feed

router = APIRouter(prefix="/api/eonet", tags=["NASA EONET Disasters"])


@router.get("/events", summary="Get Active Global Natural Disasters")
async def get_natural_disasters(
    category: Optional[str] = Query(None, description="Filter category: wildfires, severeStorms, volcanoes, etc."),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(60, ge=1, le=100, description="Max number of events")
):
    """
    Returns active natural events (wildfires, cyclones, volcanic eruptions, floods, sea ice)
    tracked by NASA Earth Observatory.
    """
    events = await eonet_feed.get_active_events(category=category, days=days, limit=limit)
    return {
        "count": len(events),
        "category_filter": category or "all",
        "events": events
    }


@router.get("/categories", summary="Get Disaster Categories")
async def get_disaster_categories():
    """Returns available categories for disaster filtering."""
    return {
        "categories": eonet_feed.get_categories()
    }
