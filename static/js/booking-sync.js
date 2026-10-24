/* No geolocation here: only committed order data is synchronized. */
(() => {
  async function read(url, options = {}) {
    const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(12000), ...options});
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sesi berakhir atau server tidak tersedia. Masuk kembali.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Sinkronisasi gagal.');
    return data;
  }
  function poll(root, update) {
    let busy = false;
    const message = root.querySelector('[data-sync-message]');
    async function tick() {
      if (busy || document.hidden) return;
      busy = true;
      try { await update(); message.textContent = `Tersinkron · ${new Date().toLocaleTimeString('id-ID')} · pembaruan otomatis setiap 3 detik`; }
      catch (error) { message.textContent = `Koneksi terputus / sinkronisasi gagal. ${error.message} Mencoba kembali otomatis.`; }
      finally { busy = false; }
    }
    setInterval(tick, 3000); window.addEventListener('online', tick);
    window.addEventListener('offline', () => { message.textContent = 'Koneksi terputus. Data terakhir tetap ditampilkan.'; });
    document.addEventListener('visibilitychange', tick); tick(); return tick;
  }
  document.querySelectorAll('[data-booking-feed]').forEach(root => {
    let revision;
    poll(root, async () => {
      const data = await read(root.dataset.bookingFeed);
      if (data.revision !== revision) { root.querySelector('[data-booking-list]').innerHTML = data.html; revision = data.revision; }
    });
  });
  document.querySelectorAll('[data-booking-detail]').forEach(root => {
    let version = root.dataset.version;
    const form = root.querySelector('[data-status-form]');
    const refresh = poll(root, async () => {
      const data = await read(root.dataset.bookingDetail);
      root.querySelectorAll('[data-live-status]').forEach(el => { el.textContent = data.status; });
      const payment = root.querySelector('.payment-panel');
      if (payment && data.status !== 'Menunggu pembayaran') payment.hidden = true;
      if (version !== data.updated_at) {
        root.querySelectorAll('[data-saved-map]').forEach(el => el._meetingMap?.remove());
        root.querySelector('[data-live-locations]').innerHTML = data.html;
        window.initSavedMaps?.(root);
        version = data.updated_at; root.dataset.version = version;
        if (form) {
          const select = form.elements.status; select.replaceChildren(new Option('Pilih status', ''));
          data.transitions.forEach(status => select.add(new Option(status, status)));
        }
      }
    });
    form?.addEventListener('submit', async event => {
      event.preventDefault();
      const message = form.querySelector('[data-save-message]'), button = form.querySelector('button');
      if (!form.elements.status.value) { message.textContent = 'Pilih status terlebih dahulu.'; return; }
      const payload = {status: form.elements.status.value, version};
      button.disabled = true; message.textContent = 'Menyimpan status…';
      try {
        const data = await read(form.action, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrf_token.value}, body: JSON.stringify(payload)});
        message.textContent = data.message; await refresh();
      } catch (error) { message.textContent = `Gagal menyimpan: ${error.message}`; }
      finally { button.disabled = false; }
    });
  });
})();
