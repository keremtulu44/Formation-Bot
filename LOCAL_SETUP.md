# Yerel Kurulum ve Test Rehberi

## 🚨 Termux İçin Önemli - 2 Farklı Build Hatası

### Hata 1: Pandas Build Hatası
Termux'ta Python 3.14 ile `pandas==2.2.2` build hatası:
```
npy_math_complex.c.src:432 cpowf undeclared
```
**Çözüm:** `pkg install python-numpy python-pandas` + venv `--system-site-packages`

### Hata 2: Borsapy / Jiter / Rust Hatası (YENİ)
```
borsapy -> openai -> jiter -> maturin -> rustc
Target triple not supported by rustup: aarch64-unknown-linux-android
ERROR: Failed to build 'jiter'
```
**Çözüm:** Borsapy'yi Termux'ta kurma! Yfinance yeterli. İstersen `--no-deps` ile.

### Termux Hızlı Kurulum (Önerilen - Güncel)

```bash
# Termux'u aç

pkg update -y
pkg install python python-numpy python-pandas git -y

cd ~
cd Formation-Bot
git checkout main
git pull origin main

# Venv --system-site-packages ile (pkg paketlerini görsün)
python -m venv venv --system-site-packages
source venv/bin/activate

# Sadece yfinance ve hafif paketler (borsapy YOK!)
pip install --upgrade pip
pip install yfinance python-dotenv pytz requests

# Klasörler
mkdir -p bot_data logs
cp .env.example .env

# Test
python -c "import pandas, numpy, yfinance; print('ok')"
python test_triangle.py
python collective_test.py
```

**Borsapy opsiyonel (gerek yok):**
```bash
# Sadece ticker için, openai olmadan
pip install borsapy --no-deps
```

**Otomatik script:**
```bash
bash setup-termux.sh
# Script borsapy'yi sormadan atlar, yfinance ile devam eder
```

### Neden?

- `pkg install python-numpy python-pandas` = Termux'un kendi derlediği prebuilt, build yok
- `pip install pandas==2.2.2` = Kaynaktan derlemeye çalışıyor, clang hatası
- `--system-site-packages` = venv içinde system paketleri görünsün
- `borsapy` = openai -> jiter -> Rust gerektiriyor, Termux aarch64 desteklemiyor, o yüzden yfinance yeterli

---

## 🚀 Windows PowerShell Hızlı Kurulum

### 1. Repo'yu Çek

```powershell
# PowerShell'i aç (Windows Terminal veya PowerShell 7)

# Klonla
git clone https://github.com/keremtulu44/Formation-Bot.git
cd Formation-Bot

# Varsayılan dal (main) üzerinde çalış
git pull origin main
```

### 2. Kurulum

> **Not (Batch 7 / C7):** Windows'a özel `setup.ps1` ve `local_test.ps1` kaldırıldı;
> Linux/Render hattında kullanılmıyorlardı ve bakımsız kalmışlardı. Aşağıdaki
> komutlar Windows PowerShell'de de çalışır.

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

### 3. Ortam ve Klasörler

```
Formation-Bot/
├── config.py              # BIST listesi, profil, sabitler
├── data.py                # Deque, resample, BIST saat kontrolü
├── reporting/             # Raporlama katmanı (panel/digest metinleri; batch-8)
├── state/                 # Kalıcılık katmanı (son tarama + digest tamponu; batch-8)
├── transport/             # Taşıma katmanı (Telegram webhook/komut; batch-8)
├── patterns/              # Ana pattern motoru (paket)
│   ├── pivots.py          # Pivot bulma
│   ├── detect.py          # Üçgen/kama + bayrak tespiti
│   ├── pole.py            # Kırılım gücü (f_breakout_strength)
│   ├── lifecycle.py       # PatternLifecycleManager
│   └── constants.py       # State sabitleri
├── main.py                # Ana döngü (BIST saat + tarama)
├── notifier.py            # Telegram (cooldown 4 saat)
├── test_triangle.py       # Üçgen test (mock)
├── test_breakout.py       # Kırılım test
├── test_flag.py           # Bayrak test
├── requirements.txt       # API bağımlılıkları
├── setup.sh               # Linux kurulum (Oracle Cloud)
├── bist-bot.service       # systemd service
├── .env.example           # Env örneği
├── FORMASYON_MANTIGI.md   # Türkçe mantık dökümanı
├── bot_data/              # Örnek/seed veri (seed okuma) - gitignore'da
│   └── THYAO.json         # Human-readable; PICKLE_CACHE=1 ise .pkl de yazılır
└── logs/
    └── bot.log

> **Batch 7 / C4:** Canlı veri artık repo dışında tutulur. `DATA_DIR` boşsa sırasıyla
> `RENDER` ortamı → `/tmp/formation-bot-data` → `/var/lib/formation-bot/data` →
> `~/.formation-bot/data` → `./bot_data` denenir; yazma **her zaman** `DATA_DIR`'e gider,
> `SEED_DATA_DIR` (varsayılan `./bot_data`) yalnız okuma yedeğidir.
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

`data.py` içinde bu iş **hazır** gelir:

```python
from data import fetch_yfinance_1h, fetch_yfinance_1d   # canlı veri
from config import MARKET_SUFFIX                        # ".IS" (env: MARKET_SUFFIX)

# fetch_yfinance_1h/1d: yfinance → borsapy yedeği, sütunları küçük harfe çevirir,
# MARKET_SUFFIX ekini kendisi uygular. Doğrudan çağırman yeterli:
df = fetch_yfinance_1h("THYAO")     # ~60 gün, 1 saatlik
```

## 🧪 Test Komutları

> **Batch 7 / C7:** Sahte veri üreteci (`mock_fetch_60d_1h`) kaldırıldı; zaman
> mantığı ve veri katmanı testleri artık gerçek/önbellek verisiyle çalışır.

```bash
# Venv aktif olmalı:  source .venv/bin/activate

# 1. Kapsamlı zaman/tarama kontrol listesi (çevrimdışı, veri gerektirmez)
python test_tarama_zamani.py

# 2. Tüm test paketi
python -m pytest -q

# 3. Veri katmanı duman testi (çevrimdışı)
python data.py

# 4. Kaynak/şablon güvenlik kontrolleri
python -m pytest -q test_kaynak_ve_guvenlik.py

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
git checkout main

# Güncelle
git pull origin main

# Değişiklik yapınca
git add -A
git commit -m "mesaj"
git push origin main

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
