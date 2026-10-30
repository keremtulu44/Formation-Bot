import pandas as pd
import pytest
from scripts.kirilim_aday_teyit_karsilastirma import build_comparison, summarize


def example():
    # Aşağı yönde 100 -> 98 teyit, adayın 10. kapanışı 94,
    # teyidin 10. kapanışı 95. Bu iki hedef farklı mumlardır.
    candidate=pd.DataFrame([{'symbol':'ABC','tf':'1h','segment_start':'S','local_index':80,
        'direction':-1,'period':'validation','status':'KIRILIM_TEYITLI','outcome_status':'VALID',
        'nonoverlap':True,'anchor':'candidate','confirm_time':'confirm','outcome_end_time':'candidate_end',
        'anchor_close':100.,'anchor_atr':2.,'end_atr':3.}])
    confirmation=pd.DataFrame([{'symbol':'ABC','tf':'1h','segment_start':'S','candidate_index':80,
        'direction':-1,'period':'validation','candidate_time':'candidate','confirm_time':'confirm',
        'confirm_delay':1,'outcome_status':'VALID','nonoverlap':True,'pattern':'Test',
        'confirm_close':98.,'confirm_atr':2.,'end_time':'confirmation_end','end10_pct':3/98*100}])
    return candidate,confirmation


def test_common_endpoint_and_different_horizon():
    candidate,confirmation=example(); row=build_comparison(candidate,confirmation).iloc[0]
    assert row.candidate_end_close==pytest.approx(94)
    assert row.confirmation_end_close==pytest.approx(95)
    assert row.candidate_to_confirm_pct==pytest.approx(-2)
    assert row.candidate_to_candidate_end_pct==pytest.approx(-6)
    assert row.confirm_to_candidate_end_pct==pytest.approx(-4/98*100)
    assert row.confirm_to_confirm_end_pct==pytest.approx(-3/98*100)
    assert len(summarize(build_comparison(candidate,confirmation)))==2


def test_no_silent_mismatched_candidate_and_confirmation():
    c,f=example(); f.loc[0,'direction']=1
    with pytest.raises(ValueError,match='uyuşmuyor'):
        build_comparison(c,f)
    c,f=example(); f.loc[0,'candidate_index']=81
    with pytest.raises(ValueError,match='eşleşmedi'):
        build_comparison(c,f)


def test_censored_horizons_are_not_included():
    c,f=example();f.loc[0,'outcome_status']='RIGHT_CENSORED'
    assert build_comparison(c,f).empty
