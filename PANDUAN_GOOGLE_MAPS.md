# Mengaktifkan Google Maps resmi di KendaraGo

Integrasi memakai **Google Maps JavaScript API**: tampilan awal 2D dan tombol
**Lihat 3D** untuk perspektif peta vektor Google. Detail bangunan bergantung pada
cakupan Google, tingkat zoom, dan kemampuan perangkat. Ini bukan tampilan
Photorealistic 3D atau Street View.

API key Google belum tersedia saat perubahan ini dibuat. Tanpa key, aplikasi
menampilkan peta 2D OpenStreetMap dan tautan **Buka Google Maps**. Tombol 3D
ditampilkan setelah Google dikonfigurasi. Jangan menganggap pengujian lokal
dengan respons tiruan sebagai verifikasi akun Google yang sesungguhnya.

## 1. Siapkan proyek Google Cloud

1. Buka [Google Cloud Console](https://console.cloud.google.com/), masuk dengan akunmu,
   lalu buat atau pilih proyek untuk KendaraGo.
2. Untuk API key standar, hubungkan akun billing milikmu. Tinjau penggunaan dan
   biaya di Google Cloud sebelum mengaktifkan layanan.
3. Buka **APIs & Services → Library**, cari **Maps JavaScript API**, lalu pilih **Enable**.
4. Buka **APIs & Services → Credentials → Create credentials → API key**.

Untuk prototipe, Google juga menyediakan Maps Demo Key dengan batasan tersendiri;
lihat [panduan resmi pengaturan key](https://developers.google.com/maps/documentation/javascript/get-api-key).

## 2. Batasi API key

Edit key dan pilih **Application restrictions → Websites**. Untuk komputer lokal,
tambahkan alamat berikut sebagai website referrer yang diizinkan:

```text
http://localhost:5000
http://localhost:5000/*
http://127.0.0.1:5000
http://127.0.0.1:5000/*
```

Di **API restrictions**, pilih **Restrict key → Maps JavaScript API**.
Saat website dipublikasikan, tambahkan origin HTTPS website sebenarnya.
Key JavaScript memang dikirim ke browser; pembatasan website dan API tetap wajib
dipasang. Jangan gunakan key server atau key tanpa pembatasan untuk ini.

## 3. Map ID untuk tampilan vektor

Untuk pengembangan lokal, `DEMO_MAP_ID` bisa digunakan. Untuk deployment sendiri,
buka **Google Maps Platform → Map Management**, buat Map ID dengan tipe
**JavaScript / Vector**, lalu gunakan ID tersebut. Aktifkan tilt/rotation pada
konfigurasi peta jika pengaturan tersebut tersedia.

Referensi: [peta vektor Google](https://developers.google.com/maps/documentation/javascript/vector-map).

## 4. Isi `.env` dan restart server

Di folder `D:\XAMPP\htdocs\KendaraGo`, edit `.env`:

```env
GOOGLE_MAPS_API_KEY=isi_key_google_milikmu
GOOGLE_MAPS_MAP_ID=DEMO_MAP_ID
MAP_TILES_ENABLED=true
```

Jangan menyalin teks `isi_key_google_milikmu` sebagai key. Jangan kirim key ke chat
atau memasukkan `.env` ke Git. Matikan server yang sedang berjalan, kemudian:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Buka formulir pemesanan, pilih titik, lalu coba **Lihat 3D**. Pin harus tetap berada
di lokasi yang dipilih saat kembali ke 2D. Uji juga halaman detail pesanan dan kantor.
Pengujian layanan Google langsung baru dapat diselesaikan setelah key ini diisi.

## 5. Jika Google menolak akses

- `RefererNotAllowedMapError`: periksa origin yang diizinkan pada pembatasan key.
- `ApiNotActivatedMapError`: aktifkan Maps JavaScript API pada proyek pemilik key.
- `BillingNotEnabledMapError`: periksa billing proyek untuk key standar.
- `InvalidKeyMapError`: periksa key, simpan `.env`, lalu restart aplikasi.
- Jika 3D dinonaktifkan, pastikan browser/perangkat mendukung WebGL dan Map ID menggunakan vektor.

Referensi: [pesan error Google Maps](https://developers.google.com/maps/documentation/javascript/error-messages)
dan [CSP Google Maps](https://developers.google.com/maps/documentation/javascript/content-security-policy).

## Kantor utama dan identitas penyewa

Admin → Kantor rental Bali hanya mengelola **satu kantor utama Denpasar**.
Isi nama/alamat kantor yang sebenarnya, pilih pin di Bali, centang konfirmasi,
lalu simpan. Menyebut kota Denpasar belum cukup untuk menentukan pin kantor;
lokasi contoh tidak otomatis dianggap terverifikasi. Lokasi lama tetap tersimpan
untuk menjaga relasi kendaraan dan riwayat pesanan, tetapi tidak menjadi daftar
kantor pemesanan baru.

Pemesanan baru wajib mengisi NIK / KTP, NISN, atau paspor. Paspor juga memerlukan
negara penerbit; nomor WhatsApp internasional dapat memakai format `+kode_negara`.
Identitas disimpan pada pesanan dan tampil lengkap hanya pada detail admin/petugas.
Nomornya disamarkan pada detail penyewa dan tidak dimasukkan ke feed pesanan umum.
Validasi format bukan verifikasi keaslian; petugas tetap mencocokkan dokumen asli.
Pesanan lama tanpa identitas diberi keterangan, tanpa mengarang data baru.
