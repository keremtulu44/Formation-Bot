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


def frame(tz="America/New_York", rows=80):
    return pd.DataFrame(
        {"open": 100.0, "high": 103.0, "low": 99.0, "close": 101.0, "volume": 0.0},
        index=pd.date_range("2025-01-01", periods=rows, tz=tz),
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
