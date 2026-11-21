import numpy as np
import pandas as pd

from research.dip_geri_alim_hacmi import ozellikler


def test_ayni_saat_paydasi_guncel_hacmi_ve_dibi_icermez():
    slots = np.array(['sabah', 'aksam'] * 21)
    f = pd.DataFrame({'low': 10., 'high': 12., 'close': 11.,
                      'volume': np.where(slots == 'sabah', 100., 500.)})
    f.loc[40, ['low', 'close', 'volume']] = [9., 11.5, 150.]
    low, vol, setup = ozellikler(f, slots)
    assert np.isnan(vol.iloc[38]) and vol.iloc[40] == 1.5
    assert low.iloc[40] == 10 and setup.iloc[40] and not setup.iloc[41]
