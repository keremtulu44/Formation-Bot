"""Yerel OB replay CSV'lerinden matrisler ve tarihlendirilmiş olay dizini."""
import argparse
from pathlib import Path

import pandas as pd

from research.ob_temas_haritasi import temas_sinifi


def olculebilir(events):
    return events[events.kapanista_aktif & events.ileri.eq(12) & events.atr.gt(0)].copy()


def say(g):
    return dict(n=len(g),bolge=g.id.nunique(),hisse=g.sembol.nunique(),
                lehte=int(g.bariyer.eq('LEHTE').sum()),aleyhte=int(g.bariyer.eq('ALEYHTE').sum()),
                belirsiz=int(g.bariyer.eq('BELIRSIZ').sum()),sure=int(g.bariyer.eq('SURE').sum()),
                temiz=int(g.temiz.eq('HEDEF').sum()),medyan_12=g.kapanis12_atr.median())


def eslesen_ilk_ikinci(g):
    """Yalnız her iki kapanışta da ölçülebilen, aynı kimlikli OB'ler."""
    cols=['id','yas','bariyer','karar_bar','temiz']
    return g[g.temas_no.eq(2)].merge(g.loc[g.temas_no.eq(1),cols],on='id',
                                     suffixes=('','_ilk'),validate='one_to_one')


def ozetle(z,e,out):
    out.mkdir(parents=True,exist_ok=True)
    g=olculebilir(e)
    g['sira']=g.temas_no.map(temas_sinifi)
    g['donem']=g.temas.str[:10].ge('2026-07-01').map({True:'son',False:'ilk'})
    z['ziyaret']=z.toplam_temas.map(temas_sinifi)
    z.groupby(['tf','boyut','ziyaret']).size().rename('bolge').to_csv(out/'BOLGELER.csv')
    e.assign(sira=e.temas_no.map(temas_sinifi)).groupby(['sira','kalana_degen']).kapanista_aktif.agg(['size','sum']).rename(
        columns={'size':'temas', 'sum':'aktif_kaldi'}).to_csv(out/'KALAN_BANT_OMRU.csv')
    tab=[]
    def ekle(ad,kume,cols):
        for key,gr in kume.groupby(cols):
            key=key if isinstance(key,tuple) else (key,)
            tab.append(dict(karsilastirma=ad,**dict(zip(cols,key)),**say(gr)))
    ekle('sira',g,['sira']); ekle('boyut_sira',g,['boyut','sira'])
    ekle('periyot',g,['tf','sira']); ekle('yon',g,['yon','sira'])
    ekle('kalan_bant',g[g.temas_no>=2],['sira','kalana_degen'])
    ekle('kalan_boyut',g[g.temas_no>=2],['boyut','kalana_degen'])
    g['hizli']=g.yas<=3
    ekle('ilk_temas_yasi',g[g.temas_no.eq(1)],['boyut','hizli'])
    ekle('donem',g,['donem','sira']); ekle('donem_kalan',g[g.temas_no>=2],['donem','kalana_degen'])
    p=eslesen_ilk_ikinci(g)
    for ad,gr in [('tum',p),('ortusmeyen',p[p.yas-p.yas_ilk>12])]:
        ekle('es_ilk_'+ad,g[g.id.isin(gr.id)&g.temas_no.eq(1)],['sira'])
        ekle('es_ikinci_'+ad,gr,['sira'])
    # Önceki tepki ikinci temastan ÖNCE kesinleşmiş olmalı.
    bilinen=p[p.karar_bar_ilk.lt(p.yas-p.yas_ilk) & p.bariyer_ilk.isin(['LEHTE','ALEYHTE'])]
    ekle('ikinci_oncesi_ilk_sonuc',bilinen,['bariyer_ilk','donem'])
    pd.DataFrame(tab).to_csv(out/'KIYAS.csv',index=False,float_format='%.6g')
    e[e.genislik.ge(2)][['sembol','tf','yon','dogum','bilinebilir','alt','ust','genislik','temas_no','temas','yas',
       'onceki_dolum','kalana_degen','kapanista_aktif','ileri','atr','ref','bariyer','karar_zamani','temiz']].to_csv(
        out/'BUYUK_OB_TEMASLARI.csv.gz',index=False,float_format='%.8g')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--girdi',type=Path,required=True); p.add_argument('--cikti',type=Path,required=True)
    a=p.parse_args(); ozetle(pd.read_csv(a.girdi/'OB.csv.gz'),pd.read_csv(a.girdi/'TEMAS.csv.gz'),a.cikti)
