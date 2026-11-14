"""D7 çoklu zaman dilimi yönetimi: saatlik ortak fiyat akışında eşleşmiş replay.
python -m research.golge_v2_mtf_olcum --workers 2
"""
import argparse, concurrent.futures, hashlib, itertools, json
from bisect import bisect_right
from pathlib import Path
import pandas as pd
from domain_engines.stabil import prepare_causal_ohlcv
from domain_engines.stabil.signals import _causal_atr14
from domain_engines.market_structure import MarketStructureEngine, MarketStructureConfig
from research.arsiv import tf_frame
from senaryo_v2.mtf_yonetim import Snapshot, ManagementBar, ManagementConfig, simulate_management

ROOT=Path('docs/arastirma/sonuclar/golge_v2'); OUT=ROOT/'mtf_olcum'
KEY=hashlib.sha256(b''.join(Path(p).read_bytes() for p in [__file__,'senaryo_v2/mtf_yonetim.py',str(ROOT/'mod0_baz.csv.gz')])).hexdigest()[:12]
PART=OUT/'parca'/KEY

def configs():
    result={'baz':ManagementConfig()}
    for trigger,lock in itertools.product([1.,1.5],[0.,.25]):
        result[f'kar_{trigger:g}_{lock:g}']=ManagementConfig(protect_trigger_r=trigger,protect_lock_r=lock)
    for two,four,action,half in itertools.product(['price','event'],['price','state'],['exit','protect'],[False,True]):
        name=f'{two}_{four}_{action}_{"yarim" if half else "hemen"}'
        result[name]=ManagementConfig(two_mode=two,four_mode=four,mtf_action=action,activate_after_half_r=half)
        result[name+'_kar1_025']=ManagementConfig(two_mode=two,four_mode=four,mtf_action=action,activate_after_half_r=half,protect_trigger_r=1,protect_lock_r=.25)
    return result

CASES=configs()

def frame(sym,tf):
    raw=tf_frame(sym,tf)
    clean,err=prepare_causal_ohlcv(raw,symbol=sym,timeframe=tf)
    if err and clean.empty: raise ValueError(f'{sym} {tf} {err}')
    if len(raw)!=len(clean): raise ValueError(f'{sym} {tf}: source row alignment')
    clean['start']=pd.DatetimeIndex(raw.index).tz_convert('Europe/Istanbul')
    return clean

def snapshots(df):
    atr=_causal_atr14(df.high.to_numpy(float),df.low.to_numpy(float),df.close.to_numpy(float),period=14)
    eng=MarketStructureEngine(MarketStructureConfig(profile='Dengeli')); out=[]; previous=None
    for i,row in enumerate(df.to_dict('records')):
        res=eng.update(row); event=0
        for ev in (res.events if res is not None else ()):
            p=ev.split(':')
            if len(p)>=3 and p[0]=='EXTERNAL' and p[1] in ('EVENT_BOS','EVENT_CHOCH'):
                event=int(p[2])
        a=float(atr[i]); a=a if pd.notna(a) and a>0 else None
        out.append(Snapshot(row['timestamp'].to_pydatetime(),float(row['close']),previous,a,event,int(eng.external_context.direction)))
        previous=float(row['close'])
    return out

def worker(job):
    symbol,rows=job; path=PART/f'{symbol}.json'
    if path.exists(): return symbol
    data={tf:frame(symbol,tf) for tf in ('1h','2h','4h','1d')}
    snaps={tf:snapshots(data[tf]) for tf in ('1h','2h','4h')}
    times={tf:[s.time for s in snaps[tf]] for tf in snaps}
    hour=data['1h']; starts=list(hour.start); closes=list(hour.timestamp); results=[]
    hour_days={t.date() for t in starts}
    daily_days=[t.date() for t in data['1d'].timestamp]
    for r in rows:
        target=data[r['tf']]; i=int(r['bar_index']); entry_time=pd.Timestamp(r['bar_close_time'])
        if i>=len(target) or target.iloc[i].timestamp != entry_time or abs(target.iloc[i]['close']-r['giris_gercek'])>1e-7: raise ValueError(f"entry mismatch {r['olay_id']}")
        if i+10>=len(target): results.append({'olay_id':r['olay_id'],'excluded':'no_target_horizon'}); continue
        horizon=target.iloc[i+10].timestamp
        # Günlük arşivde işlem günü olup saatlik arşivde hiç olmayan günleri sansürle.
        if any(entry_time.date() < day <= horizon.date() and day not in hour_days for day in daily_days):
            results.append({'olay_id':r['olay_id'],'excluded':'missing_hourly_session'}); continue
        # Saatlik mumun tamamı işlem açılışından sonraya, kapanışı ufka ait olmalı.
        begin=bisect_right(starts,entry_time-pd.Timedelta(microseconds=1)); end=bisect_right(closes,horizon)
        selected=hour.iloc[begin:end]
        if selected.empty or selected.iloc[-1].timestamp.date()!=horizon.date():
            results.append({'olay_id':r['olay_id'],'excluded':'incomplete_hourly_horizon'}); continue
        bars=[]
        for row in selected.to_dict('records'):
            t=row['timestamp']; ss=[]
            for tf in ('1h','2h','4h'):
                j=bisect_right(times[tf],t)-1
                s=snaps[tf][j] if j>=0 else None
                # Pozisyon açılmadan önceki olaylar yeni işlem sinyali sayılmaz.
                if s is not None and s.time<=entry_time: s=None
                ss.append(s)
            bars.append(ManagementBar(t.to_pydatetime(),float(row['open']),float(row['high']),float(row['low']),float(row['close']),*ss))
        entry=float(r['giris_gercek']); stop=float(r['stop']); direction=1 if r['yon']=='long' else -1
        risk=abs(entry-stop); tgt=entry+direction*2*float(r['atr_tf']); cost=.003*entry/risk
        out=dict(olay_id=r['olay_id'],sembol=symbol,tf=r['tf'],yon=r['yon'],donem=r['donem'], excluded='', old_net=r['net15_20_r'],entry_time=r['bar_close_time'],horizon=str(horizon),last_hour=str(selected.iloc[-1].timestamp),n_hour=len(bars),end_close_difference=float(selected.iloc[-1]['close']-target.iloc[i+10]['close']))
        for name,cfg in CASES.items():
            outcome=simulate_management(bars,entry=entry,stop=stop,target=tgt,direction=direction,cfg=cfg)
            out[name+'_net']=outcome.gross_r-cost; out[name+'_reason']=outcome.reason; out[name+'_index']=outcome.bar_index; out[name+'_signals']=outcome.mtf_signals
        results.append(out)
    path.write_text(json.dumps(results,ensure_ascii=False),encoding='utf8'); return symbol

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);a=p.parse_args();PART.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(ROOT/'mod0_baz.csv.gz');d=d[d.tf.isin(['4h','1d']) & d.kalite_katmani.eq('A_ARTI') & ~d.sansurlu]
    jobs=[(s,g.to_dict('records')) for s,g in d.groupby('sembol')]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(worker,j) for j in jobs]
        for i,f in enumerate(concurrent.futures.as_completed(futures),1): print(f'{i}/{len(jobs)} {f.result()}',flush=True)
    df=pd.DataFrame([row for sym,_ in jobs for row in json.loads((PART/f'{sym}.json').read_text())]);assert len(df)==len(d) and df.olay_id.nunique()==len(d)
    df.to_csv(OUT/'olaylar.csv.gz',index=False); good=df[df.excluded=='']; summaries=[]
    for group,sub in [('tum',good),('kesif',good[good.donem=='kesif']),('dogrulama',good[good.donem=='dogrulama']),('4h',good[good.tf=='4h']),('1d',good[good.tf=='1d'])]:
        for name in CASES:
            v=sub[name+'_net']; delta=v-sub.baz_net; changed=sub[name+'_reason']!=sub.baz_reason
            summaries.append(dict(group=group,variant=name,n=len(sub),net=float(v.mean()),total=float(v.sum()),win=float((v>0).mean()),delta=float(delta.mean()),mtf_exit=int((sub[name+'_reason']=='MTF_EXIT_OPEN').sum()),signal_trades=int((sub[name+'_signals']>0).sum()),changed=int(changed.sum()),base_winners_affected=int((changed & (sub.baz_net>0)).sum()),base_losses_affected=int((changed & (sub.baz_net<=0)).sum()),reasons=sub[name+'_reason'].value_counts().to_dict()))
    (OUT/'ozet.json').write_text(json.dumps({'n':len(df),'excluded':df.excluded.value_counts().to_dict(),'old_base_net':float(good.old_net.mean()),'hour_base_net':float(good.baz_net.mean()),'abs_mean_base_diff':float((good.old_net-good.baz_net).abs().mean()),'summary':summaries},ensure_ascii=False,indent=2))
    print('DONE',len(df),len(good),flush=True)
if __name__=='__main__': main()
