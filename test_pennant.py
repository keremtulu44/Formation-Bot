"""
Falama (pennant) testi — Pine v0.4.6 uyumlu sentetik veri.

Flama = güçlü DİREK + DARALAN (simetrik üçgen gibi) konsolidasyon.
Bayraktan farkı: kanal paralel değil, sıkışıyor.

Pine koşulları (FORMASYON_MANTIGI.md §4):
  standard (Simetrik Üçgen): depth 0.06-0.70, heightRatio<=0.46, durationRatio<=2.80,
      formedDuration <= maxConsolidationBars, eff < pole.efficiency + 0.08,
      kalite >= minSpecializedQuality
  inclined (Yükselen/Alçalan Üçgen): pole kalitesi >= min+10, depth 0.08-0.60,
      heightRatio<=0.40, durationRatio<=2.40, süre <= maxConsolidation*0.85,
      eff < pole.efficiency, kalite >= minSpecialized+8

Çalıştırma:  python3 test_pennant.py
"""

import warnings
import numpy as np
import pandas as pd

from patterns import ArgentEngine
from patterns.pivots import find_pivots

warnings.filterwarnings("ignore")


def _df_yap(close, start="2026-01-05 09:30", freq="h"):
    high = [c + 0.15 for c in close]
    low = [c - 0.15 for c in close]
    open_ = [c - 0.02 for c in close]
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": [3_000_000] * len(close)},
                      index=pd.date_range(start=start, periods=len(close), freq=freq, tz="Europe/Istanbul"))
    return df


def create_bull_pennant(n_bars=64):
    """
    Boğa flaması (Pine-uyumlu):
    - bar 3-8: dip 88 (low pivot adayı)
    - bar 9-20: güçlü yukarı DİREK (~3.2 TL/bar, ~3.8 ATR)
    - bar 21+: DARALAN kanal (üst 126->120, alt 122->118.5) = simetrik üçgen gibi
      pivotlar 8 barda bir döngü (üst pos==6, alt pos==2)
    """
    np.random.seed(21)
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
            c = 88.0                      # DİP (direk başlangıcı / low pivot)
        elif i <= 20:
            c = 88.0 + (i - 8) * (38.0 / 12.0)   # DİREK: bar 20'de ~126
        else:
            p_i = i - 20                  # flama konsolidasyonu
            # DARALAN (üçgen gibi) ama YAVAŞ: üst aşağı, alt yukarı.
            # Hızlı daralma (0.60/0.42) 4 barda üst<alt yapıp geometriyi çökertiyordu.
            # Ölçüm: 0.06/0.03 ile 28 barda genişlik 4.0 -> 1.6 (daralma %60, Pine eşiği
            # contraction>=%25 ve heightRatio<=0.46 için uygun).
            upper_line = 126.0 - p_i * 0.06
            lower_line = 122.0 + p_i * 0.03
            pos = p_i % 8
            if pos == 6:
                c = upper_line - 0.05     # üst pivot
            elif pos == 2:
                c = lower_line + 0.05     # alt pivot
            else:
                c = (upper_line + lower_line) * 0.5
        close.append(c + np.random.randn() * 0.02)
    return _df_yap(close)


def create_bear_pennant(n_bars=64):
    """Ayı flaması: aşağı direk + yukarı daralan konsolidasyon (fiyat aynası)."""
    df_bull = create_bull_pennant(n_bars)
    ayna = df_bull["close"].max() + df_bull["close"].min() - df_bull["close"]
    return _df_yap(list(ayna.values))


def seride_tespit_bul(df, tip):
    """Seriyi bara bara besleyip istenen tipin ilk tespit edildiği anı bul."""
    eng = ArgentEngine(profile="Dengeli")
    for i in range(30, len(df) + 1):
        snap = eng.process(df.iloc[:i])
        if snap.active and snap.active.pattern_type == tip:
            return i, snap
    return None, None


print("=== FLAMA TESTİ (Pine v0.4.6 uyumlu) ===\n")

print("Test 1: Boğa flaması (direk + daralan simetrik üçgen)")
df_bull = create_bull_pennant(48)
print(f"  Veri: {len(df_bull)} bar, son close {df_bull['close'].iloc[-1]:.2f}")
eng = ArgentEngine(profile="Dengeli")
snap = eng.process(df_bull)
if snap.active:
    print(f"  Son bar canlı: {snap.active.pattern_type} kalite {snap.active.raw_quality:.1f}")
bar, snap_b = seride_tespit_bul(df_bull, "Boğa Flaması")
if bar:
    print(f"  ✅ SERİDE TESPİT: bar {bar}'de Boğa Flaması kalite {snap_b.active.raw_quality:.1f}")
    if snap_b.active.has_pole:
        print(f"     Direk: {'yukarı' if snap_b.active.pole_dir == 1 else 'aşağı'} yönü, "
              f"{snap_b.active.pole_duration} bar, büyüklük "
              f"{snap_b.active.pole_magnitude:.2f} TL")
else:
    print("  ❌ Boğa flaması bulunamadı - Pine eşiklerine göre reddedildi")
    print(f"     Son durum: {snap.log}")

print("\nTest 2: Ayı flaması (fiyat aynası)")
df_bear = create_bear_pennant(48)
print(f"  Veri: {len(df_bear)} bar, son close {df_bear['close'].iloc[-1]:.2f}")
bar2, snap2 = seride_tespit_bul(df_bear, "Ayı Flaması")
if bar2:
    print(f"  ✅ SERİDE TESPİT: bar {bar2}'de Ayı Flaması kalite {snap2.active.raw_quality:.1f}")
else:
    print("  ❌ Ayı flaması bulunamadı")
    print(f"     Son durum: {snap2.log if snap2 else 'yok'}")

print("\nTest 3: Random veri (flama OLMAMALI)")
np.random.seed(99)
random_close = [100.0]
for _ in range(80):
    random_close.append(random_close[-1] * (1 + np.random.randn() * 0.01))
df_rnd = _df_yap(random_close)
eng_r = ArgentEngine(profile="Dengeli")
bulunan = set()
for i in range(30, len(df_rnd) + 1):
    s = eng_r.process(df_rnd.iloc[:i])
    if s.active and "Flama" in s.active.pattern_type:
        bulunan.add(s.active.pattern_type)
if bulunan:
    print(f"  ⚠️ YANLIŞ POZİTİF: {bulunan}")
else:
    print("  ✅ Flama yok (beklendiği gibi)")

print("\nTest 4: Direk yoksa flama olmamalı (sadece daralan üçgen)")
# Direk olmadan düz daralan üçgen: bayrak/flama için direk şart, üçgen olabilir
np.random.seed(5)
close = []
for i in range(70):
    if i <= 4:
        c = 100.0
    else:
        p = i - 4
        upper = 104.0 - p * 0.20
        lower = 96.0 + p * 0.16
        pos = p % 8
        c = upper - 0.05 if pos == 6 else lower + 0.05 if pos == 2 else (upper + lower) * 0.5
    close.append(c + np.random.randn() * 0.02)
df_np = _df_yap(close)
bar4, snap4 = seride_tespit_bul(df_np, "Boğa Flaması")
if bar4:
    print(f"  ⚠️ Direksiz flama bulundu (bar {bar4}) - pole olmadan flama kurulmamalı")
else:
    print("  ✅ Direksiz flama yok (Pine kuralı: direk şart)")
