#!/usr/bin/env python3
"""Teyit nedenlerini güçlü aynı-yön koşulu ve retest olarak sınıflandır."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
KEYS=['symbol','tf','segment_start','candidate_index']


def classify(candidates, checks):
    c=candidates[candidates.status=='KIRILIM_TEYITLI'].rename(columns={'local_index':'candidate_index'})
    if c.duplicated(KEYS).any(): raise ValueError('Aday kimliği yineleniyor')
    checks=checks[checks.next_state=='KIRILIM_TEYITLI']
    joined=c.merge(checks,on=KEYS,how='left',suffixes=('','_check'),validate='one_to_many',indicator=True)
    if not joined['_merge'].eq('both').all() or joined.duplicated(KEYS).any():
        raise ValueError('Her teyitli aday için tam bir teyit kontrolü gerekli')
    strong=joined.outside.astype(bool)&joined.strength_pass.astype(bool)
    retest=joined.retest.astype(bool)
    if not (strong|retest).all(): raise ValueError('Teyit nedeni bulunamadı')
    joined['reason']='YALNIZ_RETEST'
    joined.loc[strong&~retest,'reason']='YALNIZ_GUCLU_AYNI_YON'
    joined.loc[strong&retest,'reason']='HER_IKISI'
    return joined


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    p.add_argument('--output',type=Path,default=ROOT/'docs/arastirma/sonuclar/teyit_nedenleri')
    args=p.parse_args();a=args.input/'adaylar.csv.gz';c=args.input/'teyit_kontrolleri.csv.gz'
    data=classify(pd.read_csv(a),pd.read_csv(c));args.output.mkdir(parents=True,exist_ok=True)
    columns=KEYS+['period','direction','anchor','time','age','reason','outside','strength_pass','retest','strength','threshold']
    data[columns].sort_values(['symbol','tf','time']).to_csv(args.output/'olaylar.csv.gz',index=False,compression='gzip')
    data.groupby(['tf','period','direction','reason']).agg(n=('symbol','size'),stocks=('symbol','nunique')).reset_index().to_csv(args.output/'ozet.csv',index=False)
    paths=[a,c,Path(__file__).resolve()]
    meta={'n':len(data),'counts':data.reason.value_counts().to_dict(),
          'strong_definition':'outside AND strength_pass; retest ayrı koşul',
          'inputs_sha256':{str(x.resolve().relative_to(ROOT)) if x.resolve().is_relative_to(ROOT)
                           else str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}}
    (args.output/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    print(meta['counts'])


if __name__=='__main__':main()
