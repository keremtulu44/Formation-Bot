# BIST Formasyon Botu - Windows PowerShell Kurulum
# Yerele çekmek için bu scripti çalıştır

Write-Host "=== BIST Formasyon Botu - Windows Kurulum ===" -ForegroundColor Green

# 1. Git kontrol
try {
    git --version | Out-Null
} catch {
    Write-Host "Git kurulu değil! https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

# 2. Repo klonlama veya güncelleme
$repoUrl = "https://github.com/keremtulu44/Formation-Bot.git"
$branch = "arena/01a0dd9d-formation-bot"
$localDir = "Formation-Bot"

if (Test-Path $localDir) {
    Write-Host "[1/6] Repo zaten var, güncelleniyor..." -ForegroundColor Yellow
    Set-Location $localDir
    git fetch origin
    git checkout $branch
    git pull origin $branch
} else {
    Write-Host "[1/6] Repo klonlanıyor..." -ForegroundColor Yellow
    git clone $repoUrl
    Set-Location $localDir
    git checkout $branch
}

Write-Host "Branch: $branch" -ForegroundColor Cyan
Write-Host "Konum: $(Get-Location)" -ForegroundColor Cyan

# 3. Python kontrol
try {
    python --version | Out-Null
    $pythonCmd = "python"
} catch {
    try {
        py --version | Out-Null
        $pythonCmd = "py"
    } catch {
        Write-Host "Python kurulu değil! https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[2/6] Python bulundu: $(& $pythonCmd --version)" -ForegroundColor Yellow

# 4. Venv oluştur
Write-Host "[3/6] Virtual environment oluşturuluyor..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    & $pythonCmd -m venv venv
    Write-Host "venv oluşturuldu" -ForegroundColor Green
} else {
    Write-Host "venv zaten var" -ForegroundColor Green
}

# 5. Venv aktif et ve paketleri kur
Write-Host "[4/6] Paketler kuruluyor..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# pip upgrade
python -m pip install --upgrade pip

# requirements
pip install -r requirements.txt

# Ekstra: yfinance ve borsapy için ekstra bağımlılıklar
pip install python-dotenv pytz requests

Write-Host "Paketler kuruldu" -ForegroundColor Green

# 6. .env dosyası
Write-Host "[5/6] .env dosyası kontrolü..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env oluşturuldu - lütfen düzenle!" -ForegroundColor Yellow
    Write-Host "Notepad ile açmak için: notepad .env" -ForegroundColor Cyan
} else {
    Write-Host ".env zaten var" -ForegroundColor Green
}

# 7. Klasörler
Write-Host "[6/6] Klasörler oluşturuluyor..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "bot_data" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
Write-Host "bot_data/ ve logs/ hazır" -ForegroundColor Green

Write-Host ""
Write-Host "=== KURULUM TAMAMLANDI ===" -ForegroundColor Green
Write-Host ""
Write-Host "Dosya Yapısı:" -ForegroundColor Cyan
Get-ChildItem -File | Select-Object Name, Length | Format-Table -AutoSize

Write-Host ""
Write-Host "Test Komutları:" -ForegroundColor Yellow
Write-Host "  python test_triangle.py    # Üçgen testi"
Write-Host "  python test_breakout.py    # Kırılım lifecycle testi"
Write-Host "  python test_flag.py        # Bayrak testi"
Write-Host "  python data.py             # Data katmanı testi"
Write-Host "  python patterns.py         # Pattern iskelet testi"
Write-Host ""
Write-Host "Bot Çalıştırma (mock data):" -ForegroundColor Yellow
Write-Host "  python main.py"
Write-Host ""
Write-Host "Gerçek BIST verisi ile test (yfinance):" -ForegroundColor Yellow
Write-Host "  python -c `"import yfinance as yf; df=yf.Ticker('THYAO.IS').history(period='60d', interval='1h'); print(df.tail())`""
Write-Host ""
Write-Host "Telegram token girmek için:" -ForegroundColor Yellow
Write-Host "  notepad .env"
Write-Host ""
Write-Host "Git branch: $branch" -ForegroundColor Cyan
Write-Host "GitHub: $repoUrl" -ForegroundColor Cyan
