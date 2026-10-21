"""Formasyon ölçüm modülü testleri.

Kapsam: saf yardımcılar (epizot/argmin/faz/segment/rol mesafesi) + uçtan uca
duman testi. Duman testi **arşive bağımlı değildir**: sentetik çerçeve üretilir,
böylece test hızlı ve deterministiktir.

Neden bu testler var: `frm` tablosu yeni ve tek bir sessiz hata (yanlış `n`,
yanlış bar_time, yanlış ömür) bütün raporu bozar. Buradaki kontroller o üç
noktayı kilitler.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research import formasyon as fm


def _sentetik(bars: int = 400, seed: int = 7) -> pd.DataFrame:
    """Trend + gürültü içeren OHLCV çerçevesi (DatetimeIndex)."""
    rng = np.random.default_rng(seed)
    adim = rng.normal(0.0, 1.0, bars).cumsum()
    kapanis = 100.0 + adim * 0.6
    acilis = np.concatenate([[kapanis[0]], kapanis[:-1]])
    yuksek = np.maximum(acilis, kapanis) + np.abs(rng.normal(0, 0.4, bars))
    dusuk = np.minimum(acilis, kapanis) - np.abs(rng.normal(0, 0.4, bars))
    hacim = rng.integers(1000, 5000, bars).astype(float)
    idx = pd.date_range("2025-01-01", periods=bars, freq="h", tz="Europe/Istanbul")
    return pd.DataFrame({"open": acilis, "high": yuksek, "low": dusuk,
                         "close": kapanis, "volume": hacim}, index=idx)


# ------------------------------------------------------------------ yardımcılar

def test_epizot_ardisik_blok_sayar() -> None:
    assert fm._epizot([True, True, False, True]) == 2
    assert fm._epizot([False, False]) == 0
    assert fm._epizot([True]) == 1


def test_argmin_none_ve_nan_atlar() -> None:
    assert fm._argmin([None, 2.0, 1.0, None]) == 2
    assert fm._argmin([None, None]) is None
    assert fm._argmin([float("nan"), 3.0]) == 1


def test_faz_sayaci_kovalari() -> None:
    sayac = fm._faz_sayaci([
        "GEOMETRI_ADAYI", "FORMASYON_TANIMLANDI", "KIRILIM_ADAYI",
        "RETEST_BEKLENIYOR", "FORMASYON_YOK",
    ])
    assert sayac == {"geometri": 2, "kirilim": 1, "retest": 1, "diger": 1}


def test_segmentler_sid_degisiminde_boler() -> None:
    def satir(b, sid, state="OLGUNLASIYOR"):
        return (b, state, sid, None, None, 1, 1, 0, 0.0, 1, 0.0, 0, 0.0, 1, 0.0,
                "Simetrik Üçgen", "Üçgen", 0, False, None, None, None, None, None,
                None, 10.0, 2.0, 5.0, 0.2, 0.1)

    segmentler = fm._segmentler([satir(0, "a"), satir(1, "a"), satir(2, "b"), satir(3, None)])
    assert set(segmentler) == {"a", "b"}
    assert segmentler["a"]["ilk_bar"] == 0 and segmentler["a"]["son_bar"] == 1
    assert segmentler["b"]["ilk_bar"] == 2


def test_rol_mesafe_yalniz_acik_araligi_sayar() -> None:
    """Rol el değiştirdiğinde eski aralık mesafeye girmemeli."""
    rol_grup = {
        ("EXTERNAL", 1): [
            {"rol": "PH", "rol_ilk_bar": 0, "rol_son_bar": 9},
            {"rol": "PL", "rol_ilk_bar": 10, "rol_son_bar": None},
        ],
    }
    fiyat = {("EXTERNAL", 1): 110.0}
    # bar 5: yalnız PH açık → referans 100, mesafe 10/ATR(2) = 5.0
    ph, pl, ucu = fm._rol_mesafe(rol_grup, fiyat, 5, 100.0, 2.0)
    assert ph == 5.0 and pl is None and ucu == "PH"
    # bar 20: yalnız PL açık (aynı swing kimliği ama farklı rol aralığı)
    ph2, pl2, ucu2 = fm._rol_mesafe(rol_grup, fiyat, 20, 100.0, 2.0)
    assert ph2 is None and pl2 == 5.0 and ucu2 == "PL"


def test_rol_mesafe_atr_yoksa_olcmez() -> None:
    assert fm._rol_mesafe({("EXTERNAL", 1): [{"rol": "PH", "rol_ilk_bar": 0}]},
                          {("EXTERNAL", 1): 10.0}, 1, 9.0, None) == (None, None, None)


# ------------------------------------------------------------------ uçtan uca

def test_formasyon_kosu_calismazsa_bos_doner() -> None:
    bos = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    frm, olay, meta = fm.formasyon_kosu(bos, symbol="X", timeframe="1h")
    assert frm == [] and olay == []
    assert meta["formasyon_sayisi"] == 0


def test_formasyon_kosu_sentetik_sema_tutarliligi() -> None:
    """Satırlar benzersiz, ömür pozitif, bar_time mutlak, meta sayıları tutarlı."""
    frame = _sentetik()
    frm, olay, meta = fm.formasyon_kosu(frame, symbol="TEST", timeframe="1h")

    assert meta["formasyon_sayisi"] == len(frm)
    assert meta["formasyon_olay_sayisi"] == len(olay)

    sidler = [r["stable_id"] for r in frm]
    assert len(sidler) == len(set(sidler)), "aynı stable_id iki kez satır üretmemeli"

    for r in frm:
        assert r["omur_bar"] >= 1
        assert r["dogum_bar_time"] is not None
        assert not isinstance(r["dogum_bar_time"], int), "bar_time indeks değil zaman olmalı"
        assert r["olcum_son_bar"] >= r["dogum_bar"]
        # Mesafe bloğu kırılımdan önce ölçülür: asla ömürden uzun olamaz.
        assert r["frm_mesafe_olcum_bar"] <= r["omur_bar"]
        if r.get("frm_kirilim_deneme") is not None:
            assert r["frm_kirilim_deneme"] >= 0
        if r["terminal_state"] == "FORMASYON_GECERSIZ":
            assert r["frm_gecersiz_state"] != "FORMASYON_GECERSIZ"

    for o in olay:
        assert o["stable_id"] in set(sidler)
        assert isinstance(o["teyit_oncesi"], bool)
