"""Short TF display suppression must not change inputs or 4h/1d drawings."""
import copy
import pytest
import grafik
from test_grafik_iskelet import _cerceve


@pytest.mark.parametrize('tf', ['1h','2h','4h','1d'])
def test_short_tf_hides_only_stabil_display(tmp_path, tf):
    frame = _cerceve(80, tf)
    snap = grafik.anlik_goruntu(None, tf, frame, sembol='TEST')
    n=len(snap['kapanis'])
    level=float(snap['kapanis'][-1])
    snap['stabil']={'hazir':True,'seviyeler':[level]*n,'renkler':['ust']*n,
                    'reclaim_barlar':[n-3], 'momentum_barlar':[], 'iptal_barlar':[],
                    'son_seviye':level,'son_renk':'ust'}
    snap['stabil_direnc']={'hazir':True,'seviyeler':[level]*n,'renkler':['alt']*n,
                           'donus_barlar':[n-2], 'momentum_barlar':[], 'iptal_barlar':[],
                           'son_seviye':level,'son_renk':'alt'}
    before=copy.deepcopy(snap)
    _,meta=grafik.ciz(snap,tf,{'cikti':str(tmp_path/(tf+'.png'))})
    assert snap==before
    assert meta['stabil_cizimde_gizli'] == (tf in ('1h','2h'))
    for layer in ('stabil','stabil_direnc'):
        assert bool(meta['cizgiler'][layer]['cizildi']) == (tf in ('4h','1d'))
    if tf in ('1h','2h'):
        _,diagnostic=grafik.ciz(snap,tf,{'cikti':str(tmp_path/(tf+'-before.png')), 'stabil_goster':True})
        assert diagnostic['cizgiler']['stabil']['cizildi']
        assert diagnostic['cizgiler']['stabil_direnc']['cizildi']
