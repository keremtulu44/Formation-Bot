"""
Bayrak/Flama testi
"""

import pandas as pd
import numpy as np
from patterns import find_best_flag_candidate, find_pole, calculate_atr, find_pivots
from config import get_profile_params

def create_bull_flag(n_bars=250):
    """
    Boğa bayrağı - pivotlar net olacak şekilde
    """
    np.random.seed(789)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    
    close = []
    high = []
    low = []
    open_ = []
    
    pole_bars = 35
    pole_start = 90
    pole_end = 125
    
    # Bayrak kanalı - çok net paralel
    # Üst: 126 -> 123, Alt: 122 -> 119 (eğim -0.015, genişlik 4)
    
    for i in range(n_bars):
        if i < pole_bars:
            # Direk
            progress = i / pole_bars
            base = pole_start + (pole_end - pole_start) * progress
            c = base + np.random.randn() * 0.03
        else:
            flag_i = i - pole_bars
            # Paralel kanal
            upper_line = 126.0 - flag_i * 0.014
            lower_line = 122.0 - flag_i * 0.014
            
            # Net pivotlar: her 20 barda bir, 10 bar arayla üst/alt
            # Pivot için 5 bar önce/sonra düşük/yüksek olmalı
            # O yüzden pivot barında fiyatı tam sınırda yap, çevresindekileri ortada
            
            # Flag içindeki pozisyon
            cycle_pos = flag_i % 20
            
            if cycle_pos == 10:
                # Üst pivot - tam üstte, komşular ortada olacak
                c = upper_line - 0.05
            elif cycle_pos == 0:
                # Alt pivot - tam altta
                c = lower_line + 0.05
            else:
                # Diğer barlar ortada, pivot olmasın diye
                # Eğer pivot barına 5 yakınsa, biraz daha ortada
                dist_to_upper_pivot = min(abs(cycle_pos - 10), 20 - abs(cycle_pos - 10))
                dist_to_lower_pivot = min(abs(cycle_pos - 0), 20 - abs(cycle_pos - 0))
                min_dist = min(dist_to_upper_pivot, dist_to_lower_pivot)
                
                if min_dist <= 5:
                    # Pivota yakın, ortada kal, pivotu gölgeleme
                    mid = (upper_line + lower_line) / 2
                    c = mid + np.random.randn() * 0.15
                else:
                    mid = (upper_line + lower_line) / 2
                    c = mid + np.random.randn() * 0.3
                
                c = max(lower_line + 0.2, min(upper_line - 0.2, c))
        
        # High/low - pivot barlarında daha belirgin
        h = c + abs(np.random.randn() * 0.05) + 0.05
        l = c - abs(np.random.randn() * 0.05) - 0.05
        o = c + np.random.randn() * 0.03
        
        close.append(c)
        high.append(h)
        low.append(l)
        open_.append(o)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000000, 4000000, n_bars)
    }, index=dates)
    
    return df

print("=== BAYRAK TESTİ ===\n")

# Test 1: Boğa bayrağı
print("Test 1: Boğa bayrağı")
df_bull = create_bull_flag(250)
print(f"  Data: {len(df_bull)} bar, son close {df_bull['close'].iloc[-1]:.2f}")

# Direkleri kontrol et
from patterns import calculate_atr, find_pivots, find_pole
from config import get_profile_params
params = get_profile_params("Dengeli")
atr = calculate_atr(df_bull, 14)
high_pivots, low_pivots = find_pivots(df_bull, params['pivot_len'])
print(f"  Pivot: high={len(high_pivots)} low={len(low_pivots)}")

# En son high pivot için direk ara
if high_pivots:
    last_high = high_pivots[-1]
    pole = find_pole(df_bull, atr, high_pivots, low_pivots, last_high['bar'], last_high['price'], 1, params)
    print(f"  Direk (son high için): valid={pole.valid} dir={pole.direction} quality={pole.quality:.1f} mag={pole.magnitude} eff={pole.efficiency}")

# Bayrak ara
candidate, logs = find_best_flag_candidate(df_bull, profile="Dengeli", verbose=True)
print(f"  {logs[0]}")
for log in logs[1:10]:
    print(f"    {log}")

if candidate:
    print(f"  ✅ BULUNDU: {candidate.pattern_type} kalite {candidate.raw_quality:.1f}")
    print(f"     Direk: {candidate.pole_start_bar}->{candidate.pole_end_bar} mag {candidate.pole_magnitude:.2f} eff {candidate.pole_efficiency:.2f}")
    print(f"     Depth: {candidate.correction_depth:.2f} DurationRatio: {candidate.duration_ratio:.2f} HeightRatio: {candidate.consolidation_height_ratio:.2f}")
else:
    print("  ❌ Bayrak bulunamadı")

print("\nTest 2: Random data (bayrak olmamalı)")
from patterns import create_mock_data
df_random = create_mock_data(250)
cand_r, logs_r = find_best_flag_candidate(df_random, profile="Dengeli", verbose=False)
print(f"  {logs_r[0]}")
if cand_r:
    print(f"  Bulundu (false positive olabilir): {cand_r.pattern_type} {cand_r.raw_quality:.1f}")
else:
    print("  Bayrak yok (beklendiği gibi)")
