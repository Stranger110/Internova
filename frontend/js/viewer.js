/**
 * Live Space & Earth Satellite Imagery Viewer Module.
 * Displays real-time NOAA GOES full disk, NASA EPIC deep space, and SatNOGS downlinks.
 */

class ImageryViewer {
  constructor() {
    this.currentSatellite = 'GOES-16';
    this.currentChannel = 'geocolor';
    this.imageElement = document.getElementById('goesImage');
    this.metaElement = document.getElementById('imageryMeta');
    this.epicGalleryElement = document.getElementById('epicGallery');
    this.satnogsGalleryElement = document.getElementById('satnogsGallery');

    this.bindEvents();
    this.loadGOESImage();
    this.loadEPICGallery();
    this.loadSatNOGSDownlinks();

    // Auto-refresh GOES imagery every 5 minutes
    setInterval(() => this.loadGOESImage(), 5 * 60 * 1000);
  }

  bindEvents() {
    // Channel selection buttons
    const channelBtns = document.querySelectorAll('.channel-btn');
    channelBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        channelBtns.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.currentChannel = e.target.dataset.channel;
        this.loadGOESImage();
      });
    });

    // Satellite selection buttons (GOES-16 vs GOES-18)
    const satBtns = document.querySelectorAll('.sat-select-btn');
    satBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        satBtns.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.currentSatellite = e.target.dataset.sat;
        this.loadGOESImage();
      });
    });
  }

  loadGOESImage() {
    if (!this.imageElement) return;

    const timestamp = new Date().getTime();
    const url = `/api/imagery/goes/${this.currentSatellite}/image?channel=${this.currentChannel}&t=${timestamp}`;

    this.metaElement.innerHTML = `<span>Loading ${this.currentSatellite} [${this.currentChannel.toUpperCase()}]...</span>`;

    const img = new Image();
    img.onload = () => {
      this.imageElement.src = url;
      this.metaElement.innerHTML = `
        <span><b>${this.currentSatellite}</b> [${this.currentChannel.toUpperCase()}]</span>
        <span>UPDATED ${new Date().toLocaleTimeString()}</span>
      `;
    };
    img.onerror = () => {
      this.metaElement.innerHTML = `<span style="color:#f43f5e;">BUFF-RETRY: Mirror temporarily buffering...</span>`;
    };
    img.src = url;
  }

  async loadEPICGallery() {
    if (!this.epicGalleryElement) return;
    try {
      const res = await fetch('/api/imagery/epic?limit=6');
      if (!res.ok) return;
      const data = await res.json();

      this.epicGalleryElement.innerHTML = '';
      if (!data.images || data.images.length === 0) {
        this.epicGalleryElement.innerHTML = '<div style="color:var(--text-dim);font-size:12px;">Syncing deep space telemetry...</div>';
        return;
      }

      data.images.forEach(item => {
        const card = document.createElement('div');
        card.className = 'epic-card';
        card.innerHTML = `
          <img src="${item.thumb_url || item.hires_url}" alt="Earth from L1" loading="lazy">
          <div class="epic-card-meta">
            <div><b>${item.date.split(' ')[0]}</b></div>
            <div>${item.date.split(' ')[1] || ''} UTC</div>
          </div>
        `;
        card.addEventListener('click', () => {
          window.open(item.hires_url, '_blank');
        });
        this.epicGalleryElement.appendChild(card);
      });
    } catch (e) {
      console.warn('Could not load EPIC gallery:', e);
    }
  }

  async loadSatNOGSDownlinks() {
    if (!this.satnogsGalleryElement) return;
    try {
      const res = await fetch('/api/imagery/satnogs?limit=4');
      if (!res.ok) return;
      const data = await res.json();

      this.satnogsGalleryElement.innerHTML = '';
      if (!data.downlinks || data.downlinks.length === 0) {
        this.satnogsGalleryElement.innerHTML = '<div style="color:var(--text-dim);font-size:12px;">Monitoring ground station downlinks...</div>';
        return;
      }

      data.downlinks.forEach(obs => {
        const card = document.createElement('div');
        card.className = 'pass-card';
        const imgUrl = obs.payload_urls && obs.payload_urls.length > 0 ? obs.payload_urls[0] : obs.waterfall_url;

        card.innerHTML = `
          <div class="pass-header">
            <span class="pass-sat-name">${obs.satellite}</span>
            <span class="pass-countdown">OBS #${obs.observation_id}</span>
          </div>
          <div style="font-size:11px;color:var(--text-dim);margin:4px 0;">
            Ground Station ID: ${obs.station_id || 'Global'} | Freq: ${(obs.frequency_hz / 1e6).toFixed(3)} MHz
          </div>
          ${imgUrl ? `<img src="${imgUrl}" style="width:100%;height:100px;object-fit:cover;border-radius:4px;margin-top:6px;border:1px solid rgba(255,255,255,0.1);" loading="lazy">` : ''}
        `;
        if (imgUrl) {
          card.style.cursor = 'pointer';
          card.addEventListener('click', () => window.open(imgUrl, '_blank'));
        }
        this.satnogsGalleryElement.appendChild(card);
      });
    } catch (e) {
      console.warn('Could not load SatNOGS downlinks:', e);
    }
  }
}
