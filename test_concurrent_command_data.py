"""Tarama sürerken grafik ve karne okuması yarım güncelleme görmemeli."""

import threading
from collections import deque
from datetime import datetime, timedelta

import pandas as pd
import pytest

from config import ISTANBUL_TZ
from data import StockDequeManager
from karne import KarneDefteri


@pytest.mark.parametrize("daily", [False, True])
def test_dataframe_reader_waits_for_complete_cache_replacement(tmp_path, monkeypatch, daily):
    from data import seed_cache

    monkeypatch.setattr(seed_cache, "sureklilik_sorunlari_bul", lambda _dq: [])
    manager = StockDequeManager(data_dir=str(tmp_path))
    period = "D" if daily else "h"
    index = pd.date_range("2026-10-01 10:30", periods=6, freq=period, tz=ISTANBUL_TZ)
    frame = pd.DataFrame({"open": 100.0, "high": 102.0, "low": 99.0,
                          "close": 101.0, "volume": 10.0}, index=index)
    append = manager.append_gunluk_dataframe if daily else manager.append_dataframe
    read = manager.to_gunluk_dataframe if daily else manager.to_dataframe
    get = manager.get_gunluk_deque if daily else manager.get_deque
    storage = manager.gunluk_deques if daily else manager.deques
    assert append("TEST", frame.iloc[:5])

    cleared = threading.Event()
    resume = threading.Event()
    reader_started = threading.Event()
    reader_done = threading.Event()
    errors, result = [], []

    class PausedDeque(deque):
        def clear(self):
            super().clear()
            cleared.set()
            if not resume.wait(5):
                raise TimeoutError("Güncelleme serbest bırakılmadı")

    initial = get("TEST")
    storage["TEST"] = PausedDeque(initial, maxlen=initial.maxlen)

    def writer():
        try:
            assert append("TEST", frame)
        except BaseException as exc:
            errors.append(exc)

    def reader():
        reader_started.set()
        try:
            result.append(read("TEST"))
        except BaseException as exc:
            errors.append(exc)
        finally:
            reader_done.set()

    writing = threading.Thread(target=writer)
    reading = threading.Thread(target=reader)
    writing.start()
    try:
        assert cleared.wait(5)
        reading.start()
        assert reader_started.wait(5)
        assert not reader_done.wait(0.1)  # ara durumda boş deque yayımlanmamalı
    finally:
        resume.set()
        writing.join(5)
        if reading.ident is not None:
            reading.join(5)
    assert not writing.is_alive() and not reading.is_alive() and not errors
    assert len(result) == 1 and result[0] is not None and len(result[0]) == 6


def test_karne_query_uses_stable_record_snapshot_when_scan_adds_record(tmp_path):
    book = KarneDefteri(data_dir=str(tmp_path))
    now = ISTANBUL_TZ.localize(datetime(2026, 10, 30, 12))
    reading = threading.Event()
    resume = threading.Event()
    errors, result = [], []

    class PausedRecord(dict):
        def get(self, key, *args):
            if key == "kayit_zaman":
                reading.set()
                if not resume.wait(5):
                    raise TimeoutError("Karne sorgusu serbest bırakılmadı")
            return super().get(key, *args)

    book._kayitlar["ilk"] = PausedRecord(kayit_zaman=now.isoformat(), stock="THYAO")

    def query():
        try:
            result.extend(book.aralikta(now - timedelta(days=1), now + timedelta(days=1)))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=query)
    thread.start()
    try:
        assert reading.wait(5)
        book._kayitlar["yeni"] = {"kayit_zaman": now.isoformat(), "stock": "GARAN"}
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and not errors
    assert [record["stock"] for record in result] == ["THYAO"]
    assert book.boyut() == 2
