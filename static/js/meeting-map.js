/* Vector labels and building heights from OpenFreeMap; Leaflet fallback for non-WebGL devices. */
(() => {
  window.createMeetingMap = (element, {onPick, onError, modeButton, center = [115.216, -8.65], zoom = 12} = {}) => {
    let engine, marker, point, locked = false, vector = false, removed = false;
    const tiles = document.getElementById('location-config')?.dataset.tiles === 'true';
    const label = () => {
      if (!modeButton) return;
      modeButton.disabled = !vector;
      modeButton.textContent = vector ? (engine.getPitch() > 0 ? '3D aktif' : 'Lihat 3D') : 'Peta 2D';
      modeButton.setAttribute('aria-pressed', String(vector && engine.getPitch() > 0));
    };
    const api = {
      setPoint(lat, lon, recenter = true) {
        point = [lon, lat];
        if (vector) {
          if (!marker) {
            marker = new maplibregl.Marker({color: '#164d42', draggable: !locked}).setLngLat(point).addTo(engine);
            marker.on('dragend', () => { const p = marker.getLngLat(); onPick?.(p.lat, p.lng); });
          } else marker.setLngLat(point);
          marker.setDraggable(!locked);
          if (recenter) engine.jumpTo({center: point, zoom: 17});
        } else if (engine) {
          if (!marker) {
            marker = L.marker([lat, lon], {draggable: !locked}).addTo(engine);
            marker.on('dragend', () => { const p = marker.getLatLng(); onPick?.(p.lat, p.lng); });
          } else marker.setLatLng([lat, lon]);
          if (locked) marker.dragging.disable(); else marker.dragging.enable();
          if (recenter) engine.setView([lat, lon], 17);
        }
      },
      clearPin() { marker?.remove(); marker = null; point = null; },
      setLocked(value) {
        locked = value;
        if (marker && vector) marker.setDraggable(!locked);
        else if (marker) { if (locked) marker.dragging.disable(); else marker.dragging.enable(); }
      },
      remove() { removed = true; observer.disconnect(); engine?.remove(); },
      get engine() { return engine; },
      get is3D() { return vector; }
    };
    function fallback(reason) {
      if (removed) return;
      engine?.remove(); marker = null; vector = false;
      element.replaceChildren();
      if (!window.L) { onError?.('Peta tidak tersedia. Cari tempat atau gunakan lokasi saya.'); return; }
      engine = L.map(element, {scrollWheelZoom: false}).setView([center[1], center[0]], zoom);
      if (tiles) L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }).on('tileerror', () => onError?.('Peta belum termuat. Periksa internet, atau cari tempat dan isi koordinat manual.')).addTo(engine);
      engine.on('click', e => { if (!locked) onPick?.(e.latlng.lat, e.latlng.lng); });
      if (point) api.setPoint(point[1], point[0]);
      label();
      if (reason) onError?.(reason);
    }
    try {
      if (!tiles || !window.maplibregl) fallback('Peta 3D tidak tersedia. Pencarian tempat tetap dapat digunakan.');
      else {
        engine = new maplibregl.Map({container: element, style: 'https://tiles.openfreemap.org/styles/liberty',
          center, zoom, pitch: 50, maxPitch: 65, maxZoom: 19, attributionControl: true});
        vector = true;
        engine.scrollZoom.disable();
        engine.addControl(new maplibregl.NavigationControl({visualizePitch: true}), 'top-left');
        engine.on('load', () => {
          if (!vector) return;
          const style = engine.getStyle();
          const building = style.layers.find(layer => layer['source-layer'] === 'building');
          const labels = style.layers.find(layer => layer.type === 'symbol');
          if (building && !style.layers.some(layer => layer.type === 'fill-extrusion')) {
            engine.addLayer({id: 'meeting-buildings-3d', type: 'fill-extrusion', source: building.source,
              'source-layer': 'building', minzoom: 14,
              paint: {'fill-extrusion-color': '#c6d3cb',
                'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 5],
                'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
                'fill-extrusion-opacity': 0.85}}, labels?.id);
          }
          element.dataset.mapReady = 'true';
        });
        engine.on('error', () => {
          if (!vector) return;
          if (!engine.isStyleLoaded()) {
            // Defer removal until MapLibre finishes dispatching the failed request.
            setTimeout(() => { if (vector && !removed) fallback('Peta 3D gagal dimuat. Menampilkan peta 2D.'); }, 0);
          } else onError?.('Sebagian peta belum termuat. Periksa koneksi internet.');
        });
        engine.on('click', e => {
          if (locked) return;
          const feature = engine.queryRenderedFeatures(e.point).find(f => f.layer.type === 'symbol' && (f.properties?.name || f.properties?.['name:latin']));
          onPick?.(e.lngLat.lat, e.lngLat.lng, feature?.properties?.name || feature?.properties?.['name:latin']);
        });
        engine.on('pitchend', label);
        label();
      }
    } catch (error) { fallback('Perangkat ini menampilkan peta 2D. Pencarian tempat tetap tersedia.'); }
    const observer = new ResizeObserver(() => { if (vector) engine.resize(); else engine?.invalidateSize(); });
    observer.observe(element);
    modeButton?.addEventListener('click', () => { if (vector) engine.easeTo({pitch: engine.getPitch() > 0 ? 0 : 50}); });
    element._meetingMap = api;
    return api;
  };
})();
