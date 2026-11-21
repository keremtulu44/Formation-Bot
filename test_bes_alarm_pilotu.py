import numpy as np
import pandas as pd

from research.bes_alarm_pilotu import esle, rvol, stabil_olaylari


def test_ust_mum_kapanmadan_okunmaz_ve_hacim_paydasi_kendini_icermez():
    ts=pd.date_range('2026-05-05 09:00',periods=4,freq='h',tz='Europe/Istanbul')
    got=esle(ts,ts[[1,3]],[.2,5]);np.testing.assert_allclose(got,[np.nan,.2,.2,5],equal_nan=True)
    assert rvol(pd.Series([100]*20+[30])).iloc[-1]==.3


def test_dipten_geri_alis_ilk_kapanis_ve_destek_degismemeli():
    c=np.array([11,9.8,9.5,8,8.5,9,9.5,10.1,11]);o=c-.3
    f=pd.DataFrame(dict(close=c,open=o,high=c+.05,low=o-.05),index=pd.date_range('2026-01-01',periods=len(c)))
    s=np.full(len(c),10.);r=['HORIZONTAL_BASE']*len(c)
    xs=[(i,g,e['dip_bar']) for i,k,g,e in stabil_olaylari(f,s,r,7) if k=='S2']
    assert xs==[(7,'geri_alis',5),(7,'yesil80',5),(7,'temiz80',5)]
    s[5:]=10.05
    assert not [k for _,k,_,_ in stabil_olaylari(f,s,r,7) if k=='S2']


def test_yatay_donus_suresi_cikistan_sayilir():
    f=pd.DataFrame(dict(close=[9.,11.,11.,11.,11.],open=10.,low=[9.,10.5,10.5,10.3,9.9],high=11.1))
    s=np.full(len(f),10.);reg=['HORIZONTAL_BASE','STEPPING_UP','STEPPING_UP','HORIZONTAL_BASE','HORIZONTAL_BASE']
    def aday(limit):return [i for i,k,g,_ in stabil_olaylari(f,s,reg,limit) if k=='S1' and g=='aday']
    assert aday(3)==[4] and not aday(2)
