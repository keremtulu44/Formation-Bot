"""
Toplu deneme - Gerçek BIST datası ile tüm hisseleri tara
- bot_data/ içindeki 28 hisse (THYAO, GARAN vb)
- Her biri için 1H, 2H, 4H, 1D
- Üçgen/Kama + Bayrak
- Lifecycle
- Kalıcı kayıt kontrolü
"""

import os
import json
import pandas as pd
from data import StockDequeManager, resample_all_timeframes
from patterns import find_best_triangle_candidate, find_best_flag_candidate, PatternLifecycleManager
from config import BIST_30
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

data_dir = "./bot_data"
mgr = StockDequeManager(maxlen=360, data_dir=data_dir)

print(f"=== TOPLU DENEME - GERÇEK BIST VERİSİ ===\n")
print(f"Data dir: {os.path.abspath(data_dir)}")
print(f"Dosyalar: {len(os.listdir(data_dir))} adet")
print(f"BIST30 listesi: {len(BIST_30)} hisse")
print()

# İstatistikler
stats = {
    'total_stocks': 0,
    'stocks_with_data': 0,
    'total_timeframes': 0,
    'patterns_found': 0,
    'by_pattern': {},
    'by_timeframe': {'1h': 0, '2h': 0, '4h': 0, '1d': 0},
    'by_stock': {},
    'quality_sum': 0,
    'quality_max': 0,
    'quality_min': 100,
    'high_quality': 0,  # >=80
}

lifecycle_manager = PatternLifecycleManager(profile="Dengeli")

# Her hisseyi tara
for stock in BIST_30:
    stats['total_stocks'] += 1
    
    # Deque'den yükle (pkl veya json)
    df_1h = mgr.to_dataframe(stock)
    
    if df_1h is None or len(df_1h) == 0:
        print(f"❌ {stock}: Veri yok")
        continue
    
    stats['stocks_with_data'] += 1
    print(f"\n--- {stock}: {len(df_1h)} bar 1H (son {df_1h.index[-1]}) ---")
    
    # Tüm timeframe'leri üret (matematiksel dönüşüm)
    all_tf = resample_all_timeframes(df_1h)
    
    for tf_name, df_tf in all_tf.items():
        stats['total_timeframes'] += 1
        
        if len(df_tf) < 30:
            print(f"  {tf_name}: Yetersiz veri ({len(df_tf)} bar)")
            continue
        
        # Üçgen/Kama
        cand_tri, logs_tri = find_best_triangle_candidate(df_tf, profile="Dengeli", verbose=False)
        # Bayrak
        cand_flag, logs_flag = find_best_flag_candidate(df_tf, profile="Dengeli", verbose=False)
        
        # En iyi
        best = None
        if cand_tri and cand_tri.valid:
            best = cand_tri
        if cand_flag and cand_flag.valid:
            if best is None or cand_flag.raw_quality > best.raw_quality:
                best = cand_flag
        
        if best:
            stats['patterns_found'] += 1
            stats['by_timeframe'][tf_name] = stats['by_timeframe'].get(tf_name, 0) + 1
            stats['by_pattern'][best.pattern_type] = stats['by_pattern'].get(best.pattern_type, 0) + 1
            stats['by_stock'][stock] = stats['by_stock'].get(stock, 0) + 1
            stats['quality_sum'] += best.raw_quality
            stats['quality_max'] = max(stats['quality_max'], best.raw_quality)
            stats['quality_min'] = min(stats['quality_min'], best.raw_quality)
            if best.raw_quality >= 80:
                stats['high_quality'] += 1
            
            # Lifecycle
            state, break_dir, lifecycle_log = lifecycle_manager.update(f"{stock}_{tf_name}", df_tf, best)
            
            print(f"  ✅ {tf_name}: {best.pattern_type} kalite {best.raw_quality:.0f} daralma %{best.contraction*100:.0f} state {state}")
            print(f"      Üst {best.upper_now:.2f} Alt {best.lower_now:.2f} Genişlik {best.current_width:.2f} Temas {best.upper_touches}/{best.lower_touches}")
            print(f"      Lifecycle: {lifecycle_log}")
            
            # Kritik seviye
            if break_dir != 0:
                print(f"      Kırılım yönü: {'YUKARI' if break_dir==1 else 'AŞAĞI'}")
        else:
            # Neden yok? İlk log
            reason = logs_tri[0] if logs_tri else "Bilinmiyor"
            print(f"  ❌ {tf_name}: Yok - {reason[:80]}")

print(f"\n\n=== TOPLU ÖZET ===\n")
print(f"Toplam hisse: {stats['total_stocks']}")
print(f"Verisi olan: {stats['stocks_with_data']}")
print(f"Toplam timeframe denemesi: {stats['total_timeframes']} (28 hisse * 4 tf = 112)")
print(f"Bulunan pattern: {stats['patterns_found']}")
print(f"  Yüksek kalite (>=80): {stats['high_quality']}")
if stats['patterns_found'] > 0:
    print(f"  Ortalama kalite: {stats['quality_sum']/stats['patterns_found']:.1f}")
    print(f"  Max kalite: {stats['quality_max']:.1f} Min kalite: {stats['quality_min']:.1f}")

print(f"\nPattern tipine göre:")
for ptype, count in sorted(stats['by_pattern'].items(), key=lambda x: -x[1]):
    print(f"  {ptype}: {count}")

print(f"\nTimeframe'e göre:")
for tf, count in stats['by_timeframe'].items():
    print(f"  {tf}: {count}")

print(f"\nHisseye göre (en çok pattern olan):")
for stock, count in sorted(stats['by_stock'].items(), key=lambda x: -x[1])[:10]:
    print(f"  {stock}: {count} pattern")

print(f"\n=== KALICI KAYIT KONTROLÜ ===")
print(f"bot_data/ klasöründe {len(os.listdir(data_dir))} dosya var")
# Bir hisseyi yükle ve tekrar kaydet testi
test_stock = "THYAO"
df_test = mgr.to_dataframe(test_stock)
print(f"{test_stock}: {len(df_test)} bar yüklendi, son close {df_test['close'].iloc[-1]:.2f}")

# Resample testi
all_tf_test = resample_all_timeframes(df_test)
print(f"Resample: 1h={len(all_tf_test['1h'])} 2h={len(all_tf_test['2h'])} 4h={len(all_tf_test['4h'])} 1d={len(all_tf_test['1d'])}")

print(f"\n=== SONUÇ ===")
if stats['patterns_found'] == 0:
    print("Hiç pattern bulunamadı - eşik çok yüksek veya veri uygun değil")
elif stats['patterns_found'] > 50:
    print(f"Çok fazla pattern ({stats['patterns_found']}) - false positive olabilir, eşiği yükseltelim mi?")
else:
    print(f"{stats['patterns_found']} pattern bulundu - makul, canlı test için hazır")

print("\nToplu deneme bitti")
