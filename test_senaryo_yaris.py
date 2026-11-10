# -*- coding: utf-8 -*-
"""Faz 4 — pencere yarışı testleri (koşucu kurallarıyla eşdeğerlik)."""

import pytest

from senaryo.yaris import yaris_penceresi


def test_hedef_once():
    k = [101.0, 102.0, 103.1]          # hedef 103, stop 99
    s, c, pnl, mae = yaris_penceresi(k, 0, len(k), 100.0, 99.0, 103.0, 1.0)
    assert (s, c) == ("hedef", 3)
    assert pnl == pytest.approx(3.0)
    assert mae == pytest.approx(0.0)    # hiç geri çekilme yok


def test_stop_once():
    k = [99.5, 98.9]
    s, c, pnl, mae = yaris_penceresi(k, 0, len(k), 100.0, 99.0, 103.0, 1.0)
    assert (s, c) == ("stop", 2)
    assert pnl == pytest.approx(-1.0)


def test_ayni_barda_cift_dokunus_stop_kazanir():
    # normal long'da stop < hedef olduğundan çift dokunuş oluşmaz; eşik
    # çakışması (stop == hedef sınırı) durumunda muhafazakâr kural: stop.
    k = [99.0]
    s, c, _, _ = yaris_penceresi(k, 0, len(k), 100.0, 99.0, 99.0, 1.0)
    assert (s, c) == ("stop", 1)


def test_zaman_cikisi():
    k = [100.2, 100.1, 100.3]
    s, c, pnl, mae = yaris_penceresi(k, 0, 3, 100.0, 97.0, 106.0, 1.0)
    assert (s, c) == ("zaman", 3)
    assert pnl == pytest.approx(0.3)


def test_sansur_veri_biterse():
    k = [100.2, 100.1]                  # H=10 ama yalnız 2 bar var
    s, c, pnl, mae = yaris_penceresi(k, 0, 10, 100.0, 97.0, 106.0, 1.0)
    assert (s, c, pnl) == ("yok", None, 0.0)


def test_bas_indexi_ileri_kaydirir():
    # bas=2 → ilk 2 bar yok sayılır
    k = [99.0, 99.0, 98.0]
    s, c, _, _ = yaris_penceresi(k, 2, 1, 100.0, 99.0, 106.0, 1.0)
    assert (s, c) == ("stop", 1)        # yalnız k[2]=98.0 denenir


def test_mae_cozum_onesini_icerir():
    k = [99.5, 104.0]                   # önce 0,5 geri, sonra hedef
    _, _, _, mae = yaris_penceresi(k, 0, len(k), 100.0, 97.0, 103.0, 1.0)
    assert mae == pytest.approx(-0.5)


def test_gecersiz_parametre():
    with pytest.raises(ValueError):
        yaris_penceresi([1.0], 0, 0, 1.0, 0.5, 2.0, 0.1)
    with pytest.raises(ValueError):
        yaris_penceresi([1.0], -1, 5, 1.0, 0.5, 2.0, 0.1)
