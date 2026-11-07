# INTERNOVA — High-Availability Satellite Ground Station & Space Imagery Platform

A resilient, cloud-driven real-time satellite tracking and space imagery downlink platform engineered for Linux servers.

The application continuously tracks active spacecraft in Earth orbit and ingests, caches, and serves real-time Earth and deep space imagery from open satellite networks (**NOAA GOES**, **NASA EPIC**, and **SatNOGS**) with high-availability (HA) fault tolerance.

---

## Key Features

1. **Real-Time Space & Earth Imagery Feeds:**
   - **NOAA GOES-16 (East) & GOES-18 (West):** Full-Disk Earth views updated every 5–10 minutes with multi-channel support (GeoColor true color, Band 13 Infrared, and Band 08 Mid-level Water Vapor).
   - **NASA EPIC (DSCOVR):** Deep space natural-color full-disc Earth imagery taken from Lagrange Point 1 (~1,000,000 miles away).
   - **SatNOGS Global Network:** Decoded amateur satellite downlinks, telemetry, and radio waterfall spectrograms.
2. **Real-Time Orbital Engine (SGP4 + WGS84):**
   - Precise sub-satellite coordinates (Latitude, Longitude, Altitude, Velocity).
   - Radio horizon communication footprint circles.
   - 100-minute ground track trajectories.
   - Topocentric pass predictions (AOS, Culmination, LOS, Azimuth, Elevation, Doppler shift).
3. **Cross-Platform Responsive Architecture (Mobile, Tablet, Desktop):**
   - **Desktop (>= 1024px):** Split-screen Mission Control with tactical 2D orbital map on left and full data deck on right.
   - **Tablet (768px - 1023px):** Adaptive sidebar scaling with touch-optimized targets.
   - **Mobile (< 768px):** Purpose-built mobile interface with high-tech bottom navigation bar (`MAP`, `IMAGERY`, `PASSES`, `SYSTEM HA`), collapsible bottom-sheet telemetry HUD, touch-friendly channel toggles, and safe-area inset support (`env(safe-area-inset-bottom)`).
4. **High Availability (HA) Architecture:**
   - **Process Self-Healing:** Docker healthchecks (`/healthz` and `/readyz`) with automatic restart policies and `systemd` watchdog support.
   - **Multi-Node Failover:** Cloudflare Tunnel zero-downtime routing and `keepalived` LAN Virtual IP (VRRP) templates included.
   - **Upstream Circuit Breaker & Failover:** Automatic fallback mirrors for NOAA CDN and CelesTrak.
   - **Stale-While-Revalidate Caching:** Never serves 500 errors during temporary internet or upstream outages.

---

## Directory Structure

```
satellite-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app with static mounts & lifespan tasks
│   │   ├── config.py                   # HA parameters, cache TTLs, satellite catalog
│   │   ├── services/
│   │   │   ├── resilient_client.py     # HTTP client with retries, backoff & circuit breakers
│   │   │   ├── orbital.py              # SGP4 orbit propagation, footprint & pass calculator
│   │   │   ├── tle_manager.py          # Multi-mirror TLE updater with local fallback
│   │   │   ├── goes_feed.py            # NOAA GOES with AWS S3 mirror failover
│   │   │   ├── epic_feed.py            # NASA EPIC deep space poller
│   │   │   └── satnogs_feed.py         # SatNOGS global telemetry poller
│   │   └── api/
│   │       ├── routes_health.py        # /healthz and /readyz for load balancers
│   │       ├── routes_satellites.py    # Orbits, real-time positions, passes
│   │       ├── routes_imagery.py       # Resilient cached satellite images
│   │       └── routes_telemetry.py     # Live WebSocket with heartbeat reconnect
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html                      # Glassmorphic Mission Control UI
│   ├── css/
│   │   └── styles.css                  # Modern cyber-aerospace styling
│   └── js/
│       ├── app.js                      # Controller with auto-reconnecting WebSocket
│       ├── map.js                      # Leaflet 2D/3D orbit tracks, footprints, terminator
│       ├── viewer.js                   # High-res satellite image visualizer
│       └── passes.js                   # Pass countdown & sky radar
├── deploy/
│   ├── docker-compose.yml              # High-availability container setup with healthchecks
│   ├── keepalived.conf                 # Dual-node VIP configuration template
│   ├── cloudflared.yml                 # Cloudflare Tunnel zero-downtime failover template
│   ├── satellite-dashboard.service     # Linux systemd auto-healing service definition
│   └── deploy.sh                       # One-command installer for Linux servers
└── README.md
```

---

## Deployment & Running

### Option 1: Docker Compose (Recommended for Production)

Run directly from the project root:
```bash
docker compose up -d --build
```
* **Dashboard:** `http://<your-server-ip>:8000`
* **Health Check:** `http://<your-server-ip>:8000/healthz`
* **View Logs:** `docker compose logs -f`
* **Stop Container:** `docker compose down`

### Option 2: Native Linux Host / Systemd

```bash
chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh
```

### Option 3: Local Development (Python)

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser to `http://localhost:8000`.

---

## High Availability Setup Guide

### 1. Multi-Server Zero-Downtime Failover (Cloudflare Tunnel)
If you operate 2 Linux servers:
1. Install `cloudflared` on both Server 1 and Server 2.
2. Apply `deploy/cloudflared.yml` pointing to your Cloudflare Tunnel UUID.
3. Configure a Cloudflare Load Balancer with a health monitor querying `http://localhost:8000/healthz`.
4. If Server 1 crashes, loses power, or undergoes updates, Cloudflare switches traffic to Server 2 in less than 3 seconds with zero manual intervention and no public IP needed.

### 2. On-Premise LAN Hardware Failover (Keepalived / VRRP)
For local networks:
1. Install keepalived: `sudo apt-get install keepalived`.
2. Copy `deploy/keepalived.conf` to `/etc/keepalived/keepalived.conf`.
3. Set `state MASTER` (priority 101) on Server 1 and `state BACKUP` (priority 100) on Server 2.
4. Clients connect to the Virtual IP `192.168.1.200:8000`. If Server 1 fails health checks, Server 2 claims the IP in < 1 second.

---

## API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/healthz` | GET | Liveness probe for Docker / Kubernetes / Cloudflare |
| `/readyz` | GET | Readiness probe checking satellite cache availability |
| `/api/ha/status` | GET | Cluster metrics, uptime, circuit breakers, cache hit ratios |
| `/api/satellites` | GET | Real-time coordinates, altitude, velocity, and footprints |
| `/api/satellites/{id}/track` | GET | Trajectory path points (past & future) for map polyline |
| `/api/satellites/{id}/passes` | GET | Pass predictions for observer coordinates |
| `/api/imagery/manifest` | GET | Catalog of live imagery channels and satellites |
| `/api/imagery/goes/{sat}/image` | GET | Real-time GOES full disk JPEG stream (GeoColor/IR/Water Vapor) |
| `/api/imagery/epic` | GET | NASA EPIC deep space Earth images from Lagrange Point 1 |
| `/api/imagery/satnogs` | GET | Decoded ground station downlinks and waterfalls |
| `/ws/telemetry` | WebSocket | 1 Hz live satellite coordinate and radar broadcast stream |
