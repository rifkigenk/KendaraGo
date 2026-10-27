/* Use official Google Maps when configured; keep a compliant 2D map otherwise. */
(() => {
  const config = document.getElementById('location-config');
  window.createMeetingMap = (element, options = {}) => {
    if (config?.dataset.googleKey && config.dataset.tiles === 'true') {
      return window.createGoogleMeetingMap(element, options);
    }
    const {onPick, onError, modeButton} = options;
    let center = options.center || [115.216, -8.65], zoom = options.zoom || 12;
    let engine, marker, point, locked = false, removed = false, timer, generation = 0;
    const tiles = config?.dataset.tiles === 'true';
    if (modeButton) { modeButton.hidden = true; modeButton.disabled = true; }
    const frame = document.createElement('div'); frame.className = 'meeting-map-frame';
    element.before(frame); frame.append(element);
    const status = document.createElement('div'); status.className = 'meeting-map-state';
    status.setAttribute('role', 'status');
    const message = document.createElement('span');
    const retry = document.createElement('button'); retry.type = 'button';
    retry.className = 'btn btn-light btn-sm'; retry.textContent = 'Coba lagi';
    status.append(message, retry); frame.append(status);
    function state(value, text = '') {
      element.dataset.mapState = value; status.hidden = value === 'ready';
      message.textContent = text; retry.hidden = !['error', 'slow'].includes(value);
    }
    state('loading', 'Memuat peta Bali…');
    const api = {
      setPoint(lat, lon, recenter = true) {
        point = [lat, lon];
        if (recenter) { center = [lon, lat]; zoom = 17; }
        if (!engine) return;
        if (!marker) {
          marker = L.marker(point, {draggable: !locked,
            icon: L.divIcon({className: 'meeting-pin', html: '📍', iconSize: [30, 36], iconAnchor: [15, 34]})}).addTo(engine);
          marker.on('dragend', () => { const p = marker.getLatLng(); onPick?.(p.lat, p.lng); });
        } else marker.setLatLng(point);
        if (locked) marker.dragging.disable(); else marker.dragging.enable();
        if (recenter) engine.setView(point, zoom, {animate: false});
      },
      clearPin() { marker?.remove(); marker = null; point = null; },
      setLocked(value) { locked = value; if (marker) { if (locked) marker.dragging.disable(); else marker.dragging.enable(); } },
      remove() { removed = true; generation++; clearTimeout(timer); observer.disconnect(); engine?.remove(); status.remove(); },
      get engine() { return engine; },
      get is3D() { return false; }
    };
    function initialize() {
      if (removed) return;
      const current = ++generation; clearTimeout(timer);
      engine?.remove(); engine = null; marker = null; element.replaceChildren();
      element.dataset.mapEngine = '2d'; element.dataset.mapReady = 'false';
      state('loading', 'Memuat peta Bali…');
      if (!window.L) { state('error', 'Peta belum tersedia. Muat ulang halaman.'); onError?.('Peta belum tersedia.'); return; }
      engine = L.map(element, {scrollWheelZoom: false}).setView([center[1], center[0]], zoom);
      if (tiles) {
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19, updateWhenIdle: true, keepBuffer: 1,
          referrerPolicy: 'strict-origin-when-cross-origin',
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).on('tileload', () => {
          if (removed || current !== generation) return;
          clearTimeout(timer); element.dataset.mapReady = 'true'; state('ready');
        }).on('tileerror', () => {
          if (!removed && current === generation && element.dataset.mapReady !== 'true') state('error', 'Gambar peta belum tersedia. Coba lagi atau buka Google Maps.');
        }).addTo(engine);
        timer = setTimeout(() => {
          if (!removed && current === generation && element.dataset.mapReady !== 'true') state('slow', 'Peta lambat dimuat. Anda tetap dapat mencari tempat atau menggunakan koordinat.');
        }, 6000);
      } else { element.dataset.mapReady = 'true'; state('ready'); }
      engine.on('click', e => { if (!locked) onPick?.(e.latlng.lat, e.latlng.lng); });
      if (point) api.setPoint(point[0], point[1], false);
    }
    retry.addEventListener('click', () => {
      if (engine) { const view = engine.getCenter(); center = [view.lng, view.lat]; zoom = engine.getZoom(); }
      initialize();
    });
    const observer = new ResizeObserver(() => {
      if (removed || !element.clientWidth || !element.clientHeight) return;
      if (!engine) initialize(); else engine.invalidateSize({pan: false});
    });
    observer.observe(element); element._meetingMap = api;
    return api;
  };
})();
