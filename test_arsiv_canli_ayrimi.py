"""Arşiv/replay ve canlı mumların farklı kaynak sözleşmeleri."""
import os

import pandas as pd
import pytest

from research import arsiv, replay_egitim


def _archive(root, price):
    root.mkdir(exist_ok=True)
    frame = pd.DataFrame({"bar_time": pd.date_range("2025-01-01", periods=8, freq="h", tz="UTC"),
                          "open": price, "high": price + 1, "low": price - 1,
                          "close": price, "volume": 5.})
    path = root / "TEST_1h.csv.gz"
    frame.to_csv(path, index=False, compression="gzip")
    return path


@pytest.mark.parametrize("tf", ["1h", "2h", "4h"])
def test_arsiv_koku_ve_dosya_degisiminde_eski_seri_kullanilmaz(tmp_path, tf):
    a, b = tmp_path / "a", tmp_path / "b"
    path = _archive(a, 10.)
    _archive(b, 20.)
    assert arsiv.tf_frame("TEST", tf, a).close.iloc[-1] == 10.
    x = arsiv.tf_frame("TEST", tf, b)
    assert x.close.iloc[-1] == 20.
    x.iloc[0, x.columns.get_loc("close")] = 12345
    assert arsiv.tf_frame("TEST", tf, b).close.iloc[0] == 20.
    old = path.stat().st_mtime_ns
    _archive(a, 30.)
    os.utime(path, ns=(old + 1_000_000_000, old + 1_000_000_000))
    assert arsiv.tf_frame("TEST", tf, a).close.iloc[-1] == 30.
    path.unlink()
    with pytest.raises(FileNotFoundError):
        arsiv.tf_frame("TEST", tf, a)


def test_test_egitim_penceresinde_gecersiz_hacim_reddedilir():
    frame = pd.DataFrame({"open": [10., 10., 10.], "high": [11., 11., 11.],
                          "low": [9., 9., 9.], "close": [10., 10., 10.],
                          "volume": [0., -1., float("nan")]})
    assert list(replay_egitim._bad(frame)) == [0, 1, 1]


def test_canli_grafik_stabil_baglamina_arsiv_karistirilmaz(tmp_path, monkeypatch):
    import grafik_uret
    from data import StockDequeManager
    monkeypatch.setattr(arsiv, "tf_frame", lambda *a, **k: pytest.fail("canlı grafiğe arşiv karıştırıldı"))
    index = pd.date_range("2026-10-01 09:30", periods=20, freq="h", tz="Europe/Istanbul")
    frame = pd.DataFrame({"open": 10., "high": 11., "low": 9., "close": 10., "volume": 1.}, index=index)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    assert mgr.append_dataframe("TEST", frame)
    daily, _, _ = grafik_uret._stabil_baglami_hazirla("TEST", "1h", frame, str(tmp_path), yonetici=mgr)
    assert daily is None or len(daily) <= len(frame)
