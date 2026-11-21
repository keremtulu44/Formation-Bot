import pandas as pd

from research.hareket_kapsam import path, select, audit


def test_ters_once_ve_cift_sirada_hedef_degil():
    assert path([101,103],[99,100],100,1,1,2)==('ters',1)
    assert path([102],[99],100,1,1,2)==('cift',1)
    assert path([100],[98],100,1,-1,2)==('hedef',1)


def test_sonraki_slot_onceki_sirayi_degistirmez():
    rows=[dict(hisse=s,tf='4h',i=i,t=f'2026-09-01T{tm}:00+03:00',fiyat=p,hacimli=v,yon=1,frm=0)
          for i,tm in enumerate(('13:00','17:00')) for s,p,v in [('A',1,3),('B',2,2)]]
    s=select(pd.DataFrame(rows));assert s.fiyat_kart.tolist()==[0,1,0,1] and s.hacim_kart.tolist()==[1,0,1,0]


def test_hedef_mumundaki_kart_gecmiste_yakalamis_sayilmaz():
    b=pd.DataFrame(dict(hisse='A',tf='4h',i=[1,2,3],high=[110,101.1,102],low=100,
                        frm_kart=[0,0,1],hacim_kart=[0,1,0],fiyat_kart=[1,0,0]))
    m=pd.DataFrame([dict(hisse='A',tf='4h',i=1,bitis=3,yon=1,ref=100,atr=1,hedef=2)])
    r=audit(b,m).iloc[0];assert (r.frm_kart,r.hacim_kart,r.fiyat_kart)==('yok','gec','erken')
