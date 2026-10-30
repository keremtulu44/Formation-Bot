#!/usr/bin/env python3
"""Aday ve teyit kapanışlarını aynı teyitli olaylarda karşılaştır; canlıya dokunmaz."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = ['symbol', 'tf', 'segment_start', 'candidate_index']
METRICS = ('candidate_to_confirm_pct', 'candidate_to_candidate_end_pct',
           'confirm_to_candidate_end_pct', 'confirm_to_confirm_end_pct')


def build_comparison(candidates: pd.DataFrame, confirmations: pd.DataFrame) -> pd.DataFrame:
    """Yalnız iki ufku da geçerli olan teyitli olayları 1:1 birleştirir.

    Yüzdeler yön işaretli değil, gerçek fiyat değişimidir; aşağı düşüş negatiftir.
    Aday ve teyit sonrası hedef mumlar farklı olabilir; ortak hedef ayrıca verilir.
    """
    candidates = candidates[candidates.status == 'KIRILIM_TEYITLI'].copy().rename(columns={
        'local_index': 'candidate_index', 'direction': 'candidate_direction',
        'period': 'candidate_period', 'outcome_status': 'candidate_outcome_status',
        'nonoverlap': 'candidate_nonoverlap', 'anchor': 'candidate_anchor',
        'confirm_time': 'candidate_confirm_time', 'outcome_end_time': 'candidate_end_time',
    })
    if candidates.duplicated(KEYS).any() or confirmations.duplicated(KEYS).any():
        raise ValueError('Aday veya teyit kimliği yinelenmiş')
    data = confirmations.merge(candidates, on=KEYS, how='outer', validate='one_to_one',
                               indicator=True, suffixes=('', '_candidate'))
    if not data['_merge'].eq('both').all():
        raise ValueError('Aday ve teyit kayıtları bire bir eşleşmedi')
    if not ((data.direction == data.candidate_direction) &
            (data.period == data.candidate_period) &
            (data.candidate_time == data.candidate_anchor) &
            (data.confirm_time == data.candidate_confirm_time)).all():
        raise ValueError('Eşleşen aday ve teyit kimlik/zaman/yön/dönem alanları uyuşmuyor')
    data = data[(data.candidate_outcome_status == 'VALID') & (data.outcome_status == 'VALID')].copy()
    if not ((data.anchor_close > 0) & (data.confirm_close > 0) & (data.anchor_atr > 0)).all():
        raise ValueError('Geçersiz fiyat/ATR')
    data['candidate_end_close'] = data.anchor_close + data.direction * data.end_atr * data.anchor_atr
    data['confirmation_end_close'] = data.confirm_close * (1 + data.direction * data.end10_pct / 100)
    if not ((data.candidate_end_close > 0) & (data.confirmation_end_close > 0)).all():
        raise ValueError('Hedef fiyatı pozitif değil')
    data['candidate_to_confirm_pct'] = 100 * (data.confirm_close / data.anchor_close - 1)
    data['candidate_to_candidate_end_pct'] = 100 * (data.candidate_end_close / data.anchor_close - 1)
    data['confirm_to_candidate_end_pct'] = 100 * (data.candidate_end_close / data.confirm_close - 1)
    data['confirm_to_confirm_end_pct'] = 100 * (data.confirmation_end_close / data.confirm_close - 1)
    columns = KEYS + ['period', 'direction', 'pattern', 'candidate_time', 'confirm_time',
        'confirm_delay', 'anchor_close', 'anchor_atr', 'confirm_close', 'confirm_atr',
        'candidate_end_time', 'candidate_end_close', 'end_time', 'confirmation_end_close',
        'candidate_nonoverlap', 'nonoverlap', *METRICS]
    return data[columns].sort_values(['symbol', 'tf', 'candidate_time']).reset_index(drop=True)


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    result=[]
    for selection in ('raw_valid', 'confirm_nonoverlap'):
        selected = data if selection == 'raw_valid' else data[data.nonoverlap]
        for (tf, period, direction), group in selected.groupby(['tf', 'period', 'direction'], sort=True):
            row={'selection': selection, 'tf':tf, 'period':period, 'direction':int(direction),
                 'n':len(group), 'stocks':int(group.symbol.nunique())}
            for col in METRICS:
                values=group[col]
                row[f'{col}_median']=float(values.median())
                for q in (10, 25, 75, 90):
                    row[f'{col}_p{q}']=float(values.quantile(q/100))
            result.append(row)
    return pd.DataFrame(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz')
    parser.add_argument('--confirmations',type=Path,default=ROOT/'docs/arastirma/sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/arastirma/sonuclar/aday_teyit_karsilastirma')
    args=parser.parse_args()
    data=build_comparison(pd.read_csv(args.candidates),pd.read_csv(args.confirmations))
    args.output.mkdir(parents=True,exist_ok=True)
    data.to_csv(args.output/'olaylar.csv.gz',index=False,compression='gzip')
    summarize(data).to_csv(args.output/'ozet.csv',index=False)
    by_stock = (data[data.nonoverlap].groupby(['symbol', 'tf', 'period', 'direction'])
                .agg(n=('candidate_index', 'size'),
                     candidate_to_confirm_pct_median=('candidate_to_confirm_pct', 'median'),
                     candidate_to_candidate_end_pct_median=('candidate_to_candidate_end_pct', 'median'),
                     confirm_to_candidate_end_pct_median=('confirm_to_candidate_end_pct', 'median'),
                     confirm_to_confirm_end_pct_median=('confirm_to_confirm_end_pct', 'median'))
                .reset_index())
    by_stock.to_csv(args.output/'hisse_tf_ozet.csv',index=False)
    paths=[args.candidates,args.confirmations,Path(__file__).resolve()]
    manifest={'inputs_sha256':{str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT)
                                  else str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              'valid_matched':len(data), 'confirmation_nonoverlap':int(data.nonoverlap.sum()),
              'raw_and_filtered_are_separate':True, 'price_change_sign':'actual price; negative means fall',
              'candidate_target':'10th close after candidate', 'confirmation_target':'10th close after confirmation',
              'common_target':'same 10th close after candidate',
              'selection':'valid in both horizons; nonoverlap computed on confirmation windows by source'}
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('Eşleşen geçerli olay:',len(data),'teyit penceresi örtüşmeyen:',int(data.nonoverlap.sum()))


if __name__=='__main__':
    main()
