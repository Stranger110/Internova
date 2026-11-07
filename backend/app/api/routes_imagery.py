"""
Live Space and Earth Satellite Imagery API.
Provides high-resolution feeds for NOAA GOES-16/18, NASA EPIC (DSCOVR), and SatNOGS Downlinks.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from app.services.goes_feed import goes_feed
from app.services.epic_feed import epic_feed
from app.services.satnogs_feed import satnogs_feed

router = APIRouter(prefix="/api/imagery", tags=["Satellite Imagery"])


@router.get("/manifest", summary="Catalog of Live Satellite Feeds")
async def get_imagery_manifest():
    """Returns available satellite imagery feeds, channels, and coverage areas."""
    return {
        "geostationary": goes_feed.get_feed_manifest(),
        "deep_space": {
            "name": "NASA EPIC (DSCOVR)",
            "location": "Lagrange Point 1 (~1,000,000 miles from Earth)",
            "camera": "Earth Polychromatic Imaging Camera (EPIC)",
            "type": "Full Disc Natural Color Earth View"
        },
        "leo_downlinks": {
            "name": "SatNOGS Global Ground Station Network",
            "type": "Decoded Amateur LEO Downlinks & RF Waterfalls (NOAA, Meteor, Cubesats)"
        }
    }


@router.get("/goes/{satellite}/image", summary="Stream Real-Time GOES Geostationary Image")
async def get_goes_image(
    satellite: str,
    channel: str = Query("geocolor", regex="^(geocolor|infrared|watervapor|mesoscale1)$")
):
    """
    Returns JPEG bytes of latest Earth full disk or mesoscale imagery.
    Satellite: 'GOES-16' (East) or 'GOES-18' (West).
    Channel: 'geocolor', 'infrared', 'watervapor', 'mesoscale1'.
    """
    img_bytes = await goes_feed.get_latest_image_bytes(satellite=satellite, channel=channel)
    if not img_bytes:
        raise HTTPException(status_code=504, detail="Failed to retrieve imagery from satellite mirrors.")

    return Response(
        content=img_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Satellite": satellite.upper(),
            "X-Channel": channel
        }
    )


@router.get("/epic", summary="Get NASA EPIC Deep Space Earth Views")
async def get_epic_images(limit: int = Query(10, ge=1, le=24)):
    """Fetches high-resolution images taken from Lagrange-1 deep space orbit."""
    images = await epic_feed.get_latest_images(limit=limit)
    return {
        "count": len(images),
        "source": "NASA DSCOVR / EPIC",
        "distance": "Lagrange-1 (~1.5M km)",
        "images": images
    }


@router.get("/satnogs", summary="Get Decoded Ground Station Downlinks & Waterfalls")
async def get_satnogs_downlinks(limit: int = Query(12, ge=1, le=30)):
    """Fetches latest decoded payloads and waterfalls from the global SatNOGS network."""
    downlinks = await satnogs_feed.get_latest_downlinks(limit=limit)
    return {
        "count": len(downlinks),
        "network": "SatNOGS Open Ground Stations",
        "downlinks": downlinks
    }
