import pytest
from research.fvg_bir_mum_teyidi import olc


def test_teyit_kapanisi_yeni_capa_ve_teyit_mumu_sonuca_girmez():
    p = [(12,8,10),(10.8,9.2,10.6)] + [(11.2,10,11)]*11
    r = olc(p,1,8,10,True)
    assert (r['baz'], r['baz_bar'], r['karar'], r['gec']) == ('LEHTE',2,'TEYIT','SURE')


@pytest.mark.parametrize('bar,karar', [((11,9,10.1),'ILK_BELIRSIZ'),((11,9.5,10.1),'ILK_LEHTE'),
                                      ((10.5,9,9.9),'ILK_ALEYHTE')])
def test_ilk_mumda_bitmis_olay_teyide_giremez(bar,karar):
    r = olc([(10.5,9.4,10),bar]+[(10,10,10)]*11,1,9,10,True)
    assert r['karar']==karar and r['gec'] is None


def test_dusus_teyidi_ve_bant_dolumu():
    p=[(11,10,10),(10.5,9.4,9.5)] + [(9.5,8.5,9)]*11
    assert olc(p,1,10,11,False)['gec_bar']==2
    assert olc(p,1,10,10.5,False)['karar']=='BANT_DOLDU'
