$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Lingkungan Python belum tersedia. Ikuti langkah instalasi di README.md.'
}

Push-Location $PSScriptRoot
try {
    Write-Host 'Memperbarui skema database KendaraGo...'
    & $pythonPath -m flask --app app db upgrade
    if ($LASTEXITCODE -ne 0) {
        throw 'Migrasi gagal. Pastikan MySQL XAMPP aktif dan koneksi .env benar. Server belum dijalankan.'
    }

    Write-Host 'Buka http://localhost:5000'
    & $pythonPath app.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Server berhenti karena error. Periksa pesan di atas.'
    }
}
finally {
    Pop-Location
}
