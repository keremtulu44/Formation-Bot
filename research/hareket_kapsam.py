"""Çevrimdışı hareket haritası. Politika yalnız kapanmış mum özelliklerini okur."""
from pathlib import Path

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from directional_zone_replay import compute_wilder_atr
from research.arsiv import tf_frame
from research.bes_alarm_pilotu import PILOT
from patterns.lifecycle import ArgentEngine
from patterns.constants import ST_BREAK_CONFIRMED

OUT = Path('docs/arastirma/sonuclar/hareket_kapsam')


class Teyit(ArgentEngine):
    def _process_bar(self, i):
        prev = self.pattern_state
        super()._process_bar(i)
        if prev != self.pattern_state == ST_BREAK_CONFIRMED and self.active.valid:
            self.teyitler[i] = self.break_candidate_dir


def path(h,l,ref,a,d,target):
    for k,(hi,lo) in enumerate(zip(h,l),1):
        pos,neg = (hi-ref,ref-lo) if d==1 else (ref-lo,hi-ref)
        if pos>=a*target or neg>=a:
            return ('cift' if pos>=a*target and neg>=a else 'hedef' if pos>=a*target else 'ters'),k
    return 'sure',len(h)


def series(sym,tf):
    f=tf_frame(sym,tf,legacy_resample=False);f=f[f.index.tz_convert('Europe/Istanbul').strftime('%Y-%m-%d')<'2026-11-19']
    t=mum_kapanis_anlari(f.index,tf); slot=['gun' if tf=='1d' else f'{x:%H:%M}-{y:%H:%M}' for x,y in zip(f.index.tz_convert('Europe/Istanbul'),t)]
    v=f.volume/f.volume.groupby(slot).transform(lambda g:g.shift(1).rolling(20).median()).replace(0,np.nan)
    a=np.asarray(compute_wilder_atr(f),dtype=float); c,h,l,o=(f[k].to_numpy() for k in ['close','high','low','open'])
    tr=Teyit(timeframe=tf);tr.teyitler={};tr.process(f,tam_yeniden=True)
    out=[];moves=[];last={};end=len(f)-12
    for i in range(50,len(f)):
        if not a[i]>0:continue
        sg=int(np.sign(c[i]-o[i]));spread=h[i]-l[i];eff=abs(c[i]-o[i])/spread if spread else 0
        score=abs(c[i]-o[i])/a[i]+eff
        # Yüksek hacim, verimli gövdede artı; fitil baskınsa eksi. Sabit, fit yok.
        enhanced=score if not np.isfinite(v.iloc[i]) else score+np.clip(np.log2(max(.01,v.iloc[i])),-2,2)*(eff-.5)
        def family(d):
            hi=h[i-20:i].max();lo=l[i-20:i].min()
            if (c[i]>hi if d==1 else c[i]<lo):return 'kirilim'
            if (l[i]<lo<c[i] if d==1 else h[i]>hi>c[i]):return 'geri_alim'
            if d*(c[i-1]-c[i-11])>a[i] and d*(c[i-1]-c[i-3])<0:return 'trend_molasi'
            return 'diger'
        y={d:('eksik' if i>=end else path(h[i+1:i+13],l[i+1:i+13],c[i],a[i],d,2)[0]) for d in (-1,1)}
        row=dict(hisse=sym,tf=tf,i=i,t=t[i].isoformat(),ref=c[i],atr=a[i],rvol=v.iloc[i],govde=eff,
                 fiyat=score,hacimli=enhanced,yon=sg,frm=tr.teyitler.get(i,0),aile=family(sg) if sg else 'doji',
                 arti=y[1],eksi=y[-1],high=h[i],low=l[i],open=o[i])
        out.append(row)
        if i>=end:continue
        for target in (1.5,2,2.5):
            # Her hedef için iki yönde ortak kilit; hedef mumunda yeni çapa başlatılmaz.
            if i<=last.get(target,-1):continue
            for d in (1,-1):
                res,n=path(h[i+1:i+13],l[i+1:i+13],c[i],a[i],d,target)
                if res=='hedef':
                    last[target]=i+n
                    moves.append(dict(hisse=sym,tf=tf,i=i,t=row['t'],hedef=target,yon=d,bitis=i+n,
                                      hedef_zamani=t[i+n].isoformat(),ref=c[i],atr=a[i],aile=family(d),
                                      acilista=int(d*(o[i+1]-c[i])>=target*a[i])))
                    break
    return out,moves


def select(df):
    # Günü geriye dönük sıralama yok. Her kapanışta sadece o anda mevcut hisseler.
    b=df.copy();b['frm_kart']=b.frm;b['fiyat_kart']=0;b['hacim_kart']=0
    # Üç periyodun TOPLAM günlük bütçesi 10. Bir periyottaki eksik kotayı
    # diğerine gelecekteki barları görerek taşıma. Kısa seanslarda kota boş kalabilir.
    quota={'1d':{'*':2},'4h':{'13:00':1,'17:00':1,'18:00':2},
           '1h':{'10:30':1,'12:30':1,'14:30':1,'16:30':1}}
    for (tf,time),slot in b.groupby(['tf','t'],sort=False):
        cap=quota[tf].get(time[11:16],quota[tf].get('*',0))
        if not cap:continue
        slot=slot[slot.yon!=0]
        for key,col in [('fiyat','fiyat_kart'),('hacimli','hacim_kart')]:
            top=slot.sort_values([key,'hisse'],ascending=[False,True]).head(cap)
            b.loc[top.index,col]=top.yon
    return b


def audit(b,m):
    policies=['frm_kart','fiyat_kart','hacim_kart'];indexed={(s,tf):g.set_index('i') for (s,tf),g in b.groupby(['hisse','tf'])}
    for key in policies:m[key]='yok';m[key+'_bar']=np.nan
    for row in m.itertuples():
        g=indexed[row.hisse,row.tf];w=g.loc[row.i:row.bitis-1];d=row.yon
        for key in policies:
            hits=w[w[key]==d]
            if hits.empty:continue
            j=hits.index[0];pre=w.loc[row.i+1:j];best=0 if pre.empty else (pre.high.max()-row.ref if d==1 else row.ref-pre.low.min())
            m.at[row.Index,key]='erken' if best<row.atr*row.hedef/2 else 'gec';m.at[row.Index,key+'_bar']=j-row.i
    return m


def main():
    rows=[];moves=[]
    for s in PILOT:
        for tf in ('1h','4h','1d'):
            r,m=series(s,tf);rows+=r;moves+=m
    b=select(pd.DataFrame(rows));m=audit(b,pd.DataFrame(moves));OUT.mkdir(parents=True,exist_ok=True)
    m.to_csv(OUT/'HAREKETLER.csv.gz',index=False,float_format='%.8g');b.to_csv(OUT/'KARARLAR.csv.gz',index=False,float_format='%.8g')


if __name__=='__main__':main()
