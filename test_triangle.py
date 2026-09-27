"""
Üçgen formasyon testi - mock data ile
Gerçek üçgen oluşturup tespit ediyor mu bakalım
"""

import pandas as pd
import numpy as np
from patterns import (find_best_triangle_candidate, create_mock_data, calculate_atr,
                      find_pivots, scan_for_first_detection)
from config import PROFILE_PARAMS


def raporla(df, ad, verbose_logs=None):
    """Son bar canlı formasyonu; yoksa serideki İLK tespiti raporlar.
    Lifecycle motorunda formasyon kırılabilir (bu bir BAŞARIdır) — o yüzden
    'tespit edildi mi?' sorusu seri boyunca sorulur."""
    cand, logs = find_best_triangle_candidate(df, profile="Dengeli", verbose=True)
    if cand:
        print(f"  ✅ CANLI: {cand.pattern_type} kalite {cand.raw_quality:.1f}")
        print(f"     Üst: {cand.upper_now:.2f} Alt: {cand.lower_now:.2f} Daralma: "
              f"{cand.contraction*100 if cand.contraction is not None else 0:.0f}%")
        return cand
    hit, snap = scan_for_first_detection(df, families=("Üçgen", "Kama"))
    if hit:
        bar, c, q = hit
        print(f"  ✅ SERİDE TESPİT: bar {bar}'de {c.pattern_type} q{q:.0f} (o anki state: {snap.state}; "
              f"formasyon sonrasında kırılmış olabilir — bu radar için başarıdır)")
        return c
    print(f"  ❌ Formasyon bulunamadı (son state {snap.state})")
    if verbose_logs:
        for log in (verbose_logs[:3] if isinstance(verbose_logs, list) else []):
            print(f"   {log}")
    return None

def create_perfect_symmetrical_triangle(n_bars=200):
    """
    Mükemmel simetrik üçgen oluştur
    - Üst trend aşağı, alt trend yukarı
    - Daralıyor
    - Temaslar net
    """
    np.random.seed(123)
    
    # Başlangıç genişliği 20, bitiş 5
    start_width = 20
    end_width = 5
    
    # Orta çizgi 100 civarı
    mid = 100
    
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    
    close = []
    high = []
    low = []
    open_ = []
    
    for i in range(n_bars):
        # İlerleme 0-1
        progress = i / n_bars
        
        # Genişlik daralıyor
        current_width = start_width - (start_width - end_width) * progress
        
        # Üst ve alt sınır
        upper = mid + current_width/2
        lower = mid - current_width/2
        
        # Biraz noise ile fiyat ortada dolaşsın ama sınırlara değsin
        # Her 20 barda bir pivot olacak şekilde
        if i % 20 == 10:
            # Üst pivot - üst sınıra yakın
            c = upper - np.random.uniform(0, 0.5)
        elif i % 20 == 0:
            # Alt pivot - alt sınıra yakın
            c = lower + np.random.uniform(0, 0.5)
        else:
            # Ortada
            c = mid + np.random.randn() * 1.5
        
        # Sınır dışına taşmasın (ihlal olmasın)
        c = max(lower + 0.1, min(upper - 0.1, c))
        
        h = c + abs(np.random.randn() * 0.3)
        l = c - abs(np.random.randn() * 0.3)
        o = c + np.random.randn() * 0.2
        
        # Sınır kontrol
        h = min(h, upper + 0.5)
        l = max(l, lower - 0.5)
        
        close.append(c)
        high.append(h)
        low.append(l)
        open_.append(o)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(100000, 1000000, n_bars)
    }, index=dates)
    
    return df

def create_ascending_triangle(n_bars=200):
    """Yükselen üçgen - üst yatay, alt yukarı"""
    np.random.seed(456)
    
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    
    upper_level = 110  # Yatay üst
    lower_start = 90
    lower_end = 105  # Yukarı
    
    close = []
    high = []
    low = []
    open_ = []
    
    for i in range(n_bars):
        progress = i / n_bars
        lower = lower_start + (lower_end - lower_start) * progress
        upper = upper_level
        
        if i % 25 == 12:
            c = upper - np.random.uniform(0, 0.3)  # Üst temas
        elif i % 25 == 0:
            c = lower + np.random.uniform(0, 0.3)  # Alt temas
        else:
            c = (upper + lower)/2 + np.random.randn() * 1.0
        
        c = max(lower + 0.1, min(upper - 0.1, c))
        h = min(c + abs(np.random.randn()*0.3), upper + 0.3)
        l = max(c - abs(np.random.randn()*0.3), lower - 0.3)
        o = c + np.random.randn()*0.2
        
        close.append(c)
        high.append(h)
        low.append(l)
        open_.append(o)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(100000, 1000000, n_bars)
    }, index=dates)
    
    return df

print("=== ÜÇGEN TESTİ ===\n")

# Test 1: Random data (formasyon yok bekleniyor)
print("Test 1: Random data (formasyon olmamalı)")
df_random = create_mock_data(200)
candidate, logs = find_best_triangle_candidate(df_random, profile="Dengeli", verbose=True)
print(logs[0])
for log in logs[1:5]:
    print(f"  {log}")
if candidate:
    print(f"  BULUNDU: {candidate.pattern_type} kalite {candidate.raw_quality:.1f}")
else:
    print("  Formasyon yok (beklendiği gibi)")
print()

# Test 2: Simetrik üçgen (formasyon olmalı)
print("Test 2: Simetrik üçgen (formasyon OLMALI)")
df_sym = create_perfect_symmetrical_triangle(200)
candidate = raporla(df_sym, "simetrik")
if candidate and candidate.progress is not None:
    print(f"     Apex: {candidate.apex_bar} Progress: {candidate.progress*100:.0f}%")
print()

# Test 3: Yükselen üçgen
print("Test 3: Yükselen üçgen")
df_asc = create_ascending_triangle(200)
candidate = raporla(df_asc, "yükselen")
print()

# Test 4: Farklı profiller
print("Test 4: Profil karşılaştırması (simetrik üçgen)")
for profile in ["Hassas", "Dengeli", "Seçici"]:
    cand, _ = find_best_triangle_candidate(df_sym, profile=profile, verbose=False)
    if cand:
        print(f"  {profile}: {cand.pattern_type} kalite {cand.raw_quality:.1f}")
    else:
        hit, _snap = scan_for_first_detection(df_sym, profile=profile, families=("Üçgen", "Kama"))
        if hit:
            bar, c, q = hit
            print(f"  {profile}: seri içinde bar {bar} ({c.pattern_type} q{q:.0f}), son bar canlı değil")
        else:
            print(f"  {profile}: Yok")
