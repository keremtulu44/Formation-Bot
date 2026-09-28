#!/bin/bash
# BIST Bot - Oracle Cloud Always Free ARM (Ubuntu 22.04) Kurulum Scripti
# Türkçe yorumlar

set -e

echo "=== BIST Formasyon Botu Kurulum Başlıyor ==="

# 1. Sistem güncelleme
echo "[1/7] Sistem güncelleniyor..."
sudo apt update && sudo apt upgrade -y

# 2. Python ve gerekli paketler
echo "[2/7] Python ve bağımlılıklar kuruluyor..."
sudo apt install -y python3 python3-venv python3-pip git curl

# 3. Proje dizini
BOT_DIR="/opt/bist-bot"
if [ ! -d "$BOT_DIR" ]; then
    echo "[3/7] Bot dizini oluşturuluyor: $BOT_DIR"
    sudo mkdir -p $BOT_DIR
    sudo chown $USER:$USER $BOT_DIR
else
    echo "[3/7] Bot dizini zaten var: $BOT_DIR"
fi

# 4. Log dizini
echo "[4/7] Log dizini oluşturuluyor..."
sudo mkdir -p /var/log/bist-bot
sudo chown $USER:$USER /var/log/bist-bot
sudo chmod 755 /var/log/bist-bot

# 5. Python venv
echo "[5/7] Python venv oluşturuluyor..."
cd $BOT_DIR
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 6. Requirements kurulumu
echo "[6/7] Python paketleri kuruluyor..."
pip install --upgrade pip
pip install -r requirements.txt

# 7. Environment file
echo "[7/7] Environment dosyası kontrolü..."
ENV_FILE="/etc/bist-bot.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Environment dosyası oluşturuluyor: $ENV_FILE"
    sudo tee $ENV_FILE > /dev/null <<EOF
# Telegram Bot Ayarları - KENDİ BİLGİLERİNİ GİR
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
# Profil: Hassas / Dengeli / Seçici
BOT_PROFILE=Dengeli
EOF
    sudo chmod 600 $ENV_FILE
    echo "Lütfen $ENV_FILE dosyasını düzenle ve token bilgilerini gir!"
else
    echo "Environment dosyası zaten var: $ENV_FILE"
fi

echo ""
echo "=== KURULUM TAMAMLANDI ==="
echo "Sonraki adımlar:"
echo "1. sudo nano $ENV_FILE  # Token bilgilerini gir"
echo "2. sudo cp bist-bot.service /etc/systemd/system/"
echo "3. sudo systemctl daemon-reload"
echo "4. sudo systemctl enable bist-bot"
echo "5. sudo systemctl start bist-bot"
echo "6. sudo journalctl -u bist-bot -f  # Logları izle"
echo ""
