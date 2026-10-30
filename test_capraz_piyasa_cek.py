"""Termux günlük arşiv aracının ağsız güvenlik ve devam testleri."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.backfill import capraz_piyasa_cek as tool


class FakeTempo:
    dur = False
    def bekle(self): pass
    def istek_bitti(self): pass
    def basarili(self): pass
    def gecici_hata(self, reason): pass


def frame(tz="America/New_York", rows=1827):
    return pd.DataFrame(
        {"open": 100.0, "high": 103.0, "low": 99.0, "close": 101.0, "volume": 0.0},
        index=pd.date_range("2021-10-28", periods=rows, tz=tz),
    )


@pytest.fixture
def symbols(monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {
        "XAUUSD": ("XAUUSD=X", "spot", "USD"),
        "XAU_FUT": ("GC=F", "future", "USD"),
        "USDTRY": ("USDTRY=X", "fx", "TRY_per_USD"),
    })


def test_collect_separates_spot_and_future_and_resumes(tmp_path, monkeypatch, symbols):
    calls = []
    def fetch(ticker, period, interval):
        calls.append((ticker, period, interval))
        return frame(), "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    assert len(calls) == 3
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["series"]["XAUUSD"]["ticker"] == "XAUUSD=X"
    assert manifest["series"]["XAU_FUT"]["ticker"] == "GC=F"
    assert manifest["series"]["XAUUSD"]["provider_timezone"] == "America/New_York"
    assert manifest["series"]["XAUUSD"]["closed_at_verified"] is False
    with gzip.open(tmp_path / "XAUUSD_1d.csv.gz", "rt") as f:
        assert f.readline().strip() == "bar_time,open,high,low,close,volume"
        assert "+03:00" in f.readline()
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    assert len(calls) == 3


def test_failed_spot_not_silently_replaced_with_future(tmp_path, monkeypatch, symbols):
    def fetch(ticker, period, interval):
        return (None, "bulunamadı", False) if ticker == "XAUUSD=X" else (frame(), "", False)
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    monkeypatch.setattr(tool, "_stooq_cek", lambda *args: (None, "erişim yok"))
    monkeypatch.setattr(tool, "_tradingview_cek", lambda *args, **kwargs: (None, "TV erişim yok"))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    assert not (tmp_path / "XAUUSD_1d.csv.gz").exists()
    assert (tmp_path / "XAU_FUT_1d.csv.gz").exists()
    assert json.loads((tmp_path / "manifest.json").read_text())["series"]["XAUUSD"]["status"] == "error"


def test_partial_run_retries_only_missing(tmp_path, monkeypatch, symbols):
    calls = []
    def fetch(ticker, period, interval):
        calls.append(ticker)
        if ticker == "USDTRY=X" and calls.count(ticker) == 1:
            return None, "timeout", True
        return frame(), "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    assert calls.count("USDTRY=X") == 2
    assert calls.count("XAUUSD=X") == 1


def test_tampered_file_is_not_overwritten_without_explicit_refresh(tmp_path, monkeypatch, symbols):
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(), "", False))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    path = tmp_path / "XAUUSD_1d.csv.gz"
    path.write_bytes(b"tampered")
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    assert path.read_bytes() == b"tampered"
    assert tool.cek(tmp_path, "5y", yenile=True, tempo=FakeTempo(), log=lambda x: None) == 0


def test_refresh_failure_preserves_prior_file_but_exits_nonzero(tmp_path, monkeypatch, symbols):
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(), "", False))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    path = tmp_path / "XAUUSD_1d.csv.gz"
    old = path.read_bytes()
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (None, "kesinti", True))
    assert tool.cek(tmp_path, "5y", yenile=True, tempo=FakeTempo(), log=lambda x: None) == 1
    assert path.read_bytes() == old
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XAUUSD"]
    assert rec["status"] == "ok" and rec["last_error"] == "kesinti"


@pytest.mark.parametrize("data", [
    frame(tz=None),
    frame(rows=10),
    pd.concat([frame(), frame().iloc[:1]]),
    frame().assign(close=float("nan")),
    frame().assign(high=98.0),
])
def test_bad_data_rejected(data):
    with pytest.raises(ValueError):
        tool._validated_frame(data)


def test_corrupt_manifest_and_original_archive_rejected(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text("{broken")
    with pytest.raises(ValueError):
        tool._read_manifest(bad)
    with pytest.raises(SystemExit) as exc:
        tool.main(["--hedef", str(Path(tool.ROOT) / "backfill_data")])
    assert exc.value.code == 2


def test_stooq_spot_is_labeled_as_stooq_and_date_only(tmp_path, monkeypatch, symbols):
    def fetch(ticker, period, interval):
        return (None, "404", False) if ticker == "XAUUSD=X" else (frame(), "", False)
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    monkeypatch.setattr(tool, "_stooq_cek", lambda *args: (frame(tz=None), ""))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XAUUSD"]
    assert rec["provider"] == "stooq" and rec["provider_symbol"] == "xauusd"
    assert rec["provider_timezone"] is None and rec["closed_at_verified"] is False
    with gzip.open(tmp_path / "XAUUSD_1d.csv.gz", "rt") as f:
        next(f)
        assert f.readline().split(",")[0] == "2021-10-28"
    assert (tmp_path / "XAU_FUT_1d.csv.gz").exists()


def test_stooq_loader_parses_and_checks_response(monkeypatch):
    import requests
    class Response:
        text = "Date,Open,High,Low,Close\n" + "\n".join(
            f"{day.date()},100,105,95,102" for day in pd.date_range("2024-01-01", periods=80))
        def raise_for_status(self): pass
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    data, err = tool._stooq_cek("xauusd", "max")
    assert err == "" and len(data) == 80 and data.index.tz is None
    assert data.volume.isna().all()
    Response.text = "Exceeded daily quota or CAPTCHA"
    data, err = tool._stooq_cek("xauusd", "max")
    assert data is None and "Stooq verisi alınamadı" in err


def test_usdtry_invalid_high_low_preserved_and_flagged(tmp_path, monkeypatch, symbols):
    def fetch(ticker, period, interval):
        value = frame()
        if ticker == "USDTRY=X":
            value.iloc[4, value.columns.get_loc("high")] = 100.5
        return value, "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["USDTRY"]
    assert rec["quality"]["invalid_ohlc_count"] == 1
    assert len(rec["quality"]["invalid_ohlc_labels"]) == 1
    assert rec["quality"]["atr_ready"] is False
    with gzip.open(tmp_path / "USDTRY_1d.csv.gz", "rt") as f:
        data = pd.read_csv(f)
    assert data.iloc[4]["high"] == 100.5 and data.iloc[4]["close"] == 101.0


def test_index_same_ticker_max_history_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XU50": ("XU050.IS", "bist_endeks", "TRY")})
    calls = []
    def fetch(ticker, period, interval):
        calls.append((ticker, period))
        return (frame(rows=1) if period == "5y" else frame()), "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    assert calls == [("XU050.IS", "5y"), ("XU050.IS", "max")]
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XU50"]
    assert rec["download_period"] == "max" and rec["provider_symbol"] == "XU050.IS"


def test_index_shorter_history_is_marked_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XUTUM": ("XUTUM.IS", "bist_endeks", "TRY")})
    def fetch(ticker, period, interval):
        return (frame() if period == "2y" else frame(rows=1)), "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XUTUM"]
    assert rec["download_period"] == "2y" and rec["partial_history"] is True
    assert (tmp_path / "XUTUM_1d.csv.gz").exists()


def test_index_uses_tradingview_same_index_after_short_yahoo(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XU50": ("XU050.IS", "bist_endeks", "TRY")})
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(rows=1), "", False))
    tv_calls = []
    def tv(symbol, period):
        tv_calls.append((symbol, period))
        return frame(tz="UTC"), ""
    monkeypatch.setattr(tool, "_tradingview_cek", tv)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XU50"]
    assert tv_calls == [("XU050", "5y")]
    assert rec["provider"] == "tradingview" and rec["provider_symbol"] == "BIST:XU050"
    assert rec["provider_timezone"] == "UTC" and rec["auto_adjust"] is None


def test_failed_tradingview_is_explicit_not_different_index(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XUTUM": ("XUTUM.IS", "bist_endeks", "TRY")})
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(rows=1), "", False))
    monkeypatch.setattr(tool, "_tradingview_cek", lambda *args: (None, "erişim engellendi"))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XUTUM"]
    assert "erişim engellendi" in rec["last_error"]
    assert not (tmp_path / "XUTUM_1d.csv.gz").exists()


def test_tradingview_utc_conversion_and_tz_restored(monkeypatch):
    import importlib.metadata as package_metadata
    import os
    import sys
    import types

    class TV:
        def __init__(self):
            self.ws = None
        def get_hist(self, **kwargs):
            assert os.environ["TZ"] == "UTC"
            return frame(tz=None)
    dummy = types.SimpleNamespace(TvDatafeed=TV, Interval=types.SimpleNamespace(in_daily="1D"))
    monkeypatch.setitem(sys.modules, "tvDatafeed", dummy)
    monkeypatch.setattr(package_metadata, "version", lambda _: "2.1.1")
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    data, err = tool._tradingview_cek("XU050", "max")
    assert err == "" and str(data.index.tz) == "UTC"
    assert os.environ["TZ"] == "Europe/Istanbul"


def test_existing_v1_manifest_stays_usable_after_update(tmp_path, monkeypatch, symbols):
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(), "", False))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    # Eski sürüm provider alanlarını yazmıyordu.
    for record in data["series"].values():
        for key in ("provider", "provider_symbol", "download_period", "partial_history", "adjustment_note", "volume_note"):
            record.pop(key, None)
    path.write_text(json.dumps(data))
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: pytest.fail("sağlam eski kayıt atlanmalı"))
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0


def test_max_query_with_insufficient_actual_span_is_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XU50": ("XU050.IS", "bist_endeks", "TRY")})
    def fetch(ticker, period, interval):
        return (frame(rows=1) if period == "5y" else frame(rows=80)), "", False
    monkeypatch.setattr(tool.yb, "_ham_cek", fetch)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 1
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XU50"]
    assert rec["download_period"] == "max" and rec["partial_history"] is True
    assert rec["coverage_days"] == 79


@pytest.mark.parametrize("symbol", ["XAUUSD", "XAGUSD"])
def test_tv_ice_spot_fallback_is_labeled_and_never_uses_future(tmp_path, monkeypatch, symbol):
    monkeypatch.setattr(tool, "SERILER", {symbol: (symbol + "=X", "spot", "USD")})
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (None, "404", False))
    monkeypatch.setattr(tool, "_stooq_cek", lambda *args: (None, "erişim yok"))
    seen = []
    def tv(name, period, *, exchange):
        seen.append((name, period, exchange))
        return frame(tz="UTC"), ""
    monkeypatch.setattr(tool, "_tradingview_cek", tv)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"][symbol]
    assert seen == [(symbol, "5y", "FX_IDC")]
    assert rec["provider_symbol"] == "FX_IDC:" + symbol
    assert rec["provider"] == "tradingview" and rec["kind"] == "spot"
    assert "ICE" in rec["quote_note"] and "not futures" in rec["quote_note"]
    assert rec["closed_at_verified"] is False


def test_xutum_tradingview_empty_response_retried_once(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SERILER", {"XUTUM": ("XUTUM.IS", "bist_endeks", "TRY")})
    monkeypatch.setattr(tool.yb, "_ham_cek", lambda *args: (frame(rows=1), "", False))
    calls = []
    def tv(symbol, period):
        calls.append((symbol, period))
        if len(calls) == 1:
            return None, "boş veya geçersiz sağlayıcı verisi"
        return frame(tz="UTC"), ""
    monkeypatch.setattr(tool, "_tradingview_cek", tv)
    assert tool.cek(tmp_path, "5y", tempo=FakeTempo(), log=lambda x: None) == 0
    assert calls == [("XUTUM", "5y"), ("XUTUM", "5y")]
    rec = json.loads((tmp_path / "manifest.json").read_text())["series"]["XUTUM"]
    assert rec["provider_symbol"] == "BIST:XUTUM"
