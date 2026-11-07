"""
Live WebSocket Telemetry Stream for Satellite Coordinates and Real-Time Sky Tracking.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.tle_manager import tle_manager
from app.services.orbital import propagate_satellite, calculate_az_el_range

logger = logging.getLogger("satellite.telemetry_ws")
router = APIRouter(tags=["Telemetry Stream"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


ws_manager = ConnectionManager()


@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    Continuous real-time telemetry stream (1 Hz).
    Clients can send:
    { "action": "set_observer", "lat": 40.71, "lon": -74.00, "alt_m": 10 }
    to receive live topocentric Azimuth, Elevation, Range, and Doppler for all satellites.
    """
    await ws_manager.connect(websocket)
    observer = None

    async def reader():
        nonlocal observer
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("action") == "set_observer":
                        observer = {
                            "lat": float(msg.get("lat", 0.0)),
                            "lon": float(msg.get("lon", 0.0)),
                            "alt_m": float(msg.get("alt_m", 0.0))
                        }
                    elif msg.get("action") == "ping":
                        await websocket.send_json({"type": "pong", "time": datetime.now(timezone.utc).isoformat()})
                except Exception:
                    pass
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    reader_task = asyncio.create_task(reader())

    try:
        while True:
            featured = tle_manager.get_featured()
            now_dt = datetime.now(timezone.utc)
            satellites_data = []

            for sat in featured:
                coords = propagate_satellite(sat["line1"], sat["line2"], now_dt)
                if not coords:
                    continue

                item = {
                    "norad_id": sat["norad_id"],
                    "name": sat["name"],
                    "category": sat.get("category"),
                    "freq_mhz": sat.get("freq_mhz"),
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "altitude_km": coords["altitude_km"],
                    "velocity_km_s": coords["velocity_km_s"],
                    "footprint_radius_km": coords["footprint_radius_km"]
                }

                # If client specified observer coordinates, calculate real-time topocentric radar
                if observer:
                    r_ecef = coords.get("ecef_pos")
                    v_ecef = coords.get("ecef_vel")
                    if r_ecef and v_ecef:
                        az, el, rng, r_rate = calculate_az_el_range(
                            r_ecef, v_ecef,
                            observer["lat"], observer["lon"], observer["alt_m"]
                        )
                        item["radar"] = {
                            "azimuth": round(az, 1),
                            "elevation": round(el, 1),
                            "range_km": round(rng, 1),
                            "visible": el >= 0.0
                        }

                satellites_data.append(item)

            payload = {
                "type": "telemetry",
                "timestamp": now_dt.isoformat(),
                "observer": observer,
                "satellites": satellites_data
            }

            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1.0)  # 1 Hz broadcast
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket client loop terminated: {e}")
    finally:
        reader_task.cancel()
        ws_manager.disconnect(websocket)
