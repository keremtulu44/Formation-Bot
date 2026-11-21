"""Native arşivden FVG envanteri ve ilk/ikinci temasın kapanışından sonraki fiyat yolu.

python -m research.fvg_temas_izleri --cikti var/fvg_izleri
Canlı sağlayıcı, bot veya Telegram kullanılmaz.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from directional_zone_replay import (
    _normalize_frame, build_touch_episodes, compute_wilder_atr, replay_fvg_zones,
)
from research import arsiv
from research.kayit import FVG_TIMEFRAMELERI
from research.olcum import yukseklik_kovasi

UFUK = 12


def izle(frame, start, direction, atr, next_touch, terminal, category):
    """Hedef ilk temas (veya karşılaştırmada ikinci temas) kapanışından 1 ATR.

    Temas mumunun fitili hedefe yazılmaz. Aynı mumda hedef ve rakip olay
    görülürse OHLC içi sıra bilinmediğinden kazanç yazılmaz.
    """
    sign = 1 if direction == 'bullish' else -1
    ref = float(frame.at[start, 'close'])
    target = ref + sign * atr
    def zaman(i):
        return frame.at[i, 'timestamp'].isoformat()

    out = dict(temas_zamani=zaman(start), temas_kapanis=ref, temas_atr=atr, hedef=target,
               gozlenen_bar=min(UFUK, len(frame)-1-start), sonuc=None, karar_bar=None,
               karar_zamani=None, ilk_hedef_bar=None, ilk_hedef_zamani=None)
    for i in range(start, min(len(frame), start+UFUK+1)):
        h = i-start
        hit = h > 0 and (float(frame.at[i, 'high']) >= target if sign == 1 else float(frame.at[i, 'low']) <= target)
        if hit and out['ilk_hedef_bar'] is None:
            out.update(ilk_hedef_bar=h, ilk_hedef_zamani=zaman(i))
        obstacle = category if i == terminal else 'YENIDEN_TEMAS' if i == next_touch else None
        if out['sonuc'] is None and (obstacle or hit):
            out.update(sonuc=('AYNI_MUM_BELIRSIZ' if hit and obstacle else obstacle or 'HEDEF'),
                       karar_bar=h, karar_zamani=zaman(i))
        if h in (1, 3, 6, 12):
            out[f'kapanis_{h}'] = float(frame.at[i, 'close'])
    if out['sonuc'] is None:
        out['sonuc'] = 'UFUK_DOLDU' if out['gozlenen_bar'] == UFUK else 'EKSIK_UFUK'
    return out


def seri(plan):
    symbol, tf = plan
    frame = _normalize_frame(arsiv.tf_frame(symbol, tf, legacy_resample=False))
    zones, _, _ = replay_fvg_zones(symbol, tf, frame)
    atr = compute_wilder_atr(frame)
    episodes = build_touch_episodes(zones, {(symbol, tf): frame})
    touches = {}
    for ep in episodes:
        touches.setdefault(ep['zone_id'], []).append(ep)
    rows = []
    for z in zones:
        lo, hi = z['zone_lower'], z['zone_upper']
        a = atr[z['origin_index']]
        width = (hi-lo)/a if a and a > 0 else None
        eps = touches.get(z['zone_id'], [])
        base = dict(zone_id=z['zone_id'], sembol=symbol, tf=tf, yon=z['direction'],
                    dogum=z['formation_time'].isoformat(), bilinebilir=z['available_at'].isoformat(),
                    alt=lo, ust=hi, genislik_atr=width, boyut=yukseklik_kovasi(width),
                    arsivde_temas_sayisi=len(eps), terminal=z['native_terminal_category'],
                    terminal_zamani=z['native_terminal_at'].isoformat() if z['native_terminal_at'] is not None else None)
        if not eps:
            rows.append(dict(base, temas_no=0, sonuc='TEMAS_YOK'))
        for ep in eps[:2]:
            i = ep['touch_start_index']
            nxt = ep['_next_episode_start_index']
            r = dict(base, temas_no=ep['touch_number_for_zone'], temas_mum_sayisi=ep['touch_bar_count'],
                     geometrik_kesisim=frame.at[i,'low'] <= hi and frame.at[i,'high'] >= lo,
                     sonraki_temas=frame.at[nxt,'timestamp'].isoformat() if nxt is not None else None)
            if atr[i] and atr[i] > 0:
                r.update(izle(frame, i, z['direction'], atr[i], nxt, z['native_terminal_index'], z['native_terminal_category']))
            else:
                r.update(temas_zamani=ep['touch_start'].isoformat(), sonuc='ATR_YOK')
            rows.append(r)
    arsiv._OBELLEK.clear()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cikti', type=Path, required=True)
    parser.add_argument('--isleyici', type=int, default=2)
    args = parser.parse_args()
    symbols = arsiv.arsiv_sembolleri(native_only=True)
    plan = [(s, tf) for s in symbols for tf in sorted(FVG_TIMEFRAMELERI)]
    args.cikti.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(args.isleyici) as pool:
        for n, batch in enumerate(pool.map(seri, plan), 1):
            rows.extend(batch)
            if n % 50 == 0:
                print(f'{n}/{len(plan)} seri', flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(args.cikti/'tum_izler.csv.gz', index=False, float_format='%.10g')
    df[df.genislik_atr >= 1].to_csv(args.cikti/'buyuk_fvg.csv', index=False, float_format='%.10g')
    print(f'{len(plan)} seri; {df.zone_id.nunique()} bölge', flush=True)


if __name__ == '__main__':
    main()
