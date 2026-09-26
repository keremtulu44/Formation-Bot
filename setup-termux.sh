#!/data/data/com.termux/files/usr/bin/bash
# Termux için kurulum - pandas build + jiter/rust hatası çözümü

echo "=== Termux Kurulum - Formation Bot ==="
echo "Python 3.14 aarch64 için özel"

# 1. Termux paketleri - prebuilt numpy/pandas (pip build yok)
echo "[1/5] Termux prebuilt paketleri..."
pkg update -y
pkg install python python-numpy python-pandas git -y
echo "  python-numpy $(python -c 'import numpy; print(numpy.__version__)' 2>&1)"
echo "  python-pandas $(python -c 'import pandas; print(pandas.__version__)' 2>&1)"

# 2. Venv --system-site-packages ile (pkg paketlerini görsün)
echo "[2/5] Venv oluşturuluyor..."
if [ ! -d "venv" ]; then
    python -m venv venv --system-site-packages
    echo "  venv oluşturuldu --system-site-packages ile"
else
    echo "  venv zaten var"
fi
source venv/bin/activate

# 3. Pip upgrade
echo "[3/5] Pip upgrade..."
pip install --upgrade pip -q

# 4. Sadece yfinance ve hafif paketler
# borsapy KURMUYORUZ - jiter/rust hatası var
# borsapy -> openai -> jiter -> maturin -> rustc aarch64-unknown-linux-android desteklenmiyor
echo "[4/5] yfinance ve hafif paketler kuruluyor (borsapy hariç)..."
pip install yfinance pytz python-dotenv requests -q
echo "  yfinance, pytz, dotenv, requests kuruldu"

# 5. Opsiyonel: borsapy --no-deps (openai olmadan)
echo ""
echo "Borsapy Termux'ta normal kurulmuyor (jiter/rust hatası)"
echo "İstersen --no-deps ile deneyebilirsin ama yfinance yeterli:"
echo "  pip install borsapy --no-deps"
echo "Bot borsapy olmadan da çalışır (yfinance primary)"
read -p "Borsapy --no-deps ile kurulsun mu? (e/h, default h): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ee]$ ]]; then
    pip install borsapy --no-deps -q
    echo "  borsapy --no-deps kuruldu (openai yok, sadece ticker çalışır)"
else
    echo "  borsapy atlandı, yfinance ile devam"
fi

# 6. Klasörler
echo "[5/5] Klasörler..."
mkdir -p bot_data logs
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env oluşturuldu (.env.example'dan)"
fi

echo ""
echo "=== KURULUM BİTTİ ==="
echo ""
echo "Test:"
echo "  source venv/bin/activate"
echo "  python -c 'import pandas, numpy, yfinance; print(\"ok\")'"
echo "  python test_triangle.py"
echo "  python collective_test.py"
echo ""
echo "Termux hatası çözümü:"
echo "  - pandas/numpy: pkg install python-numpy python-pandas + venv --system-site-packages"
echo "  - borsapy/jiter: kurma, yfinance yeterli (borsapy --no-deps opsiyonel)"
echo ""
