# -*- coding: utf-8 -*-
"""Faz 5 — T3 kapısı testleri (önceden kayıtlı eşiklerin saf değerlendirmesi)."""

import pytest

from research.golge_kapi import ESIKLER, kapi_degerlendir


def _tam_gecer(**degisim):
    girdi = {
        "K1_dogrulama_uygun_n": 120,
        "K2_kor_farki_puan": 8.5,
        "K3_dogrulama_beklenti": 0.05,
        "K4_g1_kapali_plan_orani": 0.0,
        "K5_ret_sonrasi_plan_ihlal": 0,
        "K6_kesif_beklenti": 0.04,
        "K6_dogrulama_beklenti": 0.03,
    }
    girdi.update(degisim)
    return girdi


def test_hepsi_gecerse_gecti():
    karar = kapi_degerlendir(_tam_gecer())
    assert karar["karar"] == "GEÇTİ"
    assert karar["gecen"] == karar["toplam_esik"] == len(ESIKLER)


def test_tek_ihlal_yeter():
    karar = kapi_degerlendir(_tam_gecer(K2_kor_farki_puan=3.0))
    assert karar["karar"] == "GEÇMEDİ"
    assert karar["gecen"] == len(ESIKLER) - 1
    k2 = next(s for s in karar["esikler"] if s["kod"] == "K2")
    assert not k2["gecti"] and k2["deger"] == 3.0


def test_k1_sinir_dahil():
    assert kapi_degerlendir(_tam_gecer(K1_dogrulama_uygun_n=50))["karar"] == "GEÇTİ"
    assert kapi_degerlendir(_tam_gecer(K1_dogrulama_uygun_n=49))["karar"] == "GEÇMEDİ"


def test_eksik_anhtar_gecmez():
    girdi = _tam_gecer()
    del girdi["K3_dogrulama_beklenti"]
    karar = kapi_degerlendir(girdi)
    assert karar["karar"] == "GEÇMEDİ"
    k3 = next(s for s in karar["esikler"] if s["kod"] == "K3")
    assert k3["deger"] is None and not k3["gecti"]


def test_saflik():
    a = kapi_degerlendir(_tam_gecer())
    b = kapi_degerlendir(_tam_gecer())
    assert a == b


def test_esikler_belgedekiyle_ayni():
    # plan belgesi §4: K1≥50, K2≥+5, K3>0, K4≤5, K5=0, K6>0 (çift)
    esik_map = {kod: (op, esik) for kod, _a, op, esik, _k in ESIKLER}
    assert esik_map["K1"] == (">=", 50)
    assert esik_map["K2"] == (">=", 5.0)
    assert esik_map["K3"] == (">", 0.0)
    assert esik_map["K4"] == ("<=", 5.0)
    assert esik_map["K5"] == ("==", 0)
    assert esik_map["K6a"][0] == ">" and esik_map["K6b"][0] == ">"


def test_k4_sifir_kabul():
    assert kapi_degerlendir(_tam_gecer(K4_g1_kapali_plan_orani=0.0))["karar"] == "GEÇTİ"
    assert kapi_degerlendir(_tam_gecer(K4_g1_kapali_plan_orani=5.1))["karar"] == "GEÇMEDİ"
