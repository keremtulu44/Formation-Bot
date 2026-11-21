"""Ölçüm kartları: grup/payda, dipten geri alış örneklem duyarlılığı ve hacim kontrolü."""
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from research import arsiv
from research.bes_alarm_pilotu import esle
from directional_zone_replay import compute_wilder_atr


def sonuc(g):
    return dict(n=len(g),hisse=g.sembol.nunique(),yukari=g.bariyer.eq('LEHTE').sum(),
                asagi=g.bariyer.eq('ALEYHTE').sum(),belirsiz=g.bariyer.eq('BELIRSIZ').sum(),
                sure=g.bariyer.eq('SURE').sum(),medyan_net12=g.net12.median())


def kurallar(df):
    rows=[]
    signals=df[df.kural.ne('H')].copy()
    for (k,gr),g in signals.groupby(['kural','grup']):
        for kes,h in [('tum',g),*g.groupby('tf'),*g.groupby(g.kapanis.str[:10].ge('2026-07-01').map({True:'son',False:'ilk'}))]:
            rows.append(dict(kural=k,grup=gr,kesit=kes,**sonuc(h)))
    # F1 ve S2 adayları temel grupla aynı mumda; dahil olmayanları ayrıca say.
    for k,temel,secilen in [('F1','teyit','aday'),('S2','geri_alis','yesil80'),('S2','geri_alis','temiz80')]:
        keys=['sembol','tf','kapanis']
        base=signals[signals.kural.eq(k)&signals.grup.eq(temel)]
        if base.empty:continue
        others=signals[signals.kural.eq(k)&signals.grup.eq(secilen)][keys].drop_duplicates()
        cmp=base.merge(others,on=keys,how='left',indicator=True).query("_merge=='left_only'")
        rows.append(dict(kural=k,grup='diger_'+secilen,kesit='tum',**sonuc(cmp)))
    for gr,g in signals[signals.kural.eq('S2')].groupby('grup'):
        for n in [5,10]:rows.append(dict(kural='S2',grup=gr,kesit=f'dipten_min_{n}',**sonuc(g[g.dip_bar>=n])))
    return pd.DataFrame(rows)


def hacim(df):
    v=df[df.kural.eq('H')].copy();v['t']=pd.to_datetime(v.kapanis,utc=True)
    for s,g in v.groupby('sembol'):
        f=arsiv.tf_frame(s,'4h',legacy_resample=False);t=mum_kapanis_anlari(f.index,'4h');a=esle(pd.DatetimeIndex(g.t),t,compute_wilder_atr(f))
        f1=arsiv.tf_frame(s,'1h',legacy_resample=False);t1=mum_kapanis_anlari(f1.index,'1h');op=esle(pd.DatetimeIndex(g.t),t1,f1.open)
        v.loc[g.index,'mum_govde_1sATR']=(g.ref-op).abs()/g.atr
        v.loc[g.index,'mum_aralik_1sATR']=esle(pd.DatetimeIndex(g.t),t1,f1.high-f1.low)/g.atr
        v.loc[g.index,'dip4_4sATR']=g.dip4*g.atr/a
        arsiv._OBELLEK.clear()
    out=[]; matches=[]
    def olc(gr,kesit,g):
        out.append(dict(grup=gr,kesit=kesit,n=len(g),hisse=g.sembol.nunique(),
                        medyan_govde=g.mum_govde_1sATR.median(),govde_015=g.mum_govde_1sATR.le(.15).mean(),
                        medyan_mum_araligi=g.mum_aralik_1sATR.median(),medyan_abs_net4=g.net4.abs().median(),medyan_dip3=g.dip3.median(),medyan_dip4=g.dip4.median(),
                        medyan_dip4_4sATR=g.dip4_4sATR.median(),dip4_en_fazla_015=g.dip4.le(.15).mean(),
                        medyan_net3=g.net3.median(),medyan_net4=g.net4.median()))
    for name,g in v.groupby('grup'):olc(name,'tum',g)
    for ctrl in ('dusuk_zayif','normal_guclu'):
        cidx=[]; tidx=[]
        for _,g in v.groupby(['sembol','etiket_saat']):
            ref=g[g.grup.eq(ctrl)].sort_values('t');tgt=g[g.grup.eq('dusuk_guclu')].sort_values('t')
            used=set()
            for i,r in tgt.iterrows():
                # 7–90 gün önce: farklı gün ve örtüşmeyen gelecek penceresi, aynı saat/hisse.
                eligible=ref[(ref.t<=r.t-pd.Timedelta(days=7))&(ref.t>=r.t-pd.Timedelta(days=90))&~ref.index.isin(used)]
                if eligible.empty:continue
                j=eligible.index[-1];used.add(j);cidx.append(j);tidx.append(i)
                matches.append(dict(sembol=r.sembol,aday=r.kapanis,kontrol=v.at[j,'kapanis'],tur=ctrl,
                                    fark_dip4=r.dip4-v.at[j,'dip4'],fark_net4=r.net4-v.at[j,'net4']))
        olc('dusuk_guclu','es_'+ctrl,v.loc[tidx]);olc(ctrl,'es_'+ctrl,v.loc[cidx]);
    return pd.DataFrame(out),pd.DataFrame(matches)


def main():
    p=argparse.ArgumentParser();p.add_argument('--dizin',type=Path,required=True);a=p.parse_args();d=a.dizin
    df=pd.read_csv(d/'OLAYLAR.csv.gz');kurallar(df).to_csv(d/'KURALLAR.csv',index=False,float_format='%.6g')
    vol,matches=hacim(df);vol.to_csv(d/'HACIM.csv',index=False,float_format='%.6g');matches.to_csv(d/'HACIM_ESLER.csv',index=False,float_format='%.6g')

if __name__=='__main__':main()
