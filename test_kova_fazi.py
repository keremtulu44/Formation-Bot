# -*- coding: utf-8 -*-
"""Kova fazı regresyonu: 2s/4s çapası pencere başından bağımsız SABİT olmalı.

Köken: `resample_ohlcv` kova offset'ini kayan pencerenin İLK barından
alıyordu; pencere her saat kaydıkça faz dönüyor, bütün 2s/4s tarihi
yeniden yazılıyordu (ölçüm: 4s senaryoların yalnız %33'ü doğru fazda).
Bu testler çapanın bir daha pencere başına bağlanmasını engeller.
Ayrıntı: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md
"""

import pandas as pd
import pytest

from data import resample_ohlcv

DOGRU_ETIKET = {
    "2h": {"09:30", "11:30", "13:30", "15:30", "17:30"},
    "4h": {"09:30", "13:30", "17:30"},
}


def _seans_serisi(gun=6, tz="Europe/Istanbul"):
    """BIST saatlik serisi: 09:30..17:30 etiketleri, her gün 9 bar."""
    idx = []
    for d in range(gun):
        gun0 = pd.Timestamp(2026, 10, 19, tz=tz) + pd.Timedelta(days=d)
        idx.extend(gun0 + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(hours=h)
                   for h in range(9))
    n = len(idx)
    return pd.DataFrame(
        {"open": [100.0 + i for i in range(n)],
         "high": [102.0 + i for i in range(n)],
         "low": [99.0 + i for i in range(n)],
         "close": [101.0 + i for i in range(n)],
         "volume": [10] * n},
        index=pd.DatetimeIndex(idx))


def _etiketler(df):
    return {t.strftime("%H:%M") for t in df.index}


@pytest.mark.parametrize("tf", ["2h", "4h"])
@pytest.mark.parametrize("kayma", range(9))
def test_her_pencere_basi_dogru_seans_fazi(tf, kayma):
    df = _seans_serisi()
    out = resample_ohlcv(df.iloc[kayma:], tf)
    assert _etiketler(out) <= DOGRU_ETIKET[tf]


@pytest.mark.parametrize("tf", ["2h", "4h"])
def test_pencere_basi_kaymasi_kovalari_degistirmez(tf):
    """Pencere başından SONRA başlayan kovalar tam seriyle birebir aynı olmalı.

    Pencere başını içeren ilk kova kısmi olabilir (başı kesik); sonrası
    faz kayması olsaydı asla tam seriyle çakışmazdı.
    """
    df = _seans_serisi()
    tam = resample_ohlcv(df, tf)
    for kayma in range(1, 13):
        pencere = resample_ohlcv(df.iloc[kayma:], tf)
        sonraki = pencere[pencere.index > df.index[kayma]]
        ortak = sonraki.index.intersection(tam.index)
        assert len(ortak) > 3
        pd.testing.assert_frame_equal(sonraki.loc[ortak], tam.loc[ortak])


def test_ilk_4s_kova_seansin_ilk_dort_barini_toplar():
    df = _seans_serisi(gun=2)
    out = resample_ohlcv(df, "4h")
    ilk_dort = df.iloc[:4]
    kova = out.iloc[0]
    assert out.index[0].strftime("%H:%M") == "09:30"
    assert kova["open"] == ilk_dort["open"].iloc[0]
    assert kova["high"] == ilk_dort["high"].max()
    assert kova["low"] == ilk_dort["low"].min()
    assert kova["close"] == ilk_dort["close"].iloc[-1]
    assert kova["volume"] == ilk_dort["volume"].sum()


def test_utc_girdi_ayni_kova_anlari_ve_tz_korunur():
    """Araştırma hattı UTC besler: kova anları canlıyla aynı, tz UTC kalmalı."""
    df_ist = _seans_serisi()
    df_utc = df_ist.tz_convert("UTC")
    out_ist = resample_ohlcv(df_ist, "4h")
    out_utc = resample_ohlcv(df_utc.iloc[3:], "4h")  # kayık başlangıçla da
    assert str(out_utc.index.tz) == "UTC"
    ortak = out_utc.index.intersection(out_ist.tz_convert("UTC").index)
    sonraki = [t for t in ortak if t > df_utc.index[3]]
    assert len(sonraki) > 3
    pd.testing.assert_frame_equal(
        out_utc.loc[sonraki],
        out_ist.tz_convert("UTC").loc[sonraki])


def test_tzsiz_dizin_istanbul_duvar_saati_sayilir():
    df = _seans_serisi().tz_localize(None)
    out = resample_ohlcv(df.iloc[5:], "2h")
    assert _etiketler(out) <= DOGRU_ETIKET["2h"]


def test_kesintisiz_seri_gece_yarisi_capasinda_kararli():
    """24 saat seri (BRENT vb.): seans çapası yok, gece yarısı çapası var.

    Eskiden ilk bar çapası burada da fazı döndürüyordu; etiketler artık
    pencere başı ne olursa olsun çift saatlerde / 4'ün katlarında.
    """
    idx = pd.date_range("2026-10-19", periods=24 * 6, freq="h",
                        tz="Europe/Istanbul")
    n = len(idx)
    df = pd.DataFrame({"open": range(n), "high": range(n), "low": range(n),
                       "close": range(n), "volume": [1] * n}, index=idx)
    for kayma in (0, 1, 3, 7):
        et2 = _etiketler(resample_ohlcv(df.iloc[kayma:], "2h"))
        assert all(int(e[:2]) % 2 == 0 and e[3:] == "00" for e in et2)
        et4 = _etiketler(resample_ohlcv(df.iloc[kayma:], "4h"))
        assert all(int(e[:2]) % 4 == 0 and e[3:] == "00" for e in et4)
