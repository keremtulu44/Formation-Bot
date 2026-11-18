# -*- coding: utf-8 -*-
"""Ortak tvDatafeed istemcisinin sürüm/zaman/WS sözleşmeleri (ağsız)."""
from __future__ import annotations

import os
import sys
import types

import pandas as pd
import pytest

from scripts import tvdatafeed_client as tv


def _fake_surum(monkeypatch, dist: str, version: str):
    def fake(name):
        if name == dist:
            return version
        raise tv._metadata.PackageNotFoundError(name)

    monkeypatch.setattr(tv._metadata, "version", fake)


def _frame(rows: int = 2, tz=None):
    idx = pd.date_range("2026-11-02", periods=rows, freq="D", tz=tz)
    return pd.DataFrame({
        "Symbol": ["THYAO"] * rows,
        "Open": [100.0] * rows,
        "High": [101.0] * rows,
        "Low": [99.0] * rows,
        "Close": [100.5] * rows,
        "Volume": [1000] * rows,
    }, index=idx)


def _kur(monkeypatch, frame, *, dist="tradingview-datafeed", version="2.1.1",
         fail=False):
    """Sahte ``tvDatafeed`` modülü + doğrulanmış dağıtım metadata'sı kurar."""
    _fake_surum(monkeypatch, dist, version)
    istemciler = []
    cagri = {}

    class WS:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class TvDatafeed:
        def __init__(self):
            self.ws = WS()
            istemciler.append(self)

        def get_hist(self, **kwargs):
            cagri.update(kwargs)
            if fail:
                raise ConnectionError("WS kapandı")
            return frame

    modul = types.SimpleNamespace(
        TvDatafeed=TvDatafeed,
        Interval=types.SimpleNamespace(in_daily="1D", in_4_hour="4H"),
    )
    monkeypatch.setitem(sys.modules, tv.IMPORT_MODULU, modul)
    return istemciler, cagri


@pytest.mark.parametrize("dist,version", [
    ("tradingview-datafeed", "2.1.1"),
    ("tvdatafeed", "2.1.0"),
])
def test_dogrulanmis_iki_dagitim_kabul_edilir(monkeypatch, dist, version):
    _fake_surum(monkeypatch, dist, version)
    assert tv.dogrulanmis_surum() == (dist, version)
    assert tv.surumleri_oku() == {dist: version}


def test_bilinmeyen_surum_reddedilir(monkeypatch):
    _fake_surum(monkeypatch, "tradingview-datafeed", "9.9.9")
    with pytest.raises(RuntimeError, match="doğrulanmamış tvDatafeed dağıtımı"):
        tv.dogrulanmis_surum()


def test_kurulu_degilse_iki_kurulum_ipucu_yazilir(monkeypatch):
    def fake(name):
        raise tv._metadata.PackageNotFoundError(name)

    monkeypatch.setattr(tv._metadata, "version", fake)
    with pytest.raises(ModuleNotFoundError) as exc:
        tv.dogrulanmis_surum()
    assert "tradingview-datafeed==2.1.1" in str(exc.value)
    assert "rongardF/tvdatafeed@e6f6aaa7de43" in str(exc.value)


def test_naive_yerel_damga_utc_cevrilir_ve_surec_tz_degismez(istanbul_tz, monkeypatch):
    """İstanbul dışı/ içi fark etmeden naive duvar saati gerçek UTC'ye inmeli."""
    istemciler, cagri = _kur(monkeypatch, _frame())

    veri = tv.get_hist(symbol="THYAO", interval="in_daily", n_bars=2)

    assert str(veri.index.tz) == "UTC"
    assert veri.index[0] == pd.Timestamp("2026-11-01 21:00", tz="UTC")
    assert os.environ["TZ"] == "Europe/Istanbul"  # TZ=UTC hack'i yok
    assert list(veri.columns) == ["symbol", "open", "high", "low", "close", "volume"]
    assert cagri["symbol"] == "THYAO" and cagri["exchange"] == "BIST"
    assert cagri["interval"] == "1D" and cagri["n_bars"] == 2
    assert istemciler[0].ws.closed is True


def test_tz_aware_yeni_surum_dogrudan_utc_cevrilir(monkeypatch):
    _kur(monkeypatch, _frame(tz="Europe/Istanbul"))

    veri = tv.get_hist(symbol="THYAO", interval="in_daily", n_bars=2)

    assert str(veri.index.tz) == "UTC"
    assert veri.index[0] == pd.Timestamp("2026-11-01 21:00", tz="UTC")


def test_bos_yanit_reddedilir_ve_ws_kapanir(monkeypatch):
    istemciler, _ = _kur(monkeypatch, None)

    with pytest.raises(ValueError, match="boş veya geçersiz sağlayıcı verisi"):
        tv.get_hist(symbol="THYAO")
    assert istemciler[0].ws.closed is True


def test_cekme_hatasinda_bile_ws_kapanir(monkeypatch):
    istemciler, _ = _kur(monkeypatch, _frame(), fail=True)

    with pytest.raises(ConnectionError, match="WS kapandı"):
        tv.get_hist(symbol="THYAO")
    assert istemciler[0].ws.closed is True


def test_gecici_bos_yanitta_yeni_istemciyle_bir_kez_dener(monkeypatch):
    """EREGL 4h: 'Connection ... lost / no data' → tek yeniden deneme kurtarır."""
    _fake_surum(monkeypatch, "tradingview-datafeed", "2.1.1")
    istemciler = []

    class WS:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class TvDatafeed:
        def __init__(self):
            self.ws = WS()
            istemciler.append(self)

        def get_hist(self, **kwargs):
            return None if len(istemciler) == 1 else _frame()

    modul = types.SimpleNamespace(
        TvDatafeed=TvDatafeed,
        Interval=types.SimpleNamespace(in_daily="1D", in_4_hour="4H"),
    )
    monkeypatch.setitem(sys.modules, tv.IMPORT_MODULU, modul)

    veri = tv.get_hist(symbol="EREGL", interval="in_4_hour")

    assert len(veri) == 2
    assert len(istemciler) == 2
    assert all(c.ws.closed for c in istemciler), "her denemede WS kapanmalı"


def test_iki_deneme_de_bosssa_hata_verir_ve_tum_ws_kapanir(monkeypatch):
    istemciler, _ = _kur(monkeypatch, None)

    with pytest.raises(ValueError, match="boş veya geçersiz sağlayıcı verisi"):
        tv.get_hist(symbol="THYAO")

    assert len(istemciler) == tv.DENEME_SINIRI
    assert all(c.ws.closed for c in istemciler)


def test_bilinmeyen_aralik_sessizce_gecmez(monkeypatch):
    _kur(monkeypatch, _frame())

    with pytest.raises(ValueError, match="tvDatafeed aralığı desteklenmiyor"):
        tv.get_hist(symbol="THYAO", interval="in_3_seconds")
