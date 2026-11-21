"""Native OB motorundan temas sırası, orijinal genişlik ve kalan bant araştırması.

python -m research.ob_temas_haritasi --cikti var/ob_temas
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from directional_zone_replay import (
    _normalize_frame, build_touch_episodes, compute_wilder_atr, replay_ob_zones,
)
from research import arsiv
from research.fvg_temas_davranisi import bariyer
from research.olcum import yukseklik_kovasi


def temas_sinifi(no):
    return str(no) if no < 4 else '4+'


def kalan_kesisim(high, low, contact):
    return low <= contact['remaining_upper'] and high >= contact['remaining_lower']


def seri(plan):
    s, tf = plan
    f = _normalize_frame(arsiv.tf_frame(s, tf, legacy_resample=False))
    zlist = replay_ob_zones(s,tf,f)
    episodes = build_touch_episodes(zlist,{(s,tf):f})
    atr = compute_wilder_atr(f)
    bars = f[['high','low','close']].to_numpy()
    stamps = [t.isoformat() for t in f.timestamp]
    group = {}
    for ep in episodes:
        group.setdefault(ep['zone_id'],[]).append(ep)
    zones, events = [], []
    for z in zlist:
        eps = group.get(z['zone_id'],[])
        lo, hi = z['zone_lower'], z['zone_upper']
        b, j = z['origin_index'],z['available_index']
        width = (hi-lo)/atr[b] if atr[b] and atr[b]>0 else None
        base = dict(sembol=s,tf=tf,id=z['zone_id'],yon=z['direction'],dogum=stamps[b],
                    bilinebilir=stamps[j],alt=lo,ust=hi,genislik=width,boyut=yukseklik_kovasi(width))
        zones.append(dict(base, toplam_temas=len(eps)))
        contacts = {r['index']:r for r in z['touch_bars']}
        prev_end = None
        for ep in eps:
            i, no = ep['touch_start_index'], ep['touch_number_for_zone']
            high, low, c = bars[i]
            contact = contacts[i]
            fwd=bars[i+1:i+13]
            up = z['direction']=='bullish'
            result,n = bariyer(fwd,c,atr[i],up) if atr[i] and atr[i]>0 else ('ATR_YOK',None)
            term = z['native_terminal_index']
            nxt = ep['_next_episode_start_index']
            # +1 ATR'ye orijinal banda tekrar girilmeden / native sonlanmadan erişildi mi?
            clean='UFUK' if len(fwd)==12 else 'EKSIK'
            if term==i:
                clean='MOTOR_BITTI'
            elif atr[i] and atr[i]>0:
                for k,(h,l,_) in enumerate(fwd,i+1):
                    hit = (h-c if up else c-l)>=atr[i]
                    stop = k==nxt or k==term
                    if hit or stop:
                        clean = 'BELIRSIZ' if hit and stop else ('HEDEF' if hit else ('MOTOR_BITTI' if k==term else 'DONUS'))
                        break
            else:
                clean='ATR_YOK'
            events.append(dict(base,temas_no=no,temas=stamps[i],yas=i-j,ara_bar=i-prev_end-1 if prev_end is not None else None,
                               ref=c,atr=atr[i],onceki_dolum=contact['fill_ratio_before_bar'],
                               kalan_alt=contact['remaining_lower'],kalan_ust=contact['remaining_upper'],
                               kalana_degen=kalan_kesisim(high,low,contact),kapanista_aktif=term!=i,
                               ileri=len(fwd),bariyer=result,karar_bar=n,karar_zamani=stamps[i+n] if n else None,
                               temiz=clean,kapanis12_atr=(1 if up else -1)*(fwd[-1][2]-c)/atr[i]
                               if len(fwd)==12 and atr[i] and atr[i]>0 else None))
            prev_end=ep['touch_end_index']
    arsiv._OBELLEK.clear()
    return zones,events


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cikti',type=Path,default=Path('var/ob_temas'))
    p.add_argument('--isleyici',type=int,default=2)
    args=p.parse_args(); args.cikti.mkdir(parents=True,exist_ok=True)
    syms=arsiv.arsiv_sembolleri(native_only=True)
    plan=[(s,t) for s in syms for t in arsiv.ARASTIRMA_TIMEFRAMELERI]
    import gzip
    import csv
    with gzip.open(args.cikti/'OB.csv.gz','wt') as zf, gzip.open(args.cikti/'TEMAS.csv.gz','wt') as ef, ProcessPoolExecutor(args.isleyici) as pool:
        writers=[None,None]
        for i,res in enumerate(pool.map(seri,plan),1):
            for n,(rows,f) in enumerate(zip(res,(zf,ef))):
                if not rows:
                    continue
                if writers[n] is None:
                    writers[n]=csv.DictWriter(f,fieldnames=rows[0].keys()); writers[n].writeheader()
                writers[n].writerows(rows)
            if i%100==0:
                print(f'{i}/{len(plan)}',flush=True)
    print(f'{len(plan)} seri tamamlandı',flush=True)


if __name__=='__main__':
    main()
