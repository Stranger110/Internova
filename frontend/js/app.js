/**
 * Main Application Controller.
 * Initializes WebSocket with auto-reconnection, coordinates map, imagery viewer, and pass predictor.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. UTC Clock
  function updateClock() {
    const now = new Date();
    const utcStr = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
    const el = document.getElementById('utcClock');
    if (el) el.textContent = utcStr;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // Module references
  let mapModule = null;
  let passesModule = null;
  let viewerModule = null;
  let eonetModule = null;

  // 2. Cross-Platform Navigation (Desktop Sidebar Tabs + Mobile Bottom Nav)
  const tabBtns = document.querySelectorAll('.tab-btn');
  const navItems = document.querySelectorAll('.nav-item');
  const tabContents = document.querySelectorAll('.tab-content');
  const appContainer = document.querySelector('.app-container');

  function setActiveView(targetId, forceMode = null) {
    // Synchronize desktop tabs
    tabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === targetId);
    });

    // Synchronize mobile bottom nav
    navItems.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === targetId);
    });

    if (targetId === 'tabMap') {
      if (appContainer) {
        appContainer.classList.remove('mobile-show-sidebar');
        appContainer.classList.add('mobile-show-map');
      }
      if (mapModule) {
        if (forceMode) {
          mapModule.setMode(forceMode);
        } else {
          mapModule.setMode('satellites');
        }
        mapModule.invalidateSize();
      }
    } else {
      if (appContainer) {
        appContainer.classList.remove('mobile-show-map');
        appContainer.classList.add('mobile-show-sidebar');
      }
      tabContents.forEach(c => {
        c.classList.toggle('active', c.id === targetId);
      });

      // Synchronize map layer mode based on active tab:
      // Disasters tab -> disaster incidents visible on map, satellites hidden.
      // Other tabs (Imagery, Passes, HA) -> satellites visible on map, disasters hidden.
      if (mapModule) {
        if (targetId === 'tabDisasters') {
          mapModule.setMode('disasters');
        } else {
          mapModule.setMode('satellites');
        }
      }

      if (targetId === 'tabPasses' && passesModule) {
        setTimeout(() => passesModule.redraw(), 60);
      }
    }
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => setActiveView(btn.dataset.tab));
  });

  navItems.forEach(btn => {
    btn.addEventListener('click', () => setActiveView(btn.dataset.tab));
  });

  // HUD Mobile Drawer Toggle
  const hudElement = document.getElementById('satelliteHud');
  const hudCollapseBtn = document.getElementById('hudCollapseBtn');
  if (hudCollapseBtn && hudElement) {
    hudCollapseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      hudElement.classList.toggle('collapsed');
    });
  }
  const hudHeader = document.querySelector('.hud-header');
  if (hudHeader && hudElement) {
    hudHeader.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        hudElement.classList.toggle('collapsed');
      }
    });
  }

  // 3. Observer Location (Default San Francisco / Equator)
  let observer = { lat: 37.7749, lon: -122.4194, alt_m: 15 };

  // 4. Initialize Modules
  passesModule = new PassPredictor('radarCanvas', 'passList');
  viewerModule = new ImageryViewer();

  mapModule = new OrbitalMap('map', (selectedSat) => {
    updateHud(selectedSat);
    passesModule.setSatellite(selectedSat.norad_id);
  });

  eonetModule = new EONETManager(mapModule, setActiveView);

  mapModule.updateObserverPosition(observer.lat, observer.lon);
  passesModule.setObserver(observer.lat, observer.lon, observer.alt_m);

  // Auto-detect geolocation
  const locateBtn = document.getElementById('btnLocate');
  if (locateBtn && navigator.geolocation) {
    locateBtn.addEventListener('click', () => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          observer = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            alt_m: pos.coords.altitude || 15
          };
          updateObserverUI();
          mapModule.updateObserverPosition(observer.lat, observer.lon);
          passesModule.setObserver(observer.lat, observer.lon, observer.alt_m);
          sendObserverToWs();
        },
        (err) => alert('Location access unavailable or denied. Using default ground coordinates.')
      );
    });
  }

  function updateObserverUI() {
    const coordsEl = document.getElementById('gsCoords');
    if (coordsEl) {
      coordsEl.textContent = `${observer.lat.toFixed(2)}°, ${observer.lon.toFixed(2)}°`;
    }
  }
  updateObserverUI();

  // 5. HUD Telemetry Updates
  function updateHud(sat) {
    if (!sat) return;
    document.getElementById('hudName').textContent = sat.name;
    document.getElementById('hudCategory').textContent = sat.category ? sat.category.toUpperCase() : 'ORBIT';
    document.getElementById('hudLat').textContent = `${sat.latitude.toFixed(2)}°`;
    document.getElementById('hudLon').textContent = `${sat.longitude.toFixed(2)}°`;
    document.getElementById('hudAlt').textContent = `${sat.altitude_km} km`;
    document.getElementById('hudVel').textContent = `${sat.velocity_km_s} km/s`;
    document.getElementById('hudFootprint').textContent = `${sat.footprint_radius_km} km`;
    document.getElementById('hudFreq').textContent = sat.freq_mhz ? `${sat.freq_mhz} MHz` : 'Telemetry';
  }

  // 6. High Availability WebSocket Telemetry Client
  let ws = null;
  let reconnectTimer = null;

  function connectWs() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('Telemetry WebSocket connected.');
      document.getElementById('connPill').style.borderColor = 'rgba(16, 185, 129, 0.4)';
      document.getElementById('connStatusText').textContent = 'HA ACTIVE';
      document.getElementById('connStatusDot').style.backgroundColor = '#10b981';
      sendObserverToWs();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry') {
          mapModule.updateSatellites(msg.satellites);
          mapModule.satelliteCount = msg.satellites.length;

          // Only update the map target count if currently in Satellites mode
          if (mapModule.currentMode === 'satellites') {
            const countEl = document.getElementById('activeSatsCount');
            if (countEl) countEl.textContent = msg.satellites.length;
          }

          // If current selected sat is in update and in satellites mode, update HUD
          if (mapModule.currentMode === 'satellites') {
            const cur = msg.satellites.find(s => s.norad_id === mapModule.selectedNoradId);
            if (cur) updateHud(cur);
          }
        }
      } catch (e) {
        console.error('Error handling WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      console.warn('Telemetry WebSocket disconnected. Reconnecting in 3s...');
      document.getElementById('connPill').style.borderColor = 'rgba(244, 63, 94, 0.4)';
      document.getElementById('connStatusText').textContent = 'RECONNECTING';
      document.getElementById('connStatusDot').style.backgroundColor = '#f43f5e';

      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectWs, 3000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      ws.close();
    };
  }

  function sendObserverToWs() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        action: 'set_observer',
        lat: observer.lat,
        lon: observer.lon,
        alt_m: observer.alt_m
      }));
    }
  }

  // 7. Initial Fetch of HA Cluster Diagnostics
  async function fetchHaMetrics() {
    try {
      const res = await fetch('/api/ha/status');
      if (!res.ok) return;
      const data = await res.json();
      document.getElementById('haNodeId').textContent = data.node_id;
      document.getElementById('haUptime').textContent = `${Math.round(data.uptime_seconds)}s`;
      document.getElementById('haTotalSats').textContent = data.total_satellites_indexed;
      document.getElementById('haRequests').textContent = data.client_metrics.total_requests;
      document.getElementById('haCacheHits').textContent = data.client_metrics.cache_hits;
      document.getElementById('haFallbackHits').textContent = data.client_metrics.fallback_hits;
    } catch (e) {
      console.warn('HA metrics fetch failed:', e);
    }
  }
  setInterval(fetchHaMetrics, 5000);
  fetchHaMetrics();

  // Start WebSocket
  connectWs();
});
