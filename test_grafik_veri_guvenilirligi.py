"""Grafik/sağlayıcı hata yolları; gerçek ağ ve canlı cache kullanılmaz."""
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

import data
import grafik_uret


def _valid():
    return pd.DataFrame({"Open": [10.0], "High": [11.0], "Low": [9.0],
                         "Close": [10.0], "Volume": [0.0]},
                        index=pd.date_range("2026-10-30", periods=1, tz="UTC"))


@pytest.mark.parametrize("interval", ["1h", "1d"])
@pytest.mark.parametrize("failure", ["invalid", "missing", "permanent"])
def test_gecersiz_birincil_seri_yedege_gecer(monkeypatch, interval, failure):
    calls = []
    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kwargs):
            calls.append(self.symbol)
            if len(calls) == 1:
                if failure == "permanent":
                    raise ValueError("symbol not found")
                frame = _valid()
                if failure == "invalid":
                    frame["Open"] = float("nan")
                else:
                    frame = frame.drop(columns="Volume")
                return frame
            return _valid()
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))
    result = (data.fetch_yfinance_1h("XAUUSD", with_status=True)[0] if interval == "1h"
              else data.fetch_yfinance_1d("XAUUSD"))
    assert result is not None and len(result) == 1
    assert calls == ["XAUUSD=X", "GC=F"]


@pytest.mark.parametrize("interval", ["1h", "1d"])
def test_gecici_hatada_yedek_istegi_yok(monkeypatch, interval):
    calls = []
    class Ticker:
        def __init__(self, symbol):
            calls.append(symbol)
        def history(self, **kwargs):
            raise TimeoutError("read timed out")
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))
    if interval == "1h":
        frame, retryable, reason = data.fetch_yfinance_1h("XAUUSD", with_status=True)
        assert retryable and "timed out" in reason
    else:
        frame = data.fetch_yfinance_1d("XAUUSD")
    assert frame is None and calls == ["XAUUSD=X"]


def test_bilinmeyen_sembol_tahmini_sadece_oneri(tmp_path):
    with pytest.raises(grafik_uret.VeriYok, match="Benzer semboller: XAGUSD, XAUUSD"):
        grafik_uret.cerceve_getir("XAUSD", "1h", str(tmp_path))
    assert not list(tmp_path.rglob("*.json"))
