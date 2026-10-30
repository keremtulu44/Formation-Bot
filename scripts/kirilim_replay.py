#!/usr/bin/env python3
"""Tüm hisse arşivinde araştırma Replay'i; canlı teslimatı ölçmez."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from config import sembol_turu  # noqa: E402
from research.arsiv import arsiv_sembolleri  # noqa: E402
from research.kirilim_denetim import frame_for, label_events, replay_segment, segments  # noqa: E402

TFS = ('1h', '2h', '4h', '1d')


def worker(symbol, output):
    folder=Path(output); checkpoint=folder/'checkpoints'/f'{symbol}.json'
    hashes={tf:hashlib.sha256((ROOT/'backfill_data'/f'{symbol}_{tf}.csv.gz').read_bytes()).hexdigest() for tf in ('1h','1d')}
    code_hash=hashlib.sha256((ROOT/'research/kirilim_denetim.py').read_bytes()+(ROOT/'scripts/kirilim_replay.py').read_bytes()).hexdigest()
    if checkpoint.exists():
        previous=json.loads(checkpoint.read_text())
        if previous.get('source_sha256')==hashes and previous.get('code_sha256')==code_hash:
            return previous
    results={'symbol':symbol,'source_sha256':hashes,'code_sha256':code_hash,'series':{},'events':[],'checks':[],'errors':{}}
    for tf in TFS:
        try:
            frame, inherited, info=frame_for(ROOT/'backfill_data',symbol,tf)
            if len(frame)<100: raise ValueError('Yetersiz bar')
            bad, blocks=segments(frame,inherited)
            split=frame.index[int(len(frame)*.7)]
            info.update({'bars':len(frame),'bad_bars':int(bad.sum()),'blocks':len(blocks),'split':str(split),
                         'first':str(frame.index[0]),'last':str(frame.index[-1]),'max_math_error':0.,'prefix_samples':[]})
            evs, checks = [], []
            for block in blocks:
                events, trace, error=replay_segment(block,symbol,tf)
                end_is_break = block.index[-1] < frame.index[-1]
                rows=label_events(events,block,split,data_break_at_end=end_is_break)
                for row in rows: row['segment_start']=str(block.index[0]); row['segment_end']=str(block.index[-1])
                for row in trace: row['segment_start']=str(block.index[0])
                evs.extend(rows); checks.extend(trace)
                info['max_math_error']=max(info['max_math_error'],error)
                # İki ayrı prefix üzerinde, geleceği hiç vermeyen yeniden kurulum.
                if events:
                    for index in sorted(set([events[len(events)//2]['local_index'],events[-1]['local_index']])):
                        prefix, _, _=replay_segment(block.iloc[:index+1],symbol,tf)
                        expected=[x for x in events if x['local_index'] <= index]
                        actual=[(x['local_index'],x['candidate_state'],x['direction'],x['pattern']) for x in prefix]
                        target=[(x['local_index'],x['candidate_state'],x['direction'],x['pattern']) for x in expected]
                        info['prefix_samples'].append({'at':str(block.index[index]),'expected':len(target),'observed':len(actual),'equal':target==actual})
            # Aynı hisse/TF içinde daha önceki on mumla örtüşen adayları ayrı raporla.
            last_end=None
            for event in sorted(evs,key=lambda x:x['anchor']):
                usable=event['outcome_status']=='VALID'
                anchor=pd.Timestamp(event['anchor']); end=pd.Timestamp(event['outcome_end_time']) if event['outcome_end_time'] else None
                event['nonoverlap']=bool(usable and (last_end is None or anchor>last_end))
                if event['nonoverlap']: last_end=end
            info['candidates']=len(evs); info['checks']=len(checks)
            results['events'].extend(evs); results['checks'].extend(checks); results['series'][tf]=info
        except (ValueError, OSError, KeyError, IndexError, TypeError, ZeroDivisionError) as exc:
            results['errors'][tf]=f'{type(exc).__name__}: {exc}'
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    temp=checkpoint.with_suffix('.tmp');temp.write_text(json.dumps(results,ensure_ascii=False,allow_nan=False));os.replace(temp,checkpoint)
    return results


def write_outputs(results, output):
    output.mkdir(parents=True,exist_ok=True)
    events=pd.DataFrame([e for r in results for e in r['events']]); checks=pd.DataFrame([e for r in results for e in r['checks']])
    meta={'symbols':len(results),'requested_tfs':list(TFS),'series_ok':sum(len(r['series']) for r in results),
          'errors':{r['symbol']:r['errors'] for r in results if r['errors']},
          'source_sha256':{r['symbol']:r['source_sha256'] for r in results},
          'code_sha256': sorted({r['code_sha256'] for r in results}),
          'series':{r['symbol']:r['series'] for r in results},'events':len(events),'checks':len(checks),
          'mode':'historical_offline_unverified_sessions_not_actual_notifications'}
    if events.empty:
        raise RuntimeError('Hiç aday yok; sonuç yazılmadı')
    events.sort_values(['symbol','tf','anchor']).to_csv(output/'adaylar.csv.gz',index=False,compression='gzip')
    checks.sort_values(['symbol','tf','segment_start','candidate_index','bar_index']).to_csv(output/'teyit_kontrolleri.csv.gz',index=False,compression='gzip')
    clean=events[(events.outcome_status=='VALID') & events.nonoverlap.astype(bool)].copy()
    clean['cohort']=clean.status_at_horizon.map({'KIRILIM_TEYITLI':'CONFIRMED','KIRILIM_TEYIT_ALAMADI':'TIMEOUT',
                                                 'BASARISIZ_KIRILIM':'FAILED'}).fillna('OTHER_OR_UNKNOWN')
    rows=[]
    for (tf,period,direction,cohort),group in clean.groupby(['tf','period','direction','cohort'],sort=True):
        confirmed=group[group.confirm_bars.notna()]
        rows.append({'tf':tf,'period':period,'direction':direction,'cohort':cohort,'n':len(group),
            'stocks':group.symbol.nunique(),'hit_favorable':int(group.hit_favorable.sum()),
            'hit_adverse':int(group.hit_adverse.sum()),'end_favorable':int(group.end_favorable.sum()),
            'median_end_atr':group.end_atr.median(), 'median_peak_atr':group.max_favorable_atr.median(),
            'confirmed_n':len(confirmed),'median_confirm_bars':confirmed.confirm_bars.median() if len(confirmed) else None,
            'median_at_confirm_atr':confirmed.at_confirm_atr.median() if len(confirmed) else None})
    pd.DataFrame(rows).to_csv(output/'ozet.csv',index=False)
    (output/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    print('Tamamlandı:',meta['symbols'],'hisse,',meta['series_ok'],'seri,',len(events),'aday,',len(checks),'teyit kontrolü; hata:',len(meta['errors']),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbols',help='Virgülle hisse; varsayılan tüm arşiv hisseleri')
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--workdir',type=Path,default=ROOT/'var/kirilim_replay')
    p.add_argument('--output',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    args=p.parse_args()
    universe=[s for s in arsiv_sembolleri() if sembol_turu(s)=='hisse']
    symbols=universe if not args.symbols else [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    if not symbols or len(set(symbols))!=len(symbols) or any(x not in universe for x in symbols):
        p.error('Sembol arşivdeki hisselerden seçilmeli ve yinelenmemeli')
    if args.workers < 1 or args.workers>4: p.error('workers 1–4 olmalı')
    args.workdir.mkdir(parents=True,exist_ok=True)
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(worker,s,str(args.workdir)):s for s in symbols}
        for n,future in enumerate(as_completed(futures),1):
            symbol=futures[future]
            try:
                result=future.result(); results.append(result)
                print(f'{n}/{len(symbols)} {symbol}: {len(result["events"])} aday, hatalar={result["errors"]}',flush=True)
            except Exception as exc:  # noqa: BLE001 - her hata kapsam raporunda görünür
                results.append({'symbol':symbol,'source_sha256':{},'code_sha256':'ERROR','series':{},'events':[],
                                'checks':[],'errors':{'worker':f'{type(exc).__name__}: {exc}'}})
                print(f'{n}/{len(symbols)} {symbol}: İŞ HATASI {exc}',flush=True)
    write_outputs(results,args.output)


if __name__=='__main__':
    main()
