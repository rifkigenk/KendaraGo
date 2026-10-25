/* Bali meeting-point editor. All server writes validate the polygon again. */
(() => {
  const config = document.getElementById('location-config');
  const keys = ['place_name', 'street', 'building_number', 'village', 'district', 'city', 'province', 'postcode', 'latitude', 'longitude', 'instructions'];
  window.initSavedMaps = (root = document) => {
    root.querySelectorAll('[data-saved-map]').forEach(el => {
      if (el._meetingMap) return;
      const map = window.createMeetingMap(el, {center: [Number(el.dataset.lon), Number(el.dataset.lat)], zoom: 16});
      map.setLocked(true); map.setPoint(Number(el.dataset.lat), Number(el.dataset.lon), false);
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
    const manual = root.querySelector('[data-manual]');
    const searchEnabled = config?.dataset.searchEnabled === 'true';
    let officeVersion = '', offices = [], map, revision = 0, timer, controller;
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
      root.querySelector('[data-preview]').textContent = v.latitude && v.longitude
        ? 'Titik sudah dipilih. Pastikan pin berada di tempat pertemuan.'
        : 'Belum ada titik yang dipilih.';
    }
    function invalidate() { confirm.checked = false; revision++; preview(); }
    function isOffice() { return !admin && field('kind').value === 'office'; }
    function clearAddressDetails() {
      ['street', 'building_number', 'village', 'district', 'city', 'postcode'].forEach(k => { field(k).value = ''; });
    }
    function mark(lat, lon, center = true) {
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
      map?.setPoint(lat, lon, center);
    }
    function setPoint(lat, lon, center = true) {
      clearAddressDetails();
      field('latitude').value = Number(lat).toFixed(7);
      field('longitude').value = Number(lon).toFixed(7);
      mark(Number(lat), Number(lon), center); invalidate();
      message.textContent = 'Titik dipilih. Isi nama tempat, lalu konfirmasi.';
    }
    function apply(data = {}) {
      keys.forEach(k => { field(k).value = data[k] ?? (k === 'province' ? 'Bali' : ''); });
      if (data.kind) field('kind').value = data.kind === 'office' ? 'office' : 'other';
      if (officeSelect) officeSelect.value = data.office_id || '';
      officeVersion = data.office_updated_at || '';
      search.value = '';
      toggle();
      if (data.latitude !== undefined && data.longitude !== undefined) mark(Number(data.latitude), Number(data.longitude));
      else map?.clearPin();
      invalidate();
    }
    function toggle() {
      const locked = isOffice();
      root.querySelector('[data-map-hint]').textContent = locked ? 'Titik kantor ditentukan oleh rental.' : 'Klik peta untuk memilih titik temu.';
      root.querySelector('[data-office-wrap]')?.toggleAttribute('hidden', !locked);
      root.querySelector('[data-search-wrap]').hidden = locked || !searchEnabled;
      root.querySelector('[data-geolocate]').hidden = locked;
      root.querySelector('[data-geolocate]').disabled = locked;
      manual.hidden = locked;
      keys.forEach(k => { field(k).readOnly = k === 'province' || (locked && k !== 'instructions'); });
      if (officeSelect) officeSelect.required = locked;
      map?.setLocked(locked);
    }
    root.querySelectorAll('[data-field]').forEach(el => el.addEventListener('input', () => {
      if (['latitude', 'longitude'].includes(el.dataset.field)) clearAddressDetails();
      invalidate();
      if (['latitude', 'longitude'].includes(el.dataset.field) && field('latitude').value && field('longitude').value) mark(Number(field('latitude').value), Number(field('longitude').value));
      else if (['latitude', 'longitude'].includes(el.dataset.field)) map?.clearPin();
    }));
    root.addEventListener('invalid', event => {
      if (manual.contains(event.target)) manual.open = true;
    }, true);
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
    map = window.createMeetingMap(root.querySelector('[data-map]'), {
      modeButton: root.querySelector('[data-map-3d]'),
      onPick: (lat, lon, name) => {
        if (isOffice()) return;
        if (name) field('place_name').value = name;
        setPoint(lat, lon, false);
      },
      onError: text => { message.textContent = text; }
    });
    async function geocode(params, signal) {
      const response = await fetch(`${config.dataset.search}?${new URLSearchParams(params)}`, {signal, cache: 'no-store'});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Pencarian belum dapat dihubungi. Coba lagi.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Pencarian gagal. Isi alamat manual.');
      return data.results;
    }
    function searchPlaces() {
      if (!searchEnabled) return;
      clearTimeout(timer); controller?.abort(); results.replaceChildren(); invalidate();
      const q = search.value.trim();
      if (q.length < 3) { message.textContent = 'Ketik nama tempat minimal 3 karakter.'; return; }
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
              apply({...item, instructions: field('instructions').value, kind: field('kind').value}); results.replaceChildren();
              message.textContent = 'Titik ditemukan. Periksa pin, lalu konfirmasi.';
            }); results.append(button);
          });
          message.textContent = found.length ? 'Pilih tempat dari hasil pencarian.' : 'Tidak ditemukan di Bali. Pilih titik langsung di peta.';
        } catch (error) { if (error.name !== 'AbortError') message.textContent = error.message; }
      }, 0);
    }
    search.addEventListener('input', () => { clearTimeout(timer); controller?.abort(); results.replaceChildren(); invalidate(); });
    root.querySelector('[data-search-button]').addEventListener('click', searchPlaces);
    search.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); searchPlaces(); } });
    root.querySelector('[data-geolocate]').addEventListener('click', () => {
      if (!navigator.geolocation) { message.textContent = 'Perangkat tidak mendukung lokasi. Isi alamat dan pin manual.'; return; }
      message.textContent = 'Meminta izin lokasi perangkat…';
      const rev = revision;
      navigator.geolocation.getCurrentPosition(position => {
        if (revision !== rev) return;
        if (position.coords.accuracy > 100) { message.textContent = `Lokasi kurang akurat (±${Math.round(position.coords.accuracy)} m). Tentukan pin secara manual.`; return; }
        setPoint(position.coords.latitude, position.coords.longitude);
        message.textContent = 'Lokasi ditemukan. Isi nama tempat dan periksa pin sebelum konfirmasi.';
      }, () => { if (revision === rev) message.textContent = 'Lokasi tidak tersedia. Pilih titik di peta atau isi koordinat manual.'; }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 0});
    });
    const editor = {value, apply, root, validate: () => {
      if (!field('latitude').value || !field('longitude').value) {
        message.textContent = 'Pilih titik di peta atau gunakan lokasi saya terlebih dahulu.';
        manual.open = true;
        field('latitude').focus();
        return false;
      }
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
  bookingForm?.addEventListener('submit', event => {
    if (!editors[0].validate() || (!same.checked && !editors[1].validate())) {
      event.preventDefault(); return;
    }
    bookingForm.elements.pickup_address.value = JSON.stringify(editors[0].value());
    bookingForm.elements.return_address.value = JSON.stringify(same.checked ? editors[0].value() : editors[1].value());
    bookingForm.querySelector('[data-save-message]').textContent = 'Menyimpan pesanan…';
    bookingForm.querySelector('[type="submit"]').disabled = true;
    // Native same-origin POST: success redirects only after the database commit.
  });
  window.addEventListener('pageshow', () => {
    const button = bookingForm?.querySelector('[type="submit"]');
    if (button) button.disabled = false;
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
