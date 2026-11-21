"""Büyük FVG ilk temasında kapanış anında görülebilen özellikler; ağsız keşif."""
from pathlib import Path
import argparse

import pandas as pd

from research import arsiv
from directional_zone_replay import compute_wilder_atr

KOK = Path(__file__).resolve().parents[1]
ENVANTER = KOK/'docs/arastirma/sonuclar/buyuk_fvg_izleri/BUYUK_FVG_TARIHLERI.csv.gz'
HIPOTEZ = ('erken', 'uzaklasti', 'sig', 'dis_kapanis')


def ozellik(bars, j, i, lo, hi, up, ilk_atr):
    """Yalnız [bilinebilir, temas] kullanır. Aradaki hareket temas mumunu içermez."""
    assert j < i and hi > lo and ilk_atr > 0
    h, l, c = bars[i]
    ara = bars[j+1:i]
    uzak = None if not len(ara) else (max(ara[:,0])-hi if up else lo-min(ara[:,1])) / ilk_atr
    derinlik = (hi-l if up else h-lo) / (hi-lo)
    eps = max(abs(lo), abs(hi)) * 5e-10
    return dict(yas=i-j, erken=i-j<=3, uzak_atr=uzak,
                uzaklasti=None if uzak is None else uzak>=1, derinlik=derinlik,
                sig=derinlik<=0.5, dis_kapanis=c>hi+eps if up else c<lo-eps,
                doldu=l<=lo+eps if up else h>=hi-eps)


def bariyer(bars, ref, atr, up, *, ufuk=12):
    """Eşit uzaklıklı iki bariyer; çapa hariç, çift isabette sıra varsayılmaz."""
    for n, (h,l,_) in enumerate(bars, 1):
        poz, neg = (h-ref,ref-l) if up else (ref-l,h-ref)
        if max(poz,neg)>=atr:
            return ('BELIRSIZ' if min(poz,neg)>=atr else 'LEHTE' if poz>=atr else 'ALEYHTE'), n
    return ('SURE' if len(bars)==ufuk else 'EKSIK'), None


def tara(path):
    en = pd.read_csv(path)
    ilk = en[en.temas_no.eq(1) & en.geometrik_kesisim.eq(True)]  # noqa: E712
    rows=[]
    for (s,tf), g in ilk.groupby(['sembol','tf']):
        df = arsiv.tf_frame(s,tf,legacy_resample=False)
        bars = df[['high','low','close']].to_numpy()
        atr = compute_wilder_atr(df)
        for r in g.itertuples():
            i,j = df.index.get_indexer(pd.to_datetime([r.temas_zamani,r.bilinebilir],utc=True))
            if min(i,j)<0:
                raise ValueError(r.zone_id)
            up = r.yon=='bullish'
            feat = ozellik(bars,j,i,r.alt,r.ust,up,atr[j])
            # Tam dolum kapanışta zaten biliniyor: kalan gruplara bedava avantaj verme.
            if feat['doldu'] or i+12>=len(df):
                continue
            sonuc, n = bariyer(bars[i+1:i+13], bars[i,2], atr[i], up)
            rows.append(dict(zone_id=r.zone_id,sembol=s,tf=tf,yon=r.yon,boyut=r.boyut,
                             temas=r.temas_zamani,bilinebilir=r.bilinebilir,alt=r.alt,ust=r.ust,
                             genislik_atr=r.genislik_atr,ref=bars[i,2],atr=atr[i],
                             donem='son' if r.temas_zamani[:10]>='2026-07-01' else 'ilk',
                             temiz=r.fiyat_sonuc=='HEDEF',bariyer=sonuc,bar=n,
                             karar_zamani=df.index[i+n].tz_convert('Europe/Istanbul').isoformat() if n else None,
                             kapanis12_atr=(1 if up else -1)*(bars[i+12,2]-bars[i,2])/atr[i], **feat))
        arsiv._OBELLEK.clear()
    return pd.DataFrame(rows)


def karsilastir(df):
    rows=[]
    for ad in HIPOTEZ:
        for boyut,g in df.groupby('boyut'):
            for kesit,h in [('tumu',g),*g.groupby('donem'),*g.groupby('tf'),*g.groupby('yon')]:
                for flag,gr in h.groupby(ad):  # uzaklaşma gözlenemiyorsa iki gruba da girmez
                    rows.append(dict(ozellik=ad,boyut=boyut,kesit=kesit,var=flag,n=len(gr),
                                     temiz=int(gr.temiz.sum()),lehte=int((gr.bariyer=='LEHTE').sum()),
                                     aleyhte=int((gr.bariyer=='ALEYHTE').sum()),
                                     belirsiz=int((gr.bariyer=='BELIRSIZ').sum()),
                                     sure=int((gr.bariyer=='SURE').sum()),medyan_12=gr.kapanis12_atr.median()))
    return pd.DataFrame(rows)


def eslesme(df):
    """Aynı hisse/periyot/yön/genişlik sınıfındaki erken ve geç temasları eşit ağırlıkla kıyasla."""
    g=df[df.boyut.eq('>=2')].copy()
    g['cok_genis']=g.genislik_atr>=3
    g['lehte']=g.bariyer.eq('LEHTE')
    gruplar=['sembol','tf','yon','cok_genis','erken']
    o=g.groupby(gruplar).agg(n=('temiz','size'),temiz=('temiz','mean'),lehte=('lehte','mean')).unstack()
    o=o.dropna()  # yalnız erken ve geç gözlemi birlikte bulunan hücre
    w=o['n'].min(axis=1)
    return pd.DataFrame([dict(erken=v,hucre=len(w),agirlik=w.sum(),
                              temiz=(o['temiz'][v]*w).sum()/w.sum(),
                              lehte=(o['lehte'][v]*w).sum()/w.sum()) for v in (False,True)])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cikti',type=Path,default=Path('var/fvg_davranis'))
    args=p.parse_args(); args.cikti.mkdir(exist_ok=True,parents=True)
    df=tara(ENVANTER)
    df.to_csv(args.cikti/'OLAYLAR.csv.gz',index=False,float_format='%.8g')
    eslesme(df).to_csv(args.cikti/'ESLENMIS_YAS.csv',index=False,float_format='%.8g')
    karsilastir(df).to_csv(args.cikti/'KARSILASTIRMA.csv',index=False,float_format='%.8g')


if __name__=='__main__':
    main()
