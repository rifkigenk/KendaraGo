# WhatsApp KendaraGo

Nomor layanan: **082282026127**, format internasional **6282282026127**.
Tautan chat sudah memakai nomor ini. Bot Meta tetap nonaktif sampai konfigurasi diisi.
Nomor telepon saja tidak memberikan akses API atau mendaftarkan nomor ke Meta.

## Aktivasi

1. Buat aplikasi Meta dengan WhatsApp Business Platform, siapkan akun bisnis dan daftarkan nomor layanan sesuai petunjuk dashboard Meta. Pastikan Anda bisa menerima verifikasi nomor. Untuk percobaan, gunakan nomor uji Meta; sesuaikan WHATSAPP_NUMBER dengan nomor uji selama percobaan.
2. Jalankan migrasi: `.\venv\Scripts\python.exe -m flask --app app db upgrade`.
3. Isi `.env` (jangan commit atau kirim token ke chat):

```dotenv
WHATSAPP_NUMBER=6282282026127
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=token_dengan_izin_pengiriman_whatsapp
WHATSAPP_PHONE_NUMBER_ID=id_nomor_dari_dashboard_meta
WHATSAPP_APP_SECRET=app_secret_meta
WHATSAPP_VERIFY_TOKEN=nilai_acak_panjang_buatan_anda
WHATSAPP_API_VERSION=versi_graph_api_dari_dashboard_meta
WHATSAPP_PUBLIC_URL=https://domain-aplikasi-anda
WHATSAPP_TEMPLATE_NAME=kendarago_status_pesanan
WHATSAPP_TEMPLATE_LANGUAGE=id
```

`PHONE_NUMBER_ID` adalah ID Meta, bukan nomor 6282.... Versi API harus berbentuk `vNN.0`; isi versi yang masih didukung oleh Meta. Gunakan token operasional dengan izin yang sesuai, bukan token uji yang sudah kedaluwarsa.

4. Host aplikasi melalui HTTPS. Untuk lokal, arahkan tunnel HTTPS ke port 5000. Tambahkan hostname publik ke `TRUSTED_HOSTS` (pisahkan dengan koma) lalu restart Flask. Jangan membuka Flask debug ke internet.
5. Atur callback Meta ke `https://domain-aplikasi-anda/webhooks/whatsapp`, isi verify token yang sama, dan subscribe field `messages` serta akun WhatsApp yang sesuai.
6. Ajukan template kategori utility berbahasa Indonesia dengan **tiga parameter body** sesuai urutan berikut:

```text
Pembaruan pesanan KendaraGo {{1}}.
Status: {{2}}.
Total pesanan: {{3}}.
Silakan masuk ke akun KendaraGo untuk melihat detail.
```

Nama, bahasa, dan struktur template harus persis cocok dengan konfigurasi dan template yang disetujui Meta. Template dipakai untuk booking baru dan perubahan status, termasuk keputusan pembayaran. Pengiriman hanya untuk nomor profil pelanggan yang sudah mengirim MULAI dari WhatsApp mereka. Pastikan nomor profil benar.

7. Jalankan pengirim antrean:

```powershell
.\venv\Scripts\python.exe -m flask --app app whatsapp-send --limit 50
```

Jadwalkan perintah ini setiap menit melalui Windows Task Scheduler, dengan working directory folder KendaraGo. Program: path absolut `venv\Scripts\python.exe`; arguments: `-m flask --app app whatsapp-send --limit 50`. Tanpa scheduler, pesan masuk akan tersimpan tetapi balasan belum dikirim.

## Penggunaan

- Kirim `menu` atau sapaan untuk membuka menu.
- `1`: tautan katalog kendaraan.
- `2` / `STATUS`: tautan dashboard yang memerlukan login. Detail transaksi tidak dibuka lewat kode pesanan dalam chat.
- `3`: halaman kontak. Belum ada inbox petugas atau pengalihan percakapan langsung.
- `MULAI`: persetujuan notifikasi transaksi; `STOP`: berhenti. STOP juga membatalkan template yang masih mengantre ketika worker memprosesnya.

Tombol berlangganan muncul di dashboard pelanggan ketika integrasi aktif. Bot menu tidak menggunakan AI. Pengingat terjadwal pengambilan/pengembalian belum termasuk fitur ini.

## Operasional dan pemeriksaan

- Webhook memverifikasi HMAC SHA-256 dengan app secret. CSRF dikecualikan hanya untuk endpoint webhook. ID pesan unik mencegah pemrosesan webhook berulang.
- Outbox disimpan dalam transaksi database yang sama dengan perubahan rental. Jika booking dibatalkan oleh rollback, pesan juga tidak tersimpan.
- Balasan chat kedaluwarsa 23 jam setelah pesan pelanggan, untuk menjaga jarak dari batas jendela layanan Meta. Template kedaluwarsa setelah 24 jam dalam antrean.
- Tabel `whatsapp_outbox`: `pending` menunggu worker, `sending` sedang diklaim, `accepted` diterima API Meta, `failed` HTTP error, `unknown` hasil jaringan tidak pasti, `cancelled` kedaluwarsa atau persetujuan dicabut. `accepted` bukan bukti pesan sudah dibaca/diterima pelanggan; status delivery callback belum direkam.
- Tidak ada retry otomatis untuk menghindari pesan ganda setelah timeout. Periksa Meta sebelum menindaklanjuti `unknown` atau `sending` yang tertinggal karena worker berhenti. Perbaiki penyebab `failed` sebelum mengirim ulang secara manual. Token dan isi respons error Meta tidak ditulis ke log.
- Tarif mengikuti kategori dan negara penerima. Periksa https://business.whatsapp.com/products/platform-pricing sebelum operasional.
- Referensi implementasi Meta: https://github.com/fbsamples/whatsapp-api-examples dan https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/.

Pengujian lokal memakai API tiruan; pengiriman nyata perlu kredensial, nomor Meta, template, endpoint HTTPS, dan worker aktif.
