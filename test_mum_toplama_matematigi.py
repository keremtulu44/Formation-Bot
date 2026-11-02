"""Saatlik mumların toplama kuralları ve kaynak sınırları."""
import pandas as pd
import pytest

from data import resample_ohlcv
from grafik_uret import _gunluk_cerceve_onar_ve_olcekle


def _ohlcv(index):
    return pd.DataFrame({"open": [10., 11., 12., 13.],
                         "high": [12., 15., 13., 16.],
                         "low": [9., 10., 8., 11.],
                         "close": [11., 12., 12., 14.],
                         "volume": [2., 3., 5., 7.]}, index=index)


@pytest.mark.parametrize("tz", ["Europe/Istanbul", "UTC"])
def test_bist_1s_dort_saat_ve_gunluk_ohlcv_matematigi(tz):
    local = pd.date_range("2026-10-26 09:30", periods=4, freq="h", tz="Europe/Istanbul")
    frame = _ohlcv(local.tz_convert(tz))
    for tf in ("4h", "1d"):
        result = resample_ohlcv(frame, tf)
        assert len(result) == 1
        bar = result.iloc[0]
        assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (10., 16., 8., 14., 17.)
        assert result.index.tz == frame.index.tz
    assert resample_ohlcv(frame, "4h").index[0] == frame.index[0]


def test_gunluk_makro_yapay_bolunme_uygulanmaz():
    index = pd.date_range("2026-10-20", periods=6, freq="D", tz="Europe/Istanbul")
    prices = [100., 100., 100., 50., 50., 50.]
    daily = pd.DataFrame({"open": prices, "high": prices, "low": prices,
                          "close": prices, "volume": [0.] * len(prices)}, index=index)
    hourly = _ohlcv(pd.date_range("2026-10-23 08:00", periods=4, freq="h", tz="Europe/Istanbul"))
    result = _gunluk_cerceve_onar_ve_olcekle(daily, hourly, sembol="XAGUSD")
    pd.testing.assert_frame_equal(result, daily)
