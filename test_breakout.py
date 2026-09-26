"""
Breakout lifecycle testi
- Formasyon oluştur
- Sonra kırılım mumu ekle
- Lifecycle nasıl ilerliyor gör
"""

import pandas as pd
import numpy as np
from patterns import find_best_triangle_candidate, PatternLifecycleManager, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED
from test_triangle import create_perfect_symmetrical_triangle, create_ascending_triangle

print("=== BREAKOUT LIFECYCLE TESTİ ===\n")

# 1. Simetrik üçgen oluştur
print("1. Formasyon oluşturuluyor...")
df = create_perfect_symmetrical_triangle(200)

manager = PatternLifecycleManager(profile="Dengeli")

# İlk tespit
candidate, logs = find_best_triangle_candidate(df, profile="Dengeli", verbose=False)
print(f"   {logs[0]}")

if candidate is None:
    print("   Formasyon yok, test iptal")
    exit()

print(f"   Formasyon: {candidate.pattern_type} kalite {candidate.raw_quality:.0f}")
print(f"   Üst: {candidate.upper_now:.2f} Alt: {candidate.lower_now:.2f}")

# Lifecycle başlat
state, break_dir, log = manager.update("THYAO", df, candidate)
print(f"   State: {state} - {log}")

# 2. Kırılım mumu ekle - yukarı kırılım
print("\n2. Yukarı kırılım mumu ekleniyor...")
# Son mumun üstüne çık
upper = candidate.upper_now
last_close = df['close'].iloc[-1]

# Güçlü yukarı kırılım mumu
new_bar = {
    'open': upper - 0.2,
    'high': upper + 2.0,
    'low': upper - 0.5,
    'close': upper + 1.5,  # Üstünde kapanış
    'volume': 2000000
}

# DataFrame'e ekle
new_index = df.index[-1] + pd.Timedelta(hours=1)
new_row = pd.DataFrame([new_bar], index=[new_index])
df_break = pd.concat([df, new_row])

print(f"   Eski close: {last_close:.2f} Yeni close: {new_bar['close']:.2f} Üst: {upper:.2f}")

# Yeni candidate ile update (aynı formasyon ama yeni bar)
candidate2, _ = find_best_triangle_candidate(df_break, profile="Dengeli", verbose=False)
if candidate2 is None:
    # Eski candidate'i kullan
    candidate2 = candidate

state, break_dir, log = manager.update("THYAO", df_break, candidate2)
print(f"   State: {state} Dir: {break_dir} - {log}")

# 3. Teyit mumu
print("\n3. Teyit mumu ekleniyor (ikinci kapanış üstte)...")
new_bar2 = {
    'open': upper + 0.5,
    'high': upper + 2.5,
    'low': upper + 0.2,
    'close': upper + 2.0,
    'volume': 2500000
}
new_index2 = df_break.index[-1] + pd.Timedelta(hours=1)
new_row2 = pd.DataFrame([new_bar2], index=[new_index2])
df_confirm = pd.concat([df_break, new_row2])

state, break_dir, log = manager.update("THYAO", df_confirm, candidate2)
print(f"   State: {state} Dir: {break_dir} - {log}")

# 4. Retest mumu
print("\n4. Retest mumu ekleniyor (sınıra dönüş)...")
new_bar3 = {
    'open': upper + 1.0,
    'high': upper + 1.2,
    'low': upper - 0.3,  # Sınıra değiyor
    'close': upper + 0.5,  # Üstte tutunuyor
    'volume': 1500000
}
new_index3 = df_confirm.index[-1] + pd.Timedelta(hours=1)
new_row3 = pd.DataFrame([new_bar3], index=[new_index3])
df_retest = pd.concat([df_confirm, new_row3])

state, break_dir, log = manager.update("THYAO", df_retest, candidate2)
print(f"   State: {state} Dir: {break_dir} - {log}")

# 5. Retest sonrası tutunma
print("\n5. Retest sonrası tutunma...")
for i in range(3):
    new_bar_hold = {
        'open': upper + 0.3 + i*0.2,
        'high': upper + 1.0 + i*0.2,
        'low': upper + 0.1 + i*0.1,
        'close': upper + 0.6 + i*0.2,
        'volume': 1200000
    }
    new_idx = df_retest.index[-1] + pd.Timedelta(hours=1) * (i+1)
    df_retest = pd.concat([df_retest, pd.DataFrame([new_bar_hold], index=[new_idx])])
    
    state, break_dir, log = manager.update("THYAO", df_retest, candidate2)
    print(f"   Bar {i+1}: State: {state} - {log}")
    if state == ST_COMPLETED:
        break

print("\n=== TEST BİTTİ ===")
print(f"Son state: {state}")

# Test 2: Başarısız kırılım
print("\n\n=== BAŞARISIZ KIRILIM TESTİ ===\n")
df2 = create_ascending_triangle(200)
manager2 = PatternLifecycleManager(profile="Dengeli")
cand2, _ = find_best_triangle_candidate(df2, profile="Dengeli")
print(f"Formasyon: {cand2.pattern_type if cand2 else 'Yok'}")

state, _, log = manager2.update("GARAN", df2, cand2)
print(f"State: {state} - {log}")

# Yukarı kırılım dene
upper2 = cand2.upper_now if cand2 else 110
new_bar_fail = {
    'open': upper2 - 0.2,
    'high': upper2 + 1.0,
    'low': upper2 - 0.5,
    'close': upper2 + 0.8,
    'volume': 2000000
}
df2_break = pd.concat([df2, pd.DataFrame([new_bar_fail], index=[df2.index[-1] + pd.Timedelta(hours=1)])])
state, _, log = manager2.update("GARAN", df2_break, cand2)
print(f"Kırılım: State: {state} - {log}")

# Sonra içeri dönüş
new_bar_inside = {
    'open': upper2 + 0.5,
    'high': upper2 + 0.6,
    'low': upper2 - 1.5,
    'close': upper2 - 1.0,  # İçeri döndü
    'volume': 1000000
}
df2_fail = pd.concat([df2_break, pd.DataFrame([new_bar_inside], index=[df2_break.index[-1] + pd.Timedelta(hours=1)])])
state, _, log = manager2.update("GARAN", df2_fail, cand2)
print(f"İçeri dönüş: State: {state} - {log}")
