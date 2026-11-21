import numpy as np
import pandas as pd
import pytest

from research.fvg_fiyat_raporu import fiyat_yolu
from research.fvg_temas_izleri import izle


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_fiyat_yolu_ilk_fitili_saymaz_motor_sonrasi_devam_eder(direction):
    bars = np.array([[115, 100, 104], [104.5, 103, 104], [106, 103, 106]])
    lo, hi = 99, 102
    if direction == 'bearish':
        bars = 210-bars[:, [1,0,2]]
        lo, hi = 210-hi, 210-lo
    out = fiyat_yolu(bars, ['a','b','c'], 0, lo, hi, direction, 1)
    assert (out['fiyat_sonuc'], out['fiyat_karar_bar']) == ('HEDEF', 2)
    df = pd.DataFrame(bars, columns=['high','low','close'])
    df['timestamp'] = pd.date_range('2026-01-01', periods=3, tz='Europe/Istanbul')
    motor = izle(df, 0, direction, 1, None, 0, 'NATIVE_REACTION_TERMINAL')
    assert motor['sonuc'] == 'NATIVE_REACTION_TERMINAL' and motor['ilk_hedef_bar'] == 2


@pytest.mark.parametrize('son,sonuc', [([106,101,105], 'AYNI_MUM_BELIRSIZ'),
                                     ([104,101,103], 'BANDA_DONUS'),
                                     ([104,98,100], 'TAM_DOLUM'),
                                     ([104,103,104], 'EKSIK_UFUK')])
def test_ayrilma_ve_donus_sirasi(son, sonuc):
    bars = np.array([[104,101,104], [104,101,104], [104,103,104], son])
    out = fiyat_yolu(bars, ['a','b','c','d'], 0, 99, 102, 'bullish', 1)
    assert out['fiyat_sonuc'] == sonuc
