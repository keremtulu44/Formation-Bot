#requires -version 5.1
<#
  Yerel depoyu toparlar ve ortam teşhisini çalıştırır (2026-11-16).

  Neden: yarım kalmış bir birleştirme (merge) sonrası "needs merge" hataları
  birikir; `git pull` çalışmaz, `import config` "SyntaxError" verir. Bu betik
  sırayla: yarım merge'i iptal eder, yerel değişiklikleri stash'e alır, dalı
  uzaktaki hâline eşitler ve teşhisi yazar.

  Kullanım (tek satır, PowerShell):
    powershell -ExecutionPolicy Bypass -File .\scripts\yerel_onar.ps1

  Notlar:
    - Hiçbir şey silinmez: yerel değişiklikler `git stash list` altında durur.
    - .env .gitignore'daysa yerinde kalır (stash'e girmez).
    - Dala ait yerel commit varsa `git reflog` ile geri alınabilir.
#>
param(
    [string]$Dal = "arena/52b49b26-formation-bot",
    [switch]$TeshisYok
)

function Git {
    param([string[]]$Argler)
    Write-Host ("  > git " + ($Argler -join " ")) -ForegroundColor DarkGray
    & git @Argler 2>&1 | ForEach-Object { Write-Host ("    " + $_) }
    return $LASTEXITCODE
}

Write-Host "== Yerel onarim ==" -ForegroundColor Cyan

& git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "HATA: bu klasor bir git deposu degil. Once: cd C:\Projeler\Formation-Bot" -ForegroundColor Red
    exit 1
}

$kok = (& git rev-parse --show-toplevel).Trim()
$gitDir = (& git rev-parse --git-dir).Trim()
Write-Host "  depo: $kok" -ForegroundColor DarkGray
Write-Host "  dal : $Dal" -ForegroundColor DarkGray

# 1) Yarim kalmis islemleri iptal et
$islemler = [ordered]@{
    "MERGE_HEAD"       = "merge"
    "CHERRY_PICK_HEAD" = "cherry-pick"
    "REVERT_HEAD"      = "revert"
}
foreach ($isaret in $islemler.Keys) {
    if (Test-Path (Join-Path $gitDir $isaret)) {
        Write-Host "  yarim $($islemler[$isaret]) bulundu, iptal ediliyor" -ForegroundColor Yellow
        Git @($islemler[$isaret], "--abort") | Out-Null
    }
}
if ((Test-Path (Join-Path $gitDir "rebase-merge")) -or (Test-Path (Join-Path $gitDir "rebase-apply"))) {
    Write-Host "  yarim rebase bulundu, iptal ediliyor" -ForegroundColor Yellow
    Git @("rebase", "--abort") | Out-Null
}

# 2) Yerel degisiklikleri yedekle
$kirli = & git status --porcelain
if ($kirli) {
    $ad = "yerel-yedek-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Write-Host "  yerel degisiklikler var, '$ad' adiyla saklaniyor" -ForegroundColor Yellow
    if ((Git @("stash", "push", "-u", "-m", $ad)) -ne 0) {
        Write-Host "HATA: stash basarisiz. Elle bak: git status / git stash list" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  yerel degisiklik yok" -ForegroundColor DarkGray
}

# 3) Dali uzaktaki haline esitle
if ((Git @("fetch", "origin", $Dal)) -ne 0) {
    Write-Host "HATA: fetch basarisiz (ag / kimlik). Komutu tekrar dene." -ForegroundColor Red
    exit 1
}
& git rev-parse --verify --quiet "refs/heads/$Dal" *> $null
if ($LASTEXITCODE -ne 0) {
    if ((Git @("checkout", "-b", $Dal, "origin/$Dal")) -ne 0) { exit 1 }
} else {
    if ((Git @("checkout", $Dal)) -ne 0) { exit 1 }
}
if ((Git @("reset", "--hard", "origin/$Dal")) -ne 0) { exit 1 }

Write-Host ""
Write-Host "== Depo durumu ==" -ForegroundColor Cyan
& git log -1 --oneline | ForEach-Object { Write-Host "  son commit: $_" }
& git status -sb | Select-Object -First 3 | ForEach-Object { Write-Host "  $_" }

if ($TeshisYok) { exit 0 }

# 4) Teshis
Write-Host ""
Write-Host "== Ortam teshisi ==" -ForegroundColor Cyan
$py = Join-Path $kok ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "  .venv yok; PATH'teki python kullanilacak" -ForegroundColor Yellow
    $py = "python"
} else {
    Write-Host "  python: $py" -ForegroundColor DarkGray
}
Push-Location $kok
& $py -m scripts.saglayici_karsilastirma --mod tanis
$kod = $LASTEXITCODE
Pop-Location

Write-Host ""
if ($kod -eq 0) {
    Write-Host "Bitti. Teşhis çıktısının tamamını gönder; sonraki adımı ben vereceğim." -ForegroundColor Green
    Write-Host '  .\.venv\Scripts\python.exe -m scripts.saglayici_karsilastirma --mod canli --sembol "THYAO,GARAN,AKBNK,ASELS,EREGL" --tf "1g,1s"'
} else {
    Write-Host "Teşhis komutu hata verdi (kod $kod). Çıktıyı olduğu gibi gönder." -ForegroundColor Yellow
}
