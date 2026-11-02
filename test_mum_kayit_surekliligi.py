"""Mum kayıtlarının düzeltme, eşzamanlılık ve grafik izolasyonu testleri."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas as pd
import pytest

from data import StockDequeManager


def _frame(period="h"):
    idx = pd.date_range("2026-10-01 10:30", periods=8, freq=period, tz="Europe/Istanbul")
    return pd.DataFrame({"open": 10., "high": 12., "low": 9.,
                         "close": 11., "volume": 100.}, index=idx)


@pytest.mark.parametrize("daily", [False, True])
def test_eski_mum_duzeltmesi_uzak_kayda_gider(tmp_path, daily):
    class Store:
        def __init__(self):
            self.calls = []
        def upsert(self, key, payload):
            self.calls.append((key, payload))
            return True
    store = Store()
    mgr = StockDequeManager(data_dir=str(tmp_path), persistent_store=store)
    append = mgr.append_gunluk_dataframe if daily else mgr.append_dataframe
    save = mgr.save_gunluk_to_disk if daily else mgr.save_to_disk
    frame = _frame("D" if daily else "h")
    assert append("TEST", frame) and save("TEST")
    assert save("TEST") and len(store.calls) == 1
    update = frame.iloc[[0]].copy()
    update.iloc[0, update.columns.get_loc("volume")] = 200.
    assert append("TEST", update) and save("TEST")
    assert len(store.calls) == 2
    assert store.calls[-1][1][0]["volume"] == 200.


def test_tek_mum_tekrari_ve_gecmis_ekleme_sirali(tmp_path):
    mgr = StockDequeManager(data_dir=str(tmp_path))
    frame = _frame()
    for idx in (4, 2, 4, 3):
        row = frame.iloc[idx].to_dict()
        row["timestamp"] = frame.index[idx]
        assert mgr.append_candle("TEST", row)
    saved = mgr.to_dataframe("TEST")
    assert list(saved.index) == list(frame.index[[2, 3, 4]])
    assert mgr.save_to_disk("TEST")
    other = StockDequeManager(data_dir=str(tmp_path))
    pd.testing.assert_frame_equal(saved, other.to_dataframe("TEST"))


@pytest.mark.parametrize("daily", [False, True])
def test_es_zamanli_birlestirmeler_kayip_mum_birakmaz(tmp_path, monkeypatch, daily):
    from data import seed_cache
    monkeypatch.setattr(seed_cache, "sureklilik_sorunlari_bul", lambda _: [])
    mgr = StockDequeManager(data_dir=str(tmp_path))
    frame = _frame("D" if daily else "h")
    append = mgr.append_gunluk_dataframe if daily else mgr.append_dataframe
    get = mgr.to_gunluk_dataframe if daily else mgr.to_dataframe
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert all(executor.map(lambda n: append("TEST", frame.iloc[[n]]), range(len(frame))))
    assert list(get("TEST").index) == list(frame.index)


def test_grafik_stabil_tek_motor_sonucu_tanir():
    from grafik.kare import _sonuc_sec
    value = {"stabil": SimpleNamespace()}
    out = {"uyarilar": []}
    assert _sonuc_sec(value, "4h", cikis=out) is value
    assert not out["uyarilar"]


def test_grafik_diger_motorlari_izole_cagirilir_ve_stabil_hatasi_bildirilir(monkeypatch, tmp_path):
    import grafik_uret
    import domain_engines.runner as runner
    calls = []
    def domains(symbol, tf, frame, *, isolated=False):
        calls.append(isolated)
        return {}
    monkeypatch.setattr(runner, "run_domain_engines", domains)
    monkeypatch.setattr(runner, "run_stabil_domain", lambda *a, **k: SimpleNamespace(error="bad", data_quality=None))
    result = grafik_uret.kare_uret("TEST", "4h", demo=True, zone=True,
                                  cikti=str(tmp_path / "test.png"))
    assert calls == [True]
    assert result["yol"]
    assert any("Stabil hesaplanamadı" in str(x) for x in result["meta"].get("uyarilar", []))
