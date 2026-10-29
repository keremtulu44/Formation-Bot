# -*- coding: utf-8 -*-
"""Kart yorum katmanı (notifier/kart_yorum) — kapı sözleşmesi testleri.

Sözleşme (2026-10-29): kapı yoksa eski kart; kapı varsa ◇ (≤3, öncelik +
stok hafızası) + dikkat (≤1); kod/n yalnız logda; yalnız canlı akış anahtarı
(`kart_yorum_kapisi`) açar.
"""
import pytest

import config
from notifier import kart_yorum
from notifier.format_kart import _format_lifecycle_alert_kart_sade


@pytest.fixture(autouse=True)
def _hafiza_sifirla():
    kart_yorum.sifirla()
    yield
    kart_yorum.sifirla()


def _veri(**ek):
    veri = {
        "stock_name": "TEST",
        "timeframe": "4h",
        "state": "KIRILIM_TEYITLI",
        "pattern_name": "Yükselen Kanal",
        "critical_price_level": 100.5,
        "candle_close_price": 101.0,
        "break_dir": 1,
        "kart_yorum_kapisi": True,
    }
    veri.update(ek)
    return veri


def _bolum(**ek):
    bolum = {
        "olcum": ["◇ arşiv ölçüm 12 puan"],
        "hacim": ["katılım 4s"],
        "ust": ["▲ OB 4s 100,1-101,0 (2 temas)"],
        "alt": [],
        "engel": [],
    }
    bolum.update(ek)
    return bolum


# ── temel kapılar ───────────────────────────────────────────────────────────

def test_flag_kapali_sessiz():
    assert kart_yorum.sec(_veri(upper_touches=3), _bolum())["yorum"]
    import config as c
    eski = c.TELEGRAM_KART_YORUM
    c.TELEGRAM_KART_YORUM = False
    try:
        sonuc = kart_yorum.sec(_veri(upper_touches=3), _bolum())
        assert sonuc == {"yorum": [], "dikkat": "", "kodlar": [], "dikkat_kod": ""}
    finally:
        c.TELEGRAM_KART_YORUM = eski


def test_anhtar_yok_eski_kart():
    veri = _veri(upper_touches=3)
    del veri["kart_yorum_kapisi"]
    assert kart_yorum.sec(veri, _bolum())["kodlar"] == []


def test_teyitli_disi_sessiz():
    for state in ("KIRILIM_GECERSIZLESTI", "IZLEMEDE", "", None):
        veri = _veri(upper_touches=3, state=state)
        assert kart_yorum.sec(veri, _bolum())["kodlar"] == []


def test_kapisiz_kart_bos():
    sonuc = kart_yorum.sec(_veri(), _bolum())
    assert sonuc["yorum"] == [] and sonuc["dikkat"] == ""


def test_s15_temas_ve_ob():
    sonuc = kart_yorum.sec(_veri(upper_touches=2), _bolum())
    assert sonuc["kodlar"] == ["S15"]
    satir = sonuc["yorum"][0]
    assert "35 puan" in satir
    # karta kod/n yazılmaz
    assert "S15" not in satir and "n=" not in satir and "29.283" not in satir


def test_s15_fvgde_acilmaz():
    # FVG'de ikinci geliş farkı RED — kapı yalnız OB'de.
    bolum = _bolum(ust=["▲ FVG 4s 100,1-101,0"])
    assert kart_yorum.sec(_veri(upper_touches=2), bolum)["kodlar"] == []


# ── limit + öncelik + hafıza ────────────────────────────────────────────────

def test_uc_limit_oncelik_sirasi():
    veri = _veri(upper_touches=2, age_bars=25, stock_name="ASELS")
    bolum = _bolum(ust=["▲ OB 4s"],
                   hacim=["katılım 4s yukarı zayıflıyor"],
                   engel=["▲ 101,0 (kırılım eşiği)"])
    sonuc = kart_yorum.sec(veri, bolum)
    # açık: S15, S04, S10, S16, S17, S13, S31 → limit 3, öncelik sırası
    assert len(sonuc["yorum"]) == 3
    assert sonuc["kodlar"] == ["S15", "S04", "S10"]


def test_stok_hafizasi_ustuste_ayni_gelmez():
    veri = _veri(age_bars=6)
    ilk = kart_yorum.sec(veri, _bolum())
    assert ilk["kodlar"] == ["S04"]
    ikinci = kart_yorum.sec(veri, _bolum())
    assert "S04" not in ikinci["kodlar"]          # üst üste aynı ◇ gelmez
    farkli = _veri(age_bars=6, stock_name="BASKA")
    assert kart_yorum.sec(farkli, _bolum())["kodlar"] == ["S04"]


# ── dikkat: en fazla 1, öncelik ────────────────────────────────────────────

def test_dikkat_tek_ve_oncelik():
    bolum = _bolum(ust=["▲ FVG 4s"], hacim=["hacim 4s yok (endeks)"])
    sonuc = kart_yorum.sec(_veri(), bolum)
    # S08 (FVG) > S14 (veri yok) — ikisi de açık ama tek dikkat
    assert sonuc["dikkat_kod"] == "S08"
    assert sonuc["dikkat"].startswith("· dikkat")


def test_dikkat_yok():
    sonuc = kart_yorum.sec(_veri(), _bolum())
    assert sonuc["dikkat"] == "" and sonuc["dikkat_kod"] == ""


def test_yorum_satirlari_kart_jargonu_tasimaz():
    """Sözleşme: kart yüzeyinde ATR/RVOL/FVG/OB/BOS/CHoCH/bar yok (Faz 3)."""
    from test_kart_metin import KART_JARGON

    for kayit in kart_yorum.YORUMLAR + kart_yorum.DIKKATLAR:
        for kisa in KART_JARGON:
            assert kisa not in kayit["satir"], (kayit["kod"], kisa, kayit["satir"])


def test_yorum_satirlari_butce_sinirinda():
    """Her satır ≤300 px: `_satir` 268,85'te girintili böler, Telegram
    yerel sarımı hiç olmaz (metin eksilmez)."""
    from telegram_measure import genislik

    for kayit in kart_yorum.YORUMLAR + kart_yorum.DIKKATLAR:
        assert genislik(kayit["satir"]) <= 300, (kayit["kod"], kayit["satir"])


# ── sade kart entegrasyonu ─────────────────────────────────────────────────

def test_sade_kart_yorum_olcumun_yerine_gecer():
    veri = _veri(age_bars=6,
                 domain_bolumleri=_bolum(engel=["▲ 101,0"]))
    metin = _format_lifecycle_alert_kart_sade(veri)
    duz = " ".join(metin.split())  # girintili devam satırlarını birleştir
    assert "◇ Eski bölgede tutma 21 puan fazla" in duz
    assert "◇ arşiv ölçüm 12 puan" not in metin        # yeni kaynak eskiyi bastırır
    assert "geçmiş davranıştır, kazanç değil" in metin  # dipnot korunur
    # dikkat bloğu yok (kapı kapalı) ve CTA son satır
    assert "· dikkat" not in metin
    assert metin.rstrip().endswith("• yatırım tavsiyesi değildir")


def test_sade_kart_blokta_dikkat_var():
    veri = _veri(domain_bolumleri=_bolum(ust=["▲ FVG 4s"],
                                         hacim=["hacim 4s yok (endeks)"]))
    metin = _format_lifecycle_alert_kart_sade(veri)
    assert "· dikkat: FVG hedefi geç geliyor" in metin
    assert "· dikkat" in metin.split("• yatırım tavsiyesi değildir")[0]
    # kapı yok → eski ölçüm satırı aynen sürer
    assert "◇ arşiv ölçüm 12 puan" in metin


def test_sade_kart_anhtar_yok_eski_hal():
    veri = _veri(age_bars=25, domain_bolumleri=_bolum(engel=["▲ 101,0"]))
    del veri["kart_yorum_kapisi"]
    metin = _format_lifecycle_alert_kart_sade(veri)
    assert "◇ arşiv ölçüm 12 puan" in metin
    assert "Eski bölgede tutma" not in metin
    assert "· dikkat" not in metin
