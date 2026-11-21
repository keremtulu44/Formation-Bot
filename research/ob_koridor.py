"""İki karşıt aktif OB arasındaki dar koridordan çıkış. Yalnız yerel native arşiv."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from directional_zone_replay import _normalize_frame, compute_wilder_atr
from domain_engines.order_block import OrderBlockEngine
from research import arsiv

UFUK = 12


def kapanis_yolu(closes, alt, ust):
    for n,c in enumerate(closes,1):
        if c > ust:
            return 'YUKARI', n
        if c < alt:
            return 'ASAGI', n
    return 'YOK', None


def esik_yolu(bars, c, a):
    for n,(h,l,_) in enumerate(bars,1):
        u,d = h >= c+a, l <= c-a
        if u or d:
            return 'BELIRSIZ' if u and d else 'YUKARI' if u else 'ASAGI', n
    return 'YOK',None


def koridor(bull,bear,c,a):
    if not a or a<=0 or bull.top is None or bear.bottom is None:
        return False
    return bull.top<c<bear.bottom and bear.bottom-bull.top<=2*a


def seri(plan):
    s,tf=plan
    f=_normalize_frame(arsiv.tf_frame(s,tf,legacy_resample=False))
    bars=f[['high','low','close']].to_numpy(); atr=compute_wilder_atr(f)
    dates=[t.isoformat() for t in f.timestamp]
    engine=OrderBlockEngine(); touches={}; previous=None; used=set(); last=-UFUK-1; rows=[]
    for i,row in enumerate(f.to_dict('records')):
        for rec in engine.active_records:
            key=(rec.bullish,rec.source_index)
            if row['low']<=rec.top and row['high']>=rec.bottom:
                count,bar=touches.get(key,(0,-2))
                touches[key]=(count+int(bar!=i-1),i)
        engine.update(row)
        bull,bear=engine.export.bull,engine.export.bear
        c=row['close']; a=atr[i]
        if not koridor(bull,bear,c,a):
            previous=None
            continue
        bi,si=int(bull.source_bar),int(bear.source_bar)
        pair=(bi,si)
        eligible=previous==pair and pair not in used and i-last>UFUK
        previous=pair
        if not eligible or i+UFUK>=len(f):
            continue
        last=i; used.add(pair)
        lsz,usz=bull.top-bull.bottom,bear.top-bear.bottom
        width=bear.bottom-bull.top
        forward=bars[i+1:i+1+UFUK]
        items=dict(sembol=s,tf=tf,tarih=dates[i],alt_kaynak=dates[bi],ust_kaynak=dates[si],
                   alt_dis=bull.bottom,alt_ic=bull.top,ust_ic=bear.bottom,ust_dis=bear.top,
                   alt_kalan=lsz,ust_kalan=usz,alt_ilk=lsz/(1-bull.fill),ust_ilk=usz/(1-bear.fill),
                   alt_dolum=bull.fill,ust_dolum=bear.fill,alt_temas=touches.get((True,bi),(0,))[0],
                   ust_temas=touches.get((False,si),(0,))[0],ref=c,atr=a,aralik_atr=width/a,
                   konum=(c-bull.top)/width,son3_atr=(c-bars[i-3,2])/a)
        for ad,(yon,n) in [('ic',kapanis_yolu(forward[:,2],bull.top,bear.bottom)),
                           ('dis',kapanis_yolu(forward[:,2],bull.bottom,bear.top)),
                           ('simetrik',esik_yolu(forward,c,a))]:
            items[ad]=yon; items[ad+'_n']=n;items[ad+'_zaman']=dates[i+n] if n else None
            items[ad+'_kapanis']=forward[n-1,2] if n else None
        items['daraliyor'] = (max(bars[i-2:i+1,0])-min(bars[i-2:i+1,1]) <
                             max(bars[i-5:i-2,0])-min(bars[i-5:i-2,1]))
        rows.append(items)
    arsiv._OBELLEK.clear()
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cikti',type=Path,default=Path('var/ob_koridor'))
    p.add_argument('--isleyici',type=int,default=2)
    args=p.parse_args();args.cikti.mkdir(exist_ok=True,parents=True)
    plans=[(s,tf) for s in arsiv.arsiv_sembolleri(native_only=True) for tf in arsiv.ARASTIRMA_TIMEFRAMELERI]
    rows=[]
    with ProcessPoolExecutor(args.isleyici) as pool:
        for i,events in enumerate(pool.map(seri,plans),1):
            rows.extend(events)
            if i%100==0:print(i,len(rows),flush=True)
    pd.DataFrame(rows).to_csv(args.cikti/'KORIDORLAR.csv.gz',index=False,float_format='%.12g')
    print(f'{len(plans)} seri; {len(rows)} koridor',flush=True)


if __name__=='__main__':
    main()
