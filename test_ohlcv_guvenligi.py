"""Aşama 4 — OHLCV giriş güvenliği testleri.

Tek doğrulama sınırı: `data.ohlcv_girdi_sorunlari` + `StockDequeManager.append_*`
kapısı. Bu dosya görev spec'indeki 20 senaryoyu kapsar:
  1-12  : validator matrisi (geçerli/boş/eksik sütun/NaN/Inf/geometry/fiyat/hacim/ts)
  13    : kapanmamış mum → kapıdan geçer ama `tamamlanmis_mumlar` analizden eler
  14-16 : eski veri politikaları (mevcut testlere ince eşleme + doğrudan sınır assertleri)
  17    : karışık sembol (geçerli + geçersiz) taramada birbirini durdurmaz
  18    : geçersiz yeni veri mevcut geçerli cache'i bozmaz
  19-20 : geçersiz veri formation/domain motorlarına ulaşmaz
Gerçek ağ çağrısı yoktur; fetch sahtedir, disk izolesi tmp_path'dir.
"""

import math
from datetime import datetime, timedelta

import pandas as pd
import pytest

import config
import main as main_module
from data import ohlcv_girdi_sorunlari, tamamlanmis_mumlar, StockDequeManager
from patterns import PatternLifecycleManager

from test_live_data_flow import (  # sahte scaffolding yeniden kullanılır
    FakeDeferredAlerts,
    FakeLiveState,
    FakeNotifier,
    FakePacer,
    MISSING_20,
    sentetik_1h,
    sifirla_daily_stats,
    temel_monkeypatch,
)

IST = config.ISTANBUL_TZ


def gecerli_frame(n=55, end=None, base=100.0):
    return sentetik_1h(n, end or datetime.now(IST) - timedelta(minutes=100), base=base)


def bozuk_frame(degistirici):
    df = gecerli_frame()
    degistirici(df)
    return df


# ------------------------------------------------------- 1-12: validator matrisi
def test_01_gecerli_frame_sorunsuzdur():
    assert ohlcv_girdi_sorunlari(gecerli_frame()) == []


def test_02_bos_frame_reddedilir():
    assert ohlcv_girdi_sorunlari(pd.DataFrame()) == ["bos_frame"]
    assert ohlcv_girdi_sorunlari(None) == ["bos_frame"]


def test_03_eksik_sutun_reddedilir():
    df = gecerli_frame().drop(columns=["volume"])
    assert ohlcv_girdi_sorunlari(df) == ["eksik_sutun:volume"]


def test_04_nan_ohlcv_reddedilir():
    df = bozuk_frame(lambda d: d.__setitem__("close", d["close"])).copy()
    df.loc[df.index[3], "close"] = float("nan")
    assert "nan_deger" in ohlcv_girdi_sorunlari(df)


def test_05_sonsuz_deger_reddedilir():
    df = gecerli_frame()
    df.loc[df.index[2], "high"] = float("inf")
    df.loc[df.index[5], "volume"] = float("-inf")
    assert "sonsuza_deger" in ohlcv_girdi_sorunlari(df)


def test_06_high_lt_low_reddedilir():
    df = gecerli_frame()
    df.loc[df.index[4], "high"], df.loc[df.index[4], "low"] = (
        df.loc[df.index[4], "low"],
        df.loc[df.index[4], "high"],
    )
    assert "high_lt_low" in ohlcv_girdi_sorunlari(df)


def test_07_high_open_close_altinda_reddedilir():
    df = gecerli_frame()
    row = df.index[6]
    df.loc[row, "high"] = min(df.loc[row, "open"], df.loc[row, "close"]) - 0.5
    assert "high_tutarsiz" in ohlcv_girdi_sorunlari(df)


def test_08_low_open_close_ustunde_reddedilir():
    df = gecerli_frame()
    row = df.index[6]
    df.loc[row, "low"] = max(df.loc[row, "open"], df.loc[row, "close"]) + 0.5
    assert "low_tutarsiz" in ohlcv_girdi_sorunlari(df)


def test_09_sifir_veya_negatif_fiyat_reddedilir():
    sifir = gecerli_frame()
    sifir.loc[sifir.index[1], "close"] = 0.0
    assert "gecersiz_fiyat" in ohlcv_girdi_sorunlari(sifir)
    negatif = gecerli_frame()
    negatif.loc[negatif.index[1], "low"] = -1.0
    assert "gecersiz_fiyat" in ohlcv_girdi_sorunlari(negatif)


def test_10_negatif_hacim_reddedilir_sifir_hacim_gecerlidir():
    negatif = gecerli_frame()
    negatif.loc[negatif.index[1], "volume"] = -5.0
    assert "negatif_hacim" in ohlcv_girdi_sorunlari(negatif)
    sifir = gecerli_frame()
    sifir["volume"] = 0.0  # BIST ilk bar sözleşmesi: sıfır hacim geçerli
    assert ohlcv_girdi_sorunlari(sifir) == []


def test_11_duplicate_timestamp_kabul_idempotent():
    mgr = StockDequeManager(data_dir="/tmp/fb_ohlcv_test11")
    df = gecerli_frame(60)
    assert mgr.append_dataframe("THYAO", df) is True
    ilk_uzunluk = len(mgr.to_dataframe("THYAO"))
    row = df.index[-1]
    df.loc[row, "close"] = 999.0                    # aynı ts, yeni değer
    df.loc[row, "high"] = 999.2                     # geometri tutarlı kalsın
    assert mgr.append_dataframe("THYAO", df) is True
    birlesik = mgr.to_dataframe("THYAO")
    assert len(birlesik) == ilk_uzunluk          # çoğalma yok
    assert float(birlesik["close"].iloc[-1]) == 999.0  # son yazan kazanır


def test_12_sirasisiz_timestamp_kabul_siralanir():
    mgr = StockDequeManager(data_dir="/tmp/fb_ohlcv_test12")
    df = gecerli_frame(60).sort_index(ascending=False)  # ters sıralı gelir
    assert ohlcv_girdi_sorunlari(df) == []
    assert mgr.append_dataframe("THYAO", df) is True
    idx = mgr.to_dataframe("THYAO").index
    assert idx.is_monotonic_increasing


def test_13_kapanmamis_mum_kapidan_gecer_analizden_elernir():
    """Tek kapı ilkesi: append tamlık kontrolü yapmaz; analiz katmanı eler."""
    simdi = datetime.now(IST)
    df = gecerli_frame(55, end=simdi - timedelta(minutes=10))  # son mum henüz kapanmadı
    assert ohlcv_girdi_sorunlari(df) == []                     # kapı reddetmez
    mgr = StockDequeManager(data_dir="/tmp/fb_ohlcv_test13")
    mgr.append_dataframe("THYAO", df)
    ham = mgr.to_dataframe("THYAO")
    tam = tamamlanmis_mumlar(ham, "1h", simdi)
    assert len(tam) < len(ham)                                 # yarım mum elendi
    assert tam.index[-1] <= pd.Timestamp(simdi - timedelta(minutes=30))


def test_14_15_eski_veri_politikasi_sinirlari_degismedi():
    """Seans içi 120 dk / seans dışı 14 gün kuralları validator ile gevşetilmedi."""
    f = main_module._cache_verisi_kullanilabilir
    assert f(180, False, True) is False            # 14: seans içi eski cache → analiz dışı
    assert f(13 * 24 * 60, False, False) is True   # 15: seans dışı 13 gün kabul
    assert f(15 * 24 * 60, False, False) is False  # 15: 14 gün üst sınır


# ------------------------------------------------- 17-20: tarama entegrasyonu
def test_17_karisik_sembol_gecerli_olan_analiz_edilir(tmp_path, monkeypatch):
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    gecerli = gecerli_frame(60)

    def sahte_1h(stock, period):
        if stock == "BAD":
            return (gecerli_frame(60).assign(close=float("nan")), False, "")
        return (gecerli.copy(), False, "")

    temel_monkeypatch(monkeypatch, live_state, [], sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)
    result = main_module.scan_all_stocks(
        mgr, lifecycle, FakeNotifier(), stocks=["GOOD", "BAD"], send_alerts=False
    )

    assert result["processed"] == 1 and result["failed"] == 1
    assert result["status"] == "basarisiz"          # kısmi tarama başarı sayılmaz
    assert len(mgr.to_dataframe("GOOD")) == 60      # geçerli sembol akmaya devam etti
    assert "BAD" not in mgr.deques or len(mgr.get_deque("BAD")) == 0


def test_18_gecersiz_yeni_veri_gecerli_cache_i_bozmaz(tmp_path):
    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    eski = gecerli_frame(55, base=50.0)
    assert mgr.append_dataframe("THYAO", eski) is True
    once = mgr.to_dataframe("THYAO").copy(deep=True)

    bozuk = gecerli_frame(60, base=60.0)
    bozuk.loc[bozuk.index[10], "high"] = -3.0
    assert mgr.append_dataframe("THYAO", bozuk) is False

    sonra = mgr.to_dataframe("THYAO")
    pd.testing.assert_frame_equal(once, sonra)      # deque birebir korundu
    mgr.save_to_disk("THYAO")
    yeniden = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    pd.testing.assert_frame_equal(yeniden.to_dataframe("THYAO"), once)  # disk de
    assert mgr.sureklilik_sorunlari["THYAO"][0]["tip"] == "gecersiz_girdi"


def test_19_20_gecersiz_veri_motorlara_ulasmaz(tmp_path, monkeypatch):
    """Cache'siz sembol + geçersiz taze fetch → lifecycle/domain hiç çağrılmaz.
    Geçerli eski cache varsa analiz ESKİ veriyle sürer (açık politika)."""
    live_state = FakeLiveState()
    sifirla_daily_stats(monkeypatch)
    heartbeat = []

    def sahte_1h(stock, period):
        return (gecerli_frame(60).assign(open=float("nan")), False, "")

    cagri_1h, cagri_1d = temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    lifecycle_calls = []
    domain_calls = []

    class KayitLifecycle(PatternLifecycleManager):
        def scan(self, key, df, *a, **k):
            lifecycle_calls.append((key, len(df)))
            return super().scan(key, df, *a, **k)

    def kayit_runner(symbol, timeframe, frame, *, profile):
        domain_calls.append((symbol, timeframe, len(frame)))

    monkeypatch.setattr(main_module, "_load_domain_runner", lambda: kayit_runner)

    # a) Cache'siz sembol: motorlara hiç veri gitmez.
    mgr = StockDequeManager(data_dir=str(tmp_path / "bos"))
    result = main_module.scan_all_stocks(
        mgr, KayitLifecycle(profile=config.PROFILE), FakeNotifier(),
        stocks=[MISSING_20[0]], send_alerts=False,
    )
    assert result["processed"] == 0
    assert lifecycle_calls == [] and domain_calls == []
    assert cagri_1d == []                           # 1D bloğuna ulaşılmadan atlandı

    # b) Geçerli eski cache: analiz eski veriyle sürer; motor eski frame görür.
    lifecycle_calls.clear()
    domain_calls.clear()
    mgr2 = StockDequeManager(data_dir=str(tmp_path / "eski"))
    eski = gecerli_frame(55, base=70.0)
    mgr2.append_dataframe("THYAO", eski)
    main_module.scan_all_stocks(
        mgr2, KayitLifecycle(profile=config.PROFILE), FakeNotifier(),
        stocks=["THYAO"], send_alerts=False,
    )
    assert lifecycle_calls and domain_calls
    for _key, uzunluk in lifecycle_calls:
        assert uzunluk <= len(eski)                 # eski veri; bozuk yeni veri değil
    for _symbol, _tf, uzunluk in domain_calls:
        assert uzunluk <= len(eski)
    assert math.isfinite(float(mgr2.to_dataframe("THYAO")["open"].iloc[0]))
