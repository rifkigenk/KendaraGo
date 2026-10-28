# ==========================================================
# 01. MENJALANKAN SERVER LOKAL
# Memeriksa Python virtual, menerapkan migrasi, lalu menjalankan aplikasi Flask.
# ==========================================================

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Lingkungan Python belum tersedia. Ikuti langkah instalasi di README.md.'
}

# ==========================================================
# 02. MIGRASI SEBELUM SERVER BERJALAN
# Berpindah ke folder proyek dan menghentikan proses jika migrasi database gagal.
# ==========================================================
Push-Location $PSScriptRoot
try {
    Write-Host 'Memperbarui skema database KendaraGo...'
    & $pythonPath -m flask --app app db upgrade
    if ($LASTEXITCODE -ne 0) {
        throw 'Migrasi gagal. Pastikan MySQL XAMPP aktif dan koneksi .env benar. Server belum dijalankan.'
    }

    # ==========================================================
    # 03. MENJALANKAN APLIKASI FLASK
    # Memulai server dengan Python virtual dan menampilkan kegagalan proses bila terjadi.
    # ==========================================================
    Write-Host 'Buka http://localhost:5000'
    & $pythonPath app.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Server berhenti karena error. Periksa pesan di atas.'
    }
}
# ==========================================================
# 04. MENGEMBALIKAN DIREKTORI TERMINAL
# Memulihkan folder kerja awal setelah proses selesai atau mengalami kesalahan.
# ==========================================================
finally {
    Pop-Location
}
