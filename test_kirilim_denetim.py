import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from patterns.lifecycle import f_breakout_strength
from research.kirilim_denetim import frame_for, label_events, reference_strength, replay_segment, segments


def test_independent_strength_boundaries_and_zero_volume():
    for direction in (1,-1):
        for volume, average in [(0, 100), (None, None), (150, 100)]:
            args=(100., 110., 95., 105., volume, average, direction, 102., 4., .06, .01)
            actual, *parts=f_breakout_strength(*args)
            score, ref=reference_strength(*args)
            assert score == pytest.approx(actual, abs=1e-10)
            assert parts == pytest.approx(ref, abs=1e-10)
            assert 0 <= score <= 100


def test_thyao_reason_and_prefix_no_future_leak():
    frame, inherited, _=frame_for(Path('backfill_data'), 'THYAO', '1d')
    bad, blocks=segments(frame,inherited)
    assert not bad.any() and len(blocks)==1
    full, checks, err=replay_segment(frame,'THYAO','1d')
    candidate=next(e for e in full if e['anchor'].startswith('2026-06-12'))
    assert candidate['status']=='KIRILIM_TEYIT_ALAMADI'
    relevant=[x for x in checks if x['candidate_index']==candidate['local_index']]
    assert [round(x['strength'], 1) for x in relevant[:2]]==[33.0,35.6]
    assert all(not x['strength_pass'] and not x['retest'] for x in relevant[:2])
    assert err < 1e-9 and all(c['decision_invariant_ok'] for c in checks)
    cut=candidate['local_index']+1
    earlier, _, _=replay_segment(frame.iloc[:cut], 'THYAO','1d')
    match=next(e for e in earlier if e['anchor']==candidate['anchor'])
    for field in ('direction','candidate_state','pattern','pattern_age','anchor_close','anchor_atr','candidate_strength'):
        assert match[field]==pytest.approx(candidate[field]) if isinstance(candidate[field],float) else match[field]==candidate[field]


def test_right_censor_boundary_and_direction():
    close=[100.]*91
    close[81:91]=[105.]*10
    idx=pd.date_range('2025-01-01', periods=91, tz='UTC')
    f=pd.DataFrame({'open':close, 'high':np.array(close)+1, 'low':np.array(close)-1, 'close':close},index=idx)
    e={'local_index':80,'direction':1,'identity':1,'terminal_index':None,'confirm_index':None,'status':'RIGHT_CENSORED'}
    row=label_events([e],f,idx[90])[0]
    assert row['outcome_status']=='BOUNDARY_PURGED' and row['hit_favorable'] is None
    row=label_events([e],f,idx[80])[0]
    assert row['outcome_status']=='VALID' and row['end_favorable'] and row['hit_favorable']
    row=label_events([dict(e,local_index=85)],f,idx[80],data_break_at_end=True)[0]
    assert row['outcome_status']=='DATA_BREAK_CENSORED' and row['status']=='DATA_BREAK_CENSORED'
    assert math.isfinite(row['anchor_atr']) if 'anchor_atr' in row else True


def test_bounded_prefix_view_prevents_future_access():
    from research.kirilim_denetim import PrefixList
    values=PrefixList([1,2,3,4]);values.limit=2
    assert len(values)==2 and list(values)==[1,2] and values[-1]==2 and values[::-1]==[2,1]
    with pytest.raises(IndexError): _=values[2]


def test_long_series_prefix_and_future_mutation_agree():
    f, _, _=frame_for(Path('backfill_data'),'THYAO','1h')
    f=f.iloc[:1800].copy(); cutoff=1200
    full, _, _=replay_segment(f,'THYAO','1h')
    prefix, _, _=replay_segment(f.iloc[:cutoff], 'THYAO','1h')
    fields=('local_index','candidate_state','direction','pattern')
    assert [tuple(x[k] for k in fields) for x in full if x['local_index'] < cutoff] == [tuple(x[k] for k in fields) for x in prefix]
    f.iloc[cutoff:, f.columns.get_loc('close')] *= 1.02
    changed,_,_=replay_segment(f,'THYAO','1h')
    assert [tuple(x[k] for k in fields) for x in full if x['local_index'] < cutoff] == [tuple(x[k] for k in fields) for x in changed if x['local_index'] < cutoff]


def test_fast_causal_replay_matches_real_incremental_processing():
    from patterns.lifecycle import ArgentEngine
    f, _, _=frame_for(Path('backfill_data'),'THYAO','1h')
    f=f.iloc[:1000]
    fast, _, _=replay_segment(f,'THYAO','1h')
    engine=ArgentEngine(timeframe='1h'); incremental=[]
    for i in range(len(f)):
        old=engine.break_candidate_bar; snapshot=engine.process(f.iloc[:i+1])
        if snapshot.state in ('KIRILIM_ADAYI','KIRILIM_DENEMESI') and engine.break_candidate_bar==i and old!=i and i>=79:
            incremental.append((i,snapshot.state,snapshot.break_dir,engine.active.pattern_type))
    assert incremental == [(x['local_index'],x['candidate_state'],x['direction'],x['pattern']) for x in fast]


def test_last_native_bar_is_censored_and_idempotent(tmp_path, monkeypatch):
    import json
    import sys
    import pandas as pd
    from scripts.kirilim_sonuc_sansuru import main
    out=tmp_path/'out';out.mkdir()
    last='2026-01-31 00:00:00+03:00'
    (out/'manifest.json').write_text(json.dumps({'series':{'ABC':{'1d':{'last':last}}}}))
    common={'symbol':'ABC','tf':'1d','direction':1,'period':'validation','status_at_horizon':'KIRILIM_TEYITLI',
            'outcome_status':'VALID','hit_favorable':True,'hit_adverse':False,'end_favorable':True,
            'end_atr':2.1,'max_favorable_atr':2.2,'confirm_bars':1,'at_confirm_atr':.4}
    pd.DataFrame([{**common,'anchor':'2026-01-01 00:00:00+03:00','outcome_end_time':'2026-01-12 00:00:00+03:00'},
                  {**common,'anchor':'2026-01-20 00:00:00+03:00','outcome_end_time':last}]).to_csv(out/'adaylar.csv.gz',index=False)
    monkeypatch.setattr(sys,'argv',['censor','--input',str(out),'--workdir',str(tmp_path)])
    main();main()
    e=pd.read_csv(out/'adaylar.csv.gz')
    assert list(e.outcome_status)==['VALID','LAST_BAR_UNCERTAIN']
    assert list(e.nonoverlap)==[True,False]
    assert json.loads((out/'manifest.json').read_text())['uncertain_final_native_outcomes']==1
