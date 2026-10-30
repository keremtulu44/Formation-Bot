#!/usr/bin/env python3
"""Teyit kapanışından SONRA sabit 10 bar OHLC kapanış hareketi; offline araştırma."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from research.capraz_piyasa import quality  # noqa: E402
from research.kirilim_denetim import frame_for, segments  # noqa: E402

HORIZON=10


def measure_window(block, index, atr, direction, split, period, *, native_last=None, data_break=False):
    """Teyit sonrası barlar: değişmeyen teyit ATR'si, yalnız kapanışlar."""
    if not math.isfinite(atr) or atr<=0:
        return {'outcome_status':'INVALID_ATR'}
    end=index+HORIZON
    if end>=len(block):
        return {'outcome_status':'DATA_BREAK_CENSORED' if data_break else 'RIGHT_CENSORED'}
    if period=='discovery' and block.index[end]>=split:
        return {'outcome_status':'BOUNDARY_PURGED'}
    if native_last is not None and block.index[end]==native_last:
        return {'outcome_status':'LAST_BAR_UNCERTAIN'}
    start=float(block.close.iloc[index]); prices=block.close.iloc[index+1:end+1].to_numpy(dtype=float)
    moves=(prices-start)*direction/atr
    pct=(prices-start)*direction/start*100
    result={'outcome_status':'VALID','confirm_close':start,'confirm_atr':atr,'end_time':str(block.index[end]),
            'max_favorable_atr':float(max(0,max(moves))), 'max_adverse_atr':float(min(0,min(moves))),
            'path_plus1':bool(max(moves)>=1), 'path_plus2':bool(max(moves)>=2),
            'path_minus1':bool(min(moves)<=-1), 'path_minus2':bool(min(moves)<=-2)}
    for h in (1,2,5,10):
        result[f'end{h}_atr']=float(moves[h-1]);result[f'end{h}_pct']=float(pct[h-1])
    return result


def choose_nonoverlap(rows):
    """Her sembol/TF için ilk teyitten itibaren on mum bitene kadar bekle."""
    last_end={}
    for row in sorted(rows,key=lambda r:(r['symbol'],r['tf'],r['confirm_time'])):
        row['nonoverlap']=False
        if row['outcome_status']!='VALID':continue
        key=(row['symbol'],row['tf']);when=pd.Timestamp(row['confirm_time'])
        if key not in last_end or when>last_end[key]:
            row['nonoverlap']=True
            last_end[key]=pd.Timestamp(row['end_time'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    p.add_argument('--output',type=Path,default=ROOT/'docs/arastirma/sonuclar/teyit_sonrasi')
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    events=pd.read_csv(args.input/'adaylar.csv.gz');events=events[events.status=='KIRILIM_TEYITLI']
    rows=[];errors={}; series_count=0
    for (symbol,tf),group in events.groupby(['symbol','tf']):
        try:
            frame,inherited,_=frame_for(ROOT/'backfill_data',symbol,tf)
            _,blocks=segments(frame,inherited)
            by_start={str(b.index[0]):(b,quality(b)[2]) for b in blocks}
            split=frame.index[int(len(frame)*.7)]
            series_rows=[]
            for ev in group.itertuples():
                block,atr=by_start[ev.segment_start]
                idx=int(ev.confirm_index)
                if str(block.index[idx])!=ev.confirm_time: raise ValueError(f'teyit indeksi uyuşmuyor: {ev.confirm_time}')
                x={'symbol':symbol,'tf':tf,'direction':int(ev.direction),'period':ev.period,
                   'pattern':ev.pattern,'segment_start':ev.segment_start,'candidate_time':ev.anchor,
                   'confirm_time':ev.confirm_time,'candidate_index':int(ev.local_index),
                   'confirm_index':idx,'confirm_delay':idx-int(ev.local_index)}
                x.update(measure_window(block,idx,float(atr.iloc[idx]),x['direction'],split,x['period'],
                    native_last=frame.index[-1] if tf in ('1h','1d') else None,
                    data_break=block.index[-1]<frame.index[-1]))
                series_rows.append(x)
            rows.extend(series_rows);series_count+=1
        except (ValueError, KeyError, IndexError, TypeError, OSError) as exc:
            errors[f'{symbol}:{tf}']=f'{type(exc).__name__}: {exc}'
        print(symbol,tf,flush=True)
    if errors: raise RuntimeError(f'Seri hataları: {errors}')
    choose_nonoverlap(rows);data=pd.DataFrame(rows)
    data.to_csv(out/'teyit_sonrasi_olaylar.csv.gz',index=False,compression='gzip')
    result=[]
    for selection in ('raw','nonoverlap'):
        selected=data[(data.outcome_status=='VALID') & (data.nonoverlap if selection=='nonoverlap' else True)]
        for (tf,period,direction),g in selected.groupby(['tf','period','direction']):
            r={'selection':selection,'tf':tf,'period':period,'direction':direction,'n':len(g),'stocks':g.symbol.nunique()}
            for col in ('path_plus1','path_plus2','path_minus1','path_minus2'):
                r[col]=int(g[col].eq(True).sum())
            for col in ('end1_atr','end2_atr','end5_atr','end10_atr','end10_pct','max_favorable_atr','max_adverse_atr'):
                r[f'median_{col}']=float(g[col].median())
            r['end10_positive']=int((g.end10_atr>0).sum())
            r['end10_plus2']=int((g.end10_atr>=2).sum())
            r['end10_minus2']=int((g.end10_atr<=-2).sum())
            r['both_plus2_minus2']=int((g.path_plus2.eq(True)&g.path_minus2.eq(True)).sum())
            result.append(r)
    pd.DataFrame(result).to_csv(out/'ozet.csv',index=False)
    files=[args.input/'adaylar.csv.gz',ROOT/'scripts/kirilim_teyit_sonrasi.py',
           ROOT/'research/kirilim_denetim.py',ROOT/'research/capraz_piyasa.py']
    manifest={'source_sha256':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files},
              'confirmed_input':len(events),'series_with_confirmed':series_count,'errors':errors,
              'outcome_status':data.outcome_status.value_counts().to_dict(),
              'valid_nonoverlap':int(data.nonoverlap.sum()), 'horizon_bars':HORIZON,
              'baseline':'confirmation close and confirmation ATR (14-bar Wilder, clean segment)',
              'price_basis':'subsequent closes, not intrabar extremes, fills, or Telegram delivery'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('Tamamlandı:',manifest,flush=True)


if __name__=='__main__':main()
