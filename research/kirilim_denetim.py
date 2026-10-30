"""Çevrimdışı as-of kırılım denetimi: canlı kodu ve mesajlaşmayı değiştirmez."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from data import resample_ohlcv
from patterns.lifecycle import ArgentEngine, effective_break_buffer, effective_retest_tolerance, f_breakout_strength, f_line_price
from research.capraz_piyasa import quality, read_frame

class PrefixList(list):
    """Önden yüklenmiş veriyi o anki barın sonuna kadar gösterir.

    Motorun bazı tarihçe sınırlamaları `len(close)` kullanır; tüm gelecek açık
    tutulursa eski barların seçimleri gelecekteki seri uzunluğuna bağlı olur.
    """
    def __init__(self, values):
        super().__init__(values)
        self.limit = 0

    def __len__(self):
        return self.limit

    def __iter__(self):
        return (super(PrefixList, self).__getitem__(i) for i in range(self.limit))

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [super(PrefixList, self).__getitem__(i) for i in range(*key.indices(self.limit))]
        pos = key + self.limit if key < 0 else key
        if pos < 0 or pos >= self.limit:
            raise IndexError('henüz bilinmeyen mum')
        return super().__getitem__(pos)


HORIZON = 10
WARMUP = 80
CANDIDATE_STATES = {"KIRILIM_ADAYI", "KIRILIM_DENEMESI"}
END_STATES = {"KIRILIM_TEYITLI", "KIRILIM_TEYIT_ALAMADI", "BASARISIZ_KIRILIM", "FORMASYON_GECERSIZ"}


def _smooth(a, b, x):
    if a == b:
        return float(x >= b)
    t = min(1., max(0., (x-a)/(b-a)))
    return t*t*(3-2*t)


def reference_strength(o, h, l, c, volume, volume_sma, direction, boundary, atr, base_atr, tick):
    """Farklı ifade ile skoru yeniden hesapla; Pine eşdeğerliği iddiası değildir."""
    span = max(h-l, tick)
    atr = float(atr) if atr is not None and math.isfinite(atr) else tick*10
    denominator = max(atr, tick)
    body = (c-o)*direction/span
    close_loc = (c-l)/span if direction == 1 else (h-c)/span
    penetration = (c-boundary)*direction/denominator
    expansion = span/denominator
    vol_ok = (volume is not None and math.isfinite(volume) and volume > 0 and
              volume_sma is not None and math.isfinite(volume_sma) and volume_sma > 0)
    vol_ratio = volume/volume_sma if vol_ok else 1.
    components = [100*_smooth(.10,.65,body), 100*_smooth(.56,.88,close_loc),
                  100*_smooth(base_atr*.75,max(.24,base_atr*4),penetration),
                  100*_smooth(.65,1.55,expansion), 100*_smooth(.90,1.55,vol_ratio) if vol_ok else 50.]
    return max(0., min(100., sum(x*w for x, w in zip(components, (.24,.28,.25,.15,.08))))), components


def frame_for(root: Path, symbol: str, tf: str):
    """Kusurlu 1h bileşenleri türetilen kovaya taşır; son kova tamam kabul edilmez."""
    raw = read_frame(root / f"{symbol}_{'1d' if tf == '1d' else '1h'}.csv.gz")
    raw_bad, _, _ = quality(raw)
    if tf in ('1h', '1d'):
        return raw, raw_bad, {'raw_rows': len(raw), 'raw_bad': int(raw_bad.sum()), 'tail_dropped': 0}
    result = resample_ohlcv(raw, tf)
    flags = pd.DataFrame({'open': 1., 'high': 1., 'low': 1., 'close': 1., 'volume': raw_bad.astype(float)}, index=raw.index)
    bad_bins = resample_ohlcv(flags, tf)['volume'].reindex(result.index).fillna(1).gt(0)
    tail_dropped = int(len(result) > 0)
    if tail_dropped:
        result, bad_bins = result.iloc[:-1], bad_bins.iloc[:-1]
    return result, bad_bins, {'raw_rows': len(raw), 'raw_bad': int(raw_bad.sum()), 'tail_dropped': tail_dropped}


def segments(frame, inherited_bad):
    bad, _, _ = quality(frame)
    bad = bad | inherited_bad.reindex(frame.index).fillna(True)
    blocks = bad.cumsum()
    return bad, [g for _, g in frame.loc[~bad].groupby(blocks.loc[~bad]) if len(g) >= WARMUP + 1]


def replay_segment(frame: pd.DataFrame, symbol: str, tf: str):
    """Tek temiz blok; motor içinde referans izleme, karar kurallarına müdahale yok."""
    eng = ArgentEngine(timeframe=tf, profile='Dengeli')
    old_step, old_bar = eng._break_attempt_or_candidate_step, eng._process_bar
    checks, candidates, pending, max_error = [], [], None, 0.0
    atr = quality(frame)[2]

    def audit(b, is_attempt):
        nonlocal max_error
        a = eng.active
        boundary = f_line_price(eng.break_line_x1, eng.break_line_y1, eng.break_line_x2, eng.break_line_y2, b)
        # Bağımsız doğrusal interpolasyon aynı bar üzerinde denetlenir.
        ref_boundary = (eng.break_line_y2 if eng.break_line_x1 == eng.break_line_x2 else
            eng.break_line_y1 + (b-eng.break_line_x1) * (eng.break_line_y2-eng.break_line_y1) / (eng.break_line_x2-eng.break_line_x1))
        buf, tol = effective_break_buffer(eng, a), effective_retest_tolerance(eng, a)
        life_atr = a.frozen_atr_at_break if a.quality_frozen and a.frozen_atr_at_break is not None else eng.safe_atr
        direction = eng.break_candidate_dir
        args = (eng.open[b], eng.high[b], eng.low[b], eng.close[b], eng.volume[b], eng.vol_sma[b], direction, boundary, life_atr, eng.base_break_atr, eng.mintick)
        actual, *parts = f_breakout_strength(*args)
        reference, independent_parts = reference_strength(*args)
        diffs = [abs(boundary-ref_boundary), abs(actual-reference)] + [abs(x-y) for x,y in zip(parts,independent_parts)]
        error = max(diffs)
        max_error = max(max_error, error)
        threshold = max(25., eng.min_break_strength-6.)
        outside = (eng.close[b] > boundary+buf) if direction == 1 else (eng.close[b] < boundary-buf)
        hold = max(eng.mintick, tol*.12)
        retest = ((eng.low[b] <= boundary+tol and eng.close[b] > boundary+hold) if direction == 1 else
                  (eng.high[b] >= boundary-tol and eng.close[b] < boundary-hold))
        age = b-eng.break_candidate_bar
        result = old_step(b, is_attempt)
        valid_trigger = (outside and (not eng.use_breakout_quality_filter or actual >= threshold)) or retest
        invariant_ok = not (result == 'KIRILIM_TEYITLI' and (age <= 0 or age > eng.confirm_window or not valid_trigger))
        invariant_ok = invariant_ok and not (result == 'KIRILIM_TEYIT_ALAMADI' and age <= eng.confirm_window)
        checks.append({'symbol':symbol,'tf':tf,'candidate_index':eng.break_candidate_bar,
            'bar_index':b,'time':str(frame.index[b]),'direction':direction,'age':age,
            'window':eng.confirm_window,'boundary':boundary,'buffer':buf,'tolerance':tol,
            'close':eng.close[b], 'open':eng.open[b], 'low':eng.low[b], 'high':eng.high[b],
            'strength':actual,'strength_ref':reference,'threshold':threshold,'score_body':parts[0],
            'score_close':parts[1],'score_penetration':parts[2],'score_expansion':parts[3],
            'score_volume':parts[4], 'outside':outside, 'strength_pass':actual>=threshold,
            'retest':retest,'next_state':result,'math_max_error':error,'decision_invariant_ok':invariant_ok})
        return result

    def capture(b):
        nonlocal pending
        for name in ('open', 'high', 'low', 'close', 'volume', 'atr_array', 'vol_sma'):
            series = getattr(eng, name)
            if not isinstance(series, PrefixList):
                series = PrefixList(series)
                setattr(eng, name, series)
            series.limit = b + 1
        prev = eng.pattern_state
        previous_candidate = eng.break_candidate_bar
        old_bar(b)
        state = eng.pattern_state
        new_start = state in CANDIDATE_STATES and eng.break_candidate_bar == b and b != previous_candidate
        if pending is not None:
            same = (eng.break_candidate_bar == pending['local_index'] and
                    getattr(eng.active, 'identity', None) == pending['identity'])
            if not same:
                pending['status'] = 'REPLACED_OR_RESET'; pending['terminal_index'] = b; pending = None
            elif state in END_STATES:
                pending['status'] = state; pending['terminal_index'] = b
                if state == 'KIRILIM_TEYITLI': pending['confirm_index'] = b
                pending = None
            elif state not in CANDIDATE_STATES:
                pending['status'] = 'OTHER_TRANSITION'; pending['terminal_index'] = b; pending = None
        if new_start and b >= WARMUP-1:
            a = eng.active
            pending = {'symbol':symbol,'tf':tf,'local_index':b,'anchor':str(frame.index[b]),
                'direction':int(eng.break_candidate_dir),'candidate_state':state,'previous_state':prev,
                'pattern':a.pattern_type,'identity':getattr(a,'identity',None),
                'pattern_start_index':a.start_bar,'pattern_age':b-a.start_bar,
                'anchor_close':float(eng.close[b]),'anchor_atr':float(atr.iloc[b]),
                'candidate_strength':a.break_strength,'form_quality':a.raw_quality,
                'status':'RIGHT_CENSORED','terminal_index':None,'confirm_index':None}
            candidates.append(pending)

    eng._break_attempt_or_candidate_step = audit
    eng._process_bar = capture
    eng.process(frame)
    return candidates, checks, max_error


def label_events(events, frame, split_time, *, data_break_at_end=False):
    """Yalnız kapanış sonuçları; dönem sınırındaki hedefler purged."""
    out = []
    _, _, atr = quality(frame)
    for e in events:
        e = dict(e); i=e['local_index']; h=i+HORIZON; a=float(atr.iloc[i]); p=float(frame.close.iloc[i]); d=e['direction']
        period='discovery' if frame.index[i] < split_time else 'validation'
        e['period'] = period
        censored = 'DATA_BREAK_CENSORED' if data_break_at_end else 'RIGHT_CENSORED'
        e['outcome_status'] = censored if h>=len(frame) else ('BOUNDARY_PURGED' if period=='discovery' and frame.index[h]>=split_time else 'VALID')
        if data_break_at_end and e['status'] == 'RIGHT_CENSORED':
            e['status'] = 'DATA_BREAK_CENSORED'
        e.update(end_atr=None, max_favorable_atr=None, max_adverse_atr=None, hit_favorable=None, hit_adverse=None, end_favorable=None, confirm_bars=None, at_confirm_atr=None)
        c=e['confirm_index']
        if c is not None and c <= h:
            e['confirm_bars']=c-i; e['at_confirm_atr']=(float(frame.close.iloc[c])-p)*d/a
        if e['outcome_status']=='VALID' and math.isfinite(a) and a>0:
            movement=(frame.close.iloc[i+1:h+1].to_numpy(dtype=float)-p)*d/a
            e.update(end_atr=float(movement[-1]),max_favorable_atr=float(max(movement)),max_adverse_atr=float(min(movement)),
                     hit_favorable=bool(max(movement)>=2.),hit_adverse=bool(min(movement)<=-2.),end_favorable=bool(movement[-1]>=2.))
        elif e['outcome_status']=='VALID': e['outcome_status']='INVALID_ATR'
        e['status_at_horizon'] = ('PENDING_AT_HORIZON' if e['terminal_index'] is not None and e['terminal_index'] > h
                                  else e['status'])
        e['outcome_end_time'] = str(frame.index[h]) if h < len(frame) else None
        e['terminal_time'] = str(frame.index[e['terminal_index']]) if e['terminal_index'] is not None else None
        e['confirm_time'] = str(frame.index[c]) if c is not None else None
        e['identity'] = str(e['identity'])
        out.append(e)
    return out


def count_reasons(checks):
    results=Counter()
    for c in checks:
        if c['age'] <= c['window']:
            results['within_window'] += 1
            if not c['outside']: results['not_outside'] += 1
            if c['outside'] and not c['strength_pass']: results['outside_but_weak'] += 1
            if c['retest']: results['retest'] += 1
            if c['next_state']=='KIRILIM_TEYITLI': results['confirmed'] += 1
    return dict(results)
