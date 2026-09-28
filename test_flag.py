"""
Bayrak/Flama testi — Pine-uyumlu mock ile
Pine mimarisinde direk: diip/tepe pivotundan başlar, İLK kanal pivotunda biter (max 20 bar).
Eski mock direği 35 bar yapıp direk ucunu kanalın SON pivotuna bağlıyordu — Pine'da imkânsızdı.
Yeni mock: bar 8'de diip (low pivot) -> 12 barlık güçlü yukarı direk -> paralel kanal.
"""

import pandas as pd
import numpy as np
from patterns import (find_best_flag_candidate, ArgentEngine, calculate_atr,
                      find_pivots, find_pole)
from config import get_profile_params


def create_bull_flag(n_bars=72):
    """
    Boğa bayrağı (Pine-uyumlu):
    - bar 3-4: 92 civarı, bar 8: dip 88.0 (low pivot; 5'er bar iki yanından yüksek)
    - bar 9-20: güçlü yukarı direk (~3.2 bar/baş)
    - bar 20+: paralel kanal (üst 126, alt 122, eğim -0.02/bar)
      pivotlar: pos==6 -> üst pivot, pos==2 -> alt pivot (8 barda bir döngü)
    """
    np.random.seed(11)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    close = []
    for i in range(n_bars):
        if i <= 4:
            c = 92.0
        elif i == 5:
            c = 90.5
        elif i == 6:
            c = 89.2
        elif i == 7:
            c = 88.4
        elif i == 8:
            c = 88.0  # DİP (low pivot adayı)
        elif i <= 20:
            c = 88.0 + (i - 8) * (38.0 / 12.0)  # direk: bar 20'de ~126
        else:
            flag_i = i - 20
            upper_line = 126.0 - flag_i * 0.02
            lower_line = 122.0 - flag_i * 0.02
            pos = flag_i % 8
            if pos == 6:
                c = upper_line - 0.05   # üst pivot
            elif pos == 2:
                c = lower_line + 0.05   # alt pivot
            else:
                c = (upper_line + lower_line) * 0.5
        close.append(c + np.random.randn() * 0.02)

    high = [c + 0.15 for c in close]
    low = [c - 0.15 for c in close]
    open_ = [c - 0.02 for c in close]
    df = pd.DataFrame({'open': open_, 'high': high, 'low': low, 'close': close,
                       'volume': np.full(n_bars, 1200000)}, index=dates)
    return df


print("=== BAYRAK TESTİ (Pine-uyumlu mock) ===\n")

# Test 1: Boğa bayrağı
print("Test 1: Boğa bayrağı (diip -> direk -> paralel kanal)")
df_bull = create_bull_flag(52)  # 52 bar: kanal uzarsa durationRatio>4 -> Pine'a göre INVALID olur (doğru davranış)
params = get_profile_params("Dengeli")
atr = calculate_atr(df_bull, 14)
high_pivots, low_pivots = find_pivots(df_bull, params['pivot_len'])
print(f"  Data: {len(df_bull)} bar, son close {df_bull['close'].iloc[-1]:.2f}")
print(f"  Pivot: high={len(high_pivots)} low={len(low_pivots)}")

cand, logs = find_best_flag_candidate(df_bull, profile="Dengeli", verbose=True)
print(f"  {logs[0]}")
for log in logs[1:4]:
    print(f"   {log}")
if cand:
    print(f"  ✅ BULUNDU: {cand.pattern_type} kalite {cand.raw_quality:.1f}")
    print(f"     Direk: bar {cand.pole_start_bar}->{cand.pole_end_bar} süre {cand.pole_duration} "
          f"kalite {cand.pole_quality:.0f} büyüklük {cand.pole_magnitude:.1f}")
    print(f"     Depth {cand.correction_depth:.2f} heightRatio {cand.consolidation_height_ratio:.2f} "
          f"durationRatio {cand.duration_ratio:.2f}")
else:
    print("  ❌ Bayrak bulunamadı")

# Test 2: Random data (bayrak olmamalı)
print("\nTest 2: Random data (bayrak OLMAMALI)")
np.random.seed(42)
n = 250
close = 100 + np.cumsum(np.random.randn(n) * 0.5)
df_rand = pd.DataFrame({
    'open': close + np.random.randn(n) * 0.1,
    'high': close + np.abs(np.random.randn(n) * 0.3),
    'low': close - np.abs(np.random.randn(n) * 0.3),
    'close': close,
    'volume': np.random.randint(100000, 1000000, n)
}, index=pd.date_range(end=pd.Timestamp.now(), periods=n, freq='h'))
cand, logs = find_best_flag_candidate(df_rand, profile="Dengeli")
if cand:
    print(f"  ❌ Random data'da bayrak bulundu: {cand.pattern_type} (sorun!)")
else:
    print("  ✅ Bayrak yok (beklendiği gibi — direk olmadan bayrak kurulamaz)")

# Test 3: Ayı bayrağı (ayna simetrisi — yalnız fiyat çevrilir, ZAMAN ÇEVRİLMEZ)
print("\nTest 3: Ayı bayrağı (fiyat aynası: tepe -> aşağı direk -> paralel kanal)")
df_bear = create_bull_flag(52)
mirror_ohlc = 200.0 - df_bear[['open', 'high', 'low', 'close']]
# Aynalamada high ve low takas edilir: yeni_high = 200 - eski_low
mirror_ohlc = mirror_ohlc.rename(columns={'high': 'low', 'low': 'high'})
mirror_ohlc = mirror_ohlc[['open', 'high', 'low', 'close']]
df_bear = mirror_ohlc.assign(volume=df_bear['volume'].values)
cand, logs = find_best_flag_candidate(df_bear, profile="Dengeli")
if cand:
    print(f"  ✅ BULUNDU: {cand.pattern_type} kalite {cand.raw_quality:.1f} (beklenen: Ayı Bayrağı)")
else:
    print("  ❌ Ayı bayrağı bulunamadı")
