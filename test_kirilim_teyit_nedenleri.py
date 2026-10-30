import pandas as pd
import pytest
from scripts.kirilim_teyit_nedenleri import classify


def test_threshold_without_outside_is_retest_only():
    a=pd.DataFrame([{'symbol':'X','tf':'1h','segment_start':'start','local_index':5,'status':'KIRILIM_TEYITLI'}])
    c=pd.DataFrame([{'symbol':'X','tf':'1h','segment_start':'start','candidate_index':5,
                     'next_state':'KIRILIM_TEYITLI','outside':False,'strength_pass':True,'retest':True}])
    assert classify(a,c).iloc[0].reason=='YALNIZ_RETEST'
    c.loc[0,'outside']=True
    assert classify(a,c).iloc[0].reason=='HER_IKISI'
    c.loc[0,'retest']=False
    assert classify(a,c).iloc[0].reason=='YALNIZ_GUCLU_AYNI_YON'
    c.loc[0,'outside']=False
    with pytest.raises(ValueError,match='nedeni bulunamadı'): classify(a,c)


def test_missing_or_duplicate_confirmation_fails():
    a=pd.DataFrame([{'symbol':'X','tf':'1h','segment_start':'start','local_index':5,'status':'KIRILIM_TEYITLI'}])
    c=pd.DataFrame([{'symbol':'X','tf':'1h','segment_start':'start','candidate_index':5,
                     'next_state':'KIRILIM_TEYITLI','outside':True,'strength_pass':True,'retest':False}])
    with pytest.raises(ValueError,match='tam bir'): classify(a,pd.concat([c,c]))
    c.loc[0,'candidate_index']=6
    with pytest.raises(ValueError,match='tam bir'): classify(a,c)
