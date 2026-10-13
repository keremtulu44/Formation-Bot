"""G0 — kullanıcıya dönük sayı metninde tek standart: Türkçe virgül.

Neden bu dosya var: ayraç yüzeyler arasında ayrışmıştı — kart `_price()` virgül
basıyordu, `/durum`, `/formasyonlar`, panel, legacy alarm gövdesi ve backtest
raporu nokta basıyordu; aynı fiyat iki görünümde okunuyordu (ve grafik katmanı da
hangisini kullanacağını bilemeyecekti). Kural tek noktada tutulur:
`reporting.format.sayi()`.

Bilinçli tercihler (GRAFIK_TASARIM.md §15/§19):
  * binlik ayracı YOK — sayaçlar (`360 bar`) ve telefon satır bütçesi
    (≤283 px) bundan etkilenmesin diye;
  * sondaki sıfırlar kırpılmaz — `50,00` bilgi kaybı olmadan `50,00` kalır;
  * NaN/inf/None kullanıcı metninde hiç görünmez, `varsayilan`a düşer.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import analytics.backtest as backtest
import notification_context as context_mod
import notifier as notifier_mod
from notifier import TelegramNotifier
from reporting.format import gecen_sure, sayi

# Kullanıcıya dönük metinde nokta ondalık kalmamalı (tarihler `13 Eki 19:30`).
_NOKTA_ONDALIK = re.compile(r"\d+\.\d+")


def test_sayi_turkce_ondalik_kullanir():
    assert sayi(46.37) == "46,37"
    assert sayi(46.37, 1) == "46,4"


def test_sayi_sondaki_sifirlari_kirpmaz():
    assert sayi(50.0) == "50,00"
    assert sayi(0.0) == "0,00"


def test_sayi_binlik_ayraci_eklemez():
    assert sayi(1234567.5) == "1234567,50"


def test_sayi_gecersiz_degerde_varsayilana_doner():
    for bozuk in (None, "", "abc", float("nan"), float("inf")):
        assert sayi(bozuk) == "—"
        assert sayi(bozuk, 2, varsayilan="") == ""


def test_sayi_metni_geri_sayiya_cevrilebilir():
    # Virgül standartlaştırılırken biçimlenmiş metnin geri okunması gerekmiyor;
    # bu test yalnız ayracın tek karakter olduğunu sabitler.
    assert sayi(46.37).count(".") == 0
    assert sayi(46.37).count(",") == 1


def test_gecen_sure_virgul_kullanir():
    zaman = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=30)).isoformat()
    metin = gecen_sure(zaman)
    assert metin.endswith("sa önce") and "3,5" in metin
    assert not _NOKTA_ONDALIK.search(metin)


def test_notifier_fiyat_metinleri_virgulde():
    assert notifier_mod._format_price(70.945) == "70,94"
    assert notifier_mod._format_price_tl(70.945) == "70,94 TL"
    assert notifier_mod._sayı(46.37) == "46,37"
    # Geçersiz değer metin üretmez (boşluk -> satır zaten basılmaz).
    assert notifier_mod._format_price(None) == ""
    assert notifier_mod._format_price(float("nan")) == ""


def test_legacy_alarm_govdesi_virgul_basar():
    veri = {
        "stock_name": "THYAO", "timeframe": "1h",
        "pattern_name": "Yükselen Üçgen", "state": "KIRILIM_ADAYI",
        "confidence_score": 85, "critical_price_level": 300.0,
        "upper_now": 302.0, "lower_now": 295.0, "contraction": 0.75,
        "timestamp": datetime.now(), "break_dir": 1, "break_strength": 80,
        "break_price": 302.0,
    }
    mesaj = TelegramNotifier().format_message(veri)
    assert "302,00" in mesaj and "302.00" not in mesaj
    assert not _NOKTA_ONDALIK.search(mesaj)


def test_kart_bolumleri_virgul_kullanir():
    # Kart zaten virgül basıyordu; G0 bunu `sayi()`ne bağladı → çıktı aynı kalmalı.
    assert context_mod._price(46.37) == sayi(46.37)
    assert context_mod._price(None) == ""
    sonuclar = {"1h": {"order_block": {"export": {"bull": {
        "state": 1.0, "top": 302.0, "bottom": 295.0, "fill": 0.4}}}}}
    satirlar = context_mod._format_order_blocks(sonuclar, reference_price=290.0)
    assert satirlar, "sentetik export için OB satırı üretilmedi"
    assert "295,00–302,00 TL" in satirlar[0]
    assert not any(_NOKTA_ONDALIK.search(s) for s in satirlar)


def test_backtest_raporu_virgul_kullanir_kirpmayi_surdurur():
    assert backtest._s(46.0) == "46"          # sondaki sıfırlar kırpılıyor
    assert backtest._s(46.25) == "46,25"
    assert backtest._s(-1.25, yuzde=True) == "-1,2%"
    assert backtest._s(None) == "—"
    assert not _NOKTA_ONDALIK.search(backtest._s(46.25, birim=" TL"))


def test_yardimcilar_ayni_kurali_uretiyor():
    # Üç yüzey de (notifier, kart bağlamı, reporting) tek noktaya bağlı olmalı.
    for deger in (46.37, 0.5, 1234.567, 70.945):
        assert notifier_mod._sayı(deger) == sayi(deger)
        assert context_mod._price(deger) == sayi(deger)
