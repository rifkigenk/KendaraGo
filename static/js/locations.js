/* Bali meeting-point editor. All server writes validate the polygon again. */
(() => {
  const config = document.getElementById('location-config');
  const keys = ['place_name', 'street', 'building_number', 'village', 'district', 'city', 'province', 'postcode', 'latitude', 'longitude', 'instructions'];
  const pinIcon = () => L.divIcon({className: 'meeting-pin', html: '<span aria-hidden="true">●</span>', iconSize: [28, 28], iconAnchor: [14, 14]});
  function addTiles(map, message) {
    if (config?.dataset.tiles !== 'true') {
      if (message) message.textContent = 'Peta dasar dinonaktifkan. Isi koordinat manual.';
      return;
    }
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
    }).on('tileerror', () => {
      if (message) message.textContent = 'Peta gagal dimuat. Alamat dan koordinat tetap dapat diisi manual.';
    }).addTo(map);
  }
  window.initSavedMaps = (root = document) => {
    if (!window.L) return;
    root.querySelectorAll('[data-saved-map]').forEach(el => {
      if (el._meetingMap) return;
      const map = L.map(el, {scrollWheelZoom: false}).setView([Number(el.dataset.lat), Number(el.dataset.lon)], 15);
      el._meetingMap = map;
      addTiles(map);
      L.marker(map.getCenter(), {icon: pinIcon()}).addTo(map);
    });
  };
  const editors = [];
  document.querySelectorAll('[data-location-editor]').forEach(root => {
    const field = key => root.querySelector(`[data-field="${key}"]`);
    const confirm = root.querySelector('[data-confirm-location]');
    const message = root.querySelector('[data-location-message]');
    const officeSelect = root.querySelector('[data-office]');
    const admin = root.dataset.admin === 'true';
    const search = root.querySelector('[data-search]');
    const results = root.querySelector('[data-results]');
    let officeVersion = '', offices = [], map, marker, revision = 0, timer, controller;
    function value() {
      const data = Object.fromEntries(keys.map(k => [k, field(k).value.trim()]));
      data.kind = field('kind').value;
      data.confirmed = confirm.checked;
      data.office_id = officeSelect?.value ? Number(officeSelect.value) : null;
      data.office_updated_at = officeVersion;
      return data;
    }
    function preview() {
      const v = value();
      const address = [v.place_name, [v.street, v.building_number].filter(Boolean).join(' '), v.village, v.district, v.city, v.province, v.postcode].filter(Boolean).join(', ');
      root.querySelector('[data-preview]').textContent = `${address}\nPin: ${v.latitude || 'belum dipilih'}, ${v.longitude || 'belum dipilih'}\n${v.instructions}`;
    }
    function invalidate() { confirm.checked = false; revision++; preview(); }
    function isOffice() { return !admin && field('kind').value === 'office'; }
    function mark(lat, lon, center = true) {
      if (!map || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
      if (!marker) {
        marker = L.marker([lat, lon], {draggable: !isOffice(), icon: pinIcon()}).addTo(map);
        marker.on('dragend', () => {
          const point = marker.getLatLng(); setPoint(point.lat, point.lng, false);
          message.textContent = 'Pin berubah. Periksa kembali alamat dan konfirmasi titik temu.';
        });
      } else marker.setLatLng([lat, lon]);
      if (isOffice()) marker.dragging.disable(); else marker.dragging.enable();
      if (center) map.setView([lat, lon], 16);
    }
    function setPoint(lat, lon, center = true) {
      field('latitude').value = Number(lat).toFixed(7);
      field('longitude').value = Number(lon).toFixed(7);
      mark(Number(lat), Number(lon), center); invalidate();
    }
    function apply(data = {}) {
      keys.forEach(k => { field(k).value = data[k] ?? (k === 'province' ? 'Bali' : ''); });
      if (data.kind) field('kind').value = data.kind;
      if (officeSelect) officeSelect.value = data.office_id || '';
      officeVersion = data.office_updated_at || '';
      toggle();
      if (data.latitude !== undefined && data.longitude !== undefined) mark(Number(data.latitude), Number(data.longitude));
      else if (marker) { marker.remove(); marker = null; }
      invalidate();
    }
    function toggle() {
      const locked = isOffice();
      root.querySelector('[data-office-wrap]')?.toggleAttribute('hidden', !locked);
      root.querySelector('[data-search-wrap]').hidden = locked;
      root.querySelector('[data-geolocate]').disabled = locked;
      keys.forEach(k => { field(k).readOnly = k === 'province' || (locked && k !== 'instructions'); });
      if (officeSelect) officeSelect.required = locked;
      if (marker) { if (locked) marker.dragging.disable(); else marker.dragging.enable(); }
    }
    root.querySelectorAll('[data-field]').forEach(el => el.addEventListener('input', () => {
      invalidate();
      if (['latitude', 'longitude'].includes(el.dataset.field) && field('latitude').value && field('longitude').value) mark(Number(field('latitude').value), Number(field('longitude').value));
    }));
    field('kind').addEventListener('change', () => {
      const kind = field('kind').value; apply({kind}); results.replaceChildren();
    });
    officeSelect?.addEventListener('change', () => {
      const office = offices.find(o => o.id === Number(officeSelect.value));
      if (office) apply({...office.address, kind: 'office', office_id: office.id, office_updated_at: office.updated_at});
      else apply({kind: 'office'});
    });
    if (officeSelect) fetch(config.dataset.offices, {cache: 'no-store'}).then(r => {
      if (!r.ok) throw new Error(); return r.json();
    }).then(data => {
      offices = data.offices;
      offices.forEach(o => { const option = document.createElement('option'); option.value = o.id; option.textContent = o.name; officeSelect.append(option); });
      const initial = JSON.parse(root.dataset.initial || 'null');
      if (initial?.office_id && revision === 1) officeSelect.value = initial.office_id;
      root.querySelector('[data-office-empty]').textContent = offices.length ? 'Alamat dan pin dikelola oleh admin.' : 'Belum ada kantor terkonfirmasi. Pilih alamat lain di Bali.';
    }).catch(() => { message.textContent = 'Daftar kantor gagal dimuat. Coba muat ulang.'; });
    if (window.L) {
      map = L.map(root.querySelector('[data-map]'), {scrollWheelZoom: false}).setView([-8.45, 115.15], 9);
      addTiles(map, message);
      map.on('click', event => { if (!isOffice()) setPoint(event.latlng.lat, event.latlng.lng, false); });
      new ResizeObserver(() => map.invalidateSize()).observe(root);
    } else message.textContent = 'Peta tidak tersedia. Isi alamat dan koordinat manual.';
    async function geocode(params, signal) {
      const response = await fetch(`${config.dataset.search}?${new URLSearchParams(params)}`, {signal, cache: 'no-store'});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Sesi berakhir. Masuk kembali untuk mencari alamat.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Pencarian gagal. Isi alamat manual.');
      return data.results;
    }
    if (config?.dataset.searchEnabled !== 'true') message.textContent = 'Pencarian alamat belum terhubung. Isi alamat dan tentukan pin secara manual.';
    search.addEventListener('input', () => {
      clearTimeout(timer); controller?.abort(); results.replaceChildren(); invalidate();
      const q = search.value.trim();
      if (q.length < 3) return;
      const rev = revision;
      timer = setTimeout(async () => {
        controller = new AbortController();
        message.textContent = 'Mencari alamat…';
        try {
          const found = await geocode({q}, controller.signal);
          if (rev !== revision) return;
          found.forEach(item => {
            const button = document.createElement('button'); button.type = 'button'; button.className = 'list-group-item list-group-item-action';
            button.textContent = item.formatted;
            button.addEventListener('click', () => {
              apply({...item, kind: field('kind').value}); results.replaceChildren();
              message.textContent = 'Periksa alamat hasil pencarian, lengkapi bagian yang kosong, dan konfirmasi pin.';
            }); results.append(button);
          });
          message.textContent = found.length ? 'Pilih hasil pencarian. Detail yang tidak diketahui dibiarkan kosong.' : 'Tidak ditemukan di Bali. Coba nama lain atau isi alamat manual.';
        } catch (error) { if (error.name !== 'AbortError') message.textContent = error.message; }
      }, 450);
    });
    root.querySelector('[data-geolocate]').addEventListener('click', () => {
      if (!navigator.geolocation) { message.textContent = 'Perangkat tidak mendukung lokasi. Isi alamat dan pin manual.'; return; }
      message.textContent = 'Meminta izin lokasi perangkat…';
      const rev = revision;
      navigator.geolocation.getCurrentPosition(async position => {
        if (revision !== rev) return;
        if (position.coords.accuracy > 100) { message.textContent = `Lokasi kurang akurat (±${Math.round(position.coords.accuracy)} m). Tentukan pin secara manual.`; return; }
        setPoint(position.coords.latitude, position.coords.longitude);
        const nextRev = revision;
        message.textContent = `Akurasi perangkat ±${Math.round(position.coords.accuracy)} m. Periksa titik temu sebelum konfirmasi.`;
        try {
          const found = await geocode({latitude: position.coords.latitude, longitude: position.coords.longitude});
          if (revision === nextRev && found[0]) apply({...found[0], latitude: position.coords.latitude, longitude: position.coords.longitude, kind: field('kind').value});
        } catch (error) { if (revision === nextRev) message.textContent = error.message; }
      }, () => { message.textContent = 'Izin ditolak atau lokasi tidak tersedia. Isi alamat dan pilih pin secara manual.'; }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 0});
    });
    const editor = {value, apply, root, validate: () => {
      if (!confirm.checked) { message.textContent = 'Konfirmasi alamat dan pin terlebih dahulu.'; confirm.focus(); return false; }
      return [...root.querySelectorAll('input,select,textarea')].every(el => el.disabled || el.reportValidity());
    }};
    root.locationEditor = editor; editors.push(editor); toggle(); preview();
    const initial = JSON.parse(root.dataset.initial || 'null');
    if (initial) apply(initial);
  });
  const same = document.querySelector('[data-same-location]');
  if (same) {
    const returnRoot = document.querySelector('[data-prefix="return"]');
    const toggle = () => {
      returnRoot.hidden = same.checked;
      returnRoot.querySelectorAll('input,select,textarea,button').forEach(el => { el.disabled = same.checked; });
    };
    same.addEventListener('change', toggle); toggle();
  }
  const bookingForm = document.querySelector('[data-booking-form]');
  bookingForm?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!editors[0].validate() || (!same.checked && !editors[1].validate())) return;
    const message = bookingForm.querySelector('[data-save-message]');
    const button = bookingForm.querySelector('[type="submit"]');
    button.disabled = true; message.textContent = 'Menyimpan pesanan…';
    const body = new FormData(bookingForm);
    body.set('pickup_address', JSON.stringify(editors[0].value()));
    body.set('return_address', JSON.stringify(same.checked ? editors[0].value() : editors[1].value()));
    try {
      const response = await fetch(bookingForm.action, {method: 'POST', body, signal: AbortSignal.timeout(20000)});
      if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sesi atau token formulir berakhir. Masuk kembali lalu periksa Pesanan saya sebelum mencoba ulang.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Pesanan gagal disimpan.');
      message.textContent = 'Pesanan berhasil disimpan.'; window.location.assign(data.url);
    } catch (error) { message.textContent = navigator.onLine ? `Gagal menyimpan: ${error.message} Anda dapat mencoba ulang; kunci pesanan tetap sama.` : 'Koneksi terputus. Coba ulang setelah tersambung; kunci pesanan tetap sama.'; button.disabled = false; }
  });
  const editForm = document.querySelector('[data-location-update]');
  editForm?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!editors[0].validate() || (!same.checked && !editors[1].validate())) return;
    const message = editForm.querySelector('[data-save-message]'), button = editForm.querySelector('[type="submit"]');
    button.disabled = true; message.textContent = 'Menyimpan perubahan…';
    const payload = {version: editForm.dataset.version, pickup_address: editors[0].value(),
      return_address: editors[1].value(), same_location: same.checked, notes: editForm.elements.notes.value};
    try {
      const response = await fetch(editForm.action, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': editForm.elements.csrf_token.value},
        body: JSON.stringify(payload), signal: AbortSignal.timeout(20000)});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Gagal menyimpan.');
      message.textContent = data.message; window.location.assign(editForm.dataset.returnUrl);
    } catch (error) { message.textContent = `Gagal menyimpan: ${error.message} Periksa detail pesanan jika koneksi terputus saat menyimpan.`; button.disabled = false; }
  });
  const officeForm = document.querySelector('[data-office-form]');
  if (officeForm) {
    let id = null, version = null;
    document.querySelectorAll('[data-edit-office]').forEach(button => button.addEventListener('click', () => {
      const data = JSON.parse(button.dataset.editOffice); id = data.id; version = data.version;
      editors[0].apply(data.address || {kind: 'office', place_name: data.name});
      officeForm.querySelector('[name="active"]').checked = data.active;
      officeForm.scrollIntoView({behavior: 'smooth'});
    }));
    officeForm.querySelector('[data-new-office]').addEventListener('click', () => { id = null; version = null; editors[0].apply({kind: 'office'}); });
    officeForm.addEventListener('submit', async event => {
      event.preventDefault(); if (!editors[0].validate()) return;
      const message = officeForm.querySelector('[data-save-message]'), button = officeForm.querySelector('[type="submit"]');
      button.disabled = true; message.textContent = 'Menyimpan kantor…';
      try {
        const response = await fetch(officeForm.action, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': officeForm.elements.csrf_token.value},
          body: JSON.stringify({id, version, address: editors[0].value(), active: officeForm.elements.active.checked}), signal: AbortSignal.timeout(20000)});
        const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Gagal menyimpan kantor.');
        message.textContent = data.message; window.location.reload();
      } catch (error) { message.textContent = `Gagal menyimpan: ${error.message}`; button.disabled = false; }
    });
  }
  window.initSavedMaps();
})();
