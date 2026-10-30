#!/usr/bin/env python3
"""Kaynak sıfır hacimlerini ve türetilen kovaların hammadde sayılarını ölç."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd  # noqa: E402
from config import sembol_turu  # noqa: E402
from research.arsiv import arsiv_sembolleri  # noqa: E402
from research.capraz_piyasa import read_frame  # noqa: E402


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    args=p.parse_args();rows=[];buckets=[]
    for s in arsiv_sembolleri():
        if sembol_turu(s)!='hisse': continue
        for tf in ('1h','1d'):
            f=read_frame(ROOT/'backfill_data'/f'{s}_{tf}.csv.gz')
            z=f.volume==0
            rows.append({'symbol':s,'tf':tf,'bars':len(f),'zero_volume':int(z.sum()),
                'zero_volume_0930':int((z & (f.index.strftime('%H:%M')=='09:30')).sum()) if tf=='1h' else 0})
            if tf=='1h':
                for target in ('2h','4h'):
                    counts=f.close.resample(target,offset='9h30min').count();counts=counts[counts>0].iloc[:-1]
                    for size,count in counts.value_counts().sort_index().items():
                        buckets.append({'symbol':s,'tf':target,'source_bars':int(size),'bucket_count':int(count)})
    args.output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output/'kaynak_veri_profili.csv',index=False)
    pd.DataFrame(buckets).to_csv(args.output/'kova_veri_profili.csv',index=False)
    print('Profil:',len(rows),'yerel seri')


if __name__=='__main__':main()
