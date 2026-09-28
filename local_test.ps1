# ============================================================
# Formation-Bot - Yerel Test Paketi (PowerShell)
# Kullanim:
#   .\local_test.ps1             -> tum testleri sirayla calistirir
#   .\local_test.ps1 -PaketKur   -> once bagimliliklari kurar
# Her testin ciktisi ayrica *_cikti.txt dosyasina yazilir.
# ============================================================
param([switch]$PaketKur)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# --- Python bulun ---
$PY = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $PY = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py -3" }
else {
    Write-Host "HATA: Python bulunamadi! Kurun: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $PY (& $PY --Version)" -ForegroundColor Cyan
Invoke-Expression "$PY --version"

# --- Bagimliliklar (opsiyonel) ---
if ($PaketKur) {
    Write-Host "`nBagimliliklar kuruluyor (requirements.txt)..." -ForegroundColor Cyan
    Invoke-Expression "$PY -m pip install -r requirements.txt"
}

# --- Hizli import kontrolu ---
Invoke-Expression "$PY -c ""import pandas, numpy, pytz; print('temel paketler OK')"""
if ($LASTEXITCODE -ne 0) {
    Write-Host "Temel paketler eksik! Su komutu calistirin: .\local_test.ps1 -PaketKur" -ForegroundColor Red
    exit 1
}
$yfinanceVar = $true
Invoke-Expression "$PY -c ""import yfinance"" 2>`$null"
if ($LASTEXITCODE -ne 0) {
    $yfinanceVar = $false
    Write-Host "Not: yfinance yok -> internet isteyen testler atlanacak (pip install yfinance ile kurulabilir)" -ForegroundColor Yellow
}

# --- Test listesi (internet gerektirenler en sonda) ---
$tests = @(
    @{ Dosya = "test_triangle.py";        Internet = $false },
    @{ Dosya = "test_flag.py";            Internet = $false },
    @{ Dosya = "test_breakout.py";        Internet = $false },
    @{ Dosya = "repo_teshis.py";          Internet = $false },
    @{ Dosya = "test_accuracy.py";        Internet = $false },
    @{ Dosya = "collective_test.py";      Internet = $false },
    @{ Dosya = "test_forward.py";         Internet = $true },
    @{ Dosya = "check_4_candidates.py";   Internet = $true }
)

$ozet = @()
foreach ($t in $tests) {
    $ad = $t.Dosya
    if ($t.Internet -and -not $yfinanceVar) {
        Write-Host "`n----- $ad ATLANDI (yfinance yok) -----" -ForegroundColor Yellow
        $ozet += [pscustomobject]@{ Test = $ad; Sonuc = "ATLANDI (yfinance yok)" }
        continue
    }
    if (-not (Test-Path $ad)) {
        Write-Host "`n----- $ad BULUNAMADI -----" -ForegroundColor Yellow
        $ozet += [pscustomobject]@{ Test = $ad; Sonuc = "DOSYA YOK" }
        continue
    }
    Write-Host "`n================ $ad ================" -ForegroundColor Cyan
    $log = $ad -replace "\.py$", "_cikti.txt"
    Invoke-Expression "$PY $ad 2>&1 | Tee-Object -FilePath $log"
    $code = $LASTEXITCODE
    $durum = if ($code -eq 0) { "TAMAM" } else { "CIKIS KODU: $code" }
    $ozet += [pscustomobject]@{ Test = $ad; Sonuc = $durum }
}

Write-Host "`n================ OZET ================" -ForegroundColor Cyan
$ozet | Format-Table -AutoSize
Write-Host "Cikti dosyalari: *_cikti.txt (klasorde)"
Write-Host "Bu dosyalari sohbetde paylasabilirsiniz - ozellikle check_4_candidates_cikti.txt (gercek veriyle eski API uyumu)"
