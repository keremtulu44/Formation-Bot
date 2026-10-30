#!/usr/bin/env python3
"""Son yerel mum doğrulanmamışsa hedefini sansürle; özetleri yeniden üret."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'docs/arastirma/sonuclar/kirilim_replay')
    parser.add_argument('--workdir',type=Path,default=ROOT/'var/kirilim_replay/checkpoints')
    args=parser.parse_args(); out=args.input
    meta=json.loads((out/'manifest.json').read_text()); e=pd.read_csv(out/'adaylar.csv.gz')
    last={(s,tf):x['last'] for s,v in meta['series'].items() for tf,x in v.items()}
    mask=e.apply(lambda x: x.tf in ('1h','1d') and x.outcome_status=='VALID'
                 and x.outcome_end_time==last.get((x.symbol,x.tf)),axis=1)
    e.loc[mask,'outcome_status']='LAST_BAR_UNCERTAIN'
    # Tekrarlı çalıştırmada da en erken uygun adayları yeniden seç.
    e['nonoverlap']=False
    for _, group in e.sort_values(['symbol','tf','anchor']).groupby(['symbol','tf'],sort=False):
        last_end=None
        for row in group.itertuples():
            if row.outcome_status!='VALID': continue
            anchor=pd.Timestamp(row.anchor)
            if last_end is None or anchor>last_end:
                e.at[row.Index,'nonoverlap']=True
                last_end=pd.Timestamp(row.outcome_end_time)
    e.to_csv(out/'adaylar.csv.gz',index=False,compression='gzip')
    q=e[(e.outcome_status=='VALID')&e.nonoverlap].copy()
    q['cohort']=q.status_at_horizon.map({'KIRILIM_TEYITLI':'CONFIRMED','KIRILIM_TEYIT_ALAMADI':'TIMEOUT',
                                         'BASARISIZ_KIRILIM':'FAILED'}).fillna('OTHER_OR_UNKNOWN')
    rows=[]
    for (tf,period,direction,cohort),g in q.groupby(['tf','period','direction','cohort'],sort=True):
        c=g[g.confirm_bars.notna()]
        rows.append({'tf':tf,'period':period,'direction':direction,'cohort':cohort,'n':len(g),
            'stocks':g.symbol.nunique(),'hit_favorable':int(g.hit_favorable.eq(True).sum()),
            'hit_adverse':int(g.hit_adverse.eq(True).sum()),
            'end_favorable':int(g.end_favorable.eq(True).sum()),
            'median_end_atr':g.end_atr.median(),'median_peak_atr':g.max_favorable_atr.median(),
            'confirmed_n':len(c),'median_confirm_bars':c.confirm_bars.median() if len(c) else None,
            'median_at_confirm_atr':c.at_confirm_atr.median() if len(c) else None})
    pd.DataFrame(rows).to_csv(out/'ozet.csv',index=False)
    files=[ROOT/'config.py',ROOT/'data/replay.py',ROOT/'research/arsiv.py',ROOT/'research/capraz_piyasa.py',
           ROOT/'research/kirilim_denetim.py',ROOT/'scripts/kirilim_replay.py',ROOT/'scripts/kirilim_kontrolleri.py',
           ROOT/'scripts/kirilim_veri_profili.py',ROOT/'scripts/kirilim_iki_mum.py',ROOT/'scripts/kirilim_sonuc_sansuru.py',
           *sorted((ROOT/'patterns').glob('*.py'))]
    meta['dependency_sha256']={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}
    meta['runtime']={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
                     'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    times=[p.stat().st_mtime for p in args.workdir.glob('*.json')]
    if times:
        meta['checkpoint_write_window_utc']=[datetime.fromtimestamp(t,timezone.utc).isoformat() for t in (min(times),max(times))]
    meta['uncertain_final_native_outcomes']=int((e.outcome_status=='LAST_BAR_UNCERTAIN').sum())
    meta['postprocess_note']='1h/1d son native mum hedefine denk gelen adaylar sansürlendi; hashler çalıştırılan dosyalardır.'
    (out/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    print('Son muma bağlı sansür:',meta['uncertain_final_native_outcomes'],'filtrelenmiş aday:',len(q))


if __name__=='__main__': main()
