# Panduan penjelasan kode KendaraGo

Komentar bagian memakai judul bernomor, keterangan singkat berbahasa Indonesia,
dan pembatas `==========================================================`.
Python dan konfigurasi memakai `#`, template memakai komentar Jinja `{# ... #}`,
CSS/JavaScript memakai `/* ... */`, SQL memakai `--`, dan SVG memakai `<!-- ... -->`.
Komentar Jinja tidak dikirim sebagai isi halaman kepada pengguna.
Fungsi yang belum mempunyai docstring diberi komentar tujuan sebelum definisinya.

## Alur aplikasi

`app.py` membuat Flask, memuat `config.py`, menghubungkan extension, lalu
mendaftarkan blueprint. Route menerima request dan memanggil service untuk
aturan bisnis. Model SQLAlchemy memetakan data ke tabel. Template Jinja
menyajikan hasil menggunakan CSS dan JavaScript lokal.

`migrations/env.py` menghubungkan metadata model dengan Alembic. Revisi dalam
`migrations/versions/` menyimpan langkah perubahan skema dan pembalikannya.
`seed.py`, `enrich_seed.py`, dan `global_touring_seed.py` mengisi data demo;
`fetch_vehicle_images.py` mengambil foto beserta atribusi sumber.

## Daftar kode dan konfigurasi aplikasi

Daftar ini mencakup berkas aplikasi yang dilacak Git, termasuk konfigurasi
bertitik dan workflow dalam `.github`. Penjelasan terperinci tetap berada dekat
kode yang dijelaskan.

| Berkas | Tanggung jawab |
| --- | --- |
| [.editorconfig](.editorconfig) | Menetapkan UTF-8, akhir baris LF, indentasi, dan pembersihan spasi untuk editor. |
| [.env.example](.env.example) | Salin ke .env lalu sesuaikan secret, koneksi database, batas unggahan, dan keamanan. |
| [.github/workflows/tests.yml](.github/workflows/tests.yml) | Menjalankan pemeriksaan format Python dan pytest pada setiap push serta pull request. |
| [.gitignore](.gitignore) | Mengecualikan secret, lingkungan Python, cache, database lokal, dan unggahan pengguna. |
| [app.py](app.py) | Titik masuk aplikasi dan tempat seluruh komponen Flask dirangkai. |
| [config.py](config.py) | Konfigurasi aplikasi yang nilainya dapat diubah melalui berkas `.env`. |
| [database.sql](database.sql) | Menyiapkan sesi impor lalu membuat ulang tabel beserta data dump. |
| [enrich_seed.py](enrich_seed.py) | Penambahan katalog dan transaksi demo. Aman dijalankan berulang kali. |
| [extensions.py](extensions.py) | Objek extension Flask yang dipakai bersama oleh seluruh modul aplikasi. |
| [fetch_vehicle_images.py](fetch_vehicle_images.py) | Download model-specific vehicle photos from Wikimedia Commons. |
| [global_touring_seed.py](global_touring_seed.py) | Katalog motor touring global dengan sumber spesifikasi pabrikan resmi. |
| [migrations/alembic.ini](migrations/alembic.ini) | Mengatur logger Alembic; URL database diperoleh dari aplikasi melalui env.py. |
| [migrations/env.py](migrations/env.py) | Menghubungkan metadata Flask-SQLAlchemy dengan migrasi SQL offline atau koneksi online. |
| [migrations/script.py.mako](migrations/script.py.mako) | Mako mengisi identitas revisi serta operasi upgrade dan downgrade saat revisi dibuat. |
| [migrations/versions/3a0cc36b4214_initial_schema.py](migrations/versions/3a0cc36b4214_initial_schema.py) | initial schema |
| [migrations/versions/420ec1b3d2f7_add_rental_payment_deadline.py](migrations/versions/420ec1b3d2f7_add_rental_payment_deadline.py) | add rental payment deadline |
| [models/__init__.py](models/__init__.py) | Menyediakan model dari entities melalui satu jalur impor untuk route dan service. |
| [models/entities.py](models/entities.py) | Model SQLAlchemy yang memetakan objek Python ke tabel database KendaraGo. |
| [models/maintenance.py](models/maintenance.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/notification.py](models/notification.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/payment.py](models/payment.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/promotion.py](models/promotion.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/rental.py](models/rental.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/return_vehicle.py](models/return_vehicle.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/user.py](models/user.py) | Menyediakan alias model dari entities agar impor melalui modul ini tetap kompatibel. |
| [models/vehicle.py](models/vehicle.py) | Ekspor model kendaraan agar impor lama tetap kompatibel. |
| [pyproject.toml](pyproject.toml) | Menyamakan format Black dan djLint serta menentukan folder pengujian pytest. |
| [requirements-dev.txt](requirements-dev.txt) | Menambahkan formatter, pengujian, dan laporan cakupan di atas dependensi aplikasi. |
| [requirements.txt](requirements.txt) | Memasang Flask, akses database, keamanan, pengolahan gambar, laporan, dan server WSGI. |
| [routes/__init__.py](routes/__init__.py) | Menandai paket endpoint; masing-masing blueprint didaftarkan oleh create_app. |
| [routes/admin.py](routes/admin.py) | Route admin untuk armada, verifikasi, pembayaran, dan laporan. |
| [routes/auth.py](routes/auth.py) | Route autentikasi: login, registrasi, logout, dan perubahan password. |
| [routes/customer.py](routes/customer.py) | Route pelanggan untuk profil, pesanan, pembayaran, dan ulasan. |
| [routes/files.py](routes/files.py) | Route berkas privat dengan pemeriksaan hak akses sebelum file dikirim. |
| [routes/public.py](routes/public.py) | Route publik untuk beranda, katalog, detail, dan formulir pemesanan. |
| [routes/staff.py](routes/staff.py) | Route petugas untuk proses serah-terima dan pemeriksaan kendaraan. |
| [seed.py](seed.py) | Membuat akun demo, armada, lokasi, promo, dan transaksi contoh dalam konteks Flask. |
| [services/__init__.py](services/__init__.py) | Mengelompokkan layanan ketersediaan, sewa, pembayaran, notifikasi, dan laporan. |
| [services/availability_service.py](services/availability_service.py) | Logika untuk mendeteksi bentrok jadwal kendaraan dan pengemudi. |
| [services/notification_service.py](services/notification_service.py) | Layanan kecil untuk membuat notifikasi pengguna secara konsisten. |
| [services/payment_service.py](services/payment_service.py) | Logika bisnis pembuatan dan verifikasi pembayaran penyewaan. |
| [services/rental_service.py](services/rental_service.py) | Logika bisnis inti untuk menghitung harga dan mengelola penyewaan. |
| [services/report_service.py](services/report_service.py) | Pembuat laporan Excel dan invoice PDF dari data penyewaan. |
| [static/css/app.css](static/css/app.css) | Variabel di sini menjadi acuan warna, radius, bayangan, dan animasi. |
| [static/css/enhancements.css](static/css/enhancements.css) | Mengatur susunan kategori, ikon, teks, dan efek saat kursor diarahkan. |
| [static/favicon.svg](static/favicon.svg) | Ikon lokasi KendaraGo dalam format vektor SVG. |
| [static/js/app.js](static/js/app.js) | Interaksi dijalankan setelah elemen HTML selesai dimuat oleh browser. |
| [templates/admin/dashboard.html](templates/admin/dashboard.html) | Menampilkan ringkasan operasional, grafik, dan aktivitas penyewaan untuk admin. |
| [templates/admin/import_vehicles.html](templates/admin/import_vehicles.html) | Menyediakan formulir unggah data kendaraan dan tautan template impor. |
| [templates/admin/payments.html](templates/admin/payments.html) | Menampilkan bukti pembayaran serta formulir verifikasi pembayaran oleh admin. |
| [templates/admin/rentals.html](templates/admin/rentals.html) | Menampilkan daftar penyewaan, filter, dan akses ekspor laporan. |
| [templates/admin/vehicle_form.html](templates/admin/vehicle_form.html) | Mengisi identitas, tarif, fasilitas, lokasi, dan foto kendaraan untuk disimpan. |
| [templates/admin/vehicles.html](templates/admin/vehicles.html) | Menampilkan inventaris kendaraan beserta akses tambah, edit, dan status aktif. |
| [templates/admin/verifications.html](templates/admin/verifications.html) | Menampilkan dokumen pelanggan dan tindakan persetujuan atau penolakan verifikasi. |
| [templates/auth/change_password.html](templates/auth/change_password.html) | Mengirim password lama, password baru, dan konfirmasi melalui formulir ber-CSRF. |
| [templates/auth/login.html](templates/auth/login.html) | Menyediakan formulir masuk dan tautan registrasi akun pelanggan. |
| [templates/auth/register.html](templates/auth/register.html) | Mengumpulkan identitas akun dan konfirmasi password untuk pendaftaran pelanggan. |
| [templates/base.html](templates/base.html) | Komentar bagian di dalam berkas menjelaskan susunan dan tanggung jawab kode. |
| [templates/components/dashboard_nav.html](templates/components/dashboard_nav.html) | Menampilkan menu dashboard sesuai peran pengguna yang sedang masuk. |
| [templates/customer/book.html](templates/customer/book.html) | Mengumpulkan jadwal, lokasi, pengemudi, dan promo untuk pemesanan kendaraan. |
| [templates/customer/dashboard.html](templates/customer/dashboard.html) | Menampilkan ringkasan akun, pesanan, dan notifikasi pelanggan. |
| [templates/customer/profile.html](templates/customer/profile.html) | Mengelola identitas pelanggan dan unggahan dokumen untuk verifikasi. |
| [templates/customer/rental_detail.html](templates/customer/rental_detail.html) | Komentar bagian di dalam berkas menjelaskan susunan dan tanggung jawab kode. |
| [templates/errors/error.html](templates/errors/error.html) | Menampilkan pesan kesalahan sesuai kode HTTP serta tautan kembali. |
| [templates/public/_vehicle_card.html](templates/public/_vehicle_card.html) | Komponen kartu kendaraan yang dipakai ulang untuk foto, spesifikasi, tarif, dan detail. |
| [templates/public/content.html](templates/public/content.html) | Menampilkan judul dan isi halaman informasi yang diberikan oleh route publik. |
| [templates/public/home.html](templates/public/home.html) | Menyusun beranda dengan pencarian kendaraan, kategori, armada, dan informasi layanan. |
| [templates/public/rental_form.html](templates/public/rental_form.html) | Komentar bagian di dalam berkas menjelaskan susunan dan tanggung jawab kode. |
| [templates/public/touring_catalog.html](templates/public/touring_catalog.html) | Menampilkan katalog motor touring dengan filter dan informasi spesifikasi. |
| [templates/public/vehicle_detail.html](templates/public/vehicle_detail.html) | Menampilkan galeri, spesifikasi, fasilitas, ulasan, dan akses pemesanan kendaraan. |
| [templates/public/vehicles.html](templates/public/vehicles.html) | Menampilkan filter pencarian, hasil katalog kendaraan, dan navigasi halaman. |
| [templates/staff/dashboard.html](templates/staff/dashboard.html) | Menampilkan antrean operasional untuk serah-terima dan pengembalian kendaraan. |
| [templates/staff/inspection.html](templates/staff/inspection.html) | Mencatat hasil pemeriksaan, kondisi, dan foto saat serah-terima atau pengembalian. |
| [tests/conftest.py](tests/conftest.py) | Menyiapkan aplikasi uji dengan database sementara dan membersihkan tabel setelah setiap tes. |
| [tests/test_rental_flow.py](tests/test_rental_flow.py) | Memeriksa bentrok jadwal, pembatalan, pelepasan kuota promo, tenggat, dan kode pesanan. |
| [tests/test_security_and_pages.py](tests/test_security_and_pages.py) | Memeriksa penyamaran identitas, secret, formula Excel, halaman publik, dan gambar cadangan. |
| [utils/__init__.py](utils/__init__.py) | Mengelompokkan validasi input, pembatasan akses, keamanan, dan pengolahan unggahan. |
| [utils/decorators.py](utils/decorators.py) | Decorator untuk membatasi endpoint berdasarkan role pengguna. |
| [utils/file_handler.py](utils/file_handler.py) | Validasi dan penyimpanan aman untuk gambar serta dokumen PDF. |
| [utils/security.py](utils/security.py) | Konfigurasi keamanan HTTP, CSP, fingerprint, dan redirect internal. |
| [utils/validators.py](utils/validators.py) | Validator terpusat agar aturan input konsisten di semua formulir. |
| [wsgi.py](wsgi.py) | Entry point untuk server WSGI produksi. |

## Folder tersembunyi, lokal, dan hasil proses

| Lokasi | Isi dan perlakuan |
| --- | --- |
| `.github/workflows/tests.yml` | Pipeline instalasi dependensi, pemeriksaan format seluruh Python proyek, dan pytest. Komentar ditambahkan langsung. |
| `.editorconfig` | Aturan indentasi dan akhir baris untuk editor. |
| `.env.example` | Contoh nama variabel konfigurasi; dapat disalin untuk lingkungan lokal. |
| `.env` | Nilai konfigurasi lokal yang dibaca `config.py`; nilai rahasia tidak disalin ke panduan dan tidak diubah. |
| `.gitignore` | Pola pengecualian Git untuk secret, cache, lingkungan Python, dan data lokal. |
| `.git/` | Metadata Git: objek riwayat, referensi branch, indeks, log, konfigurasi, dan contoh hook. Dikelola Git; bukan kode aplikasi. |
| `.pytest_cache/` | Cache hasil dan identitas pengujian yang dibuat ulang oleh pytest. |
| `.coverage` | Data biner hasil pengukuran cakupan kode oleh coverage.py. |
| `__pycache__/` di setiap paket | Bytecode Python yang dibuat ulang interpreter. |
| `venv/` | Interpreter, launcher, dan paket pihak ketiga untuk lingkungan Python lokal. |
| `instance/` | Penyimpanan lokal aplikasi, termasuk unggahan privat; bukan sumber kode. |
| `migration_*.db` | Database SQLite lokal untuk pekerjaan migrasi; bukan berkas kode untuk diformat. |
| `static/uploads/**/.gitkeep` | Penanda agar folder unggahan kosong tetap dilacak Git. |

Folder metadata, cache, lingkungan virtual, dan data biner tidak diberi komentar
langsung atau diformat ulang karena formatnya dikelola alat pembuatnya.

## Aset dan dependensi pihak ketiga

| Lokasi | Peran |
| --- | --- |
| `static/vendor/bootstrap/` | CSS tata letak dan komponen JavaScript seperti menu yang dapat dibuka/tutup. |
| `static/vendor/bootstrap-icons/` | CSS ikon serta font WOFF/WOFF2. |
| `static/vendor/chartjs/` | Pustaka untuk grafik pada dashboard. |
| `static/vendor/flatpickr/` | CSS dan JavaScript pemilih tanggal. |
| `static/vendor/sweetalert2/` | Pustaka dialog dan pemberitahuan toast. |
| `static/uploads/vehicles/` | Gambar kendaraan lokal dan gambar cadangan. |
| `static/uploads/vehicles/catalog/sources.json` | Catatan sumber, pencarian, dan lisensi foto katalog; JSON tidak menerima komentar. |
| `static/uploads/vehicles/user/` | Foto kendaraan hasil unggahan melalui aplikasi. |
| `static/uploads/documents/`, `inspections/`, `payments/`, `profiles/` | Folder unggahan yang dilacak melalui penanda; lokasi penyimpanan aktual ditentukan konfigurasi dan layanan unggahan. |

Berkas vendor terkompresi dipertahankan sebagai distribusi asli. Gambar dan font
merupakan aset biner. Penjelasannya disediakan di sini, bukan disisipkan ke isinya.
`README.md` memuat petunjuk menjalankan aplikasi, `PANDUAN_PRESENTASI.md` memuat
panduan presentasi, dan `migrations/README` menjelaskan lingkungan migrasi.

## Pemeriksaan setelah perubahan

Jalankan dari root proyek dengan lingkungan virtual aktif:

```powershell
python -m black --check .
python -m djlint templates --check
python -m pytest -q
```

Black mengikuti pengecualian `venv`, cache, dan unggahan pada `pyproject.toml`.
Tes memakai konfigurasi pengujian dan database SQLite sementara.
