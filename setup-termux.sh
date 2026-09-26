#!/data/data/com.termux/files/usr/bin/bash
# Termux için kurulum - pandas build hatası çözümü

echo "=== Termux Kurulum ==="

# 1. Termux paketleri - prebuilt numpy/pandas
echo "[1/5] Termux paketleri kuruluyor (prebuilt)..."
pkg update -y
pkg install python python-numpy python-pandas git -y

# 2. Venv oluştur (opsiyonel, Termux'ta system python da olur ama venv önerilir)
echo "[2/5] Venv..."
if [ ! -d "venv" ]; then
    python -m venv venv --system-site-packages
    # --system-site-packages önemli: pkg ile kurulan numpy/pandas'ı venv görsün
fi
source venv/bin/activate

# 3. Pip upgrade
echo "[3/5] Pip upgrade..."
pip install --upgrade pip

# 4. Sadece yfinance, borsapy gibi saf python paketlerini pip ile kur
# numpy/pandas zaten pkg ile kurulu, tekrar kurma
echo "[4/5] yfinance, borsapy kuruluyor (no-deps, build yok)..."
pip install yfinance borsapy python-dotenv pytz requests --no-build-isolation --only-binary=:all: 2>&1 || pip install yfinance borsapy python-dotenv pytz requests

# 5. Klasörler
echo "[5/5] Klasörler..."
mkdir -p bot_data logs
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env oluşturuldu"
fi

echo ""
echo "=== BİTTİ ==="
echo "Test:"
echo "  python -c 'import pandas, numpy, yfinance; print(\"ok\")'"
echo "  python test_triangle.py"
echo "  python collective_test.py"
