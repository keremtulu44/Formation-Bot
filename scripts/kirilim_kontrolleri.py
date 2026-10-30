#!/usr/bin/env python3
"""Aday başlangıcı olmayan anlara ait eşleşmemiş sabit-ızgara kontrolleri."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd  # noqa: E402
from research.capraz_piyasa import quality  # noqa: E402
from research.kirilim_denetim import HORIZON, WARMUP, frame_for, segments  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    args=parser.parse_args(); out=args.input
    events=pd.read_csv(out/'adaylar.csv.gz'); meta=json.loads((out/'manifest.json').read_text()); rows=[]
    counts={'series_ok':0,'errors':{},'boundary_purged':0,'right_censored':0,
            'uncertain_final_native_bar':0,'active_candidate_excluded':0}
    for symbol, series in meta['series'].items():
        for tf in series:
            try:
                f, inherited, _=frame_for(ROOT/'backfill_data',symbol,tf)
                _, blocks=segments(f,inherited); split=f.index[int(len(f)*.7)]
                for block in blocks:
                    _,_,atr=quality(block); active=[False]*len(block)
                    relevant=events[(events.symbol==symbol)&(events.tf==tf)&(events.segment_start==str(block.index[0]))]
                    for ev in relevant.itertuples():
                        start=int(ev.local_index)
                        end=int(ev.terminal_index) if pd.notna(ev.terminal_index) else len(block)-1
                        for i in range(start,min(end+1,len(block))): active[i]=True
                    # İlk ızgara noktasını atla: ısınma sırasında başlayan ve
                    # aday dosyasına alınmayan yaşam döngüleri dışarıda kalır.
                    for i in range(WARMUP-1+HORIZON,len(block),HORIZON):
                        if active[i]:
                            counts['active_candidate_excluded']+=1;continue
                        h=i+HORIZON
                        if h>=len(block): counts['right_censored']+=1;continue
                        if tf in ('1h','1d') and block.index[h]==f.index[-1]:
                            counts['uncertain_final_native_bar']+=1;continue
                        period='discovery' if block.index[i]<split else 'validation'
                        if period=='discovery' and block.index[h]>=split:
                            counts['boundary_purged']+=1;continue
                        a=float(atr.iloc[i])
                        if not a>0: continue
                        p=float(block.close.iloc[i]); move=(block.close.iloc[i+1:h+1].to_numpy()-p)/a
                        rows.append({'symbol':symbol,'tf':tf,'anchor':str(block.index[i]),'period':period,
                            'up_end':bool(move[-1]>=2),'down_end':bool(move[-1]<=-2),
                            'up_path':bool(max(move)>=2),'down_path':bool(min(move)<=-2),
                            'end_atr':float(move[-1])})
                counts['series_ok']+=1
            except (ValueError,KeyError,IndexError,OSError,TypeError) as e:
                counts['errors'][f'{symbol}:{tf}']=f'{type(e).__name__}: {e}'
        print(symbol,flush=True)
    data=pd.DataFrame(rows)
    if data.empty: raise RuntimeError('Kontrol penceresi yok')
    data.to_csv(out/'kontroller.csv.gz',index=False,compression='gzip')
    summary=[]
    for (tf,period),g in data.groupby(['tf','period']):
        for direction in ('up','down'):
            summary.append({'tf':tf,'period':period,'direction':direction,'n':len(g),
                'stocks':g.symbol.nunique(),'path':int(g[f'{direction}_path'].sum()),
                'end':int(g[f'{direction}_end'].sum())})
    pd.DataFrame(summary).to_csv(out/'kontrol_ozet.csv',index=False)
    counts['controls']=len(data)
    (out/'kontrol_manifest.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2))
    print('Kontroller:',len(data),'hata:',len(counts['errors']))


if __name__=='__main__': main()
