"""Koridor yön hipotezleri: yalnız olay kapanışında bilinen özellikler."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from research import arsiv
from research.ob_koridor import esik_yolu


def yon(x, y):
    return pd.Series(np.select([x>y,x<y],['YUKARI','ASAGI'],default='PAS'), index=x.index)


def ozellikler(df):
    g=df.copy()
    g['oran']=g[['alt_kalan','ust_kalan']].max(axis=1)/g[['alt_kalan','ust_kalan']].min(axis=1)
    g['buyuk_iter']=yon(g.alt_kalan,g.ust_kalan)
    g['ilk_boy_iter']=yon(g.alt_ilk,g.ust_ilk)
    g['yakin_kenar']=yon(g.konum,0.5)
    g['dis_konum']=(g.ref-g.alt_dis)/(g.ust_dis-g.alt_dis)
    g['yakin_dis_kenar']=yon(g.dis_konum,0.5)
    g['son_yon']=yon(g.son3_atr,0)
    g['az_test_iter']=yon(g.ust_temas,g.alt_temas)
    g['yeni_iter']=yon(g.alt_kaynak,g.ust_kaynak)
    g['az_dolu_iter']=yon(g.ust_dolum,g.alt_dolum)
    g['donem']=np.where(g.tarih.str[:10]<'2026-07-01','ilk','son')
    return g


def kiyas(df):
    out=[]
    rules=('buyuk_iter','ilk_boy_iter','yakin_kenar','yakin_dis_kenar','son_yon','az_test_iter','yeni_iter','az_dolu_iter')
    for sample,g in [('tumu',df),('belirgin_1.5',df[df.oran>=1.5]),('belirgin_2',df[df.oran>=2]),
                     ('ortada',df[df.konum.between(.4,.6)]),
                     ('daralan_belirgin',df[df.oran.ge(1.5)&df.daraliyor]),
                     ('uc_uyum',df[df.oran.ge(1.5)&df.buyuk_iter.eq(df.yakin_kenar)&df.buyuk_iter.eq(df.az_test_iter)]),
                     ('dis_esit',df[df.oran.ge(1.5)&df.dis_konum.between(.45,.55)]),
                     ('celiski',df[(df.oran>=1.5)&df.buyuk_iter.ne(df.yakin_kenar)&df.yakin_kenar.ne('PAS')]),
                     *df.groupby('donem'),*df.groupby('tf')]:
        for rule in rules:
            h=g[g[rule].ne('PAS')]
            for target in ['ic','dis','simetrik']:
                r=h[h[target].isin(['YUKARI','ASAGI'])]
                out.append(dict(kesit=sample,kural=rule,olcu=target,toplam=len(g),tahmin=len(h),cozulen=len(r),
                                dogru=int(r[target].eq(r[rule]).sum()),yukari=int(r[target].eq('YUKARI').sum()),
                                yukari_tahmin=int(r[rule].eq('YUKARI').sum()),
                                yukari_dogru=int((r[target].eq('YUKARI')&r[rule].eq('YUKARI')).sum())))
    return pd.DataFrame(out)


def cikis_sonrasi(df):
    """İlk iç kenar aşıldığı kapanıştan tekrar çapala; o mumun hareketine kredi verme."""
    rows=[]
    for (s,tf),g in df[df.ic_n.le(6)].groupby(['sembol','tf']):
        f=arsiv.tf_frame(s,tf,legacy_resample=False); bars=f[['high','low','close']].to_numpy()
        for r in g.itertuples():
            j=f.index.get_loc(pd.Timestamp(r.ic_zaman))
            q=bars[j+1:j+7]
            if len(q)!=6:
                raise ValueError('Eksik ileri pencere')
            result,_=esik_yolu(q,bars[j,2],r.atr)
            rows.append(dict(tf=tf,donem=r.donem,ayni=result==r.ic,ters=result not in (r.ic,'YOK','BELIRSIZ'),sonuc=result))
        arsiv._OBELLEK.clear()
    return pd.DataFrame(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dizin',type=Path,required=True);a=p.parse_args()
    df=ozellikler(pd.read_csv(a.dizin/'KORIDORLAR.csv.gz'))
    kiyas(df).to_csv(a.dizin/'KIYAS.csv',index=False)
    h=cikis_sonrasi(df)
    h.groupby(['tf','donem']).agg(n=('sonuc','size'),devam=('ayni','sum'),ters=('ters','sum'),
                                  sirasi_belirsiz=('sonuc',lambda x:x.eq('BELIRSIZ').sum()),
                                  sure=('sonuc',lambda x:x.eq('YOK').sum())).to_csv(a.dizin/'CIKIS_SONRASI.csv')


if __name__=='__main__':
    main()
