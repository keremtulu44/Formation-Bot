"""Önceki 20 mum dibinin geri alınmasında aynı seans dilimine göre hacim."""
from pathlib import Path

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from directional_zone_replay import compute_wilder_atr
from research.arsiv import tf_frame
from research.fvg_temas_davranisi import bariyer
from research.stabil_replay import select_bist_equity_universe

OUT = Path('docs/arastirma/sonuclar/dip_geri_alim_hacmi')


def ozellikler(f, slots):
    low = f.low.shift(1).rolling(20).min()
    base = f.volume.groupby(slots).transform(lambda v: v.shift(1).rolling(20).median())
    # Önceki dip delinip aynı mumda geri alınmalı, kapanış üst çeyrekte olmalı.
    mask = (f.low < low) & (f.close > low) & (f.close >= f.low + .75*(f.high-f.low))
    return low, f.volume.div(base.where(base > 0)), mask


def tara(sym, tf):
    f = tf_frame(sym, tf, legacy_resample=False)
    f = f[f.index.tz_convert('Europe/Istanbul').strftime('%Y-%m-%d') < '2026-11-19']
    times = mum_kapanis_anlari(f.index, tf)
    labels = f.index.tz_convert('Europe/Istanbul')
    # Yarım seans / kısa son mumunu tam uzunlukla kıyaslama.
    slots = np.array(['gun' if tf=='1d' else f'{a:%H:%M}-{b:%H:%M}' for a,b in zip(labels,times)])
    low, vol, mask = ozellikler(f, slots)
    atr = np.asarray(compute_wilder_atr(f), dtype=float)
    bars = f[['high','low','close']].to_numpy(); prev = -13
    for i in np.flatnonzero(mask & vol.gt(0)):
        if i-prev <= 12 or i+12 >= len(f) or not atr[i]>0: continue
        prev = i
        fw = bars[i+1:i+13]; c = bars[i,2]; v = vol.iloc[i]
        result, n = bariyer(fw, c, atr[i], True)
        yield dict(hisse=sym,tf=tf,saat=slots[i],kapanis=times[i].isoformat(),
                   donem='ilk' if times[i].strftime('%Y-%m-%d')<'2026-07-01' else 'son',
                   hacim='yuksek' if v>=1.5 else 'dusuk' if v<1 else 'orta',rvol=v,
                   onceki_dip=low.iloc[i],dusuk=bars[i,1],ref=c,atr=atr[i],sonuc=result,
                   ilk_bar=n,net12=(fw[-1,2]-c)/atr[i])


def ozet(g):
    return dict(n=len(g),hisse=g.hisse.nunique(),lehte=g.sonuc.eq('LEHTE').sum(),
                aleyhte=g.sonuc.eq('ALEYHTE').sum(),belirsiz=g.sonuc.eq('BELIRSIZ').sum(),
                sure=g.sonuc.eq('SURE').sum(),medyan_net=g.net12.median())


def main():
    rows=[]
    for sym in select_bist_equity_universe(1000):
        for tf in ('1h','2h','4h','1d'): rows.extend(tara(sym,tf))
    df=pd.DataFrame(rows); OUT.mkdir(exist_ok=True,parents=True)
    df.to_csv(OUT/'OLAYLAR.csv.gz',index=False,float_format='%.8g')
    summary=[]
    for donem,sub in [('tum',df),*df.groupby('donem')]:
        for tf,grp in [('tum',sub),*sub.groupby('tf')]:
            for volume,g in grp.groupby('hacim'):
                summary.append(dict(donem=donem,tf=tf,hacim=volume,**ozet(g)))
    pd.DataFrame(summary).to_csv(OUT/'OZET.csv',index=False,float_format='%.6g')


if __name__=='__main__': main()
