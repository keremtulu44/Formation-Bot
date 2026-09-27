"""
Breakout lifecycle testi — Pine-birebir motor ile
Motor artık adayı kendisi buluyor ve kırılım anında kalite/sınırları DONDURUYOR.
Retest değerlendirmesi kırılım ÇİZGİSİ (pivotlar) üzerinden yapılır; dışarıdan
gelen yeni adayla karıştırma hatası (eski A3 bug'ı) mimari olarak imkânsız.
"""

import pandas as pd
import numpy as np
from patterns import ArgentEngine
from test_triangle import create_perfect_symmetrical_triangle, create_ascending_triangle


def add_bar(df, o, h, l, c, volume=2000000):
    new_row = pd.DataFrame([{'open': o, 'high': h, 'low': l, 'close': c, 'volume': volume}],
                           index=[df.index[-1] + pd.Timedelta(hours=1)])
    return pd.concat([df, new_row])


def step(eng, df):
    snap = eng.process(df)
    return snap


print("=== BREAKOUT LIFECYCLE TESTİ (Pine-birebir motor) ===\n")

# 1. Simetrik üçgen oluştur
print("1. Formasyon oluşturuluyor...")
df = create_perfect_symmetrical_triangle(140)
eng = ArgentEngine(profile="Dengeli")
snap = eng.process(df)
print(f"   {snap.log}")
if snap.active:
    a = snap.active
    print(f"   Formasyon: {a.pattern_type} kalite {snap.effective_quality:.0f}")
    print(f"   Üst: {a.upper_now:.2f} Alt: {a.lower_now:.2f}")
    upper = a.upper_now
else:
    # Canlı değilse seride ilk tespiti ara (formasyon kurulup kırılmış olabilir)
    from patterns import scan_for_first_detection
    hit, _ = scan_for_first_detection(df)
    if hit is None:
        print("   ❌ Hiç formasyon oluşmadı, test iptal")
        exit()
    bar, a, q = hit
    print(f"   ⚠️ Son bar canlı değil; ilk tespit bar {bar}: {a.pattern_type} q{q:.0f}")
    upper = a.upper_now

# 2. Güçlü yukarı kırılım mumu
print("\n2. Yukarı kırılım mumu ekleniyor...")
df = add_bar(df, upper - 0.2, upper + 2.0, upper - 0.5, upper + 1.5)
snap = step(eng, df)
print(f"   State: {snap.state} Dir: {snap.break_dir} - {snap.log}")

# 3. Teyit mumu (ikinci kapanış üstte)
print("\n3. Teyit mumu ekleniyor (ikinci dışarıda kapanış)...")
last_upper = snap.active.upper_now if snap.active else upper
df = add_bar(df, last_upper + 0.5, last_upper + 2.5, last_upper + 0.2, last_upper + 2.0, 2500000)
snap = step(eng, df)
print(f"   State: {snap.state} Dir: {snap.break_dir} - {snap.log}")

# 4. Retest mumu (sınıra dokunuş + üstte tutunma)
print("\n4. Retest mumu ekleniyor (sınıra dönüş)...")
boundary_now = snap.active.upper_now if snap.active else upper
df = add_bar(df, boundary_now + 0.8, boundary_now + 1.2, boundary_now - 0.3, boundary_now + 0.5, 1500000)
snap = step(eng, df)
print(f"   State: {snap.state} Dir: {snap.break_dir} - {snap.log}")

# 5. Tutunma barları (RETEST_OK -> COMPLETED)
print("\n5. Retest sonrası tutunma...")
for i in range(5):
    base = (snap.active.upper_now if snap.active else upper) + 0.6 + i * 0.2
    df = add_bar(df, base - 0.1, base + 0.5, base - 0.3, base + 0.2, 1200000)
    snap = step(eng, df)
    print(f"   Bar {i+1}: State: {snap.state} - {snap.log}")
    if snap.state == "FORMASYON_TAMAMLANDI":
        break

print(f"\n=== TEST BİTTİ ===")
print(f"Son state: {snap.state}")
ok_flow = snap.state in ("FORMASYON_TAMAMLANDI", "RETEST_BASARILI", "RETEST_BEKLENIYOR", "RETEST_EDILIYOR")
print("Akış sağlıklı:" , "✅" if ok_flow else "❌ (beklenen: teyit/retest/tamamlandı hattı)")


# === BAŞARISIZ KIRILIM TESTİ ===
print("\n\n=== BAŞARISIZ KIRILIM TESTİ ===\n")
df2 = create_ascending_triangle(140)
eng2 = ArgentEngine(profile="Dengeli")
snap2 = eng2.process(df2)
print(f"Formasyon: {snap2.log}")

if snap2.active:
    upper2 = snap2.active.upper_now
    # Kırılım
    df2 = add_bar(df2, upper2 - 0.2, upper2 + 1.0, upper2 - 0.5, upper2 + 0.8)
    snap2 = step(eng2, df2)
    print(f"Kırılım: State: {snap2.state} - {snap2.log}")
    # İçeri dönüş
    upper3 = snap2.active.upper_now if snap2.active else upper2
    df2 = add_bar(df2, upper3 + 0.5, upper3 + 0.6, upper3 - 1.5, upper3 - 1.0, 1000000)
    snap2 = step(eng2, df2)
    print(f"İçeri dönüş: State: {snap2.state} - {snap2.log}")
    print("Beklenen: KIRILIM_ADAYI/DENEMESI sonrası BASARISIZ_KIRILIM ->",
          "✅" if snap2.state == "BASARISIZ_KIRILIM" else "⚠️ " + snap2.state)
else:
    print("Aktif formasyon yok, fail-case testi atlandı")
