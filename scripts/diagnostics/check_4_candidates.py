"""
Bu 4'lü nasıl çıktı? Hangi timeframe?
Gerçek THYAO datasında 225 adaydan 4'ü neden geçti, detaylı göster
+ Resample ve kalıcı kayıt testi
"""

import yfinance as yf
import pandas as pd
from patterns import find_pivots, calculate_atr, f_build_triangle_candidate
from config import get_profile_params
import os

# 1. Veri çek - hangi timeframe?
print("=== HANGİ TIMEFRAME ÇEKTİK? ===")
print("Senin çektiğin: 60d 1h (yfinance interval='1h')")
print("Bizim bot: 1H çekip matematiksel olarak 2H, 4H, 1D'ye dönüştürüyor")
print()

ticker = yf.Ticker("THYAO.IS")
df_1h = ticker.history(period="60d", interval="1h")
print(f"Çekilen: {len(df_1h)} bar 1H")
print(f"Son 5 bar:")
print(df_1h.tail())
print()

# Sütunları küçük harfe çevir (bizim kod öyle bekliyor)
df_1h.columns = [c.lower() for c in df_1h.columns]

# 2. Resample - matematiksel dönüşüm
print("=== MATEMATİKSEL DÖNÜŞÜM (1H -> 2H, 4H, 1D) ===")
from data import resample_all_timeframes

all_tf = resample_all_timeframes(df_1h)
for tf_name, dft in all_tf.items():
    print(f"{tf_name}: {len(dft)} bar")
    if len(dft) > 0:
        print(f"  Son: {dft.index[-1]} O:{dft['open'].iloc[-1]:.2f} H:{dft['high'].iloc[-1]:.2f} L:{dft['low'].iloc[-1]:.2f} C:{dft['close'].iloc[-1]:.2f}")
print()

# Formül: 
# 2H: df.resample('2h').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
# 4H: aynı 4h ile
# 1D: 1D ile
# Sonra dropna() - BIST seans dışı boş mumları atıyoruz
print("Formül: open=first, high=max, low=min, close=last, volume=sum + dropna()")
print()

# 3. Bu 4'lü nasıl çıktı? Hangi timeframe?
print("=== BU 4'LÜ NASIL ÇIKTI? ===")
print("Timeframe: 1H (senin test ettiğin 531 bar 1H)")
print("Mantık: Son 6 high pivot + son 6 low pivot = 6*5/2 * 6*5/2 = 15*15 = 225 kombinasyon")
print("Her kombinasyon 4 pivot: hb1,hb2,lb1,lb2")
print()

params = get_profile_params("Dengeli")
atr = calculate_atr(df_1h, 14)
high_pivots, low_pivots = find_pivots(df_1h, params['pivot_len'])

print(f"Pivotlar: high={len(high_pivots)} low={len(low_pivots)}")
print(f"Son 6 high:")
for i, p in enumerate(high_pivots[-6:]):
    print(f"  [{i}] bar={p['bar']} price={p['price']:.2f} confirm={p['confirm_bar']}")
print(f"Son 6 low:")
for i, p in enumerate(low_pivots[-6:]):
    print(f"  [{i}] bar={p['bar']} price={p['price']:.2f} confirm={p['confirm_bar']}")
print()

# Tüm kombinasyonları dene ve geçen 4'ü detaylı göster
print("=== GEÇEN 4 ADAY DETAYI ===")
search_n = 6
high_search = high_pivots[-search_n:]
low_search = low_pivots[-search_n:]

passed = []
for hiA in range(len(high_search)-1):
    for hiB in range(hiA+1, len(high_search)):
        for loA in range(len(low_search)-1):
            for loB in range(loA+1, len(low_search)):
                cand, reason = f_build_triangle_candidate(
                    df_1h, atr, high_search, low_search,
                    hiA, hiB, loA, loB, params, "Dengeli", len(df_1h)-1
                )
                if cand and cand.valid:
                    passed.append((hiA, hiB, loA, loB, cand, reason))

print(f"Toplam geçen: {len(passed)}")
for idx, (hiA, hiB, loA, loB, cand, reason) in enumerate(passed):
    print(f"\n--- Geçen #{idx+1} [{hiA},{hiB},{loA},{loB}] ---")
    print(f"  {reason}")
    print(f"  Tip: {cand.pattern_type} Family: {cand.family} Dir: {cand.classic_dir}")
    print(f"  Kalite: {cand.raw_quality:.1f} (geom {cand.geometry_score:.0f} touch {cand.touch_score:.0f} mat {cand.maturity_score:.0f})")
    print(f"  Bar: start={cand.start_bar} end={cand.end_bar} apex={cand.apex_bar} progress={cand.progress*100:.0f}%")
    print(f"  Üst: {cand.upper_now:.2f} (hb1={cand.hb1} hp1={cand.hp1:.2f} hb2={cand.hb2} hp2={cand.hp2:.2f} slope={cand.upper_slope:.4f})")
    print(f"  Alt: {cand.lower_now:.2f} (lb1={cand.lb1} lp1={cand.lp1:.2f} lb2={cand.lb2} lp2={cand.lp2:.2f} slope={cand.lower_slope:.4f})")
    print(f"  Genişlik: {cand.current_width:.2f} Daralma: {cand.contraction*100:.1f}%")
    print(f"  Temas: üst {cand.upper_touches} alt {cand.lower_touches}")
    print(f"  İhlal: close {cand.historical_close_violations} wick {cand.historical_wick_violations} penalty {cand.historical_violation_penalty:.1f}")

# En iyi
if passed:
    best = max(passed, key=lambda x: x[4].raw_quality)
    print(f"\n=== EN İYİ ===")
    print(f"[{best[0]},{best[1]},{best[2]},{best[3]}] {best[4].pattern_type} {best[4].raw_quality:.1f}")

print("\n=== KALICI KAYIT YAPTIK MI? ===")
print("Şu an senin testinde yapmadık, sadece RAM'de")
print("Kalıcı kayıt için data.py'deki StockDequeManager kullanıyoruz:")
print("  - THYAO.pkl (pickle, hızlı)")
print("  - THYAO.json (json, GitHub'da görünür)")
print()

# Kalıcı kayıt testi
from data import StockDequeManager
import shutil

test_dir = "./bot_data_test"
shutil.rmtree(test_dir, ignore_errors=True)

mgr = StockDequeManager(maxlen=360, data_dir=test_dir)
# DataFrame'i deque'ye ekle
mgr.append_dataframe("THYAO", df_1h)
print(f"Deque'ye eklendi: {len(mgr.get_deque('THYAO'))} mum (maxlen 360, sen 531 çektin, son 360'ı tutar)")

# Kaydet
mgr.save_to_disk("THYAO")
print(f"Kaydedildi: {os.listdir(test_dir)}")

# Yükle
mgr2 = StockDequeManager(maxlen=360, data_dir=test_dir)
df_loaded = mgr2.to_dataframe("THYAO")
print(f"Yüklendi: {len(df_loaded)} bar")

# Temizle
shutil.rmtree(test_dir, ignore_errors=True)

print("\n=== SENİN PUSH İÇİN ===")
print("Eğer kalıcı olarak GitHub'a pushlamak istiyorsan:")
print("  1. bot_data/ klasöründe THYAO.json ve THYAO.pkl oluşacak")
print("  2. Ama .gitignore'da bot_data/ ve *.pkl ignore'lı")
print("  3. Force push için:")
print("     git add -f bot_data/THYAO.json")
print("     git add -f bot_data/THYAO.pkl  (istersen)")
print("     git commit -m 'THYAO real data'")
print("     git push origin arena/01a0dd9d-formation-bot")
print("  4. Ben de çekip kullanabilirim")
print()
print("Veya ben sana save_real_data.py hazırlayayım, tüm BIST30'u çekip kaydetsin")
