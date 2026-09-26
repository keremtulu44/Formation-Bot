"""
Doğruluk testi - Sentetik + Random + Shuffle
Manuel olmadan sistem ne kadar doğru?

1. Sentetik üçgenler (ground truth belli) - detection rate
2. Random walk - false positive rate
3. Shuffle - zaman sırası bozulunca pattern kalmamalı
"""

import pandas as pd
import numpy as np
from patterns import find_best_triangle_candidate, find_best_flag_candidate, calculate_atr, find_pivots
from config import get_profile_params
import random

# Test_triangle'daki fonksiyonları kopyala (import edemiyoruz çünkü orada random seed var)
def create_perfect_symmetrical_triangle(n_bars=250, noise_level=0.0):
    """Simetrik üçgen + gürültü seviyesi"""
    np.random.seed(None)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    close = []
    for i in range(n_bars):
        # Daralan üçgen: üst aşağı, alt yukarı
        progress = i / n_bars
        upper_line = 110 - progress * 15  # 110 -> 95
        lower_line = 90 + progress * 10   # 90 -> 100
        mid = (upper_line + lower_line) / 2
        # Gürültü
        c = mid + np.random.randn() * noise_level
        # Sınırlar içinde tut
        c = max(lower_line + 0.5, min(upper_line - 0.5, c))
        # Pivotlar için net noktalar
        if i % 30 == 15:
            c = upper_line - 0.2
        elif i % 30 == 0:
            c = lower_line + 0.2
        close.append(c)
    
    high = [c + abs(np.random.randn()*0.1)+0.1 for c in close]
    low = [c - abs(np.random.randn()*0.1)-0.1 for c in close]
    open_ = [c + np.random.randn()*0.05 for c in close]
    df = pd.DataFrame({'open': open_, 'high': high, 'low': low, 'close': close, 'volume': np.random.randint(1000000, 4000000, n_bars)}, index=dates)
    return df

def create_ascending_triangle(n_bars=250, noise_level=0.0):
    np.random.seed(None)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    close = []
    for i in range(n_bars):
        progress = i / n_bars
        upper_line = 105  # Yatay
        lower_line = 90 + progress * 12  # Yukarı
        mid = (upper_line + lower_line) / 2
        c = mid + np.random.randn() * noise_level
        c = max(lower_line + 0.5, min(upper_line - 0.5, c))
        if i % 25 == 12:
            c = upper_line - 0.2
        elif i % 25 == 0:
            c = lower_line + 0.2
        close.append(c)
    high = [c + abs(np.random.randn()*0.1)+0.1 for c in close]
    low = [c - abs(np.random.randn()*0.1)-0.1 for c in close]
    open_ = [c + np.random.randn()*0.05 for c in close]
    df = pd.DataFrame({'open': open_, 'high': high, 'low': low, 'close': close, 'volume': np.random.randint(1000000, 4000000, n_bars)}, index=dates)
    return df

def create_random_walk(n_bars=250):
    np.random.seed(None)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars) * 0.2)
    low = close - np.abs(np.random.randn(n_bars) * 0.2)
    open_ = close + np.random.randn(n_bars) * 0.1
    df = pd.DataFrame({'open': open_, 'high': high, 'low': low, 'close': close, 'volume': np.random.randint(1000000, 4000000, n_bars)}, index=dates)
    return df

print("=== DOĞRULUK TESTİ ===\n")

# 1. Sentetik üçgen - gürültü seviyesine göre detection rate
print("1. Sentetik Üçgen Detection Rate (ground truth belli)\n")
for noise in [0.0, 0.1, 0.3, 0.6, 1.0]:
    found = 0
    total = 20
    qualities = []
    for _ in range(total):
        # Rastgele tip seç
        typ = random.choice(['sym', 'asc'])
        if typ == 'sym':
            df = create_perfect_symmetrical_triangle(250, noise_level=noise)
        else:
            df = create_ascending_triangle(250, noise_level=noise)
        cand, _ = find_best_triangle_candidate(df, profile="Dengeli", verbose=False)
        if cand and cand.valid:
            found += 1
            qualities.append(cand.raw_quality)
    avg_q = sum(qualities)/len(qualities) if qualities else 0
    print(f"  Gürültü {noise:.1f}: {found}/{total} bulundu ({found/total*100:.0f}%) ort kalite {avg_q:.0f}")

# 2. Random walk false positive
print("\n2. Random Walk False Positive (olmaması lazım)\n")
found_random = 0
total_random = 50
for _ in range(total_random):
    df = create_random_walk(250)
    cand, _ = find_best_triangle_candidate(df, profile="Dengeli", verbose=False)
    if cand and cand.valid:
        found_random += 1
print(f"  Random {total_random} denemede {found_random} pattern bulundu ({found_random/total_random*100:.1f}%)")
print(f"  Beklenen: <%5, ideal <%2 (şu anki sistem {found_random/total_random*100:.1f}%)")

# 3. Shuffle test - gerçek BIST datasını karıştır
print("\n3. Shuffle Test (gerçek data karıştırılınca pattern kalmamalı)\n")
from data import StockDequeManager
mgr = StockDequeManager(data_dir="./bot_data")
df_real = mgr.to_dataframe("THYAO")
if df_real is not None:
    # Shuffle close fiyatlarını karıştır ama OHLC yapısını koru?
    # Basit: close'u karıştır, high/low ona göre ayarla
    for trial in range(5):
        df_shuffled = df_real.copy()
        shuffled_close = df_shuffled['close'].values.copy()
        np.random.shuffle(shuffled_close)
        df_shuffled['close'] = shuffled_close
        df_shuffled['high'] = shuffled_close + np.abs(np.random.randn(len(shuffled_close))*0.5)
        df_shuffled['low'] = shuffled_close - np.abs(np.random.randn(len(shuffled_close))*0.5)
        cand, _ = find_best_triangle_candidate(df_shuffled, profile="Dengeli", verbose=False)
        status = f"Pattern var: {cand.pattern_type} q{cand.raw_quality:.0f}" if cand and cand.valid else "Yok (beklendiği gibi)"
        print(f"  Shuffle {trial+1}: {status}")
else:
    print("  THYAO data yok, atlanıyor")

# 4. Stabilite testi - 360 vs 350 bar
print("\n4. Stabilite Testi (360 vs 350 bar aynı pattern'i bulmalı)\n")
if df_real is not None and len(df_real) >= 360:
    df_360 = df_real.iloc[-360:]
    df_350 = df_real.iloc[-350:]
    cand_360, _ = find_best_triangle_candidate(df_360, profile="Dengeli", verbose=False)
    cand_350, _ = find_best_triangle_candidate(df_350, profile="Dengeli", verbose=False)
    if cand_360 and cand_350:
        same_type = cand_360.pattern_type == cand_350.pattern_type
        upper_diff = abs(cand_360.upper_now - cand_350.upper_now) if cand_360.upper_now and cand_350.upper_now else 999
        print(f"  360 bar: {cand_360.pattern_type} q{cand_360.raw_quality:.0f} üst {cand_360.upper_now:.2f}")
        print(f"  350 bar: {cand_350.pattern_type} q{cand_350.raw_quality:.0f} üst {cand_350.upper_now:.2f}")
        print(f"  Aynı tip mi? {same_type}, Üst fark {upper_diff:.2f} (<%2 ise stabil)")
        print(f"  Stabil mi? {'EVET' if same_type and upper_diff < 2.0 else 'HAYIR - hassas'}")
    else:
        print(f"  360: {cand_360.pattern_type if cand_360 else 'Yok'}, 350: {cand_350.pattern_type if cand_350 else 'Yok'} - biri yok")

print("\n=== SONUÇ ===")
print("Bu testler manuel olmadan sistemin sağlamlığını gösterir:")
print("- Sentetik detection rate yüksek olmalı, gürültü artınca düşmeli")
print("- Random false positive düşük olmalı <%5")
print("- Shuffle'da pattern kalmamalı")
print("- Stabilite aynı tip bulmalı")
