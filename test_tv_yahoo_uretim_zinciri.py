# -*- coding: utf-8 -*-
"""Üretim veri zinciri: Yahoo birincil + tvDatafeed reaktif yedek (ağsız).

Bu testler GERÇEK Yahoo/TradingView çağrısı yapmaz. Sahte yfinance modülü ve
sahte `tvDatafeed` WS istemcisiyle zincirin her yönü sınanır:

* Yahoo başarılı → TV hiç çağrılmaz
* Yahoo boş / kalıcı hata / geçici hata → TV yedeği
* İkisi de başarısız → uydurma yok, UNKNOWN/fail-closed
* Makro sembol, kapalı şalter, geçersiz frame, zaman aşımı, WS kapanışı
* naive→UTC→İstanbul dönüşümü, gerçek 4s, cache birleşimi, /health, pinler
"""
from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

import pandas as pd
import pytest

import config as config_mod
import data.fetch as F
import scripts.tvdatafeed_client as TV
from data import (StockDequeManager, fetch_tv_4h, fetch_yfinance_1d,
                  fetch_yfinance_1h, fetch_yfinance_chart_data,
                  resample_all_timeframes, saglayici_durumu,
                  son_veri_kaynagi)

IST = "Europe/Istanbul"
KOK = Path(__file__).resolve().parent


def _cerceve(rows: int = 4, *, start="2026-11-02 07:00", freq="h",
             tz="UTC", kapanis=100.0, sembol_ekle=False):
    idx = pd.date_range(start, periods=rows, freq=freq, tz=tz)
    degerler = [kapanis + i for i in range(rows)]
    veri = {
        "Open": [float(v) for v in degerler],
        "High": [float(v) + 1 for v in degerler],
        "Low": [float(v) - 1 for v in degerler],
        "Close": [float(v) for v in degerler],
        "Volume": [1000] * rows,
    }
    if sembol_ekle:
        veri["Symbol"] = ["THYAO"] * rows
    return pd.DataFrame(veri, index=idx)


def _yfinance(monkeypatch, davranis):
    """davranis: 'valid' | 'empty' | hata mesajı | Exception nesnesi."""
    cagri = {"sayi": 0, "kwargs": []}

    class Ticker:
        def __init__(self, sembol):
            self.sembol = sembol
            cagri["sembol"] = sembol

        def history(self, **kwargs):
            cagri["sayi"] += 1
            cagri["kwargs"].append(kwargs)
            if davranis == "valid":
                return _cerceve(tz="Europe/Istanbul")
            if davranis == "empty":
                return pd.DataFrame()
            if isinstance(davranis, BaseException):
                raise davranis
            raise ValueError(str(davranis))

    monkeypatch.setitem(sys.modules, "yfinance",
                        types.SimpleNamespace(Ticker=Ticker))
    return cagri


def _tv_get_hist(monkeypatch, frame=None, hata=None, kayit=None):
    """Ortak istemciyi sahte get_hist ile değiştir (ağ/WS yok)."""
    if kayit is None:
        kayit = {"sayi": 0, "kwargs": []}

    def fake(**kwargs):
        kayit["sayi"] += 1
        kayit["kwargs"].append(kwargs)
        if hata is not None:
            raise hata
        return frame

    monkeypatch.setattr(TV, "get_hist", fake)
    monkeypatch.setattr(F, "TV_YEDEK_AKTIF", True)
    monkeypatch.setattr(F, "TV_GERCEK_4S_AKTIF", True)
    monkeypatch.setattr(F, "TV_ZAMAN_ASIMI_SN", 3.0)
    return kayit


@pytest.fixture(autouse=True)
def _durum_temiz(monkeypatch):
    """Her test kendi sayaçlarıyla başlasın; testler birbirini kirletmesin."""
    taze = {
        "yahoo_basari": 0, "yahoo_hata": 0,
        "tv_basari": 0, "tv_hata": 0, "yok": 0,
        "son_kaynak": None, "son_kaynak_by_symbol": {},
        "yahoo_son_basari": None, "yahoo_son_hata": None,
        "tv_son_basari": None, "tv_son_hata": None,
    }
    monkeypatch.setattr(F, "_SAGLAYICI_DURUM", taze)
    monkeypatch.setattr(F, "TV_YEDEK_AKTIF", False)  # varsayılan: testler ağsız
    return taze


# ------------------------------------------------------- 1) Yahoo birincil --
def test_yahoo_basariliyken_tv_hic_cagrilmaz(monkeypatch, _durum_temiz):
    yf = _yfinance(monkeypatch, "valid")
    tv = _tv_get_hist(monkeypatch, frame=_cerceve(),
                      hata=AssertionError("TV çağrılmamalı"))

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None and len(df) == 4
    assert df.attrs["veri_kaynagi"] == "yahoo"
    assert df.attrs["saglayici_zinciri"] == ["yahoo"]
    assert df.attrs["gercek_bar"] is False
    assert retryable is False and reason == ""
    assert yf["sayi"] == 1 and yf["kwargs"][0]["auto_adjust"] is False
    assert tv["sayi"] == 0
    assert _durum_temiz["yahoo_basari"] == 1
    assert son_veri_kaynagi("THYAO") == "yahoo"


def test_yahoo_1d_basariliyken_tv_yok(monkeypatch):
    _yfinance(monkeypatch, "valid")
    tv = _tv_get_hist(monkeypatch, hata=AssertionError("TV çağrılmamalı"))

    df = fetch_yfinance_1d("THYAO")

    assert df is not None
    assert df.attrs["veri_kaynagi"] == "yahoo"
    assert tv["sayi"] == 0


# --------------------------------------------------------- 2) TV'ye geçiş --
def test_yahoo_bos_donerse_tv_yedegi_kullanilir(monkeypatch, _durum_temiz):
    _yfinance(monkeypatch, "empty")
    tv = _tv_get_hist(monkeypatch, frame=_cerceve(sembol_ekle=True))

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None and len(df) == 4
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert str(df.index.tz) == IST
    assert df.attrs["veri_kaynagi"] == "tvdatafeed"
    assert df.attrs["saglayici_zinciri"] == ["yahoo", "tvdatafeed"]
    assert df.attrs["gercek_bar"] is True
    assert df.attrs["provider_fallback"] is True
    assert retryable is False
    assert tv["sayi"] == 1
    assert tv["kwargs"][0]["exchange"] == "BIST"
    assert tv["kwargs"][0]["interval"] == "in_1_hour"
    assert _durum_temiz["tv_basari"] == 1
    assert son_veri_kaynagi("THYAO") == "tvdatafeed"


def test_yahoo_kalici_hatada_tv_gecer_ve_retryable_degil(monkeypatch):
    _yfinance(monkeypatch, "possibly delisted; no price data found")
    _tv_get_hist(monkeypatch, frame=_cerceve())

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None
    assert df.attrs["veri_kaynagi"] == "tvdatafeed"
    assert retryable is False


def test_yahoo_gecici_hatada_tv_kurtarirsa_yeniden_deneme_gerekmez(monkeypatch):
    _yfinance(monkeypatch, TimeoutError("read timed out"))
    tv = _tv_get_hist(monkeypatch, frame=_cerceve())

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None and retryable is False
    assert tv["sayi"] == 1


def test_yahoo_gecici_hata_ve_tv_yoksa_retryable_korunur(monkeypatch):
    _yfinance(monkeypatch, TimeoutError("read timed out"))
    _tv_get_hist(monkeypatch,
                 hata=ModuleNotFoundError("tvDatafeed kurulu değil"))

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is None
    assert retryable is True                 # mevcut tek-retry sözleşmesi
    assert "timed out" in reason            # Yahoo gerekçesi silinmedi
    assert "tv:" in reason and "tvDatafeed kurulu değil" in reason


def test_1d_ve_grafik_yollari_da_tv_yedegine_duser(monkeypatch):
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=_cerceve(rows=5, freq="D"))

    gunluk = fetch_yfinance_1d("GARAN")
    grafik, retryable, _ = fetch_yfinance_chart_data(
        "GARAN", "1d", "2y")

    assert gunluk is not None and gunluk.attrs["veri_kaynagi"] == "tvdatafeed"
    assert grafik is not None and grafik.attrs["veri_kaynagi"] == "tvdatafeed"
    assert retryable is False


def test_grafik_validator_tv_serisini_de_reddedebilir(monkeypatch):
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=_cerceve())

    frame, retryable, reason = fetch_yfinance_chart_data(
        "THYAO", "1h", "60d",
        frame_validator=lambda df: (False, "bayat seri"))

    assert frame is None
    assert "bayat seri" in reason
    assert son_veri_kaynagi("THYAO") is None


# --------------------------------------------- 3) Fail-closed / kısıtlar ----
def test_ikisi_de_basarisizsa_uydurma_yok(monkeypatch, _durum_temiz):
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, hata=ConnectionError("WS kapandı"))

    df, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is None
    assert retryable is False
    assert "WS kapandı" in reason
    assert _durum_temiz["yok"] == 1
    assert son_veri_kaynagi("THYAO") is None
    durum = saglayici_durumu()
    assert durum["yahoo_son_hata"] and durum["tv_son_hata"]
    assert durum["son_kaynak"] is None


@pytest.mark.parametrize("kirik", [
    None,
    pd.DataFrame(),
    pd.DataFrame({"Close": [1.0]}, index=pd.date_range(
        "2026-11-02", periods=1, freq="h", tz="UTC")),
    pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0],
                  "close": [1.0], "volume": [1.0]}, index=[1, 2]),
    "string-cevap",
])
def test_tv_gecersiz_yaniti_sessizce_kabul_edilmez(monkeypatch, kirik):
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=kirik)

    df, _retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is None
    assert "tv:" in reason


def test_makro_sembolde_tv_denmez(monkeypatch):
    _yfinance(monkeypatch, "empty")
    tv = _tv_get_hist(monkeypatch, hata=AssertionError("TV çağrılmamalı"))

    df, _retryable, reason = fetch_yfinance_1h("XAUUSD", with_status=True)

    assert df is None
    assert tv["sayi"] == 0
    assert "makro atlandı" in reason


def test_tv_yedegi_kapaliysa_yahoo_only(monkeypatch):
    _yfinance(monkeypatch, "empty")
    tv = _tv_get_hist(monkeypatch, hata=AssertionError("TV çağrılmamalı"))
    monkeypatch.setattr(F, "TV_YEDEK_AKTIF", False)

    df, _retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is None
    assert tv["sayi"] == 0
    assert "TV yedeği kapalı" in reason


def test_tv_zaman_asimi_tarami_bloke_etmez(monkeypatch):
    _yfinance(monkeypatch, "empty")

    def yavas(**kwargs):
        time.sleep(5)
        return _cerceve()

    monkeypatch.setattr(TV, "get_hist", yavas)
    monkeypatch.setattr(F, "TV_YEDEK_AKTIF", True)
    monkeypatch.setattr(F, "TV_ZAMAN_ASIMI_SN", 0.2)

    bas = time.monotonic()
    df, _retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)
    gecen = time.monotonic() - bas

    assert df is None
    assert "zaman aşımı" in reason
    assert gecen < 2.0


# --------------------------------------------- 4) Zaman / WS / gerçek 4s ---
def test_naive_tv_damgasi_uretimde_reddedilir_ve_tz_bozulmaz(
        monkeypatch, istanbul_tz):
    """Ortak istemci naive→UTC yapar; üretim hattı naive görürse uydurmaz."""
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=_cerceve(rows=2, tz=None,
                                             start="2026-11-02 10:00"))
    once = os.environ.get("TZ")

    df, _retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is None
    assert "naive zaman damgası reddedildi" in reason
    assert os.environ.get("TZ") == once    # süreç TZ'si DEĞİŞMEDİ


def test_utc_aware_tv_damgasi_istanbula_cevrilir(monkeypatch):
    """tvDatafeed_client'ın tz-aware UTC çıktısı üretimde İstanbul'a iner."""
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=_cerceve(
        rows=2, tz="UTC", start="2026-11-02 07:00"))

    df, _retryable, _reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None
    assert str(df.index.tz) == IST
    assert df.index[0].hour == 10          # 07:00 UTC → 10:00 TSİ


def test_tv_ws_her_cagrida_kapanir(monkeypatch):
    """Ortak istemcinin gerçek kodu (sahte modülle) WS'i finally'de kapatır."""
    _yfinance(monkeypatch, "empty")
    istemciler = []

    class WS:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakeTv:
        def __init__(self):
            self.ws = WS()
            istemciler.append(self)

        def get_hist(self, **kwargs):
            return _cerceve(sembol_ekle=True)

    def fake_version(ad):
        if ad == "tradingview-datafeed":
            return "2.1.1"
        raise TV._metadata.PackageNotFoundError(ad)

    monkeypatch.setattr(TV._metadata, "version", fake_version)
    monkeypatch.setitem(sys.modules, "tvDatafeed", types.SimpleNamespace(
        TvDatafeed=FakeTv,
        Interval=types.SimpleNamespace(in_1_hour="1H", in_4_hour="4H",
                                       in_daily="1D"),
    ))
    monkeypatch.setattr(F, "TV_YEDEK_AKTIF", True)

    df, _retryable, _reason = fetch_yfinance_1h("THYAO", with_status=True)

    assert df is not None
    assert len(istemciler) >= 1
    assert all(i.ws.closed for i in istemciler)


def test_gercek_4s_turetilmis_4s_in_yerine_gecer(monkeypatch):
    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, frame=_cerceve())

    df_1h, _r, _n = fetch_yfinance_1h("THYAO", with_status=True)
    native = fetch_tv_4h("THYAO")

    assert native is not None
    assert native.attrs["gercek_4h"] is True
    tfs = resample_all_timeframes(df_1h, df_4h_native=native)
    assert tfs["4h"] is not df_1h
    assert tfs["4h"].attrs["veri_kaynagi"] == "tvdatafeed"
    assert tfs["4h"].attrs["gercek_bar"] is True
    assert len(tfs["4h"]) == len(native)
    assert "2h" in tfs and "1d" in tfs and "1h" in tfs


def test_gecersiz_native_4s_turetime_geri_duser():
    df_1h = _cerceve(rows=12, tz=IST)

    tfs = resample_all_timeframes(df_1h, df_4h_native=pd.DataFrame())
    tfs2 = resample_all_timeframes(df_1h)

    assert len(tfs["4h"]) == len(tfs2["4h"])
    assert "veri_kaynagi" not in tfs["4h"].attrs


def test_gercek_4s_kapaliysa_ek_tv_cagrisi_yok(monkeypatch, _durum_temiz):
    _yfinance(monkeypatch, "empty")
    tv = _tv_get_hist(monkeypatch, frame=_cerceve())
    monkeypatch.setattr(F, "TV_GERCEK_4S_AKTIF", False)

    fetch_yfinance_1h("THYAO", with_status=True)
    ilk_sayi = tv["sayi"]

    assert fetch_tv_4h("THYAO") is None
    assert tv["sayi"] == ilk_sayi


# ------------------------------------------- 5) Tarama (scan) katmanı -------
def test_scan_yahoo_basariliyken_ek_tv_cagrisi_yok(monkeypatch):
    import bot.scan as S
    import main

    cagrilar = []
    monkeypatch.setattr(S, "TV_GERCEK_4S_AKTIF", True)
    monkeypatch.setattr(main, "son_veri_kaynagi", lambda _s: "yahoo")
    monkeypatch.setattr(main, "fetch_tv_4h",
                        lambda _s: pytest.fail("Yahoo varken TV çağrılmamalı"))

    def sahte_resample(frame, **kwargs):
        cagrilar.append(kwargs)
        return {"1h": frame}

    monkeypatch.setattr(main, "resample_all_timeframes", sahte_resample)
    df_1h = _cerceve(tz=IST)

    tfs = S._zaman_dilimlerini_hazirla("THYAO", df_1h)

    assert tfs["1h"] is df_1h
    assert cagrilar == [{}]                # df_4h_native gönderilmedi


def test_scan_tv_yedeginde_gercek_4s_kullanilir(monkeypatch):
    import bot.scan as S
    import main

    native = _cerceve(rows=3, tz=IST)
    kayit = {"tv": 0, "kw": []}
    monkeypatch.setattr(S, "TV_GERCEK_4S_AKTIF", True)
    monkeypatch.setattr(main, "son_veri_kaynagi", lambda _s: "tvdatafeed")

    def sahte_tv(_sembol):
        kayit["tv"] += 1
        return native

    def sahte_resample(frame, df_4h_native=None):
        kayit["kw"].append(df_4h_native)
        return {"4h": df_4h_native if df_4h_native is not None else frame}

    monkeypatch.setattr(main, "fetch_tv_4h", sahte_tv)
    monkeypatch.setattr(main, "resample_all_timeframes", sahte_resample)

    tfs = S._zaman_dilimlerini_hazirla("THYAO", _cerceve(tz=IST))

    assert kayit["tv"] == 1
    assert kayit["kw"] == [native]
    assert tfs["4h"] is native


def test_scan_tv_4h_hatasinda_turetilmis_yol_korunur(monkeypatch):
    import bot.scan as S
    import main

    kayit = {"kw": []}
    monkeypatch.setattr(S, "TV_GERCEK_4S_AKTIF", True)
    monkeypatch.setattr(main, "son_veri_kaynagi", lambda _s: "tvdatafeed")

    def patlak(_sembol):
        raise ConnectionError("WS kapandı")

    def sahte_resample(frame, df_4h_native=None):
        kayit["kw"].append(df_4h_native)
        return {"4h": "turetilmis"}

    monkeypatch.setattr(main, "fetch_tv_4h", patlak)
    monkeypatch.setattr(main, "resample_all_timeframes", sahte_resample)

    tfs = S._zaman_dilimlerini_hazirla("THYAO", _cerceve(tz=IST))

    assert tfs["4h"] == "turetilmis"
    assert kayit["kw"] == [None]


def test_scan_gercek_4s_kapaliysa_tv_cagrilmaz(monkeypatch):
    import bot.scan as S
    import main

    monkeypatch.setattr(S, "TV_GERCEK_4S_AKTIF", False)
    monkeypatch.setattr(main, "son_veri_kaynagi", lambda _s: "tvdatafeed")
    monkeypatch.setattr(main, "fetch_tv_4h",
                        lambda _s: pytest.fail("kapalı şalterde TV yok"))
    monkeypatch.setattr(main, "resample_all_timeframes",
                        lambda frame, **_kw: {"1h": frame, "4h": "turetilmis"})

    tfs = S._zaman_dilimlerini_hazirla("THYAO", _cerceve(tz=IST))
    assert tfs["4h"] == "turetilmis"


# ---------------------------------------------- 6) Cache / health / pinler --
def test_karisik_kaynakli_append_tekillesir_ve_siralanir(tmp_path):
    yahoo = _cerceve(rows=3, start="2026-11-02 07:00", tz=IST)
    tv = _cerceve(rows=3, start="2026-11-02 09:00", tz=IST, kapanis=200.0)
    yahoo.index = yahoo.index.tz_convert(IST)
    tv.index = tv.index.tz_convert(IST)
    yahoo.columns = [c.lower() for c in yahoo.columns]
    tv.columns = [c.lower() for c in tv.columns]

    yonetici = StockDequeManager(maxlen=100, data_dir=str(tmp_path / "cache"))
    assert yonetici.append_dataframe("THYAO", yahoo)
    assert yonetici.append_dataframe("THYAO", tv)

    birlesik = yonetici.to_dataframe("THYAO")
    assert birlesik is not None
    assert birlesik.index.is_monotonic_increasing
    assert birlesik.index.is_unique                 # 09:00 çakışması tek bar
    assert len(birlesik) == 5                      # 07,08,09,10,11
    assert float(birlesik.loc[pd.Timestamp("2026-11-02 09:00", tz=IST),
                              "close"]) == 200.0  # TV (son gelen) kazandı


def test_health_veri_saglayicilari_alanini_raporlar(monkeypatch):
    import main as main_mod

    ozet = main_mod._saglik_ozeti()
    assert "veri_saglayicilari" in ozet
    saglayici = ozet["veri_saglayicilari"]
    for anahtar in ("tv_aktif", "tv_kurulu", "tv_dagitim", "yahoo_birincil",
                    "yahoo_basari", "tv_basari", "yok", "son_kaynak"):
        assert anahtar in saglayici
    assert isinstance(saglayici["son_kaynak_by_symbol"], dict)


def test_tv_kurulum_bilgisi_dogrulanmis_surumu_tanir(monkeypatch):
    def fake_version(ad):
        if ad == "tradingview-datafeed":
            return "2.1.1"
        raise F._metadata.PackageNotFoundError(ad)

    monkeypatch.setattr(F._metadata, "version", fake_version)
    assert saglayici_durumu()["tv_kurulu"] is True
    assert saglayici_durumu()["tv_dagitim"] == "tradingview-datafeed==2.1.1"

    def kotu_version(ad):
        if ad == "tradingview-datafeed":
            return "9.9.9"
        raise F._metadata.PackageNotFoundError(ad)

    monkeypatch.setattr(F._metadata, "version", kotu_version)
    assert saglayici_durumu()["tv_kurulu"] is False


def test_config_bayrak_yorumlayicisi_env_e_bagli(monkeypatch):
    for deger in ("0", "false", "off", "no", "kapalı", "HAYIR"):
        monkeypatch.setenv("FB_TEST_BAYRAK", deger)
        assert config_mod._env_bayrak("FB_TEST_BAYRAK") is False
    for deger in ("1", "true", "evet", "Açık"):
        monkeypatch.setenv("FB_TEST_BAYRAK", deger)
        assert config_mod._env_bayrak("FB_TEST_BAYRAK") is True


def test_strict_health_yeni_veri_alaniyla_birlikte_bayatligi_korur(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "is_bist_open", lambda _now: True)
    monkeypatch.setattr(main_mod, "_heartbeat_yasi_sn", lambda _now: 4000)
    monkeypatch.setattr(main_mod._live_state, "status",
                        lambda: {"tarama_suruyor": False})

    ozet = main_mod._saglik_ozeti()

    assert ozet["heartbeat_stale"] is True       # ?strict=1 → 503 kapısı korundu
    assert ozet["heartbeat_stale_esik_s"] == 1800
    assert "veri_saglayicilari" in ozet
    assert ozet["veri_saglayicilari"]["yahoo_birincil"] is True


def test_ikisi_de_yokken_veri_yok_modu_kapisi_acik_kalir(monkeypatch):
    import data.replay as R
    from data import veri_yok_modu_acik_mi

    _yfinance(monkeypatch, "empty")
    _tv_get_hist(monkeypatch, hata=ConnectionError("WS yok"))
    df, _retryable, _reason = fetch_yfinance_1h("THYAO", with_status=True)
    assert df is None

    simdi = pd.Timestamp("2026-11-18 12:00", tz=IST).to_pydatetime()
    monkeypatch.setattr(R, "tarama_penceresi_acik_mi", lambda _now: True)
    monkeypatch.setattr(R, "bist_tatil_adi", lambda _now: None)

    assert veri_yok_modu_acik_mi(simdi, son_bar_yasi_dk=21 * 60) is True
    assert veri_yok_modu_acik_mi(simdi, son_bar_yasi_dk=30) is False


def test_strict_unknown_kilavuzu_hala_gecerli():
    metin = (KOK / "docs/arastirma/CAPRAZ_PIYASA_UYGULAMA.md").read_text(
        encoding="utf-8")
    assert "STRICT_UNKNOWN" in metin
    assert "--availability" in metin
    assert "strict_unknown" in metin.lower()
    assert "tamamlanmış sayılmaz" in metin.lower()


def test_deploy_ve_replay_pinleri_tv_yedegini_icerir():
    for ad in ("requirements.txt", "requirements-deploy.txt"):
        metin = (KOK / ad).read_text(encoding="utf-8")
        assert "tradingview-datafeed==2.1.1" in metin
        assert "websocket-client==1.9.2" in metin


def test_env_orneginde_tv_anahtarlari_var():
    metin = (KOK / ".env.example").read_text(encoding="utf-8")
    for anahtar in ("TV_YEDEK_AKTIF", "TV_GERCEK_4S_AKTIF", "TV_EXCHANGE",
                    "TV_BAR_SAYISI", "TV_ZAMAN_ASIMI_SN"):
        assert f"\n{anahtar}=" in metin


def test_render_blueprint_tv_bayraklarini_tasir():
    metin = (KOK / "render.yaml").read_text(encoding="utf-8")
    assert "TV_YEDEK_AKTIF" in metin
    assert "TV_GERCEK_4S_AKTIF" in metin
    assert "buildCommand: bash scripts/install_deploy_dependencies.sh" in metin


def test_installer_ve_ci_ayni_deploy_pinlerini_kurar():
    installer = (KOK / "scripts/install_deploy_dependencies.sh").read_text(
        encoding="utf-8")
    workflow = (KOK / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    ortak = "bash scripts/install_deploy_dependencies.sh"
    assert f"run: {ortak}" in workflow
    assert "-r requirements-deploy.txt" in installer
    assert "pip check" in installer
    assert "requirements-deploy.txt" in workflow   # pip cache dependency path


def test_ortak_tv_istemcisi_uretim_kullanimini_belgeler():
    metin = (KOK / "scripts/tvdatafeed_client.py").read_text(encoding="utf-8")
    assert "Üretim canlı fetch hattı bu modülü kullanmaz" not in metin
    assert "üretim `data/fetch.py` da bu modülü kullanır" in metin
    assert "DENEME_SINIRI = 2" in metin
