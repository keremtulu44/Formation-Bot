from pathlib import Path
from collections import Counter
import hashlib, json
import numpy as np, pandas as pd
from research.arsiv import tf_frame, arsiv_koku
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from domain_engines.stabil import prepare_causal_ohlcv
from domain_engines.stabil.signals import _causal_atr14
from research.stabil_resistance_replay import native_mirror, project_daily_at_bar_open
root=Path(__file__).resolve().parents[1]; out=root/'docs/arastirma/stabil_direnc_replay_2026_11_06'; archive=arsiv_koku()
m=json.loads((out/'manifest.json').read_text()); s=json.loads((out/'summary.json').read_text());
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, val in m['source_sha256'].items():
    amended = m.get('post_replay_presentation_changes', {}).get(name)
    if amended:
        assert val == amended['replay_sha256']
        val = amended['final_sha256']
    assert sha(root/name)==val, f'source hash {name}'
for name, val in m.get('post_replay_verification_sha256', {}).items():
    assert sha(root/name)==val, f'verification source hash {name}'
for name, val in m['archive_sha256'].items(): assert sha(archive/name)==val, f'archive hash {name}'
for name, val in m['outputs_sha256'].items(): assert sha(out/name)==val, f'output hash {name}'
e=pd.read_csv(out/'events_4h.csv.gz',low_memory=False); n=pd.read_csv(out/'native_daily_events.csv.gz',low_memory=False); pairs=pd.read_csv(out/'matched_controls.csv.gz');
assert len(e)==m['events_4h'] and len(n)==m['events_native_daily']
assert not e.duplicated(['symbol','model','event','bar_index']).any()
p=e[e.model=='MIRROR_P4'].copy()
for col in ['origin_time','confirmed_time','first_available_time','daily_asof','event_open_time','event_close_time']:
    p[col]=pd.to_datetime(p[col],utc=True)
assert (p.origin_time<=p.confirmed_time).all()
assert (p.confirmed_time<=p.first_available_time).all()
assert (p.first_available_time<=p.daily_asof).all()
assert (p.daily_asof<=p.event_open_time).all()
assert (p.event_open_time<p.event_close_time).all()
assert (p.ceiling>=p.line).all()
for horizon in (4,8,16):
    v=e[f'status_{horizon}']=='VALID'
    assert e.loc[v,f'first_1atr_{horizon}'].notna().all()
    assert e.loc[~v,f'first_1atr_{horizon}'].isna().all()
    assert not e.loc[v,f'right_censored_{horizon}'].any()
    assert not e.loc[v,f'cross_split_{horizon}'].any()
calc=np.select([e.high<e.line,e.low>e.line,e.close>e.line],['NEAR_ONLY','GAP_ABOVE_NO_TOUCH','TOUCH_CLOSE_ABOVE'], default='WICK_TOUCH_CLOSE_AT_OR_BELOW')
assert np.all(calc==e.contact)
assert (abs(pairs.target_bar-pairs.control_bar)>=8).all()
assert not pairs.duplicated(['control_model','symbol','control_bar']).any()
assert not pairs.duplicated(['control_model','symbol','target_bar']).any()
lookup=e[e.event=='TEST'].set_index(['model','symbol','bar_index'])
for pair in pairs.itertuples():
    a=lookup.loc[('MIRROR_P4',pair.symbol,pair.target_bar)]; b=lookup.loc[(pair.control_model,pair.symbol,pair.control_bar)]
    assert a.quarter==b.quarter==pair.quarter and a.session_close==b.session_close==pair.session_close
    assert a.status_8==pair.target_status_8 and b.status_8==pair.control_status_8
    assert int(a.gap_to_line_atr>=.5)+int(a.gap_to_line_atr>=1)==pair.gap_bin
    assert int(b.gap_to_line_atr>=.5)+int(b.gap_to_line_atr>=1)==pair.gap_bin
    assert sum(a.prior_4bar_move_atr>=t for t in (-1,0,1))==pair.prior_move_bin
    assert sum(b.prior_4bar_move_atr>=t for t in (-1,0,1))==pair.prior_move_bin

def independent_first(hi,lo,close,atr):
    for h,l in zip(hi,lo):
        u,d=h>=close+atr,l<=close-atr
        if u and d:return 'AMBIGUOUS_SAME_BAR'
        if u:return 'UP_FIRST'
        if d:return 'DOWN_FIRST'
    return 'NEITHER'
sample=e[(e.model=='MIRROR_P4') & e.event.isin(['TEST','BREAK_UP','RETURN_DOWN','DEPART_BELOW']) & (e.status_8=='VALID')].sample(n=24,random_state=20261106)
for r in sample.itertuples():
    cut=capture_cutoffs(r.symbol); d=closed_at_capture(tf_frame(r.symbol,'1d'),'1d',cut['1d']); h=closed_at_capture(tf_frame(r.symbol,'4h'),'4h',cut['1h']);
    frame,err=prepare_causal_ohlcv(d,symbol=r.symbol,timeframe='1d'); assert not err
    line, obs, tl, _=native_mirror(frame); i=int(r.bar_index); di=int(project_daily_at_bar_open(pd.DatetimeIndex(frame.timestamp),h.index)[i]);
    assert abs(line.level[di]-r.line)<max(1e-8,abs(r.line)*1e-8)
    prefix, po, pt, _=native_mirror(frame.iloc[:di+1].copy().reset_index(drop=True))
    assert np.isclose(prefix.level[-1],line.level[di]) and np.isclose(prefix.ceiling[-1],line.ceiling[di])
    assert po[-1].support_identity==obs[di].support_identity
    assert pt[-1].validity==tl[di].validity and pt[-1].bars_since_support==tl[di].bars_since_support
    hs=h.high.to_numpy(); ls=h.low.to_numpy(); cs=h.close.to_numpy(); atr=_causal_atr14(hs,ls,cs)[i]
    assert np.isclose(hs[i],r.high) and np.isclose(ls[i],r.low) and np.isclose(cs[i],r.close)
    assert independent_first(hs[i+1:i+9],ls[i+1:i+9],cs[i],atr)==r.first_1atr_8
    assert np.isclose((cs[i+8]-cs[i])/atr,r.return_atr_8,rtol=1e-7,atol=1e-7)
main=e[(e.model=='MIRROR_P4') & (e.event=='TEST') & (e.period=='Y2026')]; valid=main[main.status_8=='VALID']
a=s['models']['MIRROR_P4']['Y2026']['8']; assert a['events']==len(main) and a['valid']==len(valid)
assert a['first_counts']=={k:int((valid.first_1atr_8==k).sum()) for k in ['DOWN_FIRST','UP_FIRST','AMBIGUOUS_SAME_BAR','NEITHER']}
assert a['real_touch']==int(((valid.low<=valid.line)&(valid.high>=valid.line)).sum())
print(json.dumps({'status':'OK','source_hashes':len(m['source_sha256']),'archive_hashes':len(m['archive_sha256']),
                  '4h_rows':len(e),'daily_native_rows':len(n),'matched_pairs':len(pairs),
                  'sampled_event_independent_prefix_and_paths':len(sample),
                  'mirror_2026_valid':len(valid),'actual_touch':a['real_touch'],
                  'event_counts':dict(Counter(e.event))},ensure_ascii=False,indent=2))
