"""
Main FastAPI Application Entrypoint with Lifespan Tasks, Static Frontend Mounting, and API Routers.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import HOST, PORT
from app.services.tle_manager import tle_manager
from app.api.routes_health import router as health_router
from app.api.routes_satellites import router as satellites_router
from app.api.routes_imagery import router as imagery_router
from app.api.routes_telemetry import router as telemetry_router
from app.api.routes_eonet import router as eonet_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("satellite.main")

# Background periodic poller task
async def background_tle_refresh_worker():
    """Periodically refreshes satellite TLEs from upstream mirrors every 6 hours."""
    while True:
        try:
            await tle_manager.refresh_all()
        except Exception as e:
            logger.error(f"Background TLE refresh error: {e}")
        # Sleep 6 hours
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and graceful shutdown."""
    logger.info("Initializing Satellite Ground Station System...")
    # 1. Start background TLE sync
    tle_task = asyncio.create_task(background_tle_refresh_worker())
    # 2. Allow cold start with baseline data, background refresh will update
    yield
    # 3. Graceful shutdown
    logger.info("Shutting down Satellite Ground Station System...")
    tle_task.cancel()
    try:
        await tle_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="INTERNOVA Satellite Ground Station API",
    description="Real-time satellite tracking, orbit propagation, and space imagery downlink ingestor.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for external dashboards and integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health_router)
app.include_router(satellites_router)
app.include_router(imagery_router)
app.include_router(telemetry_router)
app.include_router(eonet_router)

# Mount Frontend Static Directory
frontend_env = os.getenv("FRONTEND_DIR")
if frontend_env and Path(frontend_env).exists():
    FRONTEND_DIR = Path(frontend_env)
else:
    FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    logger.info(f"Frontend static files mounted from {FRONTEND_DIR}")
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
