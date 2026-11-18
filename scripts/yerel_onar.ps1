#requires -version 5.1
<#
  Yerel depoyu toparlar ve ortam teşhisini çalıştırır (2026-11-18).

  Neden: yarım kalmış bir birleştirme (merge) sonrası "needs merge" hataları
  birikir; `git pull` çalışmaz, `import config` "SyntaxError" verir. Bu betik
  sırayla: yarım merge'i iptal eder, yerel değişiklikleri stash'e alır, AKTİF
  dalı uzaktaki hâline eşitler ve ağsız teşhisi yazar.

  Kullanım (tek satır, PowerShell):
    powershell -ExecutionPolicy Bypass -File .\scripts\yerel_onar.ps1
    powershell -ExecutionPolicy Bypass -File .\scripts\yerel_onar.ps1 -Dal arena/baska-dal

  Notlar:
    - Varsayılan dal hardcoded DEĞİLDİR; `git rev-parse --abbrev-ref HEAD`
      ile bulunur. Başka bir dala geçmek için -Dal açıkça verilmelidir.
    - Hiçbir şey sessizce silinmez: kirli çalışma ağacı `git stash list`
      altında durur; uzaktan ileride YEREL COMMIT varsa reset yapılmaz.
    - .env .gitignore'daysa yerinde kalır (stash'e girmez).
    - Dala ait yerel commit varsa `git reflog` ile geri alınabilir.
#>
param(
    [string]$Dal = "",
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

# 0) Hangi dal? Varsayılan = şu an checkout edilmiş dal (detached HEAD değil).
$aktifDalHam = & git rev-parse --abbrev-ref HEAD 2>$null
$aktifDal = ""
if ($aktifDalHam) { $aktifDal = ([string]$aktifDalHam).Trim() }
if ([string]::IsNullOrWhiteSpace($Dal)) {
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($aktifDal) -or $aktifDal -eq "HEAD") {
        Write-Host "HATA: detached HEAD veya dal okunamadi. -Dal <dal-adi> ile belirt." -ForegroundColor Red
        exit 1
    }
    $Dal = $aktifDal
}
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

# 3) Dali uzaktaki haline esitle (yerel commit varsa DUR)
if ((Git @("fetch", "origin", $Dal)) -ne 0) {
    Write-Host "HATA: fetch basarisiz (ag / kimlik). Komutu tekrar dene." -ForegroundColor Red
    exit 1
}
& git rev-parse --verify --quiet "refs/remotes/origin/$Dal" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "HATA: origin/$Dal bulunamadi. -Dal degerini kontrol et." -ForegroundColor Red
    exit 1
}
& git rev-parse --verify --quiet "refs/heads/$Dal" *> $null
if ($LASTEXITCODE -ne 0) {
    if ((Git @("checkout", "-b", $Dal, "origin/$Dal")) -ne 0) { exit 1 }
} else {
    if ((Git @("checkout", $Dal)) -ne 0) { exit 1 }
}
$yerel = (& git rev-parse HEAD).Trim()
$uzak = (& git rev-parse "refs/remotes/origin/$Dal").Trim()
if ($yerel -ne $uzak) {
    $ilerideHam = & git rev-list --count "$uzak..$yerel" 2>$null
    $ileride = 0
    if ($LASTEXITCODE -eq 0 -and $ilerideHam) { $ileride = [int]([string]$ilerideHam).Trim() }
    if ($ileride -gt 0) {
        Write-Host "HATA: $Dal dalinda $ileride YEREL COMMIT var; reset --hard bunlari siler." -ForegroundColor Red
        Write-Host "      Once commitleri push/rebase et veya -Dal ile baska dal sec." -ForegroundColor Red
        Write-Host "      Kirli calisma agaci daha once stash'e alindi: git stash list" -ForegroundColor Yellow
        exit 1
    }
}
if ((Git @("reset", "--hard", "origin/$Dal")) -ne 0) { exit 1 }

Write-Host ""
Write-Host "== Depo durumu ==" -ForegroundColor Cyan
& git log -1 --oneline | ForEach-Object { Write-Host "  son commit: $_" }
& git status -sb | Select-Object -First 3 | ForEach-Object { Write-Host "  $_" }

if ($TeshisYok) { exit 0 }

# 4) Ağsız teşhis (canlı çekme denemesi için --tanis-dene 1 eklenmeli)
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
& $py -m scripts.saglayici_karsilastirma --mod tanis --tanis-dene 0
$kod = $LASTEXITCODE
Pop-Location

Write-Host ""
if ($kod -eq 0) {
    Write-Host "Bitti. Teşhis çıktısının tamamını gönder; sonraki adımı ben vereceğim." -ForegroundColor Green
    Write-Host '  .\.venv\Scripts\python.exe -m scripts.saglayici_karsilastirma --mod canli --sembol "THYAO,GARAN,AKBNK,ASELS,EREGL" --tf "1g,1s"'
} else {
    Write-Host "Teşhis komutu hata verdi (kod $kod). Çıktıyı olduğu gibi gönder." -ForegroundColor Yellow
}
