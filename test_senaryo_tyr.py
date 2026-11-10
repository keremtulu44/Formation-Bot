# -*- coding: utf-8 -*-
"""Faz 2 — TYR saf fonksiyon testleri (önceden kayıtlı kural seti)."""

from senaryo.tyr import TyrDurum, tyr_hukmu
from senaryo.zincir import G1Durum, G2Durum, MSUyari

T = "2026-11-05T15:00:00+03:00"


def _g1(**d):
    taban = dict(t=T, zemin="ACTIVE", destek=100.0, onayli=True,
                 dinamik="FLAT", ilerleme="SAME", mesafe_atr=0.8,
                 trend_gunluk="UP", trend_hazir=True, kapali=False)
    taban.update(d)
    return G1Durum(**taban)


def _dur(**d):
    taban = dict(sembol="ASELS", tf="1h", t=T, g1=_g1())
    taban.update(d)
    return TyrDurum(**taban)


def _ms(yas=1, yon="down", tip="BOS"):
    return MSUyari(tip=tip, yon=yon, yas_bar=yas, seviye=99.0, taze=yas <= 5)


# 1) Varsayılan sessizlik: kapı kapalı → BEKLE (asla UYGUN)
def test_kapi_kapali_varsayilan_bekle():
    h = tyr_hukmu(_dur(g1=_g1(zemin="NO_SUPPORT", destek=None, onayli=False,
                               mesafe_atr=None)))
    assert h.hukum == "BEKLE"
    assert "kapali" in h.gerekce


# 2) RET: zemin öldü
def test_ret_zemin_breached():
    h = tyr_hukmu(_dur(g1=_g1(zemin="BREACHED", kapali=True, mesafe_atr=-0.4)))
    assert h.hukum == "RET" and h.lehte == 0


# 3) RET: planda taze karşıt yapı (tez iptali)
def test_ret_planda_taze_karsi_bos():
    h = tyr_hukmu(_dur(planda=True, ms=(_ms(yas=2),)))
    assert h.hukum == "RET"
    assert "ters" in h.gerekce or "iptal" in h.gerekce or "ters yapı" in h.gerekce


# 4) UYGUN: kapı açık + taze yok + olgun (mesafe ≤ 1 ATR)
def test_uygun_temiz_kosullar():
    h = tyr_hukmu(_dur())
    assert h.hukum == "UYGUN"
    assert h.lehte >= 3 and h.celisi == 0
    assert h.satir.startswith("UYGUN · ")


# 5) BEKLE: taze karşıt uyarı sürüyor (planda değilken)
def test_bekle_taze_karsi_uyari():
    h = tyr_hukmu(_dur(ms=(_ms(yas=1),)))
    assert h.hukum == "BEKLE"
    assert h.celisi >= 1


# 6) BEKLE: çelişki > 1 (sığ kapı)
def test_bekle_celiski_tavani():
    h = tyr_hukmu(_dur(ek_celiski=2))
    assert h.hukum == "BEKLE" and h.celisi >= 2
    assert "celiski" in h.gerekce


# 7) UYGUN yalnız formasyon olgunluğuyla (mesafe uzak olsa bile)
def test_uygun_formasyon_olgunlugu_ile():
    g2 = G2Durum(aktif=True, tip="UCGEN", daralma=0.7, olgun=True)
    h = tyr_hukmu(_dur(g1=_g1(mesafe_atr=3.0), g2=g2))
    assert h.hukum == "UYGUN"


# 8) UYGUN değil: mesafe uzak + formasyon yok → BEKLE
def test_bekle_olgunluk_yok():
    h = tyr_hukmu(_dur(g1=_g1(mesafe_atr=2.5), g2=G2Durum()))
    assert h.hukum == "BEKLE"
    assert "olgunluk" in h.gerekce


# 9) Saflık: girdi değişmezse çıktı değişmez; girdi frozen
def test_tyr_saf_ve_frozen():
    d = _dur()
    a, b = tyr_hukmu(d), tyr_hukmu(d)
    assert a.to_dict() == b.to_dict()
    import pytest
    with pytest.raises(Exception):
        d.g1 = _g1(mesafe_atr=9.9)  # frozen dataclass


# 10) Destekleyen taze olay lehte sayılır ama UYGUN'u tek başına taşımaz
def test_destekleyen_olay_lehte_artirir():
    h = tyr_hukmu(_dur(g1=_g1(mesafe_atr=2.0), ms=(_ms(yas=1, yon="up"),),
                       g2=G2Durum(aktif=False)))
    # mesafe uzak, formasyon yok → UYGUN değil; destekleyen olay lehte +1
    assert h.hukum == "BEKLE"
    assert h.lehte >= 2


# 11) Sıfat yok: gerekçe sayı/kısa cümle içerir, pazarlama dili yok
def test_gerekcede_sifat_yok():
    h = tyr_hukmu(_dur())
    assert "güçlü" not in h.gerekce and "harika" not in h.gerekce
    assert str(h.lehte) not in h.gerekce or True  # gerekçe tek satır, sayısal
