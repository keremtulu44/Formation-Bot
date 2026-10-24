# -*- coding: utf-8 -*-
"""Evren genişletmesi (2026-10-22): endeksler, makro semboller, göreli güç.

Kullanıcı kararı: "endeksleri ekle — banka, xu30, xu50 … altın ve gümüş, USD".
Bu dosya eklenen sembollerin SAĞLAYICI eşlemesini, hacim davranışını, makro
alarm kapısını ve endekse göre göreli güç satırını doğrular.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
import main as main_module
import notifier
import notification_context as nc
import telegram_measure as tm


# --- 1) Sembol sınıfları ve sağlayıcı eşlemesi ------------------------------

@pytest.mark.parametrize("sembol,ticker", [
    ("XU50", "XU050.IS"),
    ("XU050", "XU050.IS"),
    ("XBANK", "XBANK.IS"),
    ("XUSIN", "XUSIN.IS"),
    ("USDTRY", "USDTRY=X"),
    ("ALTIN", "GC=F"),
    ("GUMUS", "SI=F"),
])
def test_saglayici_eslemesi_dogru(sembol, ticker):
    assert config.yahoo_ticker_for_symbol(sembol) == ticker
    # Eşleme yoksa `.IS` iki kez eklenirdi (USDTRY.IS gibi) — sessiz hata.
    assert not ticker.endswith(".IS.IS")


def test_evren_endeks_ve_makro_sembolleri_iceriyor():
    for sembol in ("XU50", "XBANK", "XUSIN", "USDTRY", "ALTIN", "GUMUS"):
        assert sembol in config.ACTIVE_STOCKS, sembol
    assert config.sembol_turu("XBANK") == "endeks"
    assert config.sembol_turu("ALTIN") == "makro"
    assert config.sembol_turu("THYAO") == "hisse"


def test_evren_ozeti_hisse_diye_saymaz():
    tam = config.evren_ozeti(["THYAO", "GARAN", "XU100", "XBANK", "ALTIN"])
    assert tam == "5 sembol (2 hisse + 2 endeks + 1 makro)"
    assert config.evren_ozeti(["THYAO", "GARAN"], ayrinti=False) == "2 sembol"


def test_ozet_satiri_283px_butcesine_sigar():
    # Ayrıntılı etiket özet satırında bölünüyordu; kısa hâli tek satır kalmalı.
    kisa = f"{config.evren_ozeti(ayrinti=False)} × 4 zaman dilimi"
    assert tm.genislik(kisa) <= notifier._kart_esik_px()
    assert tm.genislik(config.evren_ozeti()) > 0


# --- 2) Hacim: "veri yok" değil NEDEN --------------------------------------

def _hacim(sembol):
    bolumler = nc.domain_bolumleri({"4h": {"volume_participation": None}},
                                   100.0, stil="kart", alarm_tf="4h", sembol=sembol)
    return (bolumler.get("hacim") or [])


def test_endekste_hacim_nedeni_yazilir():
    satirlar = _hacim("XBANK")
    # İki kısa satır: tek satırda açıklama 466 px ölçülüyor ve bölünüyordu.
    assert satirlar == ["hacim: 4s yok (endeks)", "yön fiyattan okunur"]
    assert all(tm.genislik(s) <= notifier._kart_esik_px() for s in satirlar)


def test_makro_sembolde_hacim_nedeni_yazilir():
    satirlar = _hacim("ALTIN")
    assert satirlar == ["hacim: 4s yok (makro)", "yön fiyattan okunur"]


def test_hissede_hacim_nedeni_uydurulmaz():
    # Hisse için neden uydurulmaz: sağlayıcı hacim veriyor, boşsa gerçekten veri yok.
    assert _hacim("THYAO") == []


def test_hacim_aciklamasi_public_mesajinda_da_gorunur():
    n = notifier.TelegramNotifier()
    n.public_enabled = True
    n.public_chat_id = "-1001234567890"
    n.public_states = set(notifier.CONFIRMED_PUBLIC_STATES)
    kayit = {
        "stock_name": "XBANK", "timeframe": "4h", "pattern_name": "Yükselen Üçgen",
        "state": "KIRILIM_TEYITLI", "break_dir": 1, "break_price": 16000.0,
        "critical_price_level": 16000.0, "candle_close_price": 16120.0,
        "confidence_score": 84,
        "domain_bolumleri": {"hacim": ["hacim: 4s yok (endeks)",
                                       "yön fiyattan okunur"]},
    }
    metin = n.format_public_tekil(kayit)
    # Grup mesajı DM kartının aynısı: aynı satırlar, aynı sıra.
    assert metin == notifier._format_lifecycle_alert_kart(kayit)
    assert "hacim: 4s yok (endeks)" in metin and "yön fiyattan okunur" in metin


# --- 3) Makro alarm kapısı --------------------------------------------------

def test_makro_sembol_varsayilan_olarak_alarm_uretmez(monkeypatch):
    monkeypatch.setattr(config, "MAKRO_ALARM", False)
    assert main_module._alarm_izni_var("ALTIN") is False
    assert main_module._alarm_izni_var("USDTRY") is False
    # Endeks ve hisse normal yol (kullanıcı: "normal farksız").
    assert main_module._alarm_izni_var("XBANK") is True
    assert main_module._alarm_izni_var("THYAO") is True


def test_makro_alarm_bayragi_acilabilir(monkeypatch):
    monkeypatch.setattr(config, "MAKRO_ALARM", True)
    assert main_module._alarm_izni_var("ALTIN") is True


# --- 4) Endekse göre göreli güç --------------------------------------------

def _cerceve(getiriler, tz="Europe/Istanbul"):
    """Kapanış serisi verilen günlük yüzdelerle büyüsün."""
    fiyat = [100.0]
    for yuzde in getiriler:
        fiyat.append(fiyat[-1] * (1 + yuzde / 100.0))
    idx = pd.date_range("2026-08-01 10:00", periods=len(fiyat), freq="h", tz=tz)
    return pd.DataFrame({"open": fiyat, "high": fiyat, "low": fiyat,
                         "close": fiyat, "volume": 1000}, index=idx)


def test_goreli_guc_ayni_pencerede_puan_farki_verir():
    hisse = _cerceve([0.5] * 20)      # son 20 mumda +%10,4
    endeks = _cerceve([0.25] * 20)    # son 20 mumda +%5,1
    sonuc = main_module._endekse_gore_guc(hisse, endeks)
    assert sonuc is not None
    fark, adet = sonuc
    assert adet == 20
    assert fark == pytest.approx(5.1, abs=0.3)


def test_goreli_guc_yetersiz_veride_satir_basmaz():
    assert main_module._endekse_gore_guc(_cerceve([1] * 5), _cerceve([1] * 40)) is None
    assert main_module._endekse_gore_guc(None, _cerceve([1] * 40)) is None
    # Sıfır/negatif fiyat: bölme yok, satır yok.
    bozuk = _cerceve([1] * 25)
    bozuk.iloc[-21, bozuk.columns.get_loc("close")] = 0.0
    assert main_module._endekse_gore_guc(bozuk, _cerceve([1] * 25)) is None


def test_goreli_guc_endeks_serisini_hissenin_sonuna_hizalar():
    """Endeks daha ileri tarihliyse kesilir: farklı bitiş tarihleri kıyaslanmaz."""
    hisse = _cerceve([0.5] * 20)
    uzun = _cerceve([0.5] * 30)
    fark, _adet = main_module._endekse_gore_guc(hisse, uzun)
    assert fark == pytest.approx(0.0, abs=1e-9)


def test_goreli_guc_satiri_sade_ve_kisa():
    hisse = _cerceve([1.0] * 20)
    endeks = _cerceve([0.2] * 20)

    class SahteDeque:
        def to_dataframe(self, sembol):
            return endeks if sembol == "XU100" else None

    satir = main_module._goreli_guc_satiri("SISE", "1h", hisse, SahteDeque())
    assert satir.startswith("· 20 mum endekse ")
    assert satir.endswith(" puan")
    assert "puan" in satir            # birim: iki yüzdenin farkı yüzde değildir
    assert tm.genislik(satir) <= notifier._kart_esik_px()
    # Endeksin kendisine göre göreli güç hesaplanmaz (kendisiyle kıyas olurdu).
    assert main_module._goreli_guc_satiri("XU100", "1h", hisse, SahteDeque()) == ""
    # Endeks verisi yoksa satır yok.
    assert main_module._goreli_guc_satiri("SISE", "1h", hisse,
                                          type("D", (), {"to_dataframe": lambda s, x: None})()) == ""


# --- 5) Kart: satır tek yerde, sarma yok ------------------------------------

def _kart(goreli):
    return notifier._format_lifecycle_alert_kart({
        "stock_name": "SISE", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
        "state": "KIRILIM_TEYITLI", "break_dir": 1, "break_price": 39.26,
        "critical_price_level": 39.26, "candle_close_price": 39.60,
        "confidence_score": 81, "break_strength": 100, "age_bars": 94,
        "band_baslangic": "2026-09-30T16:30:00+03:00", "retest_seen": True,
        "mtf_destek": True, "upper_now": 39.96, "lower_now": 38.79,
        "bar_time": "2026-10-22T13:30:00+03:00",
        "bar_kapanis": "2026-10-22T17:30:00+03:00", "contraction": 0.82,
        "domain_bolumleri": {
            "yapi_ozet": ["◈ 1s yapı dış yukarı, iç yatay"],
            "hacim": ["hacim 1s hacim 1,4 kat"],
            "olcum": ["◇ 32321 formasyon · %76 tuttu"],
            "goreli": [goreli],
        },
        "domain_karsi": ["iç yapı aşağı döndü"],
    })


def test_goreli_satir_kartta_bir_kez_ve_sarmadan():
    metin = _kart("· 20 mumda endekse +1,1 puan")
    satirlar = metin.splitlines()
    assert sum(1 for s in satirlar if "endekse" in s) == 1
    assert not [s for s in satirlar if s.startswith("   ")], "girintili devam satırı yok"
    assert all(tm.genislik(s) <= notifier._kart_esik_px() for s in satirlar)
    assert sum(1 for s in satirlar if s.strip()) <= notifier._KART_MAKS_SATIR


def test_goreli_satir_gecersizlesme_kartinda_basilmaz():
    """Geri alma kartı "ne oldu"yu anlatır; göreli güç orada gürültüdür."""
    payload = {
        "stock_name": "SISE", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
        "state": "KIRILIM_GECERSIZLESTI", "break_dir": 1,
        "critical_price_level": 39.26, "candle_close_price": 39.60,
        "confidence_score": 81, "domain_bolumleri": {
            "goreli": ["· 20 mumda endekse +1,1 puan"]},
    }
    assert "endekse" not in notifier._format_lifecycle_alert_kart(payload)


# --- 6) Public kuyruk göreli satırı taşır -----------------------------------

def test_public_kuyruk_goreli_satirini_saklar():
    n = notifier.TelegramNotifier()
    n.public_enabled = True
    n.public_chat_id = "-1001234567890"
    n.public_states = set(notifier.CONFIRMED_PUBLIC_STATES)
    n._public_kuyruk = []
    n._public_alert_markers = {}
    kayit = {"stock_name": "SISE", "timeframe": "1h", "pattern_name": "Üçgen",
             "state": "KIRILIM_TEYITLI", "confidence_score": 81, "break_dir": 1,
             "formation_id": "f-1",
             "domain_bolumleri": {"goreli": ["· 20 mumda endekse +1,1 puan"]}}
    assert n.public_kuyruk(kayit) is True
    assert n._public_kuyruk[0]["domain_bolumleri"]["goreli"] == [
        "· 20 mumda endekse +1,1 puan"]
