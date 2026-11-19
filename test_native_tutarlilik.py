"""Native 2h/4h ↔ 1h tutarlılık aracının sözleşmeleri (ağsız)."""
from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd
import pytest

import research.native_tutarlilik as nt


def _yaz(yol: Path, satirlar: list[tuple[str, float, float, float, float, float]]) -> None:
    metin = "bar_time,open,high,low,close,volume\n" + "".join(
        f"{z},{o},{h},{l},{c},{v}\n" for z, o, h, l, c, v in satirlar
    )
    with gzip.open(yol, "wt", encoding="utf-8") as f:
        f.write(metin)


def _saatlik_barlar(gun_sayisi: int = 160) -> list[tuple[str, float, float, float, float, float]]:
    """09:30 hayalet barı + 10:30…17:30 gerçek barlar."""
    satirlar = []
    for gun in range(gun_sayisi):
        tarih = pd.Timestamp("2026-01-05", tz="Europe/Istanbul") + pd.Timedelta(days=gun)
        if tarih.weekday() >= 5:
            continue
        # 09:30 barları hacimsiz — Yahoo "hayalet" barı.
        # Gerçek arşiv gibi +03:00 ofseti YAZILMALI: ofsetsiz damga `utc=True`
        # ile UTC sayılır ve 3 saat kayar (testte tam bu tuzak yakalandı).
        satirlar.append((f"{tarih.date()}T09:30:00+03:00", 100.0, 100.0, 100.0, 100.0, 0.0))
        for saat, fiyat in ((10, 101), (11, 102), (12, 103), (13, 104), (14, 105), (15, 106), (16, 107), (17, 108)):
            satirlar.append((f"{tarih.date()}T{saat}:30:00+03:00", fiyat, fiyat, fiyat, fiyat, 1000.0))
    return satirlar


def _kova_yaz(yol: Path, saatlik, tf: str, fiyat_fn) -> None:
    """1h'den referans kova üretip `fiyat_fn` ile bozar — native taklidi."""
    df = pd.DataFrame(saatlik, columns=["bar_time", "open", "high", "low", "close", "volume"])
    df.index = pd.DatetimeIndex(
        pd.to_datetime(df.pop("bar_time"), utc=True).dt.tz_convert("Europe/Istanbul"),
        name="timestamp",
    )
    ref = nt._referans(df, tf)
    satirlar = [
        (
            f"{z.isoformat()}",
            fiyat_fn(o), fiyat_fn(h), fiyat_fn(l), fiyat_fn(c), v,
        )
        for z, o, h, l, c, v in ref.reset_index().itertuples(index=False)
    ]
    _yaz(yol, satirlar)


@pytest.fixture()
def arsiv(tmp_path: Path) -> Path:
    saatlik = _saatlik_barlar()
    _yaz(tmp_path / "SAGLAM_1h.csv.gz", saatlik)
    _yaz(tmp_path / "BOZUK_1h.csv.gz", saatlik)
    _kova_yaz(tmp_path / "SAGLAM_2h.csv.gz", saatlik, "2h", lambda x: x)
    _kova_yaz(tmp_path / "BOZUK_2h.csv.gz", saatlik, "2h", lambda x: x * 1.20)
    return tmp_path


def test_ayni_kova_hizalamasi_yakalanir(arsiv: Path):
    """2h kovaları 09/11/13/15/17'ye hizalı olmalı — 10/12/14 değil."""
    ref = nt._referans(nt._yukle(arsiv / "SAGLAM_1h.csv.gz"), "2h")
    saatler = sorted({z.hour for z in ref.index})
    assert saatler == [9, 11, 13, 15, 17]


def test_hacimsiz_hayalet_bar_kovada_fiyat_tasir_hacim_tasimaz(arsiv: Path):
    """09:30 hacimsiz bar: fiyatı kovaya GİRER, hacmi girmez.

    Çıkarılsaydı kova fitilsiz kalır ve native fark yapay büyürdü; hacmi
    sayılsaydı kova ortalaması bozulurdu. İkisi de yanlış.
    """
    ref = nt._referans(nt._yukle(arsiv / "SAGLAM_1h.csv.gz"), "2h")
    ilk = ref.iloc[0]
    assert ilk["open"] == 100.0        # hayalet barın fiyatı
    assert ilk["volume"] == 1000.0     # yalnız gerçek hacim (2 × 500 değil)


def test_tamamen_hacimsiz_kova_kiyas_disi(arsiv: Path):
    """Bütün 1h barları hacimsiz olan kova karşılaştırmaya girmez."""
    saatlik = _saatlik_barlar(gun_sayisi=3)
    bos = [(z, o, h, l, c, 0.0) for z, o, h, l, c, _ in saatlik]
    _yaz(arsiv / "HACIMSIZ_1h.csv.gz", bos)
    ref = nt._referans(nt._yukle(arsiv / "HACIMSIZ_1h.csv.gz"), "2h")
    assert len(ref) == 0


def test_tutarlilik_mutlak_fark_ile_olculur(arsiv: Path):
    satir = nt.sembol_karsilastir("SAGLAM", "2h", arsiv)
    assert satir is not None
    assert satir["medyan_fark_pct"] == 0.0
    assert satir["uyumsuz"] is False

    bozuk = nt.sembol_karsilastir("BOZUK", "2h", arsiv)
    assert bozuk is not None
    # Fiyat %20 yukarı: fark işaretli olsaydı -20 çıkardı. Mutlak olmalı.
    assert bozuk["medyan_fark_pct"] == pytest.approx(20.0, abs=0.01)
    assert bozuk["uyumsuz"] is True


def test_min_bar_esigi_kucuk_seriyi_atlar(arsiv: Path):
    """30 barı olan seri "uyumlu" ilan edilmemeli; ölçülmemeli."""
    saatlik = _saatlik_barlar(gun_sayisi=6)
    _yaz(arsiv / "KISA_1h.csv.gz", saatlik)
    _kova_yaz(arsiv / "KISA_2h.csv.gz", saatlik, "2h", lambda x: x * 1.5)
    assert nt.sembol_karsilastir("KISA", "2h", arsiv) is None


def test_rapor_bos_cerceveye_dayanir(tmp_path: Path):
    metin = nt.rapor_yaz(pd.DataFrame(), tmp_path / "bos.md")
    assert "bulunamadı" in metin.lower()
    assert (tmp_path / "bos.md").exists()


def test_tara_iki_zaman_dilimini_birlikte_gezer(arsiv: Path):
    df = nt.tara(arsiv, ("2h",))
    assert set(df["symbol"]) == {"SAGLAM", "BOZUK"}
    assert df["timeframe"].unique().tolist() == ["2h"]
