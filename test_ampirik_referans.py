# -*- coding: utf-8 -*-
"""Ampirik referans katmanı sözleşmesi.

Neden bu testler var: metne giren her sayı `docs/arastirma/` tablolarından
gelmeli, `n` görünmeli, satır kart bütçesine sığmalı ve tavsiye dili
kullanılmamalı. Ölçüm tablosu ile metin arasındaki tek bağ burası olduğu için
sayıların kendisi de test edilir (tablo yanlış kopyalanırsa kart yanlış konuşur).
"""

from __future__ import annotations

import pytest

import ampirik_referans as ar
import notifier
import notification_context as nc
import telegram_measure as tm


# --------------------------------------------------------------- tablo değerleri

def test_tablo_degerleri_kaynakla_ayni():
    # FORMASYON_SONUCLARI FRM-15 / FRM-16 / FRM-20
    assert ar.FRM_TERMINAL["tamamlandi"] == 76.2
    assert ar.FRM_TEYIT_MFE["medyan_atr"] == 1.23
    assert ar.FRM_UYUM["uyumlu"] == (15724, 79.7)
    assert ar.FRM_UYUM["uyumsuz"] == (13573, 73.1)
    # ARASTIRMA_BULGULARI — hacim çeyreği (4h Q4) ve MS (4h dış BOS ↑)
    assert ar.RVOL_KOVALARI["4h"][3][:2] == (11928, 61.0)
    assert ar.MS_YON[("4h", "DIS", "BOS", "UP")] == (1651, 75.0, 2.827)
    # Soru 4 — zone yüksekliği son kova
    assert ar.YUKSEKLIK_KOVALARI[-1][1:] == (162, 71.0, "kalıcı")


def test_zone_referansi_yalniz_tabloda_olan_kesit():
    assert ar.zone_referansi("OB", "1h") == (90199, 2.0054, 2.0846)
    # 1h FVG arşivde üretilmedi → ölçüm yok (uydurulmaz)
    assert ar.zone_referansi("FVG", "1h") is None
    assert ar.zone_referansi("OB", "5m") is None


# ------------------------------------------------------------------ kova atama

def test_rvol_kovasi_en_yakin_ortalama():
    assert ar.rvol_kovasi("4h", 0.4)[0] == 0
    assert ar.rvol_kovasi("4h", 1.0)[0] == 1
    assert ar.rvol_kovasi("4h", 3.2)[0] == 3
    assert ar.rvol_kovasi("4h", None) is None
    assert ar.rvol_kovasi("4h", -1) is None
    assert ar.rvol_kovasi("9h", 1.0) is None


def test_yukseklik_kovasi_sinirlari():
    assert ar.yukseklik_kovasi(0.4)[0][1] == 3276      # <0,5 ATR
    assert ar.yukseklik_kovasi(0.5)[0][1] == 1989      # 0,5–1 ATR
    assert ar.yukseklik_kovasi(1.9)[0][1] == 858       # 1–2 ATR
    assert ar.yukseklik_kovasi(2.5)[0][1] == 162       # >=2 ATR
    assert ar.yukseklik_kovasi(None) is None
    assert ar.yukseklik_kovasi(0) is None


def test_ms_referansi_yon_yoksa_tip_tabanina_duser():
    assert ar.ms_referansi("4h", "EXTERNAL", "BOS", "UP") == (1651, 75.0, 2.827)
    assert ar.ms_referansi("4h", "EXTERNAL", "BOS", None) == (3387, 71.0, 2.500)
    assert ar.ms_referansi("4h", "INTERNAL", "CHOCH", "DOWN") == (1235, 67.9, 2.077)
    assert ar.ms_referansi("4h", "EXTERNAL", "SWEEP", "UP") is None
    assert ar.ms_referansi("15m", "EXTERNAL", "BOS", "UP") is None


# ---------------------------------------------------------------- satır üretimi

def _kurulum(**ek) -> ar.Kurulum:
    veri = dict(tf="4h", yon=-1, break_price=100.0)
    veri.update(ek)
    return ar.Kurulum(**veri)


def test_satir_yoksa_uretilmez():
    assert ar.olcum_satirlari(ar.Kurulum(tf="")) == []


def test_oncelik_ve_azami():
    k = _kurulum(ms_kapsam="EXTERNAL", ms_tip="BOS", ms_yon="DOWN",
                 ph=104.0, pl=96.0, atr=1.0, bolge_top=101.0, bolge_alt=99.0,
                 rvol=3.2, retest_seen=False, zone_icinde=True)
    satirlar = ar.olcum_satirlari(k, azami=2)
    assert len(satirlar) == 2
    assert satirlar[0].startswith("◇ BOS")          # MS en önde
    assert satirlar[1].startswith("◇ rol")          # sonra rol uyumu
    tek = ar.olcum_satirlari(k, azami=1)
    assert len(tek) == 1 and tek[0] == satirlar[0]


def test_uyum_yonu_dogru_okunuyor():
    # Aşağı kırılım + altta PL → uyumlu
    uyumlu = ar.olcum_satirlari(_kurulum(yon=-1, break_price=100.0,
                                         ph=104.0, pl=96.0), azami=1)
    assert "uyumlu" in uyumlu[0] and "uyumsuz" not in uyumlu[0]
    # Aşağı kırılım ama aşağıda korunan dip yok, üstte PH var → uyumsuz
    uyumsuz = ar.olcum_satirlari(_kurulum(yon=-1, break_price=100.0,
                                          ph=96.0, pl=None), azami=1)
    assert "uyumsuz" in uyumsuz[0]


def test_retest_satiri_iki_durumu_ayirir():
    yok = ar.olcum_satirlari(_kurulum(retest_seen=False), azami=1)
    assert yok == ["◇ retest oranı %35 n28624"]
    # Retest gördüyse ölçüm derinliğe bağlı → satır basılmaz (uydurma yok)
    var = ar.olcum_satirlari(_kurulum(retest_seen=True), azami=1)
    assert var == ["◇ medyan 1,2 ATR n24618"]


def test_temel_satir_her_zaman_son_sira():
    satirlar = ar.olcum_satirlari(_kurulum(), azami=2)
    assert satirlar == ["◇ medyan 1,2 ATR n24618"]


TAVSIYE_KELIMELERI = ("al ", "sat ", "hedef", "stop", "kâr", "kar ", "zarar",
                      "tavsiye", "garanti", "kesin")


@pytest.mark.parametrize("ek", [
    {},
    {"ms_kapsam": "EXTERNAL", "ms_tip": "BOS", "ms_yon": "UP"},
    {"atr": 1.0, "bolge_top": 102.0, "bolge_alt": 101.0},
    {"rvol": 3.9},
    {"zone_icinde": True},
    {"retest_seen": True},
    {"ph": 101.0, "pl": 90.0},
])
def test_tavsiye_dili_yok(ek):
    for satir in ar.olcum_satirlari(_kurulum(**ek), azami=3):
        kucuk = satir.lower()
        for kelime in TAVSIYE_KELIMELERI:
            assert kelime not in kucuk, (kelime, satir)


@pytest.mark.parametrize("ek", [
    {},
    {"ms_kapsam": "EXTERNAL", "ms_tip": "BOS", "ms_yon": "UP"},
    {"atr": 1.0, "bolge_top": 102.0, "bolge_alt": 101.0},
    {"rvol": 3.9},
    {"zone_icinde": False},
    {"retest_seen": False},
    {"ph": 101.0, "pl": 90.0},
])
def test_satirlar_kart_butcesine_sigar(ek):
    for satir in ar.olcum_satirlari(_kurulum(**ek), azami=3):
        assert tm.genislik(satir) <= notifier._kart_esik_px(), satir


def test_her_satirda_n_var():
    k = _kurulum(ms_kapsam="IC", ms_tip="CHOCH", ms_yon="DOWN", atr=1.0,
                 bolge_top=100.5, bolge_alt=100.0, rvol=0.3,
                 zone_icinde=False, retest_seen=False, ph=105.0, pl=95.0)
    for satir in ar.olcum_satirlari(k, azami=7):
        assert " n" in satir, satir


# ------------------------------------------------------------------ bölüm/bağlama

def _sonuclar():
    """Küçük ama gerçek alan adlarını taşıyan export sözlüğü."""
    return {
        "4h": {
            "order_block": {"export": {"bull": {"top": 100.4, "bottom": 99.6,
                                               "state": 1, "fill": 0.2}}},
            "fvg": {"export": {}},
            "market_structure": {"export": {
                "external_protected_high": 104.0,
                "external_protected_low": 96.0,
                "events": ({"scope": "EXTERNAL", "event_type": "EVENT_BOS",
                            "direction": -1, "confirmation_status": "CONFIRMED",
                            "validity": "VALID", "relevance": "CURRENT",
                            "is_active": True, "event_bar": 41},),
            }},
            "volume_participation": {"export": {"rvol": 3.4}},
        },
        "1h": {},
    }


def test_bolum_varsayilan_kapali():
    bolumler = nc.domain_bolumleri(_sonuclar(), 100.0, stil="kart", alarm_tf="4h")
    assert "olcum" not in bolumler


def test_bolum_acikken_exporttan_satir_uretir():
    bolumler = nc.domain_bolumleri(_sonuclar(), 100.0, stil="kart", alarm_tf="4h",
                                   olcum=True, atr=1.0, yon=-1, retest_seen=False)
    satirlar = bolumler["olcum"]
    assert satirlar, bolumler
    assert all(s.startswith("◇") for s in satirlar)
    assert len(satirlar) <= 2
    # MS export'u BOS ↓ dış olarak okunmalı (en yüksek öncelik)
    assert any("BOS" in s and "↓" in s for s in satirlar), satirlar
    # Üçüncü sırada yüksek RVOL satırı var (3,4 → 4h üst çeyrek)
    genis = nc.domain_bolumleri(_sonuclar(), 100.0, stil="kart", alarm_tf="4h",
                                olcum=True, atr=1.0, yon=-1, retest_seen=False,
                                azami_olcum=4)["olcum"]
    assert any("yüksek RVOL" in s for s in genis), genis


def test_olcum_hatasi_alarmi_dusurmez():
    # Bozuk/eksik export: istisna sızmamalı ve export'a bağlı hiçbir iddia
    # (MS/zone/RVOL) basılmamalı; yalnız formasyon tabanı kalır.
    bozuk = {"4h": {"market_structure": {"error": "boom"},
                    "volume_participation": {"skipped": True}}}
    satirlar = nc.olcum_bolumu(bozuk, 100.0, alarm_tf="4h")
    assert satirlar == ["◇ medyan 1,2 ATR n24618"], satirlar


def test_kart_olcum_satirini_basar():
    payload = {
        "stock_name": "SISE", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
        "pattern_name": "Yükselen Üçgen", "break_dir": 1, "break_price": 39.26,
        "candle_close_price": 39.60, "confidence_score": 81, "break_strength": 100,
        "age_bars": 94, "band_baslangic": "2026-09-30T16:30:00+03:00",
        "retest_seen": False, "mtf_destek": True,
        "domain_bolumleri": {
            "hacim": ["katılım 4s destekliyor"],
            "olcum": ["◇ rol uyumlu %80 n15724"],
        },
    }
    satirlar = notifier._format_lifecycle_alert_kart(payload).splitlines()
    assert "◇ rol uyumlu %80 n15724" in satirlar
    assert 8 <= len(satirlar) <= 14, satirlar
    assert satirlar[-1] == "• yatırım tavsiyesi değildir"
    # Kart sözleşmesi: girintili devam satırı ve 3+ öğeli zincir yok
    assert not [s for s in satirlar if s.startswith(" ")]
    assert not [s for s in satirlar if s.count("·") >= 2]


# ------------------------------------------------------------------- komut yüzeyi

def test_komut_metni_ana_sayilari_tasir():
    metin = ar.komut_metni()
    assert metin.startswith("◇ Arşiv ölçümü")
    assert ar.OLCUM_TABANI in metin
    assert "n 32321" in metin          # FRM-15 tabanı
    assert "%79,7" in metin and "%73,1" in metin   # FRM-20 iki grup
    assert len(metin) <= 1100, len(metin)
    # Yasal uyarı satırı "tavsiye" kelimesini taşır; tarama dışında tutulur.
    tarama = metin.replace("Yatırım tavsiyesi değildir.", "")
    for kelime in TAVSIYE_KELIMELERI:
        assert kelime not in tarama.lower(), kelime


def test_komut_metni_satirlari_telegram_butcesine_sigar():
    for satir in ar.komut_metni().splitlines():
        assert tm.genislik(satir) <= tm.SATIR_BUTCE, satir


def test_komut_main_uzerinde_kayitli():
    import main

    assert main.TELEGRAM_KOMUTLARI["olcum"] is main._komut_olcum
    assert main.TELEGRAM_KOMUTLARI["referans"] is main._komut_olcum
    assert "/olcum" in main.KOMUT_YARDIM
    assert main._komut_olcum("") == ar.komut_metni()
