# -*- coding: utf-8 -*-
"""Faz 6 — giriş teyidi testleri (devamlılık: zemin, dip, kovalama)."""

from senaryo.giris_teyidi import MOM3_TAVANI_ATR, PENCERE, giris_teyidi


def _gec(low, close, i, zemin, atr):
    return giris_teyidi(low=low, close=close, i=i, zemin=zemin, atr=atr)


def test_sabitler_belgedekiyle_ayni():
    # FAZ6 §2: pencere=3, mom3 tavani=0,50 ATR
    assert PENCERE == 3
    assert MOM3_TAVANI_ATR == 0.50


def test_temiz_devam_gecer():
    # zemin tutuyor, dip oluşmuş (giriş dibin üstünde), koşu sakin
    low = [100, 99.5, 98.8, 99.2]
    close = [100.5, 99.8, 99.4, 100.2]
    ok, neden = _gec(low, close, i=3, zemin=98.0, atr=1.0)
    assert ok and neden == "tamam"


def test_zemin_alti_kapanis_elir():
    # son pencerede zemin altında kapanış var (destek kırılıp dönmüş)
    low = [100, 99, 96.5, 99.5]
    close = [100.5, 99.2, 96.8, 99.8]     # i=2'de96,8 < zemin98
    ok, neden = _gec(low, close, i=3, zemin=98.0, atr=1.0)
    assert not ok and neden == "zemin_alti_kapanis"


def test_yeni_dip_elir():
    # giriş barı yeni dip yapıyor (düşüşe alım)
    low = [100, 99.4, 99.0, 98.5]         # low[3] < min(low[1..2])
    close = [100.5, 99.8, 99.3, 99.1]
    ok, neden = _gec(low, close, i=3, zemin=97.0, atr=1.0)
    assert not ok and neden == "dip_teyidi_yok"


def test_kovalama_elir():
    # son3 barda koşu0,5 ATR üzerinde (zirveye yakın giriş)
    low = [100, 101, 102, 103]
    close = [100.5, 101.5, 102.5, 104.0]  # close[3]-close[0]=3,5 >0,5·1
    ok, neden = _gec(low, close, i=3, zemin=95.0, atr=1.0)
    assert not ok and neden == "kovalama"


def test_esit_dip_gecer():
    # çift dip eşitliği yeni dip sayılmaz (low[i] == min(prev))
    low = [100, 99.0, 99.4, 99.0]
    close = [100.2, 99.3, 99.6, 99.5]
    ok, neden = _gec(low, close, i=3, zemin=98.5, atr=1.0)
    assert ok and neden == "tamam"


def test_cekic_yeni_dip_olarak_kesilir():
    # bilinen davranış (belge §5): çekiç barı yeni dip yapıyorsa kesilir
    low = [100, 99.5, 99.2, 98.9]
    close = [100.5, 99.7, 99.4, 100.8]
    ok, neden = _gec(low, close, i=3, zemin=98.0, atr=1.0)
    assert not ok and neden == "dip_teyidi_yok"


def test_kontrol_sirasi_zemin_once():
    # hem zemin ihlali hem yeni dip varsa önce zemin raporlanır
    low = [100, 99, 97.0, 96.0]
    close = [100.5, 99.0, 97.5, 98.5]     # i=2'de kapanış<zemin; i=3 yeni dip
    ok, neden = _gec(low, close, i=3, zemin=98.0, atr=1.0)
    assert not ok and neden == "zemin_alti_kapanis"
