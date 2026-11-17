# -*- coding: utf-8 -*-
"""Sağlayıcı karşılaştırma aracının sözleşmeleri (ağsız).

Araç canlı modda Yahoo/borsapy'ye gider; bu testler **ağa çıkmadan** mantığı
kilitler: normalize, karşılaştırma, karar kapısı, arşiv kalite sayımı ve
ulaşılamayan sağlayıcının rapora düşmesi.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import pytest

from scripts import saglayici_karsilastirma as S

IST = "Europe/Istanbul"


def _seri(kapanislar, baslangic="2026-10-01 09:30", hacim=1000, tz=IST):
    idx = pd.date_range(datetime.fromisoformat(baslangic), periods=len(kapanislar),
                        freq="h", tz=tz)
    return pd.DataFrame({
        "open": kapanislar, "high": [k * 1.01 for k in kapanislar],
        "low": [k * 0.99 for k in kapanislar], "close": kapanislar,
        "volume": [hacim] * len(kapanislar),
    }, index=idx)


# ------------------------------------------------------------ NORMALİZE ----
def test_normalize_kolon_ve_tz_birlestirir():
    ham = _seri([10, 11, 12]).rename(columns=str.upper)
    ham.index = ham.index.tz_convert("UTC")
    df = S.normalize(ham)
    assert list(df.columns) == S.KOLONLAR
    assert str(df.index.tz) == "Europe/Istanbul"
    assert df.index.is_monotonic_increasing


def test_normalize_tekrar_eden_damgayi_tekilleştirir():
    ham = pd.concat([_seri([10, 11]), _seri([10, 99])])
    df = S.normalize(ham)
    assert len(df) == 2
    assert df["close"].iloc[-1] == 99        # son kayıt kazanır


def test_normalize_bos_ve_eksik_kolon():
    assert S.normalize(None) is None
    assert S.normalize(pd.DataFrame()) is None
    with pytest.raises(ValueError):
        S.normalize(pd.DataFrame({"close": [1]}, index=pd.date_range(
            "2026-10-01", periods=1, freq="h", tz=IST)))


# -------------------------------------------------------- KARŞILAŞTIRMA ----
def test_ayni_seri_gecer():
    seri = S.normalize(_seri([10, 11, 12, 13]))
    metrik = S.karsilastir(seri, seri)
    assert metrik["ortak_oran"] == 1.0
    assert metrik["medyan_fark_pct"] == 0.0
    assert metrik["karar"] == "geç"


def test_kucuk_yuvarlama_farki_gecer():
    ref = S.normalize(_seri([10.000, 11.000, 12.000]))
    aday = S.normalize(_seri([10.004, 11.004, 12.004]))   # %0,04
    metrik = S.karsilastir(ref, aday)
    assert metrik["karar"] == "geç"
    assert metrik["medyan_fark_pct"] == pytest.approx(0.04, abs=0.005)


def test_buyuk_fiyat_farki_reddedilir():
    ref = S.normalize(_seri([10, 11, 12]))
    aday = S.normalize(_seri([10.5, 11.5, 12.5]))         # %5
    metrik = S.karsilastir(ref, aday)
    assert metrik["karar"].startswith("red")
    assert metrik["max_fark_pct"] > S.ESIK_MAX_FARK_PCT


def test_bar_eksigi_kosullu_veya_red():
    ref = S.normalize(_seri([10, 11, 12, 13, 14, 15, 16, 17, 18, 19]))
    aday = S.normalize(_seri([10, 11, 12, 13, 14, 15, 16, 17, 18]))   # 1 eksik (%10)
    metrik = S.karsilastir(ref, aday)
    assert metrik["eksik_oran"] == pytest.approx(0.10, abs=0.01)
    assert metrik["karar"].startswith("koşullu")


def test_ortak_bar_yoksa_red():
    ref = S.normalize(_seri([10, 11, 12]))
    aday = S.normalize(_seri([10, 11, 12], baslangic="2026-09-01 09:30"))
    metrik = S.karsilastir(ref, aday)
    assert metrik["ortak_bar"] == 0
    assert metrik["karar"].startswith("red")


def test_karar_esikleri_sabit():
    """Eşikler gizli değişmesin: karar kapısı bu üç sayıya bağlı."""
    assert S.ESIK_ORTak_BAR == 0.98
    assert S.ESIK_MEDYAN_FARK_PCT == 0.05
    assert S.ESIK_MAX_FARK_PCT == 0.50


# --------------------------------------------------------------- ARŞİV -----
def _arsiv_yaz(dizin, sembol, kapanislar):
    kayitlar = [{"timestamp": ts.isoformat(), "open": k, "high": k * 1.01,
                 "low": k * 0.99, "close": k,
                 "volume": 0.0 if i == 0 else 1000.0}
                for i, (ts, k) in enumerate(zip(
                    pd.date_range("2026-10-01 09:30", periods=len(kapanislar),
                                  freq="h", tz=IST), kapanislar))]
    (dizin / f"{sembol}.json").write_text(json.dumps(kayitlar), encoding="utf-8")


def test_arsiv_kalite_sayar(tmp_path):
    # 9 bar = 1 gün; 4s türetimi 3 bar üretir, üçüncüsü kısmi (1 saat)
    _arsiv_yaz(tmp_path, "THYAO", [10 + i for i in range(9)])
    rapor = S.arsiv_kalite(tmp_path, tf_dakika=240)
    assert rapor["sembol"] == 1
    assert rapor["toplam_bar"] == 9
    assert rapor["gun_bar_dagilimi"] == {9: 1}
    assert rapor["ilk_bar_etiketi"] == {"09:30:00": 1}
    assert rapor["turetilen_tf_bar"] == 3
    assert rapor["turetilen_tf_kismi"] == 1
    assert rapor["sifir_hacim_pct"] == pytest.approx(100 / 9, abs=0.1)


def test_arsiv_bozuk_dosya_raporu_dusurmez(tmp_path):
    _arsiv_yaz(tmp_path, "THYAO", [10, 11, 12])
    (tmp_path / "BOZUK.json").write_text("{bozuk", encoding="utf-8")
    rapor = S.arsiv_kalite(tmp_path)
    assert rapor["sembol"] == 1


# --------------------------------------------------------- CANLI AKIŞ ------
def test_canli_karsilastir_fake_saglayici(monkeypatch):
    ref = _seri([10, 11, 12])
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_ref", lambda s, tf, n: ref)
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_aday", lambda s, tf, n: ref * 1.0001)
    sonuc = S.canli_karsilastir(["THYAO"], ["1h"], referans="sahte_ref",
                                adaylar=["sahte_aday"])
    assert sonuc[0]["karar"] == "geç"
    assert sonuc[0]["ortak_bar"] == 3


def test_canli_karsilastir_ulasilamayan_saglayici(monkeypatch):
    def patla(s, tf, n):
        raise ConnectionError("TLS kapandı")
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_ref", patla)
    sonuc = S.canli_karsilastir(["THYAO"], ["1h"], referans="sahte_ref",
                                adaylar=["sahte_aday"])
    assert sonuc[0]["karar"].startswith("red")
    assert "ulaşılamadı" in sonuc[0]["karar"]


# --------------------------------------------------------------- RAPOR -----
def test_rapor_markdown_satirlari():
    metin = S.rapor_markdown([
        {"sembol": "THYAO", "tf": "1h", "ortak_bar": 360, "medyan_fark_pct": 0.012,
         "max_fark_pct": 0.3, "sifir_hacim_ref_pct": 10.8,
         "sifir_hacim_aday_pct": 1.2, "karar": "geç"},
    ])
    assert "| THYAO | 1h | 360 |" in metin
    assert "0,012" in metin          # Türkçe ondalık
    assert "| geç |" in metin


def test_cli_arsiv_modu_cikti_uretir(tmp_path, capsys):
    _arsiv_yaz(tmp_path, "THYAO", [10, 11, 12])
    cikti = tmp_path / "rapor.md"
    kod = S.main(["--mod", "arsiv", "--veri-dizini", str(tmp_path),
                  "--cikti", str(cikti)])
    assert kod == 0
    assert "Yerel arşiv kalitesi" in capsys.readouterr().out
    assert "sıfır hacim" in cikti.read_text(encoding="utf-8")
