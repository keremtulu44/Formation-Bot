# -*- coding: utf-8 -*-
"""Kart metni sözleşmesi (GÖRSEL-8/9): ölçüm tabanlı, zincirsiz, taşmasız.

Kullanıcı şikâyeti (2026-10-15): "mesaj aşırı karışık / nokta nokta / okunabilirlik
kötü". Ölçülen kaynak: bugünkü kart 40-45 satır, ~%40'ı girintili DEVAM satırı,
7 satır aynı `▪` ile başlıyor, satır başına 1,6 öğe ama 44 `·` karakteri var.

Yeni sözleşme:
  * satır = TEK konu; 3+ öğeli zincir yok (en çok 2 ayırıcı),
  * girintili devam satırı YOK (satır bölünmesi = `_kart_esik_px` eşiği),
  * satır sayısı sabit bir sayı değil ÖLÇÜLMÜŞ tavan: hiçbir satır px bütçesini
    aşmaz ve kart `_KART_MAKS_SATIR`ı geçmez (2026-10-21 kararı: 19-20 satır),
  * kârenin taşıdığı bilgi (kutular/yapı/kırılan seviye/daralma/temas) metinde
    TEKRARLANMAZ; `TELEGRAM_KART_SUZGEC=0` eski tam kartı geri getirir.
"""

from __future__ import annotations

import pytest

import notifier
import telegram_measure as tm


def _payload(**ek):
    veri = {
        "stock_name": "SISE", "timeframe": "1h", "state": "KIRILIM_TEYITLI",
        "pattern_name": "Yükselen Üçgen", "break_dir": -1, "break_price": 39.26,
        "critical_price_level": 39.26, "candle_close_price": 39.18,
        "confidence_score": 81, "break_strength": 100, "age_bars": 94,
        "band_baslangic": "2026-09-30T16:30:00+03:00", "retest_seen": False,
        "mtf_destek": True, "upper_now": 39.96, "lower_now": 38.79,
        "domain_bolumleri": {"hacim": ["katılım 1s destekliyor", "katılım 2s 0,42 zayıf"]},
    }
    veri.update(ek)
    return veri


def _satirlar(metin: str) -> list[str]:
    return metin.splitlines()


def _tasma(satirlar: list[str]) -> list[str]:
    """Bütçenin güvenli sınırını aşan satırlar (`_satir` bölerdi)."""
    return [s for s in satirlar if tm.genislik(s) > notifier._kart_esik_px()]


# ------------------------------------------------------------------ normal kart


def test_teyitli_kart_tasmaz_ve_zincirsiz():
    satirlar = _satirlar(notifier._format_lifecycle_alert_kart(_payload()))
    # Satır sayısı bir TASARIM hedefi değil ÖLÇÜM tavanıdır: kart bütçeyi
    # aşmadığı sürece satır sayısı serbesttir (GÖRSEL-9, 2026-10-21).
    assert len(satirlar) <= notifier._KART_MAKS_SATIR, satirlar
    assert not _tasma(satirlar), _tasma(satirlar)
    assert not [s for s in satirlar if s.startswith(" ")], "girintili devam satırı yok"
    # Zincir kuralı: 3+ öğe tek satıra sığdırılmaz (2 öğe serbest, ör.
    # `· kapanış 39,60 · sınır 39,26`).
    assert satirlar[0].startswith("▼ SISE 1s AŞAĞI TEYİTLİ")
    assert satirlar[-1] == "• yatırım tavsiyesi değildir"
    # 3+ ayırıcılı satır yok: `·`/`—` karışımı tek satırda 2'yi geçmez.
    assert not [x for x in satirlar if x.count("·") + x.count("—") >= 3]


def test_teyitli_kart_karenin_taşıdığı_bilgiyi_tekrarlamaz():
    metin = notifier._format_lifecycle_alert_kart(_payload(domain_bolumleri={
        "yapi": ["🏗 1s yapı: HH→LH ↓ / LL→HL ↓"],
        "ust": ["▲ OB 1s 44,14-44,86 (▼) · %0"],
        "alt": ["▲ OB 1s 42,98-43,40 (▼) · %0"],
        "hacim": ["katılım 1s destekliyor"],
    }))
    for yasak in ("◈", "▸", "▤", "▪", "OB 1s", "%0"):
        assert yasak not in metin, yasak


def test_kalicilik_ve_esik_yonu_dogru():
    """Eşik GÜNCEL bant sınırıdır: aşağı kırılımı alt sınırın üstü bozar."""
    metin = notifier._format_lifecycle_alert_kart(_payload())
    assert "bozulur: 38,79 üstü kapanış" in metin
    yukari = notifier._format_lifecycle_alert_kart(_payload(
        break_dir=1, break_price=40.10, candle_close_price=40.25,
        upper_now=40.44, lower_now=39.10, state="KIRILIM_TEYITLI"))
    assert "bozulur: 40,44 altı kapanış" in yukari


# ------------------------------------------------------------- geçersizleşme


def test_gecersizlesme_karti_formasyon_ve_tf_ile_sinirli():
    satirlar = _satirlar(notifier._format_lifecycle_alert_kart(_payload(
        state="KIRILIM_GECERSIZLESTI", domain_bolumleri={
            "yapi": ["🏗 1s yapı: HH→LH ↓ / LL→HL ↓"],
            "ust": ["▲ OB 1s 44,14-44,86 (▼) · %0"],
            "hacim": ["katılım 1s destekliyor"],
        })))
    assert len(satirlar) <= notifier._KART_MAKS_SATIR, satirlar
    assert not _tasma(satirlar)
    assert satirlar[0] == "▼ SISE 1s GEÇERSİZLEŞTİ"
    assert satirlar[1] == "Yükselen Üçgen - bandına dönüş"
    assert any(s.startswith("· dönüş sınırı 38,79 üstü") for s in satirlar)
    assert "× geçersiz" not in "\n".join(satirlar)
    assert "◈" not in "\n".join(satirlar) and "OB 1s" not in "\n".join(satirlar)


def test_gecersizlesmede_katilim_tek_satir_kalir():
    """Geçersizleşme gövdesi kısa kalır: katılım bölümünden en çok 2 satır gelir."""
    metin = notifier._format_lifecycle_alert_kart(_payload(
        state="KIRILIM_GECERSIZLESTI", domain_bolumleri={
            "hacim": ["katılım 1s destek yok", "katılım 1g 0,52 ile bitti",
                      "katılım 4s veri yok"]}))
    satirlar = _satirlar(metin)
    assert len([s for s in satirlar if s.startswith("katılım ")]) <= 2
    assert len(satirlar) <= notifier._KART_MAKS_SATIR


# ---------------------------------------------------------- güncelleme + süzgeç


def test_guncelleme_karti_kisa_ve_ayni_kadrajda():
    tam = _satirlar(notifier._format_lifecycle_alert_kart(_payload()))
    guncel = _satirlar(notifier._format_lifecycle_alert_kart(_payload(), guncelleme=True))
    assert len(guncel) < len(tam)
    assert any("değişiklik yok" in s for s in guncel)
    assert guncel[-1] == "• yatırım tavsiyesi değildir"
    assert not _tasma(guncel)


def test_suzgec_kapatilinca_eski_tam_kart_doner(monkeypatch):
    """Kill-switch: `TELEGRAM_KART_SUZGEC=0` → 25 Eyl biçimi (geri dönüş yolu)."""
    monkeypatch.setattr(notifier, "TELEGRAM_KART_SUZGEC", 0)
    eski = notifier._format_lifecycle_alert_kart(_payload(
        contraction=0.52, band_kaynak="zone", kalite=81,
        domain_bolumleri={"yapi": ["🏗 1s yapı: HH→LH ↓ / LL→HL ↓"],
                          "ust": ["▲ OB 1s 44,14-44,86 (▼) · %0"],
                          "hacim": ["katılım 1s destekliyor"]}))
    assert "◈" in eski or "▪" in eski
    assert "dönüş sınırı" not in eski


def test_suzgec_kapaliyken_de_patlamaz_veri_eksikse(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_KART_SUZGEC", 0)
    metin = notifier._format_lifecycle_alert_kart({"stock_name": "X", "timeframe": "1h",
                                                  "state": "KIRILIM_TEYITLI"})
    assert metin.strip()


@pytest.mark.parametrize("durum", ["KIRILIM_TEYITLI", "KIRILIM_GECERSIZLESTI"])
def test_eksik_alanlarla_da_uretilir(durum):
    metin = notifier._format_lifecycle_alert_kart({"stock_name": "THYAO", "timeframe": "4h",
                                                   "state": durum, "pattern_name": "Üçgen",
                                                   "break_dir": -1})
    satirlar = _satirlar(metin)
    assert satirlar[0].startswith(("▲", "▼")) and satirlar[-1].startswith("• ")
    assert not _tasma(satirlar)


# ---------------------------------------------------- sade dil sözleşmesi (Faz 3)

def _kart_metni(**ek):
    """7 bloklu sade kartı ölçüm bloğuyla üret (DM biçimi)."""
    payload = {
        "stock_name": "SISE", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
        "pattern_name": "Yükselen Üçgen", "break_dir": 1, "break_price": 39.26,
        "candle_close_price": 39.60, "confidence_score": 81, "break_strength": 100,
        "age_bars": 94, "band_baslangic": "2026-09-30T16:30:00+03:00",
        "retest_seen": False, "mtf_destek": True, "upper_now": 39.96,
        "bar_time": "2026-10-21T13:30:00+03:00",
        "bar_kapanis": "2026-10-21T17:30:00+03:00",
        "domain_bolumleri": {
            "engel": ["▲ direnç · boşluk 4s 41,90 +%5,8"],
            "yapi_ozet": ["◈ 4s yapı dış ve iç yukarı"],
            "hacim": ["katılım 4s hacim 0,45 kat"],
            "olcum": ["◇ 32321 formasyon · %76 tuttu",
                      "◇ tutunca ~1,05 TL · %2,6",
                      "◇ rol uyumlu %80 · 15724"],
        },
        "domain_karsi": ["iç yapı aşağı döndü"],
    }
    payload.update(ek)
    return notifier._format_lifecycle_alert_kart(payload)


#: Kart yüzeyinde yaşamayan kısaltmalar (kullanıcı: "herkesin anlayabileceği format").
KART_JARGON = ("ATR", "RVOL", "FVG", "BOS", "CHoCH", "OB ", " n1", "n1651", "bar ")


def test_kart_jargon_tasimaz():
    metin = _kart_metni()
    for kisa in KART_JARGON:
        assert kisa not in metin, (kisa, metin)


def test_kart_mum_dili_kullanir():
    """"bar" yerine "mum": aynı şey, herkesin bildiği sözcük."""
    assert "mum" in _kart_metni()
    assert "bant 94 bar" not in _kart_metni()


def test_kart_olcum_bloku_uc_satir_ve_dipnot():
    satirlar = _kart_metni().splitlines()
    olcum = [s for s in satirlar if s.startswith("◇")]
    assert len(olcum) == 3, olcum
    assert "· geçmiş davranış, kazanç değil" in satirlar


def test_kart_satir_butcesi_ve_satir_tavani():
    metin = _kart_metni()
    dolu = [s for s in metin.splitlines() if s.strip()]
    assert len(dolu) <= notifier._KART_MAKS_SATIR, len(dolu)
    for satir in dolu:
        assert tm.genislik(satir) <= notifier._kart_esik_px() + 0.1, satir
        assert satir == satir.lstrip(), f"girinti yok: {satir!r}"


# ------------------------------------------------- MS arızası kartı kirletmez

def test_ms_hatasi_kartta_gorunmez_ama_tasinir():
    """Karar D (2026-10-22): `⚠ MS domain devre dışı` YALNIZ /durum'da.

    Alarm kartı karar belgesidir; altyapı arızası (motor çöktü) oraya giremez.
    Bilgi kaybolmaz: `uyari` anahtarında taşınır, sayaç `/durum`da görünür.
    """
    import notification_context as nc

    outputs = {"4h": {"market_structure": {"error": "engine failed", "skipped": False,
                                           "export": None}}}
    bolumler = nc.domain_bolumleri(outputs, 100.0, stil="kart", alarm_tf="4h")
    # Boş bölümler sözlükten DÜŞER (`domain_bolumleri` süzerek döner).
    assert bolumler.get("yapi") in (None, [])
    assert bolumler["uyari"] == ["⚠️ Piyasa yapısı analizi tamamlanamadı"]
    kart = notifier._format_lifecycle_alert_kart(_payload(domain_bolumleri=bolumler))
    assert "tamamlanamadı" not in kart
    assert "MS" not in kart and "domain" not in kart.lower()


def test_ms_hata_sayaci_durum_satirina_yazilir():
    import main as main_module

    main_module._ms_hata_sayaci.update({"hisseler": set(), "son": ""})
    assert main_module._ms_hata_satiri() == ""  # hata yoksa sessiz
    bozuk = {"4h": {"market_structure": {"error": "engine failed", "skipped": False}}}
    main_module._ms_hata_kaydet(bozuk, "SISE")
    satir = main_module._ms_hata_satiri()
    assert satir.startswith("⚠️ MS (piyasa yapısı) motoru: 1 hissede hata")
    assert "engine failed" in satir
    # Aynı hissenin ikinci TF alarmı sayacı ŞİŞİRMEZ (hisse bazlı sayım).
    main_module._ms_hata_kaydet(bozuk, "SISE")
    assert main_module._ms_hata_sayaci["hisseler"] == {"SISE"}
    # Sağlıklı tur sayaca dokunmaz; ikinci hisse ayrı sayılır.
    main_module._ms_hata_kaydet({"4h": {"market_structure": {"error": None, "skipped": True}}},
                                "GARAN")
    main_module._ms_hata_kaydet(bozuk, "GARAN")
    assert "2 hissede" in main_module._ms_hata_satiri()
    main_module._ms_hata_sayaci.update({"hisseler": set(), "son": ""})
