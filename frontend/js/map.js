/**
 * Orbital Command Map Module.
 * Manages Leaflet map, Day/Night solar terminator, satellite markers, footprints, ground tracks,
 * and contextual switching between Satellites and NASA EONET Disaster mode.
 */

class OrbitalMap {
  constructor(containerId, onSatelliteSelect) {
    this.containerId = containerId;
    this.onSatelliteSelect = onSatelliteSelect;
    this.map = null;
    this.markers = {};
    this.footprints = {};
    this.groundTrackPolyline = null;
    this.terminatorPolygon = null;
    this.selectedNoradId = 25544; // Default to ISS
    this.observerMarker = null;

    // View Mode State: 'satellites' | 'disasters'
    this.currentMode = 'satellites';
    this.satelliteCount = 10;
    this.disasterCount = 0;

    // Dedicated Layer Groups
    this.satellitesLayer = null;
    this.disastersLayer = null;

    this.initMap();
  }

  initMap() {
    // Initialize Leaflet map
    this.map = L.map(this.containerId, {
      center: [20, 0],
      zoom: 2.2,
      minZoom: 1.5,
      maxZoom: 10,
      worldCopyJump: true,
      zoomControl: false
    });

    // Basemap 1: High-Tech Dark Gray Tactical Base (100% Free, No API key, No watermarks)
    const darkGray = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri',
      maxZoom: 16
    });

    // Basemap 2: High-Resolution Real Satellite Imagery Base
    const satelliteView = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; NASA, USGS',
      maxZoom: 18
    });

    // Basemap 3: OpenStreetMap Cyber-Inverted Base
    const osmDark = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      className: 'dark-tiles',
      maxZoom: 19
    });

    // Add default basemap
    darkGray.addTo(this.map);

    // Satellites Layer Group (added to map by default on startup)
    this.satellitesLayer = L.layerGroup().addTo(this.map);

    // Disaster Layer Group (kept in memory, attached ONLY when on Disasters tab)
    this.disastersLayer = L.layerGroup();

    // Basemap switcher control at top right
    const baseMaps = {
      "Tactical Dark": darkGray,
      "Satellite (Esri)": satelliteView,
      "High Contrast": osmDark
    };
    this.layerControl = L.control.layers(baseMaps, null, { position: 'topright' }).addTo(this.map);

    // Zoom control at top right
    L.control.zoom({ position: 'topright' }).addTo(this.map);

    // Initial solar terminator
    this.updateSolarTerminator();
    setInterval(() => this.updateSolarTerminator(), 60000); // refresh every minute

    // Window resize handler
    window.addEventListener('resize', () => this.invalidateSize());
  }

  setMode(mode) {
    if (mode === this.currentMode) return;
    this.currentMode = mode;

    const hudEl = document.getElementById('satelliteHud');
    const badgeTargetTitle = document.getElementById('badgeTargetTitle');
    const badgeCount = document.getElementById('activeSatsCount');
    const badgeSubTitle = document.getElementById('badgeSubTitle');
    const badgeSubVal = document.getElementById('badgeSubVal');
    const badgeThirdTitle = document.getElementById('badgeThirdTitle');
    const badgeThirdVal = document.getElementById('badgeThirdVal');

    if (mode === 'disasters') {
      // 1. Detach satellites layer (markers, footprints, tracks)
      if (this.map.hasLayer(this.satellitesLayer)) {
        this.map.removeLayer(this.satellitesLayer);
      }

      // 2. Attach disasters layer
      if (!this.map.hasLayer(this.disastersLayer)) {
        this.map.addLayer(this.disastersLayer);
      }

      // 3. Hide satellite telemetry HUD
      if (hudEl) {
        hudEl.style.display = 'none';
      }

      // 4. Update HUD badges for Disasters view
      if (badgeTargetTitle) badgeTargetTitle.textContent = 'ACTIVE DISASTERS';
      if (badgeCount) badgeCount.textContent = this.disasterCount || '--';
      if (badgeSubTitle) badgeSubTitle.textContent = 'INCIDENT FEED';
      if (badgeSubVal) {
        badgeSubVal.textContent = 'NASA EONET v3';
        badgeSubVal.style.color = 'var(--accent-rose)';
      }
      if (badgeThirdTitle) badgeThirdTitle.textContent = 'MONITORING';
      if (badgeThirdVal) {
        badgeThirdVal.textContent = 'EARTH OBSERVATORY';
        badgeThirdVal.style.color = 'var(--accent-amber)';
      }
    } else {
      // mode === 'satellites'
      // 1. Detach disasters layer
      if (this.map.hasLayer(this.disastersLayer)) {
        this.map.removeLayer(this.disastersLayer);
      }

      // 2. Attach satellites layer
      if (!this.map.hasLayer(this.satellitesLayer)) {
        this.map.addLayer(this.satellitesLayer);
      }

      // 3. Restore satellite telemetry HUD
      if (hudEl) {
        hudEl.style.display = '';
      }

      // 4. Update HUD badges for Satellites view
      if (badgeTargetTitle) badgeTargetTitle.textContent = 'TRACKING TARGETS';
      if (badgeCount) badgeCount.textContent = this.satelliteCount || '10';
      if (badgeSubTitle) badgeSubTitle.textContent = 'PROPAGATION';
      if (badgeSubVal) {
        badgeSubVal.textContent = 'SGP4 / WGS84';
        badgeSubVal.style.color = 'var(--accent-emerald)';
      }
      if (badgeThirdTitle) badgeThirdTitle.textContent = 'TELEMETRY';
      if (badgeThirdVal) {
        badgeThirdVal.textContent = '1 HZ LIVE';
        badgeThirdVal.style.color = 'var(--accent-cyan)';
      }
    }

    this.invalidateSize();
  }

  invalidateSize() {
    if (this.map) {
      setTimeout(() => {
        this.map.invalidateSize();
      }, 120);
    }
  }

  flyToLocation(lat, lon, zoom = 5) {
    if (this.map) {
      this.map.flyTo([lat, lon], zoom, {
        duration: 1.2,
        easeLinearity: 0.25
      });
    }
  }

  updateSolarTerminator() {
    // Calculates sun position on Earth and draws day/night boundary
    const now = new Date();
    const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 1000 / 60 / 60 / 24);
    const declination = -23.44 * Math.cos((2 * Math.PI / 365) * (dayOfYear + 10)); // Sun declination in degrees
    const gmtHours = now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
    const sunLon = (12 - gmtHours) * 15; // Greenwich solar longitude

    const points = [];
    const decRad = (declination * Math.PI) / 180;

    for (let lon = -180; lon <= 180; lon += 3) {
      const deltaLonRad = ((lon - sunLon) * Math.PI) / 180;
      let latRad = Math.atan(-Math.cos(deltaLonRad) / Math.tan(decRad));
      let lat = (latRad * 180) / Math.PI;
      points.push([lat, lon]);
    }

    // Close the shadow polygon towards the dark pole
    if (declination > 0) {
      points.push([-90, 180], [-90, -180]);
    } else {
      points.push([90, 180], [90, -180]);
    }

    if (this.terminatorPolygon) {
      this.terminatorPolygon.setLatLngs(points);
    } else {
      this.terminatorPolygon = L.polygon(points, {
        color: 'transparent',
        fillColor: '#000000',
        fillOpacity: 0.38,
        interactive: false
      }).addTo(this.map);
    }
  }

  updateObserverPosition(lat, lon) {
    if (this.observerMarker) {
      this.observerMarker.setLatLng([lat, lon]);
    } else {
      const icon = L.divIcon({
        className: 'observer-marker',
        html: `<div style="width:14px;height:14px;border-radius:50%;background:#f59e0b;border:2px solid #fff;box-shadow:0 0 10px #f59e0b;"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
      });
      this.observerMarker = L.marker([lat, lon], { icon }).addTo(this.satellitesLayer)
        .bindPopup(`<b>Ground Station</b><br>Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}`);
    }
  }

  updateSatellites(satellites) {
    satellites.forEach(sat => {
      const { norad_id, name, latitude, longitude, footprint_radius_km, category } = sat;
      const isSelected = norad_id === this.selectedNoradId;

      // Color coding by category
      let color = '#38bdf8'; // Cyan default
      if (category === 'station') color = '#10b981'; // Emerald for ISS / Tiangong
      if (category === 'weather-leo') color = '#38bdf8'; // Cyan for NOAA / Meteor
      if (category === 'weather-geo') color = '#a855f7'; // Purple for GOES
      if (category === 'science') color = '#f59e0b'; // Amber for Hubble

      // Update or create marker in satellitesLayer
      if (!this.markers[norad_id]) {
        const icon = L.divIcon({
          className: 'sat-marker',
          html: `
            <div class="sat-marker-dot" style="background-color: ${color}; color: ${color};"></div>
            <div class="sat-label">${name}</div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });

        const marker = L.marker([latitude, longitude], { icon }).addTo(this.satellitesLayer);
        marker.on('click', () => {
          this.selectedNoradId = norad_id;
          if (this.onSatelliteSelect) this.onSatelliteSelect(sat);
          this.fetchGroundTrack(norad_id);
        });

        this.markers[norad_id] = marker;
      } else {
        this.markers[norad_id].setLatLng([latitude, longitude]);
      }

      // Update or create footprint circle in satellitesLayer
      const radiusMeters = (footprint_radius_km || 2000) * 1000;
      if (!this.footprints[norad_id]) {
        const circle = L.circle([latitude, longitude], {
          radius: radiusMeters,
          color: color,
          weight: 1,
          opacity: isSelected ? 0.8 : 0.25,
          fillColor: color,
          fillOpacity: isSelected ? 0.08 : 0.02,
          interactive: false
        }).addTo(this.satellitesLayer);
        this.footprints[norad_id] = circle;
      } else {
        const circle = this.footprints[norad_id];
        circle.setLatLng([latitude, longitude]);
        circle.setRadius(radiusMeters);
        circle.setStyle({
          opacity: isSelected ? 0.8 : 0.25,
          fillOpacity: isSelected ? 0.08 : 0.02
        });
      }
    });
  }

  async fetchGroundTrack(noradId) {
    try {
      const res = await fetch(`/api/satellites/${noradId}/track?past_min=50&future_min=50&step_min=2`);
      if (!res.ok) return;
      const data = await res.json();
      this.drawGroundTrack(data.track);
    } catch (e) {
      console.warn('Could not fetch ground track:', e);
    }
  }

  drawGroundTrack(points) {
    if (this.groundTrackPolyline) {
      this.satellitesLayer.removeLayer(this.groundTrackPolyline);
      this.groundTrackPolyline = null;
    }

    if (!points || points.length === 0) return;

    // Split points across the antimeridian (+180/-180) to avoid lines stretching across the entire map
    const segments = [];
    let currentSegment = [];

    for (let i = 0; i < points.length; i++) {
      if (i > 0) {
        const lonDiff = Math.abs(points[i][1] - points[i - 1][1]);
        if (lonDiff > 180) {
          segments.push(currentSegment);
          currentSegment = [];
        }
      }
      currentSegment.push(points[i]);
    }
    if (currentSegment.length > 0) segments.push(currentSegment);

    this.groundTrackPolyline = L.polyline(segments, {
      color: '#38bdf8',
      weight: 2,
      opacity: 0.7,
      dashArray: '4, 6'
    }).addTo(this.satellitesLayer);
  }
}
