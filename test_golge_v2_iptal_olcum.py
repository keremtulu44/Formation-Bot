"""Deneysel çıkışların zaman sırası ve iki bar şartı."""
from types import SimpleNamespace as NS
from senaryo_v2.yaris import _tek_yarisi_simule_et


def bar(i, *, high=101, low=99, close=100, bands=(), pressure=None, usable=True):
    return NS(i=i, open=100, high=high, low=low, close=close, blok_bear=bands,
              blok_bull=(), vp_volume_usable=usable, vp_pressure_5=pressure,
              ms_bos_down_now=False, ms_bos_up_now=False)

def run(bars, **kwargs):
    return _tek_yarisi_simule_et(tuple(bars),olay_bar_idx=0,dolum_idx=0,start_scan_idx=1,
        yon='long',giris=100,stop=90,hedef=110,atr_baz=1,ufuk_bar=len(bars)-1,
        intrabar=True,tez_iptal=False,**kwargs)

def test_duvar_ayni_band_iki_temasta_ve_hedeften_sonra():
    z=NS(family='FVG',available_index=0,lower=100,upper=102,height_atr=1)
    # Bandın temas sonrası listeden kaybolması aynı banda ikinci dokunuşu engellemez.
    bars=[bar(0,bands=(z,)),bar(1,bands=()),bar(2,bands=())]
    assert run(bars,duvar_iptal=True)[2:] == ('DUVAR_IPTAL',2)
    bars[2]=bar(2,high=111)
    assert run(bars,duvar_iptal=True)[2:] == ('HEDEF',2)

def test_farkli_duvarlar_veya_kesilen_temas_iptal_degil():
    z=NS(family='OB',available_index=0,lower=100,upper=102,height_atr=1)
    z2=NS(family='OB',available_index=1,lower=95,upper=99,height_atr=1)
    bars=[bar(0,bands=(z,)),bar(1,bands=(z2,)),bar(2,high=99,low=98,close=99)]
    assert run(bars,duvar_iptal=True)[2] == 'ZAMAN_STOPU'

def test_ters_baski_iki_ardisik_kullanilabilir_bar_ve_stop_onceligi():
    bars=[bar(0),bar(1,pressure=-.2),bar(2,pressure=-.2)]
    assert run(bars,baski_iptal=True)[2:] == ('BASKI_IPTAL',2)
    bars[1]=bar(1,pressure=-.2,usable=False)
    assert run(bars,baski_iptal=True)[2]=='ZAMAN_STOPU'
    bars[1]=bar(1,pressure=-.2); bars[2]=bar(2,low=89,pressure=-.2)
    assert run(bars,baski_iptal=True)[2]=='STOP'
