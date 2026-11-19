#!/data/data/com.termux/files/usr/bin/bash
# Termux kurulumu - pandas build + jiter/rust hatası çözümü
# 2026-11-18: NATIVE 1h/2h/4h/1d arşivi için TV/datafeed pinleri eklendi.

echo "=== Termux Kurulum - Formation Bot (native 4 TF) ==="
echo "Python 3.14 aarch64 için özel"

# 1. Termux paketleri - prebuilt numpy/pandas (pip build yok)
echo "[1/6] Termux prebuilt paketleri..."
pkg update -y
pkg install python python-numpy python-pandas git -y
# termux-wake-lock için; paket yoksa kurulumu düşürme, çekim --wake-lock'suz sürer.
pkg install termux-api -y || echo "  termux-api kurulamadı; wake-lock olmadan devam"
echo "  python-numpy $(python -c 'import numpy; print(numpy.__version__)' 2>&1)"
echo "  python-pandas $(python -c 'import pandas; print(pandas.__version__)' 2>&1)"

# 2. Venv --system-site-packages ile (pkg paketlerini görsün)
echo "[2/6] Venv oluşturuluyor..."
if [ ! -d "venv" ]; then
    python -m venv venv --system-site-packages
    echo "  venv oluşturuldu --system-site-packages ile"
else
    echo "  venv zaten var"
fi
source venv/bin/activate

# 3. Pip upgrade
echo "[3/6] Pip upgrade..."
pip install --upgrade pip -q

# 4. Native arşiv bağımlılıkları: yfinance + doğrulanmış TV/datafeed
# borsapy KURMUYORUZ - jiter/rust hatası var ve 2h/4h native bar vermez.
echo "[4/6] yfinance + tradingview-datafeed + websocket-client kuruluyor..."
pip install -r requirements-termux.txt -q

# 5. Kurulum doğrulaması: ortak istemci doğrulanmış dağıtımı reddederse
#    backfill betiği zaten fail-closed durur; burada erken uyarı ver.
echo "[5/6] Dağıtım/sürüm doğrulanıyor..."
python - <<'PY'
import pandas, numpy, yfinance, pytz, websocket
from scripts.tvdatafeed_client import dogrulanmis_surum

ad, surum = dogrulanmis_surum()
print("  pandas", pandas.__version__, "numpy", numpy.__version__)
print("  yfinance", yfinance.__version__, "websocket-client", websocket.__version__)
print("  tvdatafeed", ad, surum)
print("  native plan: 1h=yahoo 2h=tvdatafeed 4h=tvdatafeed 1d=yahoo")
PY

# 6. Klasörler
echo "[6/6] Klasörler..."
mkdir -p bot_data logs
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env oluşturuldu (.env.example'dan)"
fi

echo ""
echo "=== KURULUM BİTTİ ==="
echo ""
echo "Sonraki adım (repo güncelse çekim):"
echo "  source venv/bin/activate"
echo "  python scripts/backfill/yahoo_backfill.py --probe"
echo "  python scripts/backfill/yahoo_backfill.py --limit 10"
echo "  termux-wake-lock && python scripts/backfill/yahoo_backfill.py"
echo ""
echo "Termux hatası çözümü:"
echo "  - pandas/numpy: pkg install python-numpy python-pandas + venv --system-site-packages"
echo "  - borsapy/jiter: kurma; 2h/4h native için tradingview-datafeed==2.1.1 yeterli"
echo "  - tvDatafeed kurulu değilse: pip install -r requirements-termux.txt"
echo ""
