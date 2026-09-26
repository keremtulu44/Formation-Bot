"""
Forward test - Gerçek BIST datasında pattern sonrası ne olmuş?
Manuel olmadan doğruluk ölçer.

Mantık:
- 360 bar var, son 20 barı gelecek gibi kullan
- 340 bar ile pattern tespit et
- Sonraki 20 barda (340-360) kırılım oldu mu? Klasik yöne uydu mu? Fiyat gitti mi?
"""

import pandas as pd
from data import StockDequeManager, resample_all_timeframes
from patterns import find_best_triangle_candidate, find_best_flag_candidate, calculate_atr
from config import BIST_30, get_profile_params
import logging

logging.basicConfig(level=logging.WARNING)

mgr = StockDequeManager(data_dir="./bot_data")
params = get_profile_params("Dengeli")

def check_forward(df_full, detection_bar=340, lookahead=20):
    """
    detection_bar'a kadar olan data ile pattern bul, sonraki lookahead barda ne olmuş bak
    Döner: (found, breakout_occurred, direction_match, price_moved, details)
    """
    if len(df_full) < detection_bar + lookahead:
        return None
    
    df_detect = df_full.iloc[:detection_bar].copy()
    df_future = df_full.iloc[detection_bar:detection_bar+lookahead].copy()
    
    if len(df_detect) < 50:
        return None
    
    # Pattern bul
    cand_tri, _ = find_best_triangle_candidate(df_detect, profile="Dengeli", verbose=False)
    cand_flag, _ = find_best_flag_candidate(df_detect, profile="Dengeli", verbose=False)
    
    best = None
    if cand_tri and cand_tri.valid:
        best = cand_tri
    if cand_flag and cand_flag.valid:
        if best is None or cand_flag.raw_quality > best.raw_quality:
            best = cand_flag
    
    if not best:
        return {'found': False}
    
    # ATR
    atr_series = calculate_atr(df_full, 14)
    atr_at_detect = atr_series.iloc[detection_bar-1] if detection_bar-1 < len(atr_series) else 1.0
    if pd.isna(atr_at_detect) or atr_at_detect <= 0:
        atr_at_detect = 1.0
    
    upper = best.upper_now
    lower = best.lower_now
    if upper is None or lower is None:
        return {'found': True, 'pattern': best.pattern_type, 'quality': best.raw_quality, 'breakout': False, 'reason': 'Üst/Alt None'}
    
    buffer = atr_at_detect * params['break_atr_mult']
    
    # Future'da kırılım var mı?
    breakout_dir = 0
    breakout_bar = None
    breakout_price = None
    
    for i in range(len(df_future)):
        idx = detection_bar + i
        if idx >= len(df_full):
            break
        close = df_full['close'].iloc[idx]
        if close > upper + buffer:
            breakout_dir = 1
            breakout_bar = i
            breakout_price = close
            break
        elif close < lower - buffer:
            breakout_dir = -1
            breakout_bar = i
            breakout_price = close
            break
    
    if breakout_dir == 0:
        return {
            'found': True,
            'pattern': best.pattern_type,
            'quality': best.raw_quality,
            'contraction': best.contraction,
            'upper': upper,
            'lower': lower,
            'breakout': False,
            'classic_dir': best.classic_dir,
        }
    
    # Klasik yöne uydu mu?
    classic_dir = best.classic_dir
    if classic_dir == 0:
        direction_match = True  # Simetrik nötr, her yön ok
    else:
        direction_match = (breakout_dir == classic_dir)
    
    # Fiyat ne kadar gitti? (ATR cinsinden)
    # Kırılımdan sonraki 10 barda max hareket
    future_after_break = df_full.iloc[detection_bar+breakout_bar:detection_bar+lookahead]
    if len(future_after_break) == 0:
        price_move_atr = 0
    else:
        if breakout_dir == 1:
            max_price = future_after_break['high'].max()
            price_move = max_price - breakout_price
        else:
            min_price = future_after_break['low'].min()
            price_move = breakout_price - min_price
        price_move_atr = price_move / atr_at_detect if atr_at_detect > 0 else 0
    
    return {
        'found': True,
        'pattern': best.pattern_type,
        'quality': best.raw_quality,
        'contraction': best.contraction,
        'upper': upper,
        'lower': lower,
        'breakout': True,
        'breakout_dir': breakout_dir,
        'breakout_bar': breakout_bar,
        'breakout_price': breakout_price,
        'classic_dir': classic_dir,
        'direction_match': direction_match,
        'price_move_atr': price_move_atr,
        'success': direction_match and price_move_atr >= 1.0,  # En az 1 ATR gittiyse başarılı
    }

print("=== FORWARD TEST - Gerçek BIST ===\n")
print("Her hisse için 340 bar ile tespit, sonraki 20 bar (340-360) forward kontrol")
print(f"BIST30: {len(BIST_30)} hisse\n")

results = []
for stock in BIST_30:
    df = mgr.to_dataframe(stock)
    if df is None or len(df) < 360:
        continue
    
    # 1h için test
    res = check_forward(df, detection_bar=340, lookahead=20)
    if res is None:
        continue
    if not res.get('found'):
        print(f"❌ {stock} 1h: Pattern yok (340 bar)")
        continue
    
    results.append((stock, '1h', res))
    
    if res['breakout']:
        status = "✅ KIRILIM" if res['success'] else "⚠️ KIRILIM ama zayıf"
        dir_str = "YUKARI" if res['breakout_dir']==1 else "AŞAĞI"
        match_str = "klasik yöne uydu" if res['direction_match'] else "klasik yöne UYMADI"
        print(f"{status} {stock} 1h {res['pattern']} q{res['quality']:.0f} -> {dir_str} bar+{res['breakout_bar']} {match_str} hareket {res['price_move_atr']:.1f} ATR")
    else:
        print(f"⏸️ {stock} 1h {res['pattern']} q{res['quality']:.0f} - 20 barda kırılım yok (sıkışma devam)")

print(f"\n=== ÖZET ===\n")
total = len(results)
if total == 0:
    print("Hiç pattern bulunamadı")
else:
    breakout_cnt = sum(1 for _,_,r in results if r.get('breakout'))
    success_cnt = sum(1 for _,_,r in results if r.get('success'))
    direction_match_cnt = sum(1 for _,_,r in results if r.get('direction_match'))
    
    print(f"Toplam pattern bulunan: {total}")
    print(f"Kırılım olan: {breakout_cnt} ({breakout_cnt/total*100:.0f}%)")
    print(f"Klasik yöne uyan: {direction_match_cnt}/{breakout_cnt} ({direction_match_cnt/max(breakout_cnt,1)*100:.0f}% of breakouts)")
    print(f"Başarılı (yön uydu + >=1 ATR hareket): {success_cnt}/{breakout_cnt} ({success_cnt/max(breakout_cnt,1)*100:.0f}% of breakouts)")
    print(f"Genel başarı (başarılı / toplam pattern): {success_cnt}/{total} ({success_cnt/total*100:.0f}%)")
    
    print(f"\nKaliteye göre:")
    for q_thresh in [70,75,80,85]:
        subset = [r for _,_,r in results if r['quality'] >= q_thresh]
        if not subset:
            continue
        succ = sum(1 for r in subset if r.get('success'))
        print(f"  Q>={q_thresh}: {len(subset)} pattern, {succ} başarılı ({succ/len(subset)*100:.0f}%)")
    
    print(f"\nPattern tipine göre başarı:")
    from collections import defaultdict
    by_type = defaultdict(list)
    for _,_,r in results:
        by_type[r['pattern']].append(r)
    for ptype, lst in by_type.items():
        succ = sum(1 for r in lst if r.get('success'))
        print(f"  {ptype}: {len(lst)} pattern, {succ} başarılı ({succ/len(lst)*100:.0f}%)")

print("\nForward test bitti - bu oran random'dan yüksekse sistem işe yarıyor")
