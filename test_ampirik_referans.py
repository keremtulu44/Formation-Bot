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
    # Aile kısıtsız: önce MS ("sürdü"), sonra formasyon sonucu ("tuttu").
    assert "sürdü" in satirlar[0], satirlar
    assert "tuttu" in satirlar[1], satirlar
    tek = ar.olcum_satirlari(k, azami=1)
    assert len(tek) == 1 and tek[0] == satirlar[0]


def test_uyum_yonu_dogru_okunuyor():
    # Aşağı kırılım + altta PL → uyumlu
    uyumlu = [x for x in ar.olcum_satirlari(_kurulum(yon=-1, break_price=100.0,
                                                    ph=104.0, pl=96.0), azami=9)
              if "rol" in x]
    assert uyumlu and "uyumlu" in uyumlu[0] and "uyumsuz" not in uyumlu[0]
    assert "%80" in uyumlu[0]
    # Aşağı kırılım ama aşağıda korunan dip yok, üstte PH var → uyumsuz
    uyumsuz = [x for x in ar.olcum_satirlari(_kurulum(yon=-1, break_price=100.0,
                                                      ph=96.0, pl=None), azami=9)
               if "rol" in x]
    assert uyumsuz and "uyumsuz" in uyumsuz[0]
    assert "%73" in uyumsuz[0]


def test_retest_satiri_iki_durumu_ayirir():
    # Retest görülmediyse taban oran basılır (artık en önde "tuttu" var).
    yok = ar.olcum_satirlari(_kurulum(retest_seen=False, aile="FRM"), azami=9)
    assert "◇ geri çekilme %35 · 28624" in yok, yok
    # Retest gördüyse ölçüm derinliğe bağlı → satır basılmaz (uydurma yok)
    var = ar.olcum_satirlari(_kurulum(retest_seen=True, aile="FRM"), azami=9)
    assert not [x for x in var if "geri çekilme" in x], var


def test_temel_satir_her_zaman_ilk_sira():
    """Formasyon ailesinde ilk satır "tuttu mu" sorusudur."""
    satirlar = ar.olcum_satirlari(_kurulum(aile="FRM"), azami=2)
    assert satirlar[0] == "◇ 32321 formasyon · %76 tuttu", satirlar


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


def test_taban_her_olcumde_gorunur():
    """Ölçüm tabanı gizlenmez: ya satırın kendisinde ya aynı blokta bir üstte.

    Sade dil sürümünde `n1651` gibi kısaltma kalktı; taban düz sayı oldu
    (`1651 olayın %75'i`, `· 15724`). Türetilmiş satır (ör. TL çevirisi)
    kendi tabanını taşımıyorsa bir üstteki ölçüm satırı taşır.
    """
    k = _kurulum(ms_kapsam="IC", ms_tip="CHOCH", ms_yon="DOWN", atr=1.0,
                 bolge_top=100.5, bolge_alt=100.0, rvol=0.3,
                 zone_icinde=False, retest_seen=False, ph=105.0, pl=95.0)
    satirlar = ar.olcum_satirlari(k, azami=9)
    assert satirlar

    def taban_var(satir: str) -> bool:
        # 3+ haneli sayı = ölçüm tabanı. Fiyat (39,60) ve yüzde (2,6) bu
        # kalıba girmez; taban her zaman en az 3 hanelidir (162, 858, 32321…).
        import re as _re
        return bool(_re.search(r"\d{3,}", satir))

    onceki = False
    for satir in satirlar:
        assert taban_var(satir) or onceki, f"taban yok: {satir}"
        onceki = taban_var(satir)


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
    # MS export'u "devam etti" olarak okunmalı (sade dil, en yüksek öncelik).
    # Aile verilmediği için kısıt yok; MS satırı ilk sırada gelir.
    assert any("sürdü" in s for s in satirlar), satirlar
    # Yüksek hacim satırı (3,4 → 4h üst çeyrek) geniş limitte görünür.
    genis = nc.domain_bolumleri(_sonuclar(), 100.0, stil="kart", alarm_tf="4h",
                                olcum=True, atr=1.0, yon=-1, retest_seen=False,
                                azami_olcum=9)["olcum"]
    assert any("hacim yüksekken" in s for s in genis), genis


def test_olcum_hatasi_alarmi_dusurmez():
    # Bozuk/eksik export: istisna sızmamalı ve export'a bağlı hiçbir iddia
    # (MS/zone/RVOL) basılmamalı; yalnız formasyon tabanı kalır.
    bozuk = {"4h": {"market_structure": {"error": "boom"},
                    "volume_participation": {"skipped": True}}}
    satirlar = nc.olcum_bolumu(bozuk, 100.0, alarm_tf="4h", aile="FRM")
    assert satirlar == ["◇ 32321 formasyon · %76 tuttu"], satirlar


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
    # Ölçüm tavanı: kart `_KART_MAKS_SATIR`ı geçmez ve hiçbir satır px bütçesini
    # aşmaz (satır sayısı tasarım hedefi değil, ölçülen sınırdır).
    assert len(satirlar) <= notifier._KART_MAKS_SATIR, satirlar
    assert satirlar[-1] == "• yatırım tavsiyesi değildir"
    # Kart sözleşmesi: girintili devam satırı ve 3+ öğeli zincir yok
    assert not [s for s in satirlar if s.startswith(" ")]
    assert not [s for s in satirlar if s.count("·") + s.count("—") >= 3], satirlar


# ------------------------------------------------------------------- komut yüzeyi

def test_komut_metni_ana_sayilari_tasir():
    metin = ar.komut_metni()
    assert metin.startswith("◇ Arşiv ölçümü")
    assert ar.OLCUM_TABANI in metin
    assert "32321 formasyondan" in metin            # FRM-15 tabanı
    assert "%79,7" in metin and "%73,1" in metin    # FRM-20 iki grup
    assert len(metin) <= 1100, len(metin)


def test_komut_metni_kartla_ayni_dili_konusur():
    """/olcum, kartın artık basmadığı terimleri öğretmemeli.

    Kart 2026-10-22'de sade dile geçti; komut metni eski sözlüğü gösterirse
    kullanıcı karta bakıp "bu ne" der.
    """
    metin = ar.komut_metni()
    for eski in ("RVOL", "retest", "zone içinde", "MS 4s dış BOS",
                 "tamamlandı %", "bar)"):
        assert eski not in metin, eski
    assert "kırılımı tuttu" in metin
    assert "geri çekilme" in metin
    assert "nadir" in metin


def test_komut_metni_aileleri_ayri_anlatir():
    metin = ar.komut_metni()
    assert "FRM ailesi" in metin and "MS ailesi" in metin and "ZONE ailesi" in metin
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


# ------------------------------------------------------------ aile ayrımı (Faz 2)

def test_aile_frm_yalniz_formasyon_olcumlerini_basar():
    """Formasyon alarmı MS/zone satırı basmaz; iki ayrı yüzde yan yana gelmez."""
    k = _kurulum(aile="FRM", ms_kapsam="EXTERNAL", ms_tip="BOS", ms_yon="UP",
                 atr=1.0, bolge_top=102.0, bolge_alt=101.0, rvol=3.9,
                 zone_icinde=True, retest_seen=False, ph=104.0, pl=96.0)
    satirlar = ar.olcum_satirlari(k, azami=7)
    assert satirlar, "FRM satırı üretmeli"
    assert not [s for s in satirlar if s.startswith("◇ BOS")], satirlar
    assert not [s for s in satirlar if "RVOL" in s], satirlar
    assert not [s for s in satirlar if "zone" in s], satirlar


def test_aile_ms_yalniz_devam_satirini_basar():
    k = _kurulum(aile="MS", ms_kapsam="EXTERNAL", ms_tip="BOS", ms_yon="UP",
                 atr=1.0, bolge_top=102.0, bolge_alt=101.0, rvol=3.9,
                 zone_icinde=True, retest_seen=False, ph=104.0, pl=96.0)
    satirlar = ar.olcum_satirlari(k, azami=7)
    assert len(satirlar) == 1
    assert "sürdü" in satirlar[0], satirlar


def test_aile_zone_yalniz_bolge_olcumlerini_basar():
    k = _kurulum(aile="ZONE", ms_kapsam="EXTERNAL", ms_tip="BOS", ms_yon="UP",
                 atr=1.0, bolge_top=102.0, bolge_alt=101.0, rvol=3.9,
                 zone_icinde=True, retest_seen=False, ph=104.0, pl=96.0)
    satirlar = ar.olcum_satirlari(k, azami=7)
    assert not [s for s in satirlar if s.startswith("◇ BOS")], satirlar
    assert satirlar, "zone ölçümü üretmeli"


def test_aile_bos_kisit_yok_eski_davranis():
    """`aile=""` geri dönüş yolu: hiçbir satır türü elenmez."""
    k = _kurulum(aile="", ms_kapsam="EXTERNAL", ms_tip="BOS", ms_yon="UP",
                 atr=1.0, bolge_top=102.0, bolge_alt=101.0, rvol=3.9,
                 zone_icinde=True, retest_seen=False, ph=104.0, pl=96.0)
    metin = " ".join(ar.olcum_satirlari(k, azami=9))
    assert "sürdü" in metin and "tuttu" in metin


# ------------------------------------------------- sade dil (Faz 3)

KISALTMALAR = ("ATR", "RVOL", "MTF", "BOS", "CHoCH", "FVG", "OB ", " OB",
               "bar ", " n1", "n1651", "n15724")

#: Ölçüm satırlarında yasak sıfatlar: ölçülebilir olmayan güç/olasılık imaları.
YASAK_SIFATLAR = ("tipik", "zayıf", "güçlü", "muhtemel", "ihtimal",
                  "bekleniyor", "yüksek olasılık")


@pytest.mark.parametrize("aile,ek", [
    ("FRM", {"atr": 1.0, "ph": 105.0, "pl": 95.0, "retest_seen": False}),
    ("MS", {"ms_kapsam": "EXTERNAL", "ms_tip": "BOS", "ms_yon": "UP"}),
    ("ZONE", {"atr": 1.0, "bolge_top": 102.0, "bolge_alt": 101.0,
              "rvol": 3.9, "zone_icinde": True}),
])
def test_sade_dilde_kisaltma_yok(aile, ek):
    """Kart ölçüm satırı kısaltma taşımaz (kullanıcı: "kod yazan birinin bile
    bileceği" dil yasak). Teknik kimlik metinde kalabilir, ÖLÇÜ satırında kalmaz."""
    kurulum = _kurulum(aile=aile, **ek)
    satirlar = ar.olcum_satirlari(kurulum, azami=9)
    assert satirlar, aile
    for satir in satirlar:
        for kisa in KISALTMALAR:
            assert kisa not in satir, (aile, kisa, satir)


@pytest.mark.parametrize("aile,ek", [
    ("FRM", {"atr": 1.0, "ph": 105.0, "pl": 95.0}),
    ("MS", {"ms_kapsam": "EXTERNAL", "ms_tip": "BOS", "ms_yon": "DOWN"}),
    ("ZONE", {"atr": 1.0, "bolge_top": 102.0, "bolge_alt": 101.0, "rvol": 0.2}),
])
def test_sade_dilde_sifat_yok(aile, ek):
    for satir in ar.olcum_satirlari(_kurulum(aile=aile, **ek), azami=9):
        for sifat in YASAK_SIFATLAR:
            assert sifat not in satir.lower(), (aile, sifat, satir)


def test_tuttu_ifadesi_motorun_terminal_durumunu_dogru_anlatir():
    """`tamamlandı` = "hedefe ulaştı" DEĞİL; "kırılım tuttu, banda dönmedi".

    Bu ayrım kartın en yanlış anlaşılacak yeridir (kullanıcı 2026-10-22:
    "formasyonun tamamlanması teknik bilen biri bile anlayamayabilir").
    """
    satir = ar.olcum_satirlari(_kurulum(aile="FRM"), azami=1)[0]
    assert "tuttu" in satir
    assert "tamamlandı" not in satir and "hedef" not in satir


def test_hareket_satiri_tl_ve_yuzde_verir():
    """1,23 ATR → canlı ATR ve fiyatla TL + yüzde (okumak için ATR bilmek gerekmez)."""
    k = _kurulum(aile="FRM", atr=0.85, break_price=39.60, ph=43.0, pl=36.0)
    satirlar = ar.olcum_satirlari(k, azami=9)
    hareket = [x for x in satirlar if "tutunca" in x]
    assert hareket, satirlar
    assert "TL" in hareket[0] and "%" in hareket[0], hareket[0]


def test_hareket_satiri_atr_yoksa_kat_olarak_kalir():
    k = _kurulum(aile="FRM", atr=None, break_price=39.60, ph=43.0, pl=36.0)
    hareket = [x for x in ar.olcum_satirlari(k, azami=9) if "tutunca" in x]
    assert not hareket, "ATR yoksa TL çevirisi uydurulmaz"


# ------------------------------------------------ nadir kademesi (n < 300)

def test_nadir_kova_oran_basmaz():
    """n<300'de yüzde yazılmaz: 162 gözlemde %71 "sonuç" değil gürültüdür."""
    # Yükseklik kovası ≥2 kat → n=162
    k = _kurulum(aile="ZONE", atr=1.0, bolge_top=103.5, bolge_alt=101.0,
                 rvol=1.0, zone_icinde=True)
    satirlar = ar.olcum_satirlari(k, azami=9)
    assert any("nadir (162) · yorum yok" in s for s in satirlar), satirlar
    assert not any("%71" in s for s in satirlar), satirlar


def test_nadir_esigi_tabloda_tek_yerde():
    assert ar.NADIR_ESIK == 300
    assert ar._nadir(162) == "◇ nadir (162) · yorum yok"
