/**
 * Pass Predictor & Sky Radar Module.
 * Calculates upcoming overhead passes and renders a high-tech polar sky radar display.
 */

class PassPredictor {
  constructor(canvasId, passListId) {
    this.canvas = document.getElementById(canvasId);
    this.passListElement = document.getElementById(passListId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.currentObserver = { lat: 37.7749, lon: -122.4194, alt_m: 15 };
    this.selectedNoradId = 25544; // Default to ISS
    this.cachedPasses = [];

    this.initCanvas();
    this.drawRadar();
  }

  initCanvas() {
    if (!this.canvas) return;
    // Set high-DPI resolution
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = rect.width > 50 ? rect.width : 240;
    const displayHeight = rect.height > 50 ? rect.height : 240;
    this.canvas.width = displayWidth * dpr;
    this.canvas.height = displayHeight * dpr;
    if (this.ctx) {
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(dpr, dpr);
    }
  }

  redraw() {
    this.initCanvas();
    this.drawRadar(this.cachedPasses && this.cachedPasses.length > 0 ? this.cachedPasses[0] : null);
  }

  setObserver(lat, lon, alt_m = 15) {
    this.currentObserver = { lat, lon, alt_m };
    this.fetchPasses(this.selectedNoradId);
  }

  setSatellite(noradId) {
    this.selectedNoradId = noradId;
    this.fetchPasses(noradId);
  }

  async fetchPasses(noradId) {
    if (!this.passListElement) return;
    this.passListElement.innerHTML = '<div style="color:var(--text-dim);font-size:12px;">Computing topocentric orbits...</div>';

    try {
      const { lat, lon, alt_m } = this.currentObserver;
      const url = `/api/satellites/${noradId}/passes?lat=${lat}&lon=${lon}&alt_m=${alt_m}&hours=24&min_el=10`;
      const res = await fetch(url);
      if (!res.ok) return;

      const data = await res.json();
      this.cachedPasses = data.passes || [];
      this.renderPassList(data.name, this.cachedPasses);
      this.drawRadar(this.cachedPasses[0]);
    } catch (e) {
      console.warn('Could not fetch passes:', e);
      this.passListElement.innerHTML = '<div style="color:var(--accent-rose);font-size:12px;">Pass prediction unavailable.</div>';
    }
  }

  renderPassList(satName, passes) {
    if (!this.passListElement) return;
    this.passListElement.innerHTML = '';

    if (!passes || passes.length === 0) {
      this.passListElement.innerHTML = `
        <div style="color:var(--text-muted);font-size:12px;padding:10px 0;">
          No passes above 10° elevation for <b>${satName}</b> in the next 24 hours from this location.
        </div>
      `;
      return;
    }

    passes.forEach(p => {
      const aosDate = new Date(p.aos_time);
      const minutesUntil = Math.max(0, Math.round((p.aos_timestamp * 1000 - Date.now()) / 60000));
      const card = document.createElement('div');
      card.className = 'pass-card';

      card.innerHTML = `
        <div class="pass-header">
          <span class="pass-sat-name">${satName}</span>
          <span class="pass-countdown">${minutesUntil === 0 ? 'ACTIVE / IN VIEW' : `in ${minutesUntil}m`}</span>
        </div>
        <div class="pass-grid">
          <div>AOS: <b>${aosDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</b></div>
          <div>Max El: <b style="color:var(--accent-cyan);">${p.max_elevation}°</b></div>
          <div>Duration: <b>${Math.round(p.duration_seconds / 60)}m</b></div>
          <div>AOS Az: <b>${p.aos_azimuth}°</b></div>
          <div>Culm Az: <b>${p.culmination_azimuth}°</b></div>
          <div>Doppler: <b>${p.max_doppler_hz ? `±${(p.max_doppler_hz/1000).toFixed(1)}k` : 'N/A'}</b></div>
        </div>
      `;
      card.addEventListener('mouseenter', () => this.drawRadar(p));
      this.passListElement.appendChild(card);
    });
  }

  drawRadar(highlightPass = null) {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const width = this.canvas.width / (window.devicePixelRatio || 1);
    const height = this.canvas.height / (window.devicePixelRatio || 1);
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(cx, cy) - 20;

    ctx.clearRect(0, 0, width, height);

    // 1. Concentric elevation circles (0°, 30°, 60°)
    const rings = [0, 30, 60];
    rings.forEach(el => {
      const r = radius * (1 - el / 90);
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, 2 * Math.PI);
      ctx.strokeStyle = el === 0 ? 'rgba(56, 189, 248, 0.4)' : 'rgba(255, 255, 255, 0.1)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Elevation text
      ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.font = '9px monospace';
      ctx.fillText(`${el}°`, cx + 3, cy - r + 10);
    });

    // 2. Crosshairs
    ctx.beginPath();
    ctx.moveTo(cx, cy - radius);
    ctx.lineTo(cx, cy + radius);
    ctx.moveTo(cx - radius, cy);
    ctx.lineTo(cx + radius, cy);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.stroke();

    // 3. Compass Labels (N, E, S, W)
    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('N', cx, cy - radius - 6);
    ctx.fillText('S', cx, cy + radius + 14);
    ctx.fillText('E', cx + radius + 10, cy + 4);
    ctx.fillText('W', cx - radius - 10, cy + 4);

    // 4. Center Zenith Marker (90°)
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, 2 * Math.PI);
    ctx.fillStyle = '#10b981';
    ctx.fill();

    // 5. Draw pass trajectory arc if available
    if (highlightPass) {
      const aosAz = (highlightPass.aos_azimuth - 90) * (Math.PI / 180);
      const culmAz = (highlightPass.culmination_azimuth - 90) * (Math.PI / 180);
      const maxEl = highlightPass.max_elevation;

      const rAos = radius; // 0 deg elevation is horizon
      const rCulm = radius * (1 - maxEl / 90);

      const xAos = cx + rAos * Math.cos(aosAz);
      const yAos = cy + rAos * Math.sin(aosAz);

      const xCulm = cx + rCulm * Math.cos(culmAz);
      const yCulm = cy + rCulm * Math.sin(culmAz);

      // Trajectory curve
      ctx.beginPath();
      ctx.moveTo(xAos, yAos);
      ctx.quadraticCurveTo(xCulm, yCulm, xCulm, yCulm);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Peak blip
      ctx.beginPath();
      ctx.arc(xCulm, yCulm, 5, 0, 2 * Math.PI);
      ctx.fillStyle = '#f59e0b';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }
}
