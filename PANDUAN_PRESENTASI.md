# Panduan Presentasi KendaraGo

Dokumen ini adalah catatan singkat untuk menjelaskan kode dan perintah yang
dipakai dalam proyek. Gunakan sebagai panduan memahami program, bukan sekadar
teks untuk dihafalkan.

## Demo peta sederhana (sekitar 30 detik)

1. Buka formulir pemesanan, lalu klik titik temu di peta atau tekan **Gunakan lokasi saya**.
2. Isi **Nama tempat / titik temu**. Tambahkan patokan jika perlu, lalu centang **Titik temu sudah sesuai**.
3. Biarkan **Kembalikan kendaraan di tempat yang sama** tercentang dan buat pesanan.
4. Pada detail pesanan, tunjukkan tombol **Buka di Google Maps** untuk membantu menuju lokasi.

Contoh penjelasan:

> "Peta ini membantu pelanggan dan petugas bertemu di lokasi yang sama. Pelanggan
> cukup memilih titik, memberi nama tempat, dan mengonfirmasi. Lokasinya tersimpan
> bersama pesanan dan bisa dibuka di Google Maps."

Desa, kecamatan, kode pos, dan koordinat tidak perlu diketik pada alur utama.
Koordinat manual tersedia jika diperlukan. Pencarian tempat hanya ditampilkan
jika layanan pencarian sudah dikonfigurasi. Titik tetap diperiksa agar berada di Bali.
Kode utama ada di `templates/components/location_editor.html`,
`static/js/locations.js`, dan `services/location_service.py`.

## Presentasi dashboard admin: kode dahulu, baru tampilan

Mulai dari `app.py`, kemudian fokus pada satu fitur dashboard. Gunakan urutan
berikut agar hubungan kode dengan hasilnya jelas. Durasi sekitar 4–5 menit.

| Urutan | Kode yang dibuka | Penjelasan dan hasil yang ditunjukkan |
|---|---|---|
| 1 | `app.py`: `create_app()` dan `app.register_blueprint(admin_bp)` | Flask menyiapkan aplikasi dan mendaftarkan modul admin. |
| 2 | `routes/admin.py`: `bp`, `guard()`, dan `dashboard()` | Prefix `/admin` dan route `/` membentuk URL `/admin/`. Login dan peran admin diperiksa sebelum halaman dibuka. |
| 3 | `models/entities.py`: `class Vehicle`, lalu `stats` di `routes/admin.py` | Model mewakili tabel kendaraan. `count()` menghitung total data; `filter_by(status="Tersedia", is_active=True)` menghitung kendaraan aktif yang tersedia. Hasilnya menjadi angka kartu statistik. |
| 4 | `revenue`, `recent`, dan `render_template(...)` di `routes/admin.py` | Pendapatan menjumlahkan pembayaran berstatus `Diverifikasi` sejak awal bulan. Transaksi diurutkan dari terbaru dan dibatasi delapan. Ketiga data dikirim sebagai `stats`, `revenue`, dan `recent`. |
| 5 | `templates/admin/dashboard.html`: `extends`, `block content`, dan `include` | Template memakai kerangka `base.html`, mengisi konten, dan menyertakan menu `components/dashboard_nav.html`. Tunjukkan header serta menu pada browser. |
| 6 | Loop `{% for label,key,icon ... %}` dan `{{ stats[key] }}` | Satu loop menghasilkan delapan kartu statistik. `{{ ... }}` menampilkan nilai; `{% ... %}` menjalankan logika template. Tunjukkan angka kartu di browser. |
| 7 | Loop `{% for item in recent %}` dan bagian `revenue` | Setiap transaksi menjadi satu baris tabel. Bagian `else` menampilkan pesan saat belum ada transaksi. Nilai pendapatan tampil di panel kanan. |
| 8 | `<canvas id="statusChart">`, lalu `static/js/admin-dashboard.js` | Flask menulis angka ke atribut `data-*`. JavaScript membaca `dataset`, mengubahnya menjadi angka dengan `Number()`, lalu Chart.js menggambar grafik donat. Grafik menunjukkan status kendaraan, bukan pendapatan. |
| 9 | `static/css/app.css`: `.dashboard-shell`, `.stat-card`, `.dashboard-panel` | CSS mengatur tata letak, kartu, dan panel. Bootstrap menyediakan grid seperti `col-sm-6` dan `col-xl-3` agar jumlah kolom menyesuaikan lebar layar. |

Alur yang perlu dipahami:

```text
Browser meminta /admin/
  -> Flask memeriksa login dan peran admin
  -> route mengambil data database melalui model SQLAlchemy
  -> render_template mengirim data ke template Jinja
  -> HTML dan CSS membentuk halaman
  -> JavaScript membaca data dan menggambar grafik
```

Contoh kalimat saat menjelaskan:

> "Saya mulai dari fungsi dashboard di routes/admin.py. Fungsi ini menghitung
> kendaraan melalui model Vehicle, lalu menyimpan hasilnya dalam stats.
> Data dikirim ke dashboard.html menggunakan render_template. Di template,
> stats[key] menampilkan angka pada kartu. Sekarang saya buka browser untuk
> menunjukkan hasil kode tersebut, yaitu kartu Total kendaraan dan Tersedia."

Sebelum demo, nyalakan MySQL XAMPP lalu jalankan
`.\venv\Scripts\python.exe app.py` dari folder proyek. Buka
`http://127.0.0.1:5000/auth/login`, masuk menggunakan akun admin yang sudah
dimiliki, lalu buka `http://127.0.0.1:5000/admin/`. Template harus dibuka melalui
Flask agar Jinja diproses. Jika browser masih memakai JavaScript lama, tekan
`Ctrl+F5`. Tidak perlu menjalankan seed atau migrasi untuk perbaikan grafik ini.

## Ringkasan aplikasi

KendaraGo adalah sistem penyewaan mobil dan sepeda motor berbasis Flask.
Pengguna dibagi menjadi tiga peran:

- **Pelanggan** mengelola profil, memesan kendaraan, membayar, dan memberi ulasan.
- **Petugas** menangani pemeriksaan pengambilan dan pengembalian kendaraan.
- **Admin** mengelola armada, memverifikasi pelanggan dan pembayaran, serta
  mengekspor laporan.

Data disimpan di MySQL melalui SQLAlchemy ORM. Tampilan dibuat dengan Jinja,
Bootstrap, CSS, dan JavaScript.

## Arti perintah instalasi dan menjalankan aplikasi

```powershell
py -m venv venv
```

Membuat *virtual environment* bernama `venv`. Tujuannya agar paket Python proyek
terpisah dari paket milik sistem atau proyek lain.

```powershell
.\venv\Scripts\Activate.ps1
```

Mengaktifkan virtual environment di PowerShell. Setelah aktif, perintah
`python` dan `pip` memakai interpreter serta paket dari folder `venv`.

```powershell
python -m pip install -r requirements.txt
```

Memasang seluruh dependensi yang tercatat di `requirements.txt`. Bentuk
`python -m pip` memastikan `pip` yang digunakan berasal dari Python yang aktif.

```powershell
python seed.py
```

Menjalankan data awal (*seeding*), misalnya akun demo, kategori, lokasi, dan
kendaraan. Seed dibuat idempoten agar tidak menggandakan data yang sudah ada.

```powershell
python app.py
```

Menjalankan Flask development server di `http://127.0.0.1:5000`. Pada
`app.py`, blok `if __name__ == "__main__"` memastikan server hanya dijalankan
ketika file tersebut dieksekusi langsung.

```powershell
$env:FLASK_APP = "app.py"
flask db migrate -m "deskripsi perubahan"
flask db upgrade
```

Perintah pertama memberitahu Flask letak aplikasi. `migrate` membuat rancangan
perubahan skema berdasarkan model, sedangkan `upgrade` menerapkannya ke database.

## Susunan kode

| Bagian | Tanggung jawab |
|---|---|
| `app.py` | Membuat aplikasi, memasang extension, dan mendaftarkan Blueprint. |
| `config.py` | Membaca `.env` dan menyimpan konfigurasi aplikasi. |
| `extensions.py` | Menyediakan objek database, login, CSRF, migrasi, dan rate limit. |
| `models/` | Memetakan class Python ke tabel dan relasi database. |
| `routes/` | Menerima request HTTP, memvalidasi input, dan mengembalikan response. |
| `services/` | Menyimpan logika bisnis yang dapat dipakai oleh beberapa route. |
| `utils/` | Menyediakan validasi, keamanan, decorator role, dan upload file. |
| `templates/` | Membentuk halaman HTML dengan Jinja. |
| `static/` | Menyimpan CSS, JavaScript, gambar, dan library antarmuka. |

Pemisahan ini menerapkan prinsip *separation of concerns*: route tidak perlu
menangani seluruh perhitungan sendiri, dan logika bisnis lebih mudah diuji serta
digunakan ulang.

## Lokasi folder fitur dan assets

Tidak ada satu folder bernama `features/` atau `assets/` dalam proyek ini.
Kode setiap fitur terbagi menjadi penerima permintaan di `routes/`, proses bisnis
di `services/`, tampilan di `templates/`, dan data di `models/`. Assets publik
berada di `static/`.

| Fitur | Kode penerima permintaan | Tampilan halaman | Proses pendukung |
|---|---|---|---|
| Beranda, pencarian, filter, katalog, detail, dan informasi | `routes/public.py` | `templates/public/` | `services/availability_service.py` |
| Formulir sewa menuju WhatsApp | `routes/public.py` fungsi `rental_request` | `templates/public/rental_form.html` | Fungsi `build_whatsapp_message` dalam route publik |
| Login, registrasi, logout, dan ubah password | `routes/auth.py` | `templates/auth/` | `models/user.py`, `utils/security.py`, `utils/validators.py` |
| Profil, pemesanan, pembayaran, pembatalan, ulasan, dan invoice pelanggan | `routes/customer.py` | `templates/customer/` | `services/rental_service.py`, `services/payment_service.py`, `services/report_service.py` |
| Armada, impor CSV, verifikasi pelanggan dan pembayaran, serta laporan admin | `routes/admin.py` | `templates/admin/` | `services/payment_service.py`, `services/report_service.py` |
| Pemeriksaan pengambilan dan pengembalian kendaraan | `routes/staff.py` | `templates/staff/` | `services/rental_service.py` |
| Unduhan dokumen, bukti bayar, dan foto pemeriksaan | `routes/files.py` | Ditautkan dari halaman sesuai peran | `utils/file_handler.py` |
| Ketersediaan kendaraan dan pengemudi | Dipanggil route publik, pelanggan, dan admin | Pilihan jadwal pada katalog dan pemesanan | `services/availability_service.py` |
| Pembuatan notifikasi | Dipanggil dari proses terkait | Menu akun dan dashboard pelanggan | `services/notification_service.py` |

### Isi folder assets

| Lokasi | Isi dan kegunaan |
|---|---|
| `static/css/app.css` | Gaya utama: warna dasar, tombol, navigasi, katalog, dashboard, dan responsivitas. |
| `static/css/enhancements.css` | Gaya tambahan untuk kategori, langkah menyewa, testimoni, banner, dan touring. |
| `static/js/app.js` | Interaksi header, menu ponsel, animasi, toast, kalender, konfirmasi, dan pratinjau gambar. |
| `static/vendor/` | Library lokal Bootstrap, Bootstrap Icons, Flatpickr, SweetAlert2, dan Chart.js. |
| `static/uploads/vehicles/` | Foto kendaraan; `catalog/` memuat foto katalog dan `user/` menampung unggahan kendaraan. |
| `static/favicon.svg` | Ikon situs yang ditampilkan pada tab browser. |
| `templates/base.html` | Kerangka halaman yang memuat CSS dan JavaScript melalui `url_for('static', filename=...)`. |

Dokumen identitas, foto profil, bukti pembayaran, dan foto pemeriksaan yang
diunggah oleh aplikasi disimpan di `instance/private_uploads/`, sesuai pengaturan
`PRIVATE_UPLOAD_FOLDER` dalam `config.py`. Aksesnya melalui `routes/files.py`.
Folder kosong `static/uploads/documents/`, `profiles/`, `payments/`, dan
`inspections/` bukan acuan lokasi penyimpanan unggahan privat aplikasi saat ini.

### Cara membaca komentar pembatas

Nomor komentar adalah urutan bagian dalam file tersebut. Judul menjelaskan
nama bagian, lalu kalimat di bawahnya menjelaskan tujuan kode yang mengikuti.
Contoh pada CSS dan JavaScript:

```css
/* ==========================================================
   01. WARNA DAN UKURAN DASAR
   Variabel di sini menjadi acuan warna, radius, bayangan, dan animasi.
   ========================================================== */
```

Pada Python formatnya memakai `#` pada setiap baris, sedangkan pada template
Jinja memakai `{# ... #}` agar penjelasannya tidak tampil pada halaman web.
Komentar pembatas tersedia pada route fitur, layanan bisnis, CSS, JavaScript,
dan kerangka halaman `templates/base.html`.

Untuk menjelaskan sebuah fitur, mulai dari halaman di `templates/`, lanjutkan
ke fungsi penerimanya di `routes/`, lalu tunjukkan proses di `services/` dan
struktur data di `models/`. Contoh pembayaran: `templates/customer/rental_detail.html`
→ fungsi `pay` di `routes/customer.py` → `services/payment_service.py`
→ `models/payment.py`.

## Urutan menunjukkan kode formulir dan pembayaran

Gunakan nomor pada komentar pembatas sebagai urutan presentasi. Tidak perlu
menjelaskan setiap baris; jelaskan tujuan satu bagian, input yang diterima, lalu
hasil yang dikeluarkan.

### Formulir sewa tanpa login

1. Buka `templates/public/rental_form.html`, mulai dari **01. Header Halaman**.
2. Lanjutkan ke **02. Ringkasan Kendaraan** untuk menjelaskan data unit terpilih.
3. Tunjukkan **03. Formulir Penyewaan**, dari identitas sampai persetujuan.
4. Tunjukkan **04. Interaksi Pilihan Pengemudi** untuk menjelaskan pergantian
   kolom SIM dan pengemudi.
5. Buka `routes/public.py` bagian **04. Formulir Penyewaan Ringkas**. Urutan
   `04A` sampai `04H` mengikuti perjalanan data dari form menuju WhatsApp.

### Pembayaran pelanggan

1. Buka `templates/customer/rental_detail.html` bagian **02. Ringkasan Pesanan
   dan Biaya**.
2. Lanjutkan ke **03. Formulir Pembayaran** dan tunjukkan dropdown metode.
3. Tunjukkan **05. Interaksi Metode Pembayaran** untuk menjelaskan mengapa bukti
   pembayaran hanya muncul pada metode tertentu.
4. Buka `routes/customer.py` bagian **05. Proses Pembayaran**. Urutan `05A`
   sampai `05D` menjelaskan validasi hingga penyimpanan.
5. Akhiri di `services/payment_service.py`: daftar metode, validasi, penyimpanan,
   lalu verifikasi admin tersusun sebagai bagian `01` sampai `04`.

### Tampilan

Buka `static/css/app.css` dari **01. Warna dan Ukuran Dasar**. Untuk formulir,
langsung menuju **07. Detail Kendaraan dan Formulir Sewa**, kemudian **07A.
Pembayaran**. Bagian **11. Tampilan Responsif** menjelaskan penyesuaian layar
tablet dan telepon genggam.

## Alur saat halaman dibuka

1. Browser mengirim HTTP request ke URL aplikasi.
2. Flask mencocokkan URL dengan decorator `@bp.route(...)`.
3. Decorator login/role memeriksa izin pengguna jika halaman dilindungi.
4. Fungsi route membaca input dan memanggil model atau service yang diperlukan.
5. SQLAlchemy menjalankan query ke database.
6. Route mengembalikan HTML, redirect, PDF, Excel, atau pesan error.
7. `after_request` menambahkan header keamanan sebelum response sampai ke browser.

## Alur pemesanan kendaraan

1. Pelanggan memilih kendaraan dan tanggal.
2. `vehicle_is_available()` memeriksa bentrok sewa serta perawatan.
3. `calculate_price()` menghitung jumlah hari, sewa kendaraan, sopir, promo,
   deposit, dan total.
4. `create_rental()` memvalidasi profil dan kendaraan, lalu membuat kode booking.
5. Harga disimpan sebagai *snapshot* pada pesanan supaya perubahan harga armada
   tidak mengubah transaksi lama.
6. Sistem membuat status log dan notifikasi, kemudian melakukan `db.session.commit()`.

## Istilah dan sintaks yang sering ditanyakan

### Blueprint

Blueprint mengelompokkan route. Contohnya, Blueprint admin memakai prefix
`/admin`, sehingga halaman admin terpisah jelas dari halaman pelanggan.

### Decorator

Sintaks `@bp.route(...)`, `@login_required`, dan `@roles_required(...)` disebut
decorator. Decorator menambahkan perilaku pada fungsi tanpa menyalin kode yang
sama ke setiap fungsi.

### ORM dan model

SQLAlchemy ORM memungkinkan tabel direpresentasikan sebagai class. Contoh:
`Vehicle.query.get(...)` mencari data kendaraan, sedangkan `db.session.add(...)`
menandai objek agar disimpan. `db.session.commit()` mengesahkan transaksi.

### Relationship, primary key, dan foreign key

- *Primary key* seperti `id` adalah identitas unik suatu baris.
- *Foreign key* menghubungkan baris dengan tabel lain, misalnya pesanan ke kendaraan.
- `db.relationship()` memudahkan akses hubungan itu sebagai objek Python.

### Request dan response

`request` berisi data yang masuk dari browser. `render_template()` menghasilkan
HTML, `redirect()` mengarahkan ke URL lain, `flash()` menyiapkan pesan singkat,
dan `abort()` menghentikan proses dengan kode error HTTP.

### GET dan POST

GET dipakai untuk mengambil atau menampilkan data. POST dipakai untuk tindakan
yang mengubah data, misalnya login, membuat pesanan, atau verifikasi pembayaran.
Form POST dilindungi token CSRF.

### Hash password

Password tidak disimpan sebagai teks asli. `generate_password_hash()` membuat
hash satu arah, dan `check_password_hash()` membandingkan input login dengan hash
tersebut tanpa membuka password asli.

### Environment variable

Nilai sensitif atau berbeda antar-komputer diletakkan di `.env`, misalnya
`SECRET_KEY` dan `DATABASE_URL`. `.env` tidak boleh dibagikan ke repository;
`.env.example` hanya berisi contoh nama variabel.

### Commit, flush, dan rollback

- `flush()` mengirim perubahan sementara agar ID baru tersedia, tetapi transaksi
  masih dapat dibatalkan.
- `commit()` menyimpan semua perubahan transaksi secara permanen.
- `rollback()` membatalkan transaksi yang gagal agar sesi database kembali bersih.

### Keamanan yang digunakan

- CSRF melindungi form dari request palsu yang memakai sesi korban.
- Rate limit membatasi percobaan login atau request berlebihan.
- CSP dan header keamanan membatasi sumber script serta perilaku browser.
- Validasi upload memeriksa ukuran, ekstensi, isi gambar/PDF, dan lokasi file.
- Pemeriksaan role mencegah pelanggan membuka fungsi admin atau petugas.

## Pertanyaan singkat yang mungkin muncul

**Mengapa memakai Flask?**  
Flask ringan dan fleksibel. Struktur Blueprint, service, dan model dapat disusun
sesuai kebutuhan tanpa membawa komponen yang tidak diperlukan.

**Mengapa memakai service terpisah dari route?**  
Agar aturan harga, ketersediaan, pembayaran, dan laporan tidak bercampur dengan
urusan HTTP. Kode menjadi lebih mudah dirawat dan digunakan ulang.

**Mengapa memakai MySQL dan SQLAlchemy?**  
MySQL menyimpan data relasional secara konsisten, sedangkan SQLAlchemy mengurangi
SQL manual dan menyediakan relasi serta transaksi melalui objek Python.

**Apa fungsi `create_app()`?**  
Fungsi tersebut adalah *application factory*: membuat instance Flask, memuat
konfigurasi, memasang extension, mendaftarkan Blueprint, dan error handler.

**Mengapa dokumen pelanggan tidak disimpan di folder publik?**  
KTP, SIM, bukti pembayaran, dan foto pemeriksaan bersifat privat. File hanya
dikirim setelah route memeriksa pemilik atau role pengguna.

**Apa beda autentikasi dan otorisasi?**  
Autentikasi memastikan siapa pengguna melalui login. Otorisasi memastikan fitur
apa yang boleh dibuka pengguna berdasarkan role dan kepemilikan data.
