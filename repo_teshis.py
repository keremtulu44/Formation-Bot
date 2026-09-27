"""
Repo.teshis - Dökümana (FORMASYON_MANTIGI.md / Pine davranışı) karşı hızlı sapma teşhisi
Sadece okur, hiçbir şeyi değiştirmez.
"""
import pandas as pd
import numpy as np
from data import StockDequeManager
from patterns import (find_best_triangle_candidate, find_best_flag_candidate,
                      calculate_atr, find_pivots, f_build_triangle_candidate)
from config import get_profile_params

mgr = StockDequeManager(data_dir="./bot_data")
params = get_profile_params("Dengeli")

print("=" * 70)
print("TEŞHİS 1: Tespittte fiyat formasyonun İÇİNDE mi? (Pine'da kontol var)")
print("=" * 70)
outside_cnt = 0
total_cnt = 0
stale_cnt = 0
examples = []
for stock in ["THYAO", "GARAN", "AKBNK", "ASELS", "SISE", "FROTO", "SASA", "TUPRS", "ALARK", "KCHOL"]:
    df = mgr.to_dataframe(stock)
    if df is None or len(df) < 100:
        continue
    cand, _ = find_best_triangle_candidate(df, profile="Dengeli", verbose=False)
    if cand and cand.valid:
        total_cnt += 1
        close = df['close'].iloc[-1]
        upper, lower = cand.upper_now, cand.lower_now
        width_now = upper - lower
        outside = not (lower <= close <= upper)
        # son pivot ile tespit barı arası mesafe (recency)
        staleness = (len(df) - 1) - cand.end_bar
        if outside:
            outside_cnt += 1
        if staleness > 10:
            stale_cnt += 1
        examples.append(f"  {stock}: {cand.pattern_type} q{cand.raw_quality:.0f} close={close:.2f} "
                        f"aralık=[{lower:.2f},{upper:.2f}] {'DIŞARIDA!' if outside else 'içeride'} "
                        f"sonPivotTazeliği={staleness} bar")
for e in examples:
    print(e)
print(f"\n--> {total_cnt} tespitten {outside_cnt} tanesinde fiyat formasyon DIŞINDA (Pine'da böyle aday seçilmez)")
print(f"--> {stale_cnt} tanesinde son pivot 10+ bar eski (recency priority Pine'da var, Python'da YOK)")

print()
print("=" * 70)
print("TEŞHİS 2: İhlal taraması hangi aralığı tarıyor?")
print("=" * 70)
df = mgr.to_dataframe("THYAO")
cand, _ = find_best_triangle_candidate(df, profile="Dengeli", verbose=False)
if cand:
    print(f"THYAO: start_bar={cand.start_bar} end_bar={cand.end_bar} current_bar={len(df)-1}")
    print(f"Taranan aralık: {cand.start_bar}..{cand.end_bar} ({cand.historical_scanned_bars} bar)")
    unscanned = (len(df)-1) - cand.end_bar
    print(f"TaranMAYAN kuyruk: {unscanned} bar (döküman §6 S1 kuralı: son pivot ile bar_index-1 arası DA taranmalı)")
    print(f"selection_score alanı: {cand.selection_score} (hiç hesaplanmıyor - döküman §7 eksik)")

print()
print("=" * 70)
print("TEŞHİS 3: Mükemmel simetrik üçgen yanlış sınıflanıyor mu?")
print("=" * 70)
np.random.seed(123)
n = 200
mid, sw, ew = 100, 20, 5
rows = []
for i in range(n):
    p = i / n
    w = sw - (sw - ew) * p
    up, lo = mid + w/2, mid - w/2
    if i % 20 == 10:
        c = up - 0.2
    elif i % 20 == 0:
        c = lo + 0.2
    else:
        c = mid
    c = max(lo + 0.1, min(up - 0.1, c))
    rows.append((c + 0.05, c + 0.15, c - 0.15, c))
df_sym = pd.DataFrame(rows, columns=['open', 'high', 'low', 'close'],
                      index=pd.date_range("2025-01-01", periods=n, freq='h'))
df_sym['volume'] = 1000
cand, logs = find_best_triangle_candidate(df_sym, profile="Dengeli", verbose=False)
if cand:
    atr = calculate_atr(df_sym, 14).iloc[-1]
    us_n = cand.upper_slope / atr
    ls_n = cand.lower_slope / atr
    print(f"Sınıf: {cand.pattern_type} (GERÇEK: Simetrik Üçgen)")
    print(f"upperSlopeNorm={us_n:+.4f} (negatif olmalı)  lowerSlopeNorm={ls_n:+.4f} (pozitif olmalı)")
    print(f"flatTol={params['flat_slope_norm_tol']} -> yatay sayılan eğimler gerçekte yönlü olabilir")
    print(f"contraction={cand.contraction*100:.0f}% progress={cand.progress*100:.0f}%")
else:
    print("Hiç aday bulunamadı (mükemmel üçgende 0/1 - yanlış negatif)")

print()
print("=" * 70)
print("TEŞHİS 4: Kalite skoru başarı ile korele mi? (forward mini-test, 1h)")
print("=" * 70)
results = []
for stock in ["THYAO","AKBNK","KCHOL","SAHOL","BIMAS","ASELS","FROTO","TOASO","PETKM","PGSUS",
              "SASA","GUBRF","EKGYO","HALKB","TCELL","TAVHL","DOHOL","ALARK","SISE","TUPRS"]:
    df_full = mgr.to_dataframe(stock)
    if df_full is None or len(df_full) < 360:
        continue
    df_det = df_full.iloc[:340]
    fut = df_full.iloc[340:360]
    for cand_df, finder in ((df_det, find_best_triangle_candidate),):
        cand, _ = finder(cand_df, profile="Dengeli", verbose=False)
    cand_flag, _ = find_best_flag_candidate(df_det, profile="Dengeli", verbose=False)
    best = None
    if cand and cand.valid: best = cand
    if cand_flag and cand_flag.valid and (best is None or cand_flag.raw_quality > best.raw_quality):
        best = cand_flag
    if not best:
        continue
    atr_d = calculate_atr(df_full, 14).iloc[339]
    buf = atr_d * params['break_atr_mult']
    bdir, bprice = 0, None
    for i in range(len(fut)):
        c = fut['close'].iloc[i]
        if c > best.upper_now + buf: bdir, bprice = 1, c; break
        if c < best.lower_now - buf: bdir, bprice = -1, c; break
    if bdir == 0:
        results.append((stock, best.pattern_type, best.raw_quality, None, None)); continue
    match = (best.classic_dir == 0) or (bdir == best.classic_dir)
    after = df_full.iloc[340+i:360]
    move = ((after['high'].max() - bprice) if bdir == 1 else (bprice - after['low'].min())) / atr_d
    results.append((stock, best.pattern_type, best.raw_quality, match and move >= 1.0, bdir))
ok = [r for r in results if r[3] is not None]
print(f"{'Hisse':8} {'Tip':18} {'Q':5} {'Sonuç':8} {'Kırılım':8}")
for r in results:
    sonuc = {True: 'BAŞARILI', False: 'BAŞARISIZ', None: 'kırılım yok'}[r[3]]
    yon = {1: 'yukarı', -1: 'aşağı', 0: '-'}[r[4] or 0]
    print(f"{r[0]:8} {r[1]:18} {r[2]:<5.0f} {sonuc:8} {yon:8}")
hi = [r for r in ok if r[2] >= 80]; lo = [r for r in ok if r[2] < 80]
print(f"\nQ>=80: {len(hi)} pattern, {sum(1 for r in hi if r[3])} başarılı")
print(f"Q< 80: {len(lo)} pattern, {sum(1 for r in lo if r[3])} başarılı")
