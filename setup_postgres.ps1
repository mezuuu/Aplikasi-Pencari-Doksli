# setup_postgres.ps1
# Script untuk menginstall PostgreSQL dan membuat database image_detection
# Jalankan sebagai Administrator

param(
    [string]$PgPassword = "postgres123",
    [string]$DbName = "image_detection",
    [string]$PgVersion = "16"
)

Write-Host "=== Setup PostgreSQL untuk Sistem Deteksi Manipulasi Gambar ===" -ForegroundColor Cyan

# --- 1. Install PostgreSQL via winget ---
Write-Host "`n[1/4] Menginstall PostgreSQL $PgVersion..." -ForegroundColor Yellow

$pgInstaller = "postgresql-$PgVersion-windows-x64.exe"
$pgUrl = "https://sbp.enterprisedb.com/getfile.jsp?fileid=1259296"  # PostgreSQL 16 latest
$installerPath = "$env:TEMP\$pgInstaller"

# Cek apakah sudah terinstall
$pgFound = Get-Command psql -ErrorAction SilentlyContinue
if (-not $pgFound) {
    # Coba download installer langsung
    Write-Host "Mendownload PostgreSQL installer..." -ForegroundColor Gray
    
    # Coba via winget dengan versi berbeda
    $wingetResult = winget install --id PostgreSQL.PostgreSQL.16 --accept-source-agreements --accept-package-agreements 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget gagal. Silakan download PostgreSQL manual dari:" -ForegroundColor Red
        Write-Host "https://www.postgresql.org/download/windows/" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Setelah install, jalankan script ini lagi atau lanjutkan dari langkah 2." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "PostgreSQL sudah terinstall: $(psql --version)" -ForegroundColor Green
}

# --- 2. Temukan psql ---
Write-Host "`n[2/4] Mencari psql..." -ForegroundColor Yellow

$pgDirs = @(
    "C:\Program Files\PostgreSQL\16\bin",
    "C:\Program Files\PostgreSQL\15\bin",
    "C:\Program Files\PostgreSQL\14\bin",
    "C:\Program Files\PostgreSQL\17\bin"
)

$psqlPath = $null
foreach ($dir in $pgDirs) {
    if (Test-Path "$dir\psql.exe") {
        $psqlPath = "$dir\psql.exe"
        Write-Host "Ditemukan: $psqlPath" -ForegroundColor Green
        break
    }
}

if (-not $psqlPath) {
    Write-Host "psql tidak ditemukan di lokasi standar." -ForegroundColor Red
    Write-Host "Tambahkan bin folder PostgreSQL ke PATH, lalu jalankan script ini lagi." -ForegroundColor Yellow
    exit 1
}

# Tambahkan ke PATH sesi ini
$pgBinDir = Split-Path $psqlPath
$env:PATH = "$pgBinDir;$env:PATH"
$env:PGPASSWORD = $PgPassword

# --- 3. Buat database ---
Write-Host "`n[3/4] Membuat database '$DbName'..." -ForegroundColor Yellow

# Cek apakah database sudah ada
$dbExists = & $psqlPath -U postgres -lqt 2>&1 | Select-String $DbName
if ($dbExists) {
    Write-Host "Database '$DbName' sudah ada." -ForegroundColor Green
} else {
    & $psqlPath -U postgres -c "CREATE DATABASE $DbName ENCODING 'UTF8' LC_COLLATE 'Indonesian_Indonesia.1252' LC_CTYPE 'Indonesian_Indonesia.1252' TEMPLATE template0;" 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Coba tanpa locale khusus
        & $psqlPath -U postgres -c "CREATE DATABASE $DbName;"
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database '$DbName' berhasil dibuat." -ForegroundColor Green
    } else {
        Write-Host "Gagal membuat database. Coba jalankan manual:" -ForegroundColor Red
        Write-Host "  psql -U postgres -c `"CREATE DATABASE $DbName;`"" -ForegroundColor Gray
    }
}

# --- 4. Update .env dan jalankan migrations ---
Write-Host "`n[4/4] Mengupdate .env dan menjalankan Django migrations..." -ForegroundColor Yellow

$envFile = "$PSScriptRoot\backend\.env"
$envContent = Get-Content $envFile -Raw
$envContent = $envContent -replace "USE_POSTGRES=false", "USE_POSTGRES=true"
Set-Content $envFile $envContent
Write-Host ".env diupdate: USE_POSTGRES=true" -ForegroundColor Green

# Jalankan migrations
Write-Host "Menjalankan migrations..." -ForegroundColor Gray
Push-Location "$PSScriptRoot\backend"
python manage.py migrate
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nMigrations berhasil!" -ForegroundColor Green
} else {
    Write-Host "`nMigrations gagal. Cek output di atas." -ForegroundColor Red
}
Pop-Location

Write-Host "`n=== Setup Selesai ===" -ForegroundColor Cyan
Write-Host "Jalankan backend dengan: python manage.py runserver" -ForegroundColor White
