#!/usr/bin/env python3
"""Geçerli adayların başlangıca göre ilk iki kapanış gelişimi."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd  # noqa: E402
from research.kirilim_denetim import frame_for, segments  # noqa: E402


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    args=p.parse_args();out=args.input
    events=pd.read_csv(out/'adaylar.csv.gz');events=events[events.outcome_status=='VALID'];rows=[];errors={}
    for (symbol,tf),group in events.groupby(['symbol','tf']):
        try:
            frame,inherited,_=frame_for(ROOT/'backfill_data',symbol,tf);_,blocks=segments(frame,inherited)
            by_start={str(b.index[0]):b for b in blocks}
            for ev in group.itertuples():
                block=by_start[ev.segment_start];i=ev.local_index
                if i+2>=len(block): raise ValueError('geçerli sonuçta eksik ilk iki mum')
                moves=(block.close.iloc[i+1:i+3].to_numpy()-ev.anchor_close)*ev.direction/ev.anchor_atr
                rows.append({'symbol':symbol,'tf':tf,'segment_start':ev.segment_start,'anchor':ev.anchor,
                    'period':ev.period,'direction':ev.direction,'status':ev.status_at_horizon,'nonoverlap':ev.nonoverlap,
                    'end2_atr':float(moves[-1]),'max2_atr':float(max(moves)),'min2_atr':float(min(moves)),
                    'path2_favorable':bool(max(moves)>=2),'path2_adverse':bool(min(moves)<=-2)})
        except (ValueError,KeyError,IndexError,OSError,TypeError) as ex:
            errors[f'{symbol}:{tf}']=str(ex)
    if errors: raise RuntimeError(f'İki mum hesabı eksik: {errors}')
    d=pd.DataFrame(rows);d.to_csv(out/'iki_mum.csv.gz',index=False,compression='gzip')
    selected=d[d.nonoverlap]; summary=[]
    for (tf,period,direction,status),g in selected.groupby(['tf','period','direction','status']):
        summary.append({'tf':tf,'period':period,'direction':direction,'status':status,'n':len(g),
            'median_end2_atr':g.end2_atr.median(),'path2_favorable':int(g.path2_favorable.sum()),
            'path2_adverse':int(g.path2_adverse.sum())})
    pd.DataFrame(summary).to_csv(out/'iki_mum_ozet.csv',index=False)
    print('İki mum:',len(d),'aday, hata 0')


if __name__=='__main__':main()
