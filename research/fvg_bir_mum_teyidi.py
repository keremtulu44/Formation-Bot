"""≥2 ATR ve 1–3 mumda ilk temas adayında tek mum beklemenin fırsat maliyeti."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from directional_zone_replay import compute_wilder_atr
from research import arsiv
from research.fvg_temas_davranisi import KOK, bariyer

GIRDI = KOK / 'docs/arastirma/sonuclar/fvg_temas_davranisi/OLAYLAR.csv.gz'


def olc(pencere, atr, alt, ust, yukari):
    """0 temas; 1 karar; 2–12 teyitten sonraki sonuç. Ufuk iki kolda aynı anda biter."""
    if len(pencere) != 13 or atr <= 0:
        raise ValueError('Temas ve 12 ileri mum ile pozitif ATR gerekli')
    ref = pencere[0][2]
    h, l, c = pencere[1]
    baz, baz_n = bariyer(pencere[1:], ref, atr, yukari)
    ilk, _ = bariyer(pencere[1:2], ref, atr, yukari, ufuk=1)
    eps = max(abs(alt), abs(ust))*5e-10
    doldu = l <= alt+eps if yukari else h >= ust-eps
    # İlk bar iki eşiğe de değdiyse sıralama yapılamaz; her durumda tren kaçmıştır.
    if ilk != 'SURE':
        karar = 'ILK_'+ilk
    elif doldu:
        karar = 'BANT_DOLDU'
    else:
        karar = 'TEYIT' if (c>ref if yukari else c<ref) else 'TEYIT_YOK'
    yeni, n = None, None
    if karar in {'TEYIT','TEYIT_YOK'}:
        yeni,n = bariyer(pencere[2:], c, atr, yukari, ufuk=11)
    return dict(karar=karar, baz=baz, baz_bar=baz_n, gec=yeni,
                gec_bar=n+1 if n is not None else None, ref=ref, teyit_ref=c, atr=atr)


def tara():
    g = pd.read_csv(GIRDI)
    sec = g[g.boyut.eq('>=2') & g.erken]
    rows=[]
    for (s,tf), grup in sec.groupby(['sembol','tf']):
        f = arsiv.tf_frame(s,tf,legacy_resample=False)
        bars = f[['high','low','close']].to_numpy()
        atr = compute_wilder_atr(f)
        local = f.index.tz_convert("Europe/Istanbul")
        anchors = set(f.index.get_indexer(pd.to_datetime(grup.temas, utc=True)))
        for r in grup.itertuples():
            i = f.index.get_loc(pd.Timestamp(r.temas))
            m = olc(bars[i:i+13],atr[i],r.alt,r.ust,r.yon=='bullish')
            sign = 1 if r.yon == 'bullish' else -1
            m['sonraki_acilis_atr'] = sign*(float(f.open.iloc[i+1])-m['ref'])/atr[i]
            if tf == '4h':
                # Aynı hisse, hafta günü, saat ve taşınan yön; 12 barlık pencereler çakışmaz.
                j = next((k for k in range(i-13, -1, -1) if k not in anchors and atr[k]
                          and local[k].weekday()==local[i].weekday() and local[k].time()==local[i].time()), None)
                if j is not None:
                    ref,_ = bariyer(bars[j+1:j+2],bars[j,2],atr[j],r.yon=='bullish',ufuk=1)
                    m.update(kontrol_mumu=local[j].isoformat(),
                             kontrol_ilk=ref if ref!='SURE' else 'ESIK_YOK')
            def ts(n):
                return f.index[i+n].tz_convert('Europe/Istanbul').isoformat() if n is not None else None
            if m['baz'] != r.bariyer:
                raise ValueError(f'Önceki çapa ile uyuşmuyor: {r.zone_id}')
            rows.append(dict(zone_id=r.zone_id,sembol=s,tf=tf,yon=r.yon,donem=r.donem,
                             temas=r.temas,teyit_mumu=ts(1),baz_zamani=ts(m['baz_bar']),
                             gec_zamani=ts(m['gec_bar']), **m))
        arsiv._OBELLEK.clear()
    return pd.DataFrame(rows)


def ozet(df):
    sayim=[]
    for kesit,g in [('tumu',df),*df.groupby('donem'),*df.groupby('tf'),*df.groupby('yon')]:
        onay = g.karar.eq('TEYIT')
        for ad,h,k in [('temasta',g,'baz'),('bekle_filtreleme',g[g.gec.notna()],'gec'),
                       ('bekle_teyit',g[onay],'gec'),('bekle_teyitsiz_kontrol',g[g.karar.eq('TEYIT_YOK')],'gec'),
                       ('teyitli_ayni_olay_eski_capa',g[onay],'baz')]:
            sayim.append(dict(kesit=kesit,kol=ad,aday=len(g),kart=len(h),
                              **{v:int(h[k].eq(v).sum()) for v in ['LEHTE','ALEYHTE','BELIRSIZ','SURE']}))
    return pd.DataFrame(sayim)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cikti',type=Path,default=Path('var/fvg_bir_mum_teyidi'))
    args=p.parse_args(); args.cikti.mkdir(parents=True,exist_ok=True)
    df=tara()
    df.to_csv(args.cikti/'OLAYLAR.csv.gz',index=False,float_format='%.10g')
    ozet(df).to_csv(args.cikti/'OZET.csv',index=False)
    g = df[df.kontrol_ilk.notna()].copy()
    g['saat'] = g.temas.str[11:16]
    g['aday_lehte'] = g.karar.eq('ILK_LEHTE')
    g['kontrol_lehte'] = g.kontrol_ilk.eq('LEHTE')
    g.groupby('saat').agg(eslesme=('zone_id','size'), aday=('aday_lehte','sum'),
                           kontrol=('kontrol_lehte','sum')).to_csv(args.cikti/'SAAT_KONTROL.csv')


if __name__=='__main__':
    main()
