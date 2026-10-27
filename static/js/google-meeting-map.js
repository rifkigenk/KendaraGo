/* Official Google Maps JavaScript API. The browser key must have referrer restrictions. */
(() => {
  const config = document.getElementById('location-config');
  const nonce = document.currentScript?.nonce || '';
  let loader, authenticationFailed = false;
  window.gm_authFailure = () => {
    authenticationFailed = true;
    window.dispatchEvent(new Event('kendarago-google-map-error'));
  };
  function loadGoogle() {
    if (authenticationFailed) return Promise.reject(new Error('Google Maps belum dapat diakses. Gunakan tautan Google Maps atau isi koordinat.'));
    if (window.google?.maps?.Map && window.google.maps.marker?.AdvancedMarkerElement) return Promise.resolve();
    if (loader) return loader;
    loader = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const params = new URLSearchParams({key: config.dataset.googleKey, v: 'weekly',
        loading: 'async', libraries: 'maps,marker', callback: 'kendaragoGoogleMapsReady',
        language: 'id', region: 'ID', auth_referrer_policy: 'origin'});
      script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
      script.async = true; script.nonce = nonce;
      const timeout = setTimeout(fail, 12000);
      function fail() {
        clearTimeout(timeout); script.remove(); loader = null;
        reject(new Error('Google Maps belum termuat. Periksa koneksi atau buka Google Maps.'));
      }
      window.kendaragoGoogleMapsReady = () => {
        clearTimeout(timeout);
        if (authenticationFailed) reject(new Error('Google Maps belum dapat diakses.'));
        else resolve();
      };
      script.onerror = fail;
      document.head.append(script);
    });
    return loader;
  }

  window.createGoogleMeetingMap = (element, {onPick, onError, modeButton, center = [115.216, -8.65], zoom = 12} = {}) => {
    let engine, marker, point, locked = false, removed = false, loading = false, timer, generation = 0;
    const frame = document.createElement('div'); frame.className = 'meeting-map-frame';
    element.before(frame); frame.append(element);
    const status = document.createElement('div'); status.className = 'meeting-map-state';
    status.setAttribute('role', 'status');
    const text = document.createElement('span');
    const retry = document.createElement('button'); retry.type = 'button';
    retry.className = 'btn btn-light btn-sm'; retry.textContent = 'Coba lagi';
    status.append(text, retry); frame.append(status);
    function state(value, message = '') {
      element.dataset.mapState = value; status.hidden = value === 'ready';
      text.textContent = message; retry.hidden = value !== 'error';
    }
    function label() {
      if (!modeButton) return;
      const supported = !!engine && engine.getRenderingType() === window.google?.maps?.RenderingType.VECTOR;
      modeButton.hidden = false; modeButton.disabled = loading || !supported || authenticationFailed;
      modeButton.textContent = engine?.getTilt() > 0 ? 'Gunakan 2D' : 'Lihat 3D';
      modeButton.setAttribute('aria-pressed', String(engine?.getTilt() > 0));
      modeButton.title = supported ? 'Perspektif bangunan Google Maps' : '3D memerlukan dukungan peta vektor pada perangkat ini';
    }
    function destroyMap() {
      if (marker) { google.maps.event.clearInstanceListeners(marker); marker.map = null; }
      if (engine) google.maps.event.clearInstanceListeners(engine);
      marker = null; engine = null; element.replaceChildren();
    }
    function authError() {
      if (removed) return;
      clearTimeout(timer); loading = false;
      element.dataset.mapReady = 'false';
      state('error', 'Google Maps belum dapat diakses. Gunakan tautan Google Maps atau isi koordinat.');
      label();
    }
    const api = {
      setPoint(lat, lon, recenter = true) {
        point = {lat, lng: lon};
        if (recenter) { center = [lon, lat]; zoom = 17; }
        if (!engine) return;
        if (!marker) {
          marker = new google.maps.marker.AdvancedMarkerElement({map: engine, position: point,
            gmpDraggable: !locked, title: 'Titik temu penyewa'});
          marker.addListener('dragend', event => {
            if (locked) return;
            const position = event.latLng;
            if (position) onPick?.(position.lat(), position.lng());
          });
        } else marker.position = point;
        marker.gmpDraggable = !locked;
        if (recenter) { engine.setCenter(point); engine.setZoom(zoom); }
      },
      clearPin() { if (marker) { google.maps.event.clearInstanceListeners(marker); marker.map = null; } marker = null; point = null; },
      setLocked(value) { locked = value; if (marker) marker.gmpDraggable = !locked; },
      remove() { removed = true; generation++; clearTimeout(timer); observer.disconnect(); window.removeEventListener('kendarago-google-map-error', authError); modeButton?.removeEventListener('click', toggleMode); destroyMap(); status.remove(); },
      get engine() { return engine; },
      get is3D() { return !!engine && engine.getTilt() > 0; }
    };
    async function initialize() {
      if (removed || loading) return;
      loading = true; const current = ++generation;
      element.dataset.mapEngine = 'google'; element.dataset.mapReady = 'false';
      state('loading', 'Memuat Google Maps…');
      if (modeButton) modeButton.disabled = true;
      try {
        await loadGoogle();
        if (removed || current !== generation) return;
        destroyMap();
        engine = new google.maps.Map(element, {
          center: {lat: center[1], lng: center[0]}, zoom, minZoom: 5, maxZoom: 20,
          mapId: config.dataset.googleMapId || 'DEMO_MAP_ID',
          renderingType: google.maps.RenderingType.VECTOR,
          tilt: 0, heading: 0, tiltInteractionEnabled: true, headingInteractionEnabled: true,
          gestureHandling: 'cooperative', streetViewControl: false,
          mapTypeControl: true, fullscreenControl: true
        });
        engine.addListener('click', event => {
          if (locked || !event.latLng) return;
          if (event.placeId) event.stop();
          onPick?.(event.latLng.lat(), event.latLng.lng());
        });
        engine.addListener('tilesloaded', () => {
          if (removed || current !== generation || authenticationFailed) return;
          clearTimeout(timer); loading = false; element.dataset.mapReady = 'true'; state('ready'); label();
        });
        engine.addListener('tilt_changed', label);
        engine.addListener('renderingtype_changed', label);
        if (point) api.setPoint(point.lat, point.lng, false);
        timer = setTimeout(() => {
          if (removed || current !== generation) return;
          loading = false; state('error', 'Google Maps lambat dimuat. Coba lagi atau gunakan tautan Google Maps.'); label();
        }, 12000);
      } catch (error) {
        if (removed || current !== generation) return;
        loading = false; state('error', error.message); onError?.(error.message);
      }
    }
    function toggleMode() {
      if (!engine || loading || authenticationFailed) return;
      if (engine.getRenderingType() !== google.maps.RenderingType.VECTOR) return;
      if (engine.getTilt() > 0) { engine.setTilt(0); engine.setHeading(0); }
      else { engine.setMapTypeId('roadmap'); engine.setZoom(Math.max(17, engine.getZoom())); engine.setTilt(60); }
      label();
    }
    retry.addEventListener('click', () => { clearTimeout(timer); initialize(); });
    modeButton?.addEventListener('click', toggleMode);
    window.addEventListener('kendarago-google-map-error', authError);
    const observer = new ResizeObserver(() => {
      if (removed || !element.clientWidth || !element.clientHeight) return;
      if (!engine) initialize();
      else { const position = engine.getCenter(); google.maps.event.trigger(engine, 'resize'); engine.setCenter(position); }
    });
    state('loading', 'Memuat Google Maps…'); observer.observe(element); element._meetingMap = api;
    return api;
  };
})();
