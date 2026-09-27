"""
Falama (pennant) testi — Pine v0.4.6 uyumlu sentetik veri.

Flama = güçlü DİREK + DARALAN (üçgen gibi) konsolidasyon.
Bayraktan farkı: kanal paralel değil, sıkışıyor.

Pine koşulları (FORMASYON_MANTIGI.md §4):
  standard (Simetrik Üçgen geometrisi): depth 0.06-0.70, heightRatio<=0.46, durationRatio<=2.80,
      formedDuration <= maxConsolidationBars, eff < pole.efficiency + 0.08,
      kalite >= minSpecializedQuality
  inclined (Yükselen/Alçalan Üçgen geometrisi): pole kalitesi >= min+10, depth 0.08-0.60,
      heightRatio<=0.40, durationRatio<=2.40, süre <= maxConsolidation*0.85,
      eff < pole.efficiency, kalite >= minSpecialized+8

Ölçüm notu (2026-09-27): kanal eğimleri ATR'ye göre normalize edilir
(upper_slope_norm = eğim / geometry_atr). ATR ~0.3 olan sentetik veride
-0.06/+0.06 eğimleri "Simetrik Üçgen"i, -0.001/+0.15 ise "Yükselen Üçgen"i üretir.
Standart flama YALNIZ Simetrik Üçgen geometrisinde kurulur (Pine tablo mantığı).

Çalıştırma:  python3 test_pennant.py
"""

import warnings
import numpy as np
import pandas as pd

from patterns import ArgentEngine

warnings.filterwarnings("ignore")


def _df_yap(close, start="2026-01-05 09:30", freq="h"):
    high = [c + 0.15 for c in close]
    low = [c - 0.15 for c in close]
    open_ = [c - 0.02 for c in close]
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": [3_000_000] * len(close)},
                      index=pd.date_range(start=start, periods=len(close), freq=freq, tz="Europe/Istanbul"))
    return df


def _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, pole_bars=12, asagi=False,
                     seed=21):
    """
    Direk + daralan kanalli flama verisi.

    - bar 0-8: dip 88 (low pivot adayi)
    - bar 8-8+pole_bars: güçlü DIREK (asagi=False: 88->126 / True: 128->88)
    - sonrasi: DARALAN kanal (üst 126 + p*upper_k, alt 122 + p*lower_k)

    Geometri secimi (ölçümlü):
      upper_k=-0.06, lower_k=+0.06 -> Simetrik Üçgen  (standart flama)
      upper_k=-0.001, lower_k=+0.15 -> Yükselen Üçgen (eğik flama)
      upper_k=-0.06, lower_k=-0.03 -> Alçalan Kema    (flama OLMAZ)
    """
    np.random.seed(seed)
    close = []
    for i in range(n_bars):
        if i <= 4:
            c = 92.0
        elif i == 5:
            c = 90.5 if not asagi else 108.0
        elif i == 6:
            c = 89.2 if not asagi else 118.0
        elif i == 7:
            c = 88.4 if not asagi else 124.0
        elif i == 8:
            c = 88.0 if not asagi else 128.0   # DİP (boğa) / ZİRVE (ayı) = direk başlangıcı
        elif i <= 8 + pole_bars:
            adim = (38.0 if not asagi else -40.0) / pole_bars
            c = (88.0 if not asagi else 128.0) + (i - 8) * adim
        else:
            p_i = i - 8 - pole_bars
            if asagi:
                upper_line = 95.0 + p_i * upper_k
                lower_line = 89.0 + p_i * lower_k
            else:
                upper_line = 126.0 + p_i * upper_k
                lower_line = 122.0 + p_i * lower_k
            pos = p_i % 8
            if pos == 6:
                c = upper_line - 0.05     # üst pivot
            elif pos == 2:
                c = lower_line + 0.05     # alt pivot
            else:
                c = (upper_line + lower_line) * 0.5
        close.append(c + np.random.randn() * 0.02)
    return _df_yap(close)


def create_bull_pennant(n_bars=48):
    """Boğa flaması: yukarı direk + simetrik daralan kanal (standart varyant)."""
    return _kanalli_pennant(n_bars=n_bars, upper_k=-0.06, lower_k=0.06, asagi=False, seed=21)


def create_bull_inclined_pennant(n_bars=48):
    """Boğa eğik flaması: yukarı direk + yükselen üçgen kanalı (eğik varyant)."""
    return _kanalli_pennant(n_bars=n_bars, upper_k=-0.001, lower_k=0.15, asagi=False, seed=21)


def create_bear_pennant(n_bars=48):
    """Ayı flaması: boğa flamasının fiyat aynası (aşağı direk + simetrik kanal)."""
    df_bull = _kanalli_pennant(n_bars=n_bars, upper_k=-0.06, lower_k=0.06,
                               asagi=False, seed=21)
    ayna = df_bull["close"].max() + df_bull["close"].min() - df_bull["close"]
    return _df_yap(list(ayna.values))


def create_wedge_like(n_bars=48):
    """Kema benzeri: direk + iki eğimi aynı yönde kanal -> flama OLMAMALI."""
    return _kanalli_pennant(n_bars=n_bars, upper_k=-0.06, lower_k=-0.03, asagi=False, seed=23)


def seride_tespit_bul(df, tip):
    """Seriyi bara bara besleyip istenen tipin ilk tespit edildiği anı bul."""
    eng = ArgentEngine(profile="Dengeli")
    for i in range(30, len(df) + 1):
        snap = eng.process(df.iloc[:i])
        if snap.active and snap.active.pattern_type == tip:
            return i, snap
    return None, None


def _direk_satiri(a):
    if not a.has_pole:
        return "     Direk: yok"
    return ("     Direk: %s yönü, %d bar, büyüklük %.2f TL, direk kalitesi %.1f" % (
        "yukarı" if a.pole_dir == 1 else "aşağı", a.pole_duration, a.pole_magnitude or 0.0,
        a.pole_quality))


print("=== FLAMA TESTİ (Pine v0.4.6 uyumlu) ===\n")

print("Test 1: Boğa flaması standart (direk + simetrik üçgen kanalı)")
df_bull = create_bull_pennant(48)
print(f"  Veri: {len(df_bull)} bar, son close {df_bull['close'].iloc[-1]:.2f}")
eng = ArgentEngine(profile="Dengeli")
snap = eng.process(df_bull)
if snap.active:
    print(f"  Son bar canlı: {snap.active.pattern_type} kalite {snap.active.raw_quality:.1f}")
bar, snap_b = seride_tespit_bul(df_bull, "Boğa Flaması")
if bar:
    a = snap_b.active
    print(f"  ✅ SERİDE TESPİT: bar {bar}'de Boğa Flaması kalite {a.raw_quality:.1f}")
    print(f"     Pine varyantı: {a.specialized_variant or '-'}")
    print(_direk_satiri(a))
    assert a.specialized_variant == "Flama (standart)", a.specialized_variant
else:
    print("  ❌ Boğa flaması bulunamadı - Pine eşiklerine göre reddedildi")
    print(f"     Son durum: {snap.log}")

print("\nTest 2: Ayı flaması standart (aşağı direk + simetrik üçgen kanalı)")
df_bear = create_bear_pennant(48)
bar2, snap2 = seride_tespit_bul(df_bear, "Ayı Flaması")
if bar2:
    a = snap2.active
    print(f"  ✅ SERİDE TESPİT: bar {bar2}'de Ayı Flaması kalite {a.raw_quality:.1f}")
    print(f"     Pine varyantı: {a.specialized_variant or '-'}")
    print(_direk_satiri(a))
    assert a.specialized_variant == "Flama (standart)", a.specialized_variant
else:
    print("  ❌ Ayı flaması bulunamadı")
    print(f"     Son durum: {snap2.log if snap2 else 'yok'}")

print("\nTest 3: Eğik flama (yukarı direk + yükselen üçgen kanalı)")
df_incl = create_bull_inclined_pennant(48)
bar3, snap3 = seride_tespit_bul(df_incl, "Boğa Flaması")
if bar3:
    a = snap3.active
    print(f"  ✅ SERİDE TESPİT: bar {bar3}'de Boğa Flaması kalite {a.raw_quality:.1f}")
    print(f"     Pine varyantı: {a.specialized_variant or '-'}")
    print(_direk_satiri(a))
    assert a.specialized_variant == "Flama (eğik)", a.specialized_variant
else:
    print("  ⚠️ Eğik flama bulunamadı - geometri veya kalite eşiği tutmadı")
    print(f"     Son durum: {snap3.log if snap3 else 'yok'}")

print("\nTest 4: Kema benzeri kanal (direk + aynı yönde eğimler) -> flama OLMAMALI")
df_wedge = create_wedge_like(48)
bar4, snap4 = seride_tespit_bul(df_wedge, "Boğa Flaması")
if bar4:
    print(f"  ⚠️ Kema kanalında flama bulundu (bar {bar4}) - Pine'da flama üçgen ister")
else:
    print("  ✅ Kema kanalında flama yok (Pine kuralı: flama üçgen geometrisi ister)")

print("\nTest 5: Random veri (flama OLMAMALI)")
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

print("\nTest 6: Direk yoksa flama olmamalı (sadece daralan üçgen)")
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
bar6, snap6 = seride_tespit_bul(df_np, "Boğa Flaması")
if bar6:
    print(f"  ⚠️ Direksiz flama bulundu (bar {bar6}) - pole olmadan flama kurulmamalı")
else:
    print("  ✅ Direksiz flama yok (Pine kuralı: direk şart)")
