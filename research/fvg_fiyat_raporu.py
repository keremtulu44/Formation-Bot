"""FVG izlerini ham OHLC ile eşleyip zaman damgalı, motor ömründen bağımsız fiyat yolu üretir."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from directional_zone_replay import compute_wilder_atr
from research import arsiv
from research.fvg_temas_izleri import UFUK


def fiyat_yolu(bars, stamps, i, lo, hi, direction, atr):
    """Temas dahil en fazla 13 mum. Ardışık kesişimler aynı ziyarettir."""
    up = direction == 'bullish'
    ref = bars[i, 2]
    target = ref + (atr if up else -atr)
    disari = False
    r = {'fiyat_sonuc': None, 'fiyat_karar_zamani': None, 'fiyat_karar_bar': None,
         'banda_donus': None, 'tam_dolum': None, 'kesisen_mum': 0}
    mfe = mae = 0.0
    for n, (h, l, close) in enumerate(bars[i:i+UFUK+1]):
        stamp = stamps[i+n]
        # Ara CSV sınırları 10 anlamlı basamakta taşır; aynı fiyatın
        # son ondalık farkı teması/fitil dolumunu tersine çevirmesin.
        eps = max(abs(lo), abs(hi)) * 5e-10
        overlap = h >= lo-eps and l <= hi+eps
        r['kesisen_mum'] += int(overlap)
        fill = l <= lo+eps if up else h >= hi-eps
        revisit = overlap and disari
        hit = n > 0 and (h >= target if up else l <= target)
        if n:
            mfe = max(mfe, (h-ref if up else ref-l)/atr)
            mae = max(mae, (ref-l if up else h-ref)/atr)
        if fill and not r['tam_dolum']:
            r['tam_dolum'] = stamp
        if revisit and not r['banda_donus']:
            r['banda_donus'] = stamp
        if r['fiyat_sonuc'] is None and (hit or fill or revisit):
            r.update(fiyat_sonuc=('AYNI_MUM_BELIRSIZ' if hit and (fill or revisit) else
                                  'TAM_DOLUM' if fill else 'BANDA_DONUS' if revisit else 'HEDEF'),
                     fiyat_karar_zamani=stamp, fiyat_karar_bar=n)
        disari = not overlap
    if not r['fiyat_sonuc']:
        r['fiyat_sonuc'] = 'EKSIK_UFUK' if len(bars)-1-i < UFUK else 'UFUK_DOLDU'
    r.update(lehte_atr=mfe, aleyhte_atr=mae)
    return r


def ozet(frame):
    """Payda bütün geometrik ilk temaslar. Belirsiz/eksik gözlemler ayrı kolonlarda."""
    result = []
    for (boyut, tf), g in frame.groupby(['boyut', 'tf']):
        say = g.fiyat_sonuc.value_counts()
        result.append(dict(boyut=boyut, tf=tf, ilk_temas=len(g), hedef=int(say.get('HEDEF', 0)),
                           donus=int(say.get('BANDA_DONUS', 0)), dolum=int(say.get('TAM_DOLUM', 0)),
                           ayni_mum=int(say.get('AYNI_MUM_BELIRSIZ', 0)), ufuk_doldu=int(say.get('UFUK_DOLDU', 0)),
                           eksik=int(say.get('EKSIK_UFUK', 0))))
    return pd.DataFrame(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--girdi', required=True, type=Path)
    p.add_argument('--cikti', required=True, type=Path)
    args = p.parse_args()
    out = args.cikti
    out.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(args.girdi).rename(columns={'sonuc':'motor_sonuc', 'sonraki_temas':'sonraki_motor_temasi'})
    updates = {}
    for (s, tf), group in data[data.temas_no > 0].groupby(['sembol','tf']):
        frame = arsiv.tf_frame(s, tf, legacy_resample=False)
        atr = compute_wilder_atr(frame)
        bars = frame[['high','low','close']].to_numpy()
        stamps = [x.isoformat() for x in frame.index.tz_convert('Europe/Istanbul')]
        idx = {t:i for i,t in enumerate(stamps)}
        for row in group.itertuples():
            i = idx[row.temas_zamani]
            if atr[i] and row.geometrik_kesisim:
                updates[row.Index] = fiyat_yolu(bars, stamps, i, row.alt, row.ust, row.yon, atr[i])
        arsiv._OBELLEK.clear()
    data = data.join(pd.DataFrame.from_dict(updates, orient='index'))
    buyuk = data[data.genislik_atr >= 1].sort_values(['temas_zamani','dogum','sembol','tf'])
    buyuk.to_csv(out/'BUYUK_FVG_TARIHLERI.csv.gz', index=False, float_format='%.10g')
    ozet(data[(data.temas_no == 1) & data.fiyat_sonuc.notna()]).to_csv(out/'ILK_TEMAS_OZET.csv', index=False)


if __name__ == '__main__':
    main()
