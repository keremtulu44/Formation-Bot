"""Yönlü kart çıktısı, ayrı hareket kapsamı ve filtre kayıplarını ayrı dök."""
import numpy as np
import pandas as pd

from research.hareket_kapsam import OUT


def main():
    b=pd.read_csv(OUT/'KARARLAR.csv.gz');m=pd.read_csv(OUT/'HAREKETLER.csv.gz')
    cut='2026-07-01';b['donem']=np.where(b.t.str[:10]<cut,'ilk','son');m['donem']=np.where(m.t.str[:10]<cut,'ilk','son')
    stats=[]
    for key in ['frm_kart','fiyat_kart','hacim_kart']:
        g=b[b[key]!=0].copy();g['sonuc']=g.arti.where(g[key]==1,g.eksi)
        stat=g.groupby(['donem','tf','sonuc']).size().rename('n').reset_index();stat['kural']=key;stats.append(stat)
    pd.concat(stats).to_csv(OUT/'KART_SAYIMI.csv',index=False)
    b['slot']=b.groupby(['tf','t']).hacim_kart.transform('any');idx={(s,t):g.set_index('i') for (s,t),g in b.groupby(['hisse','tf'])}
    z=m[(m.hedef==2)&(m.donem=='son')].copy();reason=[]
    for r in z.itertuples():
        w=idx[r.hisse,r.tf].loc[r.i:r.bitis-1];e=w[w.slot]
        reason.append(r.hacim_kart if r.hacim_kart!='yok' else 'saat_yok' if e.empty else 'yon_yok' if not (e.yon==r.yon).any() else 'sirada_elendi')
    z['neden']=reason
    z.groupby(['tf','yon','aile','fiyat_kart','hacim_kart','neden']).size().rename('n').to_csv(OUT/'KAPSAM_KAYBI.csv')
    swaps=b[(b.donem=='son')&(b.fiyat_kart!=b.hacim_kart)].copy();swaps['karar']=np.where(swaps.fiyat_kart==0,'eklendi','elendi');swaps['sonuc']=swaps.arti.where(swaps.yon==1,swaps.eksi)
    swaps[['tf','t','hisse','yon','aile','ref','atr','rvol','govde','fiyat','hacimli','karar','sonuc']].to_csv(OUT/'DEGISEN_KARTLAR.csv',index=False)


if __name__=='__main__':main()
