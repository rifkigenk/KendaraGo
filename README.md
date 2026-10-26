# KendaraGo

Sistem informasi penyewaan mobil dan sepeda motor berbasis Flask dan MySQL. Aplikasi memakai pola application factory, Blueprint per peran, SQLAlchemy ORM, autentikasi Flask-Login, dan CSRF protection.

> Untuk persiapan menjelaskan kode dan perintah saat demo, baca
> [`PANDUAN_PRESENTASI.md`](PANDUAN_PRESENTASI.md).

Integrasi WhatsApp Meta: lihat [PANDUAN_WHATSAPP.md](PANDUAN_WHATSAPP.md).

## Fitur yang tersedia

- Halaman publik, katalog kendaraan, pencarian, filter, sorting, pagination, dan detail kendaraan.
- Registrasi, login multi-role, ingat saya, logout, proteksi role, profil, dokumen, dan perubahan password.
- Pemeriksaan bentrok jadwal kendaraan/perawatan dan pengemudi.
- Pemesanan dengan snapshot harga, pengemudi, promo, deposit, status, dan audit log.
- Preferensi pembayaran melalui transfer bank, QRIS, dompet digital, EDC, atau tunai; termasuk unggah bukti dan verifikasi admin.
- Checklist pengambilan/pengembalian, kilometer, kondisi, foto, denda, dan perubahan status armada.
- Dashboard dan navigasi kerja khusus untuk pelanggan, petugas, dan admin.
- Aset antarmuka utama disimpan lokal agar layout tetap stabil tanpa bergantung pada CDN.
- Invoice PDF, ekspor laporan Excel, notifikasi dalam aplikasi, ulasan, dan halaman error.
- Skema 22 tabel MySQL serta seed 74 armada bergambar; 40 kendaraan harian hingga Rp900.000/hari ditampilkan di katalog publik.
- Setiap model aktif memakai foto tersendiri, fasilitas mobil/motor dipisahkan, dan armada premium global tetap tersedia sebagai data arsip admin.
- Katalog kendaraan populer untuk layanan sewa di kawasan Bali, dengan titik layanan di Denpasar, Kuta, Ubud, Canggu, Sanur, dan Bandara Ngurah Rai.

## Instalasi Windows (XAMPP)

1. Buka XAMPP Control Panel lalu jalankan **Apache** (opsional untuk phpMyAdmin) dan **MySQL**.
2. Buat database kosong bernama `db_kendarago` melalui phpMyAdmin.
3. Salin `.env.example` menjadi `.env`, buat dua secret acak yang berbeda, lalu sesuaikan koneksi MySQL.
4. Dari PowerShell di folder proyek jalankan migration dan seed:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(32))"
python -m flask --app app db upgrade
python seed.py
python app.py
```

Jika PowerShell menolak aktivasi:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Untuk Command Prompt:

```cmd
py -m venv venv
venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m flask --app app db upgrade
python seed.py
python app.py
```

Buka `http://127.0.0.1:5000`.

> Pada komputer ini, `venv`, seluruh dependensi, database, dan data awal sudah dibuat. Pastikan MySQL XAMPP aktif lalu jalankan `powershell -ExecutionPolicy Bypass -File .\start.ps1`. Script menerapkan migrasi yang belum dijalankan sebelum membuka server di `http://localhost:5000`.

Jika semua halaman menampilkan error 500 setelah kode diperbarui, periksa log terminal.
Pesan `Unknown column 'rentals.guest_name'` berarti skema database belum mengikuti
fitur pesanan tamu. Jalankan `start.ps1`, atau jalankan migrasi secara manual sebelum server:

```powershell
.\venv\Scripts\python.exe -m flask --app app db upgrade
.\venv\Scripts\python.exe app.py
```

Cadangkan database sebelum migrasi. Jangan menghapus tabel atau mengimpor ulang
`database.sql` untuk mengatasi error ini; migrasi mempertahankan data yang sudah ada.

## Konfigurasi

```env
SECRET_KEY=hasil_acak_pertama
WTF_CSRF_SECRET_KEY=hasil_acak_kedua
DATABASE_URL=mysql+pymysql://root:@localhost/db_kendarago
APP_ENV=development
MAX_CONTENT_LENGTH=2097152
WHATSAPP_NUMBER=6282282026127
RATELIMIT_ENABLED=true
PAYMENT_DEADLINE_HOURS=2
```

Nomor WhatsApp harus memakai format internasional tanpa tanda `+`, misalnya `6282282026127`. Ukuran unggahan maksimal adalah 2 MB. `RATELIMIT_ENABLED` boleh diatur ke `false` hanya saat pengujian lokal. Untuk produksi, gunakan `APP_ENV=production`, HTTPS dan cookie aman, kredensial database khusus, penyimpanan rate limit bersama (bukan `memory://`), serta server WSGI produksi. Aplikasi akan menolak start jika konfigurasi produksi penting belum aman.

Contoh menjalankan server WSGI pada Windows setelah konfigurasi produksi siap:

```powershell
waitress-serve --listen=127.0.0.1:8000 wsgi:application
```

## Akun demo

Password di atas hanya kredensial masuk; database menyimpannya sebagai hash Werkzeug.

| Peran | Email | Password |
|---|---|---|
| Admin | `admin@kendarago.com` | `Admin123!` |
| Petugas | `petugas@kendarago.com` | `Petugas123!` |
| Pelanggan demo | `pelanggan@kendarago.com` | `Pelanggan123!` |
| Pelanggan lama (riwayat sewa selesai dan diskon loyalitas) | `pelanggan.lama@kendarago.com` | `PelangganLama123!` |

Permintaan dari formulir publik disimpan sebagai permintaan sewa dan ditampilkan
di Admin → Pemesanan. Pemilihan pengemudi terhubung dengan data pengemudi di
database. Pelanggan yang sudah memiliki penyewaan berstatus selesai mendapat
diskon loyalitas otomatis 10% sampai Rp150.000 untuk transaksi minimal Rp300.000.

## Sumber katalog kendaraan Indonesia

Daftar model Indonesia diperiksa pada 10 September 2026 berdasarkan katalog resmi pabrikan dan data pasar berikut:

- [Data penjualan model Juli 2026 dari GAIKINDO](https://www.gaikindo.or.id/mobil-niaga-gran-max-carry-l-300-masuk-20-besar-penjualan-juli-2026/)
- [Katalog Toyota Indonesia](https://www.toyota.astra.co.id/home)
- [Pembaruan model Honda Indonesia 2026](https://www.honda-indonesia.com/news/honda-hadir-di-iims-2026-dengan-penyegaran-relevan-dan-value-lebih-kompetitif-untuk-memperkuat-kepercayaan-konsumen)
- [Katalog Daihatsu Indonesia](https://daihatsu.co.id/)
- [Daftar harga Suzuki Indonesia 2026](https://www.suzuki.co.id/pricelist)
- [Dokumen model Mitsubishi Indonesia 2026](https://microsite.mitsubishi-motors.co.id/digital-document/)
- [Daftar harga BYD Indonesia 2026](https://prod.byd.com/id/pricelist)
- [Jajaran Yamaha Indonesia di IIMS 2026](https://www.yamaha-motor.co.id/archives/news/product/2026/02/yamaha-gebrak-iims-2026-tampilkan-model-terbaru-dan-rayakan-70-tahun-perjalanan-global/)

## Struktur utama

```text
KendaraGo/
├── app.py                 # application factory dan registrasi Blueprint
├── config.py              # konfigurasi environment, database, sesi, upload
├── extensions.py          # SQLAlchemy, Login, CSRF, dan Migrate
├── database.sql           # skema MySQL siap impor
├── seed.py                # akun dan data awal
├── enrich_seed.py         # katalog, gambar, transaksi, pembayaran tambahan
├── global_touring_seed.py # katalog touring dunia dan data teknis
├── requirements.txt       # dependensi Python terkunci
├── models/                # 21 model/tabel dan relasi
├── routes/                # public, auth, customer, staff, admin
├── services/              # availability, rental, payment, report, notification
├── utils/                 # role guard, validasi, upload aman
├── templates/             # template Jinja per area
└── static/                # CSS, JavaScript, vendor lokal, dan folder upload
```

## Pemeliharaan database

Migration awal sudah disertakan. Saat model berubah, buat revision baru lalu upgrade:

```powershell
python -m flask --app app db migrate -m "deskripsi perubahan"
python -m flask --app app db upgrade
```

Jangan menjalankan `seed.py` untuk menghapus data. Seed bersifat idempoten: jika akun admin sudah ada, script berhenti tanpa menggandakan data.

Pesanan yang melewati tenggat pembayaran ditutup otomatis saat aplikasi menerima
request. Untuk deployment produksi, perintah berikut juga dapat dijalankan berkala:

```powershell
python -m flask --app app expire-rentals
```

## Pengujian

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
