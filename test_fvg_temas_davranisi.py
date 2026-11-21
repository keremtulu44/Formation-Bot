import numpy as np
import pandas as pd
import pytest

from research.fvg_temas_davranisi import ozellik, bariyer, eslesme


def test_temas_mumu_uzaklasma_kaniti_olamaz():
    bars = np.array([[10,9,10], [12,9.5,11], [99,1,1]])
    f = ozellik(bars,0,1,9,10,True,1)
    assert f['uzaklasti'] is None and f['sig'] and f['dis_kapanis'] and not f['doldu']
    assert f == ozellik(bars[:2],0,1,9,10,True,1)


@pytest.mark.parametrize('up,sonuc', [(True,'ALEYHTE'), (False,'LEHTE')])
def test_ilk_bariyer_ve_ayni_bar_belirsizligi(up, sonuc):
    assert bariyer([[10.5,9,9],[12,9,11]],10,1,up) == (sonuc,1)
    assert bariyer([[11,9,10]],10,1,up) == ('BELIRSIZ',1)
    assert bariyer([[10,10,10]]*12,10,1,up) == ('SURE',None)


def test_eslesme_tek_tarafli_hucreyi_tasimasin():
    rows=[dict(sembol=s,tf='4h',yon='bullish',boyut='>=2',genislik_atr=2.5,erken=v,temiz=v,bariyer='LEHTE')
          for s,v in [('A',True),('A',False),('B',False)]]
    r=eslesme(pd.DataFrame(rows)).set_index('erken')
    assert r.hucre.tolist()==[1,1] and r.agirlik.tolist()==[1,1]
    assert r.temiz.tolist()==[0,1]
