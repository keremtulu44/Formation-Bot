# -*- coding: utf-8 -*-
"""Faz 1 — zaman disiplini testleri (gelecek sızıntısı yasağı)."""

import pandas as pd
import pytest

from senaryo.zaman import (
    as_of,
    bar_zamani,
    gelecek_sizintisi_var_mi,
    kapatilmis_barlar,
    son_kapanis,
    ust_tf_kapandi_mi,
)


def _frame(saatler: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(s) for s in saatler], tz="UTC")
    return pd.DataFrame(
        {"open": range(len(idx)), "high": range(len(idx)),
         "low": range(len(idx)), "close": range(len(idx)), "volume": 1.0},
        index=idx,
    )


def test_asof_gelecegi_keser():
    f = _frame(["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 12:00"])
    kesik = as_of(f, pd.Timestamp("2026-01-01 11:00", tz="UTC"))
    assert len(kesik) == 2
    assert kesik.index.max() <= pd.Timestamp("2026-01-01 11:00", tz="UTC")
    assert not gelecek_sizintisi_var_mi(kesik, pd.Timestamp("2026-01-01 11:00", tz="UTC"))


def test_asof_kopyadir_asil_degismez():
    f = _frame(["2026-01-01 10:00", "2026-01-01 11:00"])
    onceki_len = len(f)
    kesik = as_of(f, pd.Timestamp("2026-01-01 10:00", tz="UTC"))
    kesik.iloc[0, 0] = 999
    assert len(f) == onceki_len
    assert f.iloc[0, 0] == 0  # asıl çerçeve mühürlü


def test_asof_tamamen_gelecekte_bos():
    f = _frame(["2026-01-01 10:00"])
    bos = as_of(f, pd.Timestamp("2026-01-01 09:00", tz="UTC"))
    assert len(bos) == 0


def test_kapatilmis_barlar_alias():
    f = _frame(["2026-01-01 10:00", "2026-01-01 11:00"])
    pd.testing.assert_frame_equal(
        kapatilmis_barlar(f, pd.Timestamp("2026-01-01 11:00", tz="UTC")),
        as_of(f, pd.Timestamp("2026-01-01 11:00", tz="UTC")),
    )


def test_mtf_kati_kural_ust_tf_kapanisi():
    gunluk = _frame(["2026-01-01 21:00", "2026-01-02 21:00"])  # UTC gün sonu etiketleri
    t_ilk = pd.Timestamp("2026-01-02 10:00", tz="UTC")
    t_iki = pd.Timestamp("2026-01-03 10:00", tz="UTC")
    # ilk karar anında yalnız 01.01 günlük barı kapandı
    assert son_kapanis(gunluk, t_ilk) == pd.Timestamp("2026-01-01 21:00", tz="UTC")
    assert ust_tf_kapandi_mi(gunluk, t_ilk)
    # ikinci karar anında 02.01 barı da kapandı (geçmişe bakmıyor)
    assert son_kapanis(gunluk, t_iki) == pd.Timestamp("2026-01-02 21:00", tz="UTC")


def test_ust_tf_henuz_kapanmamissa_yok():
    bos = _frame([])
    assert son_kapanis(bos, pd.Timestamp("2026-01-01", tz="UTC")) is None
    assert not ust_tf_kapandi_mi(bos, pd.Timestamp("2026-01-01", tz="UTC"))
    gunluk = _frame(["2026-01-01 21:00"])
    assert son_kapanis(gunluk, pd.Timestamp("2026-01-01 10:00", tz="UTC")) is None


def test_bar_zamani_sinir():
    f = _frame(["2026-01-01 10:00"])
    assert bar_zamani(f.index, 0).startswith("2026-01-01")
    with pytest.raises(IndexError):
        bar_zamani(f.index, 5)


def test_asof_tur_hatali():
    with pytest.raises(TypeError):
        as_of("kare-cizgi", pd.Timestamp("2026-01-01"))
