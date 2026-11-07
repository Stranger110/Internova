/**
 * NASA EONET (Earth Observatory Natural Event Tracker) Controller.
 * Manages disaster markers on the Leaflet map and renders the incident inspector list.
 */

class EONETManager {
  constructor(mapModule, onSelectView) {
    this.mapModule = mapModule;
    this.onSelectView = onSelectView;
    this.events = [];
    this.markers = {};
    this.activeCategory = 'all';

    this.listContainer = document.getElementById('disastersList');
    this.countBadge = document.getElementById('disastersCount');

    this.bindFilters();
    this.fetchEvents();

    // Auto-refresh disaster feeds every 15 minutes
    setInterval(() => this.fetchEvents(), 15 * 60 * 1000);
  }

  bindFilters() {
    const filterBtns = document.querySelectorAll('.disaster-filter-btn');
    filterBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.activeCategory = btn.dataset.category;
        this.renderEvents();
        this.plotMarkers();
      });
    });
  }

  async fetchEvents() {
    if (this.listContainer) {
      this.listContainer.innerHTML = '<div style="color:var(--text-dim);font-size:11px;font-family:var(--font-mono);padding:10px 0;">Syncing NASA EONET incident telemetry...</div>';
    }

    try {
      const res = await fetch('/api/eonet/events?days=45&limit=80');
      if (!res.ok) return;
      const data = await res.json();
      this.events = data.events || [];

      if (this.mapModule) {
        this.mapModule.disasterCount = this.events.length;
        if (this.mapModule.currentMode === 'disasters') {
          const badgeCount = document.getElementById('activeSatsCount');
          if (badgeCount) badgeCount.textContent = this.events.length;
        }
      }

      if (this.countBadge) {
        this.countBadge.textContent = this.events.length;
      }

      this.renderEvents();
      this.plotMarkers();
    } catch (e) {
      console.warn('Could not fetch NASA EONET events:', e);
      if (this.listContainer) {
        this.listContainer.innerHTML = '<div style="color:var(--accent-rose);font-size:11px;font-family:var(--font-mono);">Failed to connect to NASA EONET.</div>';
      }
    }
  }

  getCategoryColor(catId) {
    switch (catId) {
      case 'wildfires':
        return '#f97316'; // Amber/Orange
      case 'severeStorms':
        return '#a855f7'; // Purple/Violet
      case 'volcanoes':
        return '#ef4444'; // Crimson
      case 'seaLakeIce':
        return '#38bdf8'; // Cyan
      case 'floods':
        return '#3b82f6'; // Blue
      default:
        return '#eab308'; // Gold
    }
  }

  getCategorySvg(catId, color) {
    switch (catId) {
      case 'wildfires':
        // Flame
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="${color}" stroke="${color}" stroke-width="1"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`;
      case 'severeStorms':
        // Cyclone
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.5"><path d="M12 2a10 10 0 0 0-7.07 17.07A10 10 0 0 0 19.07 4.93"/><path d="M12 6a6 6 0 0 0-4.24 10.24A6 6 0 0 0 16.24 7.76"/><circle cx="12" cy="12" r="2" fill="${color}"/></svg>`;
      case 'volcanoes':
        // Volcano Peak
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2"><path d="m2 20 7-14 4 8 3-4 6 10H2z"/><circle cx="11" cy="4" r="1.5" fill="${color}"/><circle cx="15" cy="5" r="1" fill="${color}"/></svg>`;
      case 'seaLakeIce':
        // Ice Crystal
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2"><path d="m12 2 3 5h5l-4 3 2 6-6-4-6 4 2-6-4-3h5z"/></svg>`;
      default:
        // Alert triangle
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    }
  }

  getFilteredEvents() {
    if (!this.activeCategory || this.activeCategory === 'all') {
      return this.events;
    }
    return this.events.filter(e => e.category_id === this.activeCategory);
  }

  plotMarkers() {
    if (!this.mapModule || !this.mapModule.disastersLayer) return;

    // Clear previous disaster markers
    this.mapModule.disastersLayer.clearLayers();
    this.markers = {};

    const filtered = this.getFilteredEvents();

    if (this.mapModule) {
      this.mapModule.disasterCount = filtered.length;
      if (this.mapModule.currentMode === 'disasters') {
        const badgeCount = document.getElementById('activeSatsCount');
        if (badgeCount) badgeCount.textContent = filtered.length;
      }
    }

    filtered.forEach(ev => {
      const color = this.getCategoryColor(ev.category_id);
      const svgIcon = this.getCategorySvg(ev.category_id, color);

      const customIcon = L.divIcon({
        className: 'disaster-map-marker',
        html: `
          <div class="disaster-pulse-ring" style="border-color:${color};box-shadow:0 0 10px ${color};"></div>
          <div class="disaster-marker-inner" style="background:rgba(10,13,20,0.9);border:1.5px solid ${color};">
            ${svgIcon}
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const marker = L.marker([ev.latitude, ev.longitude], { icon: customIcon });

      const dateStr = ev.date ? new Date(ev.date).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : 'Active';
      const magStr = ev.magnitude_value ? `${ev.magnitude_value.toLocaleString()} ${ev.magnitude_unit || ''}` : 'Detected';

      const popupContent = `
        <div class="disaster-popup">
          <div class="disaster-popup-cat" style="color:${color};">${ev.category_title.toUpperCase()}</div>
          <div class="disaster-popup-title">${ev.title}</div>
          <div class="disaster-popup-grid">
            <div>Coordinates: <b>${ev.latitude.toFixed(2)}°, ${ev.longitude.toFixed(2)}°</b></div>
            <div>Detected: <b>${dateStr}</b></div>
            <div>Magnitude: <b>${magStr}</b></div>
          </div>
          ${ev.source_url ? `<a href="${ev.source_url}" target="_blank" rel="noopener" class="disaster-popup-link">NASA Earth Observatory Reference &rarr;</a>` : ''}
        </div>
      `;

      marker.bindPopup(popupContent, { maxWidth: 280, className: 'eonet-leaflet-popup' });
      this.mapModule.disastersLayer.addLayer(marker);
      this.markers[ev.id] = marker;
    });
  }

  renderEvents() {
    if (!this.listContainer) return;
    this.listContainer.innerHTML = '';

    const filtered = this.getFilteredEvents();

    if (this.mapModule) {
      this.mapModule.disasterCount = filtered.length;
      if (this.mapModule.currentMode === 'disasters') {
        const badgeCount = document.getElementById('activeSatsCount');
        if (badgeCount) badgeCount.textContent = filtered.length;
      }
    }

    if (filtered.length === 0) {
      this.listContainer.innerHTML = `
        <div style="color:var(--text-dim);font-size:12px;font-family:var(--font-mono);padding:14px 0;">
          No active natural events matching category '${this.activeCategory}'.
        </div>
      `;
      return;
    }

    filtered.forEach(ev => {
      const color = this.getCategoryColor(ev.category_id);
      const card = document.createElement('div');
      card.className = 'disaster-card';
      card.style.borderLeft = `3px solid ${color}`;

      const dateStr = ev.date ? new Date(ev.date).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : 'Active';
      const magStr = ev.magnitude_value ? `${ev.magnitude_value.toLocaleString()} ${ev.magnitude_unit || ''}` : null;

      card.innerHTML = `
        <div class="disaster-card-header">
          <span class="disaster-card-tag" style="color:${color};background:${color}22;">
            ${ev.category_title.toUpperCase()}
          </span>
          <span class="disaster-card-date">${dateStr}</span>
        </div>
        <div class="disaster-card-title">${ev.title}</div>
        <div class="disaster-card-meta">
          <span>Lat: ${ev.latitude.toFixed(2)}°, Lon: ${ev.longitude.toFixed(2)}°</span>
          ${magStr ? `<span>${magStr}</span>` : ''}
        </div>
        <div class="disaster-card-action">
          <span>TARGET ON MAP &rarr;</span>
        </div>
      `;

      card.addEventListener('click', () => {
        // Ensure map is in disasters mode
        if (this.mapModule) {
          this.mapModule.setMode('disasters');
        }

        // Fly to location on map
        this.mapModule.flyToLocation(ev.latitude, ev.longitude, 6);

        // Open marker popup if available
        if (this.markers[ev.id]) {
          setTimeout(() => {
            this.markers[ev.id].openPopup();
          }, 600);
        }

        // On mobile view, switch to MAP so the user sees the incident immediately
        if (this.onSelectView && window.innerWidth <= 768) {
          this.onSelectView('tabMap', 'disasters');
        }
      });

      this.listContainer.appendChild(card);
    });
  }
}
