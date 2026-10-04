"""
Gerçek BIST verisini çekip kalıcı olarak kaydet
- yfinance ile 60d 1h
- Hem pickle hem json
- bot_data/ klasörüne
- Sonra git add -f ile pushlayabilirsin
"""

import yfinance as yf
import os
import shutil
from data import StockDequeManager
from config import BIST_30, BIST_50, ACTIVE_STOCKS
import time
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Hangi hisseler? Şimdilik BIST30 ile test, sonra 50
stocks_to_fetch = BIST_30  # veya BIST_50

print(f"=== GERÇEK VERİ ÇEKME VE KALICI KAYIT ===")
print(f"Hisseler: {len(stocks_to_fetch)} adet")
print(f"Liste: {stocks_to_fetch[:5]}...")

# Deque manager - kalıcı
data_dir = "./bot_data"
mgr = StockDequeManager(maxlen=360, data_dir=data_dir)

# Eğer bot_data varsa temizle mi? Hayır, üzerine ekle
# shutil.rmtree(data_dir, ignore_errors=True)

success = 0
failed = 0

for idx, stock in enumerate(stocks_to_fetch):
    try:
        print(f"\n[{idx+1}/{len(stocks_to_fetch)}] {stock} çekiliyor...")
        
        # yfinance ile çek
        ticker = yf.Ticker(f"{stock}.IS")
        df = ticker.history(period="60d", interval="1h")
        
        if df is None or len(df) == 0:
            print(f"  ❌ Boş veri")
            failed += 1
            continue
        
        print(f"  Çekildi: {len(df)} bar 1H")
        
        # Sütun isimlerini küçük harfe çevir
        df.columns = [c.lower() for c in df.columns]
        
        # Deque'ye ekle (son 360'ı tutar)
        mgr.append_dataframe(stock, df)
        
        # Kaydet (hem pkl hem json)
        mgr.save_to_disk(stock)
        
        print(f"  ✅ Kaydedildi: {stock}.pkl + {stock}.json")
        success += 1
        
        # Rate limit - ban yememek için
        if idx < len(stocks_to_fetch) - 1:
            delay = random.uniform(2, 4)  # Gerçekte 45-50sn ama test için 2-4sn
            print(f"  {delay:.1f}sn bekleniyor...")
            time.sleep(delay)
            
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        failed += 1
        continue

print(f"\n=== BİTTİ ===")
print(f"Başarılı: {success}, Başarısız: {failed}")
print(f"Klasör: {os.path.abspath(data_dir)}")
print(f"Dosyalar: {len(os.listdir(data_dir))} adet")

# Özet
print(f"\nDosya listesi (ilk 10):")
for f in os.listdir(data_dir)[:10]:
    print(f"  {f}")

print(f"\n=== GITHUB'A PUSH İÇİN ===")
print(f"Şu an .gitignore'da bot_data/ ve *.pkl ignore'lı")
print(f"Pushlamak için PowerShell'de:")
print(f"")
print(f"  cd Formation-Bot")
print(f"  git add -f bot_data/*.json   # Sadece json'ları pushla (human-readable)")
print(f"  # Veya pkl de dahil:")
print(f"  git add -f bot_data/")
print(f"  git commit -m 'real BIST data 30 stocks 60d 1h'")
print(f"  git push origin arena/01a0dd9d-formation-bot")
print(f"")
print(f"Ben de çekip kullanabilirim:")
print(f"  git pull origin arena/01a0dd9d-formation-bot")
print(f"")
print(f"Not: bot_data çok büyürse (30 hisse * 360 bar ~ 5MB json), GitHub'a pushlamak yavaş olabilir")
print(f"Alternatif: Sadece 1-2 hisse (THYAO, GARAN) pushla test için")
