import pandas as pd
import pytest
from scripts.kirilim_teyit_sonrasi import measure_window, choose_nonoverlap


def test_conf_after_close_forward_only_up_and_down():
    idx=pd.date_range('2025-01-01',periods=15,freq='D',tz='Europe/Istanbul')
    frame=pd.DataFrame({'close':[500,100,101,102,103,104,105,106,107,108,109,110,999,999,999]},index=idx)
    up=measure_window(frame,1,5,1,idx[14],'validation')
    down=measure_window(frame,1,5,-1,idx[14],'validation')
    assert up['confirm_close']==100 and up['confirm_atr']==5
    assert up['end10_atr']==2 and up['end10_pct']==10
    assert up['path_plus1'] and up['path_plus2'] and not up['path_minus1']
    assert down['end10_atr']==-2 and down['path_minus2'] and not down['path_plus1']
    assert up['max_favorable_atr']==2 and down['max_adverse_atr']==-2


def test_censor_and_split_boundaries():
    idx=pd.date_range('2025-01-01',periods=13,freq='D')
    frame=pd.DataFrame({'close':[100.]*13},index=idx)
    assert measure_window(frame,3,1,1,idx[-1],'validation')['outcome_status']=='RIGHT_CENSORED'
    assert measure_window(frame,3,1,1,idx[-1],'validation',data_break=True)['outcome_status']=='DATA_BREAK_CENSORED'
    assert measure_window(frame,1,1,1,idx[11],'discovery')['outcome_status']=='BOUNDARY_PURGED'
    assert measure_window(frame,1,1,1,idx[12],'discovery',native_last=idx[11])['outcome_status']=='LAST_BAR_UNCERTAIN'
    assert measure_window(frame,1,0,1,idx[-1],'validation')['outcome_status']=='INVALID_ATR'


def test_nonoverlap_includes_exact_endpoint_as_overlap():
    rows=[{'symbol':'A','tf':'1d','confirm_time':'2025-01-01','end_time':'2025-01-11','outcome_status':'VALID'},
          {'symbol':'A','tf':'1d','confirm_time':'2025-01-11','end_time':'2025-01-21','outcome_status':'VALID'},
          {'symbol':'A','tf':'1d','confirm_time':'2025-01-12','end_time':'2025-01-22','outcome_status':'VALID'},
          {'symbol':'B','tf':'1d','confirm_time':'2025-01-11','end_time':'2025-01-21','outcome_status':'VALID'},
          {'symbol':'A','tf':'1d','confirm_time':'2025-01-23','outcome_status':'RIGHT_CENSORED'}]
    choose_nonoverlap(rows)
    assert [x['nonoverlap'] for x in rows]==[True,False,True,True,False]


def test_prior_data_and_future_beyond_horizon_do_not_change_results():
    idx=pd.date_range('2025-01-01',periods=20,freq='D')
    frame=pd.DataFrame({'close':[100.]*20},index=idx)
    a=measure_window(frame,4,2,1,idx[-1],'validation')
    frame.iloc[:4]=900;frame.iloc[15:]=500
    b=measure_window(frame,4,2,1,idx[-1],'validation')
    assert a==b
    assert a['end10_atr']==pytest.approx(0)
