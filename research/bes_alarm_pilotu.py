"""Beş kullanıcı hipotezi: kapanmış native mumlar, yerel ve teslimatsız replay."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from functools import partial

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from directional_zone_replay import compute_wilder_atr
from domain_engines.stabil import build_single_pass_history
from domain_engines.stabil.candidate_regime import classify_candidate_support_regimes
from domain_engines.market_structure import MarketStructureEngine
from domain_engines.order_block import OrderBlockEngine
from domain_engines.fvg import FvgEngulfingConfig, FvgEngulfingEngine
from domain_engines.fvg.fvg_engulfing_models import FvgState
from patterns.detect import LIVE_STATES
from patterns.lifecycle import ArgentEngine
from patterns.constants import ST_BREAK_CONFIRMED
from research import arsiv
from research.fvg_temas_davranisi import bariyer

# Sabit örneklem; sonuçlara göre sembol seçilmez.
PILOT='AKBNK AKSA ALARK ARCLK ASELS ASTOR BIMAS DOAS EKGYO ENKAI EREGL FROTO GARAN GUBRF HALKB ISCTR KCHOL KRDMD PGSUS SAHOL SISE TCELL THYAO TUPRS'.split()
BOS={'1h':10,'2h':5,'4h':3,'1d':2}


def esle(times,source,values):
    """Eşit kapanış dahil; ilk üst mumdan önce bilinmiyor."""
    j=source.searchsorted(times,side='right')-1
    out=np.full(len(times),np.nan)
    if len(source):
        out[j>=0]=np.asarray(values,dtype=float)[j[j>=0]]
    return out


def rvol(v):
    base=v.shift(1).rolling(20).mean()
    return v/base.where(base>0)


def stabil_olaylari(f,s,reg,limit):
    c,h,l,o=(f[k].to_numpy() for k in ('close','high','low','open'))
    start=dip=exitbar=None
    for i in range(1,len(f)):
        fixed=np.isfinite(s[i]) and s[i]==s[i-1]
        if not fixed:
            start=dip=None
        if not np.isfinite(s[i]):
            exitbar=None
            continue
        # Çizgiye yukarıdan ayrılma: dikey proxy sırasında fiyat tümüyle üstünde.
        if reg[i] in ('STEPPING_UP','STEPPING_DOWN'):
            if l[i]>s[i] and (not np.isfinite(s[i-1]) or l[i-1]<=s[i-1] or reg[i]!=reg[i-1]):
                exitbar=i
        elif reg[i]=='BREACHED_FIXED_SUPPORT' or (exitbar is not None and s[i]!=s[exitbar]):
            exitbar=None
        elif exitbar is not None and 0<i-exitbar<=limit and reg[i].startswith(('HORIZONTAL','LONG_HORIZONTAL','NEWLY_FLATTENED')) and l[i]<=s[i]<=h[i]:
            yield i,'S1','aday',{'cikis_bar':i-exitbar}
            exitbar=None
        if fixed and reg[i].startswith(('HORIZONTAL','LONG_HORIZONTAL','NEWLY_FLATTENED')) and l[i]<=s[i]<=h[i] and not (l[i-1]<=s[i-1]<=h[i-1]):
            yield i,'S1','yatay_temas',{}
        if fixed and c[i]<s[i] and (start is not None or c[i-1]>=s[i-1]):
            if start is None:
                start=dip=i
            if l[i]<=l[dip]: dip=i
        if fixed and start is not None and c[i]>s[i]:
            if l[i]<l[dip]: dip=i
            n=i-dip+1; green=c[dip:i+1]>o[dip:i+1]; body=c[dip:i+1]-o[dip:i+1]
            strong=green & (body>=.5*(h[dip:i+1]-l[dip:i+1]))
            extra={'dip_fiyat':l[dip],'dip_etiketi':f.index[dip].isoformat(),'dip_bar':n,'yesil':green.mean(),'temiz_yesil':strong.mean()}
            yield i,'S2','geri_alis',extra
            if n>=3 and green.mean()>=.8: yield i,'S2','yesil80',extra
            if n>=3 and strong.mean()>=.8: yield i,'S2','temiz80',extra
            start=dip=None


class Iz(ArgentEngine):
    def _process_bar(self,i):
        prev=self.pattern_state
        super()._process_bar(i)
        a=self.active
        if not a.valid: return
        if self.pattern_state==ST_BREAK_CONFIRMED and prev!=self.pattern_state and self.break_candidate_dir==1:
            self.teyit.add(i)
        if self.pattern_state in LIVE_STATES and a.upper_slope+a.lower_slope>0:
            self.egim[i]=a.stable_id


def symbol(sym, *, yalniz_stabil_hacim=False):
    fs={t:arsiv.tf_frame(sym,t,legacy_resample=False) for t in BOS}
    # Ortak son arşiv günü kısmi olabilir; tüm serilerde dışarıda bırak.
    fs={t:f[f.index.tz_convert('Europe/Istanbul').date < pd.Timestamp('2026-11-19').date()] for t,f in fs.items()}
    ts={t:mum_kapanis_anlari(f.index,t) for t,f in fs.items()}
    rv={t:rvol(f.volume) for t,f in fs.items()}
    if yalniz_stabil_hacim:
        from domain_engines.stabil.runtime import prepare_causal_ohlcv
        from domain_engines.stabil.stabil_support_lifecycle import build_daily_support_observations, build_support_lifecycle_timeline
        d,_=prepare_causal_ohlcv(fs['1d'],symbol=sym,timeframe='1d')
        pts=classify_candidate_support_regimes(build_support_lifecycle_timeline(
            build_daily_support_observations(d),include_prefix_events=False))
        daily=pd.DatetimeIndex(d.timestamp);weekly=[]
    else:
        hist=build_single_pass_history(sym,fs['1d'],fs['4h'],include_support_prefix_events=False)
        pts=classify_candidate_support_regimes(hist.support_timeline)
        daily=pd.DatetimeIndex(hist.daily_close_times);weekly=hist.weekly_frame
    if len(weekly):
        ts['1w']=pd.DatetimeIndex(weekly.timestamp);rv['1w']=rvol(weekly.volume)
    rows=[];errors=[]; fvg2=[]
    for tf in ('2h','1h','4h','1d'):
        f=fs[tf];times=ts[tf]; sup=esle(times,daily,[p.support_level for p in pts]);idx=daily.searchsorted(times,side='right')-1
        reg=[pts[k].regime.value if k>=0 else '' for k in idx]
        at=np.asarray(compute_wilder_atr(f),dtype=float);bars=f[['high','low','close']].to_numpy();cl=bars[:,2]
        upper={'1h':'2h','2h':'4h','4h':'1d','1d':'1w'}[tf]
        ur=esle(times,ts[upper],rv[upper]) if upper in ts else np.full(len(f),np.nan)
        def add(i,k,grp,extra=None):
            a=at[i]; fw=bars[i+1:i+13]
            if not np.isfinite(a) or a<=0 or len(fw)<12:return
            b,n=bariyer(fw,cl[i],a,True)
            row=dict(sembol=sym,tf=tf,kapanis=times[i].isoformat(),kural=k,grup=grp,ref=cl[i],atr=a,
                     destek=sup[i],bariyer=b,ilk_bar=n,net12=(fw[-1,2]-cl[i])/a)
            for h in (3,4):
                row['dip'+str(h)]=max(0,(cl[i]-fw[:h,1].min())/a)
                row['net'+str(h)]=(fw[h-1,2]-cl[i])/a
            row.update(extra or {});rows.append(row)
        if tf in ('1d','4h'):
            for i,k,g,ex in stabil_olaylari(f,sup,reg,7 if tf=='1d' else 12):add(i,k,g,ex)
        if tf=='1h':
            v4=esle(times,ts['4h'],rv['4h'])
            last={}
            for i,v in enumerate(rv[tf]):
                if not (.0<v<=.3 or .8<=v<=1.2):continue
                top='guclu' if ur[i]>=.8 and v4[i]>=1 else 'zayif' if ur[i]<.8 and v4[i]<1 else None
                if not top:continue
                group=('dusuk_' if v<=.3 else 'normal_')+top
                if i-last.get(group,-100)<=4:continue
                last[group]=i;add(i,'H',group,{'rvol':v,'rvol2':ur[i],'rvol4':v4[i],'etiket_saat':f.index[i].tz_convert('Europe/Istanbul').strftime('%H:%M')})
        if yalniz_stabil_hacim:continue
        tr=Iz(profile='Dengeli');tr.teyit=set();tr.egim={};tr.process(f,tam_yeniden=True)
        ob=OrderBlockEngine();fg=FvgEngulfingEngine(FvgEngulfingConfig(timeframe=tf)) if tf!='1h' else None
        ms=MarketStructureEngine();lastbos=-1000; seen=set();baseseen=set()
        for i,row in enumerate(f.reset_index().rename(columns={f.index.name:'timestamp'}).to_dict('records')):
            ob.update(row); bounds=None;known=False
            if fg is not None:
                fg.update(row);known=i>=99 and str(fg.last_data_quality)=='OK';r=fg.active_bearish_fvg
                if r is not None and r.state!=FvgState.CANDIDATE and not r.invalid and not r.full_fill:
                    bounds=(r.lower_boundary+r.gap_size*r.maximum_fill_ratio,r.upper_boundary)
                if tf=='2h':fvg2.append((known,bounds))
            elif i in tr.teyit:
                j=ts['2h'].searchsorted(times[i],side='right')-1
                if j>=0:known,bounds=fvg2[j]
            if i in tr.teyit and known and i>=99 and np.isfinite(sup[i]):
                price=cl[i];ds=[0 if bounds[0]<=price else bounds[0]-price] if bounds and bounds[1]>=price else []
                for rec in ob.active_records:
                    if not rec.bullish:
                        a,b=sorted(ob._active_remaining_zone(rec))
                        if b>=price:ds.append(max(0,a-price))
                gap=min(ds)/at[i] if ds else float('inf');ex={'mesafe_atr':gap}
                add(i,'F1','teyit',ex)
                if price>sup[i] and gap>=1:add(i,'F1','aday',ex)
            if ms is not None:
                try:ms.update(row)
                except (AssertionError,ValueError) as exc:
                    errors.append(dict(sembol=sym,tf=tf,bar=i,hata=repr(exc)));ms=None
            if ms is not None:
                # Yalnız o mumda teyitli iç/dış yapı olayı.
                for ev in (ms.latest_external_event,ms.latest_internal_event):
                    if ev is not None and ev.event_bar==i and str(ev.event_type)=='EVENT_BOS' and ev.direction==1:
                        lastbos=i
            if i in tr.egim and ms is not None and np.isfinite(ur[i]):
                sid=tr.egim[i];ex={'ust_rvol':ur[i],'bos_yasi':i-lastbos}
                if sid not in baseseen:add(i,'F2','egim',ex);baseseen.add(sid)
                if sid not in seen and i-lastbos<BOS[tf] and ur[i]>.5:
                    add(i,'F2','aday',ex);seen.add(sid)
    return rows,errors


def main():
    p=argparse.ArgumentParser();p.add_argument('--cikti',type=Path,required=True);p.add_argument('--semboller',default=','.join(PILOT));p.add_argument('--genis-stabil-hacim',action='store_true');a=p.parse_args()
    a.cikti.mkdir(parents=True,exist_ok=True);rows=[];errors=[]
    symbols=a.semboller.split(',')
    if a.genis_stabil_hacim:
        from research.stabil_replay import select_bist_equity_universe
        symbols=select_bist_equity_universe(1000)
    with ProcessPoolExecutor(2) as pool:
        for s,(r,e) in zip(symbols,pool.map(partial(symbol,yalniz_stabil_hacim=a.genis_stabil_hacim),symbols)):
            print(s,len(r),len(e),flush=True);rows.extend(r);errors.extend(e)
    pd.DataFrame(rows).to_csv(a.cikti/'OLAYLAR.csv.gz',index=False,float_format='%.8g');pd.DataFrame(errors,columns=['sembol','tf','bar','hata']).to_csv(a.cikti/'MS_EKSIK.csv',index=False)

if __name__=='__main__':main()
