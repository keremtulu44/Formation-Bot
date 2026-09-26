# Yerele Çekme - PowerShell Rehberi

## 🚨 Termux İçin Önemli - Pandas Build Hatası Çözümü

Termux'ta Python 3.14 ile `pandas==2.2.2` build hatası veriyor (numpy derlenemiyor). Çözüm:

### Termux Hızlı Kurulum (Önerilen)

```bash
# Termux'u aç

pkg update -y
pkg install python python-numpy python-pandas git -y

cd ~
cd Formation-Bot
git checkout arena/01a0dd9d-formation-bot
git pull origin arena/01a0dd9d-formation-bot

# Venv --system-site-packages ile (pkg paketlerini görsün)
python -m venv venv --system-site-packages
source venv/bin/activate

# Sadece saf python paketleri
pip install --upgrade pip
pip install yfinance borsapy python-dotenv pytz requests

# Klasörler
mkdir -p bot_data logs
cp .env.example .env

# Test
python -c "import pandas, numpy, yfinance; print('ok')"
python test_triangle.py
```

**Veya otomatik script:**
```bash
bash setup-termux.sh
```

### Neden?

- `pkg install python-numpy python-pandas` = Termux'un kendi derlediği prebuilt paketler, build yok
- `pip install pandas==2.2.2` = Kaynaktan derlemeye çalışıyor, clang hatası
- `--system-site-packages` = venv içinde system paketleri (numpy/pandas) görünsün

---

## 🚀 Windows PowerShell Hızlı Kurulum

### 1. Repo'yu Çek

```powershell
# PowerShell'i aç (Windows Terminal veya PowerShell 7)

# Klonla
git clone https://github.com/keremtulu44/Formation-Bot.git
cd Formation-Bot

# Branch'e geç (bizim çalışma branch'imiz)
git checkout arena/01a0dd9d-formation-bot

# Güncel mi kontrol et
git pull origin arena/01a0dd9d-formation-bot
```

### 2. Otomatik Kurulum Scripti

```powershell
# PowerShell'de çalıştır (ExecutionPolicy hatası alırsan: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned)
.\setup.ps1
```

Bu script şunları yapar:
- venv oluşturur
- requirements.txt kurar
- .env oluşturur (.env.example'dan)
- bot_data/ ve logs/ klasörlerini oluşturur

### 3. Manuel Kurulum (setup.ps1 çalışmazsa)

```powershell
# Python venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Paketler
python -m pip install --upgrade pip
pip install -r requirements.txt

# Ekstra
pip install yfinance borsapy pandas numpy pytz python-dotenv requests

# .env
Copy-Item ".env.example" ".env"
notepad .env   # Token bilgilerini gir

# Klasörler
mkdir bot_data
mkdir logs
```

## 📁 Dosya Konumları

```
Formation-Bot/
├── config.py              # BIST listesi, profil, sabitler
├── data.py                # Deque, resample, BIST saat kontrolü
├── patterns.py            # Ana pattern motoru (79KB)
│   ├── find_pivots()      # Pivot bulma
│   ├── find_best_triangle_candidate()  # Üçgen/kama
│   ├── find_best_flag_candidate()      # Bayrak
│   ├── f_breakout_strength()           # Kırılım gücü
│   └── PatternLifecycleManager         # Lifecycle
├── main.py                # Ana döngü (BIST saat + tarama)
├── notifier.py            # Telegram (cooldown 4 saat)
├── test_triangle.py       # Üçgen test (mock)
├── test_breakout.py       # Kırılım test
├── test_flag.py           # Bayrak test
├── requirements.txt       # API bağımlılıkları
├── setup.ps1              # Windows kurulum
├── setup.sh               # Linux kurulum (Oracle Cloud)
├── bist-bot.service       # systemd service
├── logrotate.conf         # Log rotate
├── .env.example           # Env örneği
├── FORMASYON_MANTIGI.md   # Türkçe mantık dökümanı
├── bot_data/              # Kalıcı veri (pickle + json) - gitignore'da
│   ├── THYAO.pkl          # Hızlı yükleme
│   └── THYAO.json         # Human-readable, GitHub'da görünsün istersen
└── logs/
    └── bot.log
```

## 🔌 API Kullanımı - Ne Kullanıyoruz?

### Primary: yfinance (Önerilen)

```python
import yfinance as yf

# BIST için .IS suffix
ticker = yf.Ticker("THYAO.IS")
df = ticker.history(period="60d", interval="1h")
print(df.head())
# Sütunlar: Open, High, Low, Close, Volume
# Bizim kod open/high/low/close küçük harf bekliyor, data.py çeviriyor
```

**Avantaj:**
- Ücretsiz, stabil (TradingView ban riski yok)
- 60 gün 1H için yeterli (Yahoo 730 gün 1H verir)
- Sen daha önce tvdatafeed ile fark yok demiştin

**Dezavantaj:**
- Bazen BIST için 1H boş dönebilir (tatil, düşük hacim)
- Rate limit var ama 45sn bekleme ile çözülüyor

### Alternatif: borsapy (İş Yatırım + TradingView)

```python
import borsapy as bp

# Ticker
t = bp.Ticker("THYAO")
df = t.history(period="1ay", interval="1s")  # interval seçenekleri farklı
print(df.head())

# Veya
bp.download("THYAO", period="1ay")
```

**Avantaj:**
- BIST'e özel, İş Yatırım API
- Daha fazla BIST verisi

**Dezavantaj:**
- TradingView kısmı bazen SSL hatası (sandbox'ta gördük)
- Dokümantasyon az

### Eski: tvdatafeed (Kullanmıyoruz artık)

```python
# PyPI'de yok, git'ten kurulur
# pip install git+https://github.com/rongardF/tvdatafeed.git

from tvDatafeed import TvDatafeed, Interval
tv = TvDatafeed()
df = tv.get_hist(symbol="THYAO", exchange="BIST", interval=Interval.in_1_hour, n_bars=360)
```

**Neden kullanmıyoruz:**
- Unofficial, sık bozuluyor
- IP ban riski (Oracle Cloud'da)
- PyPI'de yok

**Bizim karar:** yfinance primary, borsapy fallback, tvdatafeed opsiyonel

### data.py'de Nasıl Değiştirilir?

```python
# data.py içinde mock_fetch_60d_1h yerine:

def real_fetch_yfinance(stock: str, n_bars: int = 360) -> pd.DataFrame:
    import yfinance as yf
    ticker = yf.Ticker(f"{stock}.IS")
    df = ticker.history(period="60d", interval="1h")
    # Sütun isimlerini küçük harfe çevir
    df.columns = [c.lower() for c in df.columns]
    return df

# Sonra StockDequeManager ile kullan
```

## 🧪 Test Komutları (PowerShell)

```powershell
# Venv aktif olmalı
.\venv\Scripts\Activate.ps1

# 1. Üçgen testi
python test_triangle.py

# 2. Kırılım testi
python test_breakout.py

# 3. Bayrak testi
python test_flag.py

# 4. Data katmanı
python data.py

# 5. Hızlı tarama (2 hisse, mock)
python -c "
from data import StockDequeManager, mock_fetch_60d_1h
from patterns import PatternLifecycleManager
from notifier import TelegramNotifier
from main import scan_all_stocks
import config
config.ACTIVE_STOCKS = ['THYAO', 'GARAN']
config.RATE_LIMIT_MIN = 1
config.RATE_LIMIT_MAX = 2
mgr = StockDequeManager(data_dir='./test_data')
life = PatternLifecycleManager()
notif = TelegramNotifier()
for s in config.ACTIVE_STOCKS:
    df = mock_fetch_60d_1h(s, 100)
    mgr.append_dataframe(s, df)
scan_all_stocks(mgr, life, notif)
"

# 6. Gerçek BIST verisi ile tek hisse test (internet gerekli)
python -c "
import yfinance as yf
from patterns import find_best_triangle_candidate
ticker = yf.Ticker('THYAO.IS')
df = ticker.history(period='60d', interval='1h')
print(f'THYAO: {len(df)} bar')
df.columns = [c.lower() for c in df.columns]
cand, logs = find_best_triangle_candidate(df, profile='Dengeli', verbose=True)
print(logs[0])
if cand:
    print(f'BULUNDU: {cand.pattern_type} {cand.raw_quality:.1f}')
"
```

## 🔐 .env Ayarı

```powershell
notepad .env
```

İçine:

```
TELEGRAM_BOT_TOKEN=1234567890:AAH_senin_tokenin
TELEGRAM_CHAT_ID=123456789
BOT_PROFILE=Dengeli
```

Token yoksa boş bırak, mock modda çalışır (sadece log).

## 📤 Git Komutları (PowerShell)

```powershell
# Durum
git status

# Branch kontrol
git branch

# Bizim branch
git checkout arena/01a0dd9d-formation-bot

# Güncelle
git pull origin arena/01a0dd9d-formation-bot

# Değişiklik yapınca
git add -A
git commit -m "mesaj"
git push origin arena/01a0dd9d-formation-bot

# Main ile karşılaştır
git log --oneline --graph --all -10
```

## 🚀 Oracle Cloud Deployment (Sonra)

```powershell
# setup.sh Linux için, Windows'ta değil
# Oracle'da:
# scp -r Formation-Bot ubuntu@<ip>:/opt/bist-bot
# ssh ubuntu@<ip>
# cd /opt/bist-bot
# bash setup.sh
# sudo cp bist-bot.service /etc/systemd/system/
# sudo systemctl enable bist-bot --now
```

## ❓ Sorun Giderme

**yfinance SSL hatası:**
```powershell
pip install --upgrade yfinance curl_cffi
```

**borsapy hatası:**
```powershell
pip install --upgrade borsapy
# Veya yfinance kullan
```

**Pivot bulunamadı:**
- Veri yetersiz (min 50 bar)
- Mock data kullan

**Telegram göndermiyor:**
- .env'de token boş mu?
- Mock modda sadece log basar

## 📞 Sonraki Adım

Canlı BIST verisi ile test edince bana logları at, false positive varsa eşiği ayarlarız.
