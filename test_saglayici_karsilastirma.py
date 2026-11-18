# -*- coding: utf-8 -*-
"""Sağlayıcı karşılaştırma aracının sözleşmeleri (ağsız).

Araç canlı modda Yahoo/borsapy'ye gider; bu testler **ağa çıkmadan** mantığı
kilitler: normalize, karşılaştırma, karar kapısı, arşiv kalite sayımı ve
ulaşılamayan sağlayıcının rapora düşmesi.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

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


def test_hata_metni_sebebi_de_yazar():
    """'red (SyntaxError)' tek başına teşhis edilemez; mesaj da rapora girmeli."""
    metin = S._hata_metni(SyntaxError("invalid syntax (f-string)"))
    assert metin.startswith("SyntaxError:")
    assert "invalid syntax" in metin
    assert len(S._hata_metni(ValueError("x" * 900))) <= 160


def test_tani_ortam_bilgisi_verir():
    bilgi = S.tani()
    assert bilgi["python"].count(".") == 2
    assert set(bilgi["importlar"]) == {"yfinance", "borsapy", "tvdatafeed"}
    # Python <3.10 ise uyarı metni dolu olmalı, aksi halde boş
    assert (bilgi["surum_uyari"] is None) == (tuple(map(int, bilgi["python"].split(".")[:2])) >= (3, 10))
    metin = S.tani_markdown(bilgi)
    assert "Python:" in metin and "Import:" in metin


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


def test_liste_virgul_ve_bosluk_ayracini_birlestirir():
    """PowerShell virgülü ayırır; her iki yazım da aynı listeye inmeli."""
    assert S._liste(["THYAO,GARAN", "AKBNK"]) == ["THYAO", "GARAN", "AKBNK"]
    assert S._liste(["THYAO", "GARAN"]) == ["THYAO", "GARAN"]
    assert S._liste(["1g,1s"]) == ["1g", "1s"]


def test_cli_arsiv_modu_cikti_uretir(tmp_path, capsys):
    _arsiv_yaz(tmp_path, "THYAO", [10, 11, 12])
    cikti = tmp_path / "rapor.md"
    kod = S.main(["--mod", "arsiv", "--veri-dizini", str(tmp_path),
                  "--cikti", str(cikti)])
    assert kod == 0
    assert "Yerel arşiv kalitesi" in capsys.readouterr().out
    assert "sıfır hacim" in cikti.read_text(encoding="utf-8")


def test_cakisma_isareti_kalan_dosyayi_bulur(tmp_path):
    """Yarım merge 'SyntaxError' gibi görünür; tanı dosyayı adıyla söylemeli."""
    (tmp_path / "bozuk.py").write_text("x = 1\n" + "<" * 7 + " HEAD\ny = 2\n", encoding="utf-8")
    (tmp_path / "temiz.py").write_text("x = 1\n", encoding="utf-8")

    bulunan = S.cakisma_dosyalari(tmp_path)

    assert [Path(p).name for p in bulunan] == ["bozuk.py"]
    bilgi = S.tani(kok=str(tmp_path))
    assert "bozuk.py" in S.tani_markdown(bilgi)


def test_cakisma_yoksa_temiz_der(tmp_path):
    (tmp_path / "temiz.py").write_text("x = 1\n", encoding="utf-8")
    assert S.cakisma_dosyalari(tmp_path) == []
    assert "yok (çalışma ağacı temiz)" in S.tani_markdown(S.tani(kok=str(tmp_path)))


def test_tani_deneme_hatasini_iziyle_yazar():
    def patlayan(sembol, tf, adet):
        raise SyntaxError("invalid syntax (config.py, line 3)")

    bilgi = S.tani(dene=True, kok="", saglayicilar={"yahoo": patlayan})

    assert bilgi["denemeler"]["yahoo"]["hata"].startswith("SyntaxError:")
    assert bilgi["denemeler"]["yahoo"]["izi"], "hata izi boş olmamalı"
    metin = S.tani_markdown(bilgi)
    assert "Deneme yahoo: SyntaxError:" in metin


def test_tani_ceken_saglayiciyi_bar_sayisiyla_isaretler():
    def calisan(sembol, tf, adet):
        idx = pd.date_range("2026-11-02", periods=5, freq="D", tz=S.ISTANBUL)
        return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5,
                             "close": 1.5, "volume": 10}, index=idx)

    bilgi = S.tani(dene=True, kok="", saglayicilar={"borsapy": calisan})

    assert bilgi["denemeler"]["borsapy"] == {"bar": 5}
    assert "5 bar geldi" in S.tani_markdown(bilgi)


# ------------------------------------------------------------- 2s / 4s -----
def _saatlik_gun(gun: str = "2026-11-02", bar: int = 9):
    """09:30–17:30 arası 1 saatlik barlar (BIST seansı)."""
    idx = pd.date_range(f"{gun} 09:30", periods=bar, freq="h", tz=IST)
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.0, "volume": 1000}, index=idx)


def test_tf_kodu_turkce_yazimi_cevirir():
    assert S.tf_kodu("1g") == "1d"
    assert S.tf_kodu("1s") == "1h"
    assert S.tf_kodu("2s") == "2h"
    assert S.tf_kodu("4s") == "4h"
    assert S.tf_kodu(" 4S ") == "4h"
    with pytest.raises(ValueError, match="bilinmeyen zaman dilimi"):
        S.tf_kodu("3s")


def test_turet_4s_gun_basina_uc_bar_verir():
    """9 saatlik bar → 2 tam 4s + gün sonunda 40 dakikalık kısa bar."""
    dort = S.turet(_saatlik_gun(), 240)

    assert len(dort) == 3
    assert [str(t.time()) for t in dort.index] == ["09:30:00", "13:30:00", "17:30:00"]
    assert S.bar_kapsama_dk(dort, 240) == [240, 240, 40]
    assert S.kisa_bar_orani(dort, 240) == pytest.approx(33.33, abs=0.01)


def test_turet_2s_gun_basina_bes_bar_verir():
    iki = S.turet(_saatlik_gun(), 120)

    assert len(iki) == 5
    assert S.kisa_bar_orani(iki, 120) == pytest.approx(20.0, abs=0.01)


def test_gercek_4s_barlari_kisa_saymaz():
    """TradingView gerçek 4h: 10:00 ve 14:00 → ikisi de tam, kısa bar yok."""
    idx = pd.DatetimeIndex(["2026-11-02 10:00", "2026-11-02 14:00"]).tz_localize(IST)
    gercek = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                           "close": 100.0, "volume": 1000}, index=idx)

    assert S.bar_kapsama_dk(gercek, 240) == [240, 240]
    assert S.kisa_bar_orani(gercek, 240) == 0.0


def test_gunluk_karsilastirma_fiyat_uyumunu_olcer():
    """Farklı kova ızgarasındaki iki kaynak gün bazında karşılaştırılır."""
    ref = S.turet(_saatlik_gun(), 240)
    idx = pd.DatetimeIndex(["2026-11-02 10:00", "2026-11-02 14:00"]).tz_localize(IST)
    aday = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.5, "volume": 5000}, index=idx)

    metrik = S.karsilastir_gunluk(ref, aday, tf_dakika=240)

    assert metrik["olcek"] == "gün"
    assert metrik["ortak_bar"] == 1                 # aynı gün
    assert metrik["medyan_fark_pct"] == pytest.approx(0.5, abs=0.01)
    assert metrik["aday_kisa_pct"] == 0.0
    assert metrik["ref_kisa_pct"] == pytest.approx(33.33, abs=0.01)


def test_borsapy_2s_4s_desteklemedigini_soyler():
    with pytest.raises(ValueError, match="borsapy 2s/4s vermiyor"):
        S._borsapy("THYAO", "4h", 10)


def test_tvdatafeed_aralik_eslemesi():
    assert S.TV_ARALIK == {"1h": "in_1_hour", "2h": "in_2_hour",
                           "4h": "in_4_hour", "1d": "in_daily"}


def test_canli_4s_gun_olcegine_duser(monkeypatch):
    """2s/4s karşılaştırması gün ızgarasında yapılmalı (damga damga değil)."""
    ref = S.turet(_saatlik_gun(), 240)
    idx = pd.DatetimeIndex(["2026-11-02 10:00", "2026-11-02 14:00"]).tz_localize(IST)
    aday = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.0, "volume": 1000}, index=idx)
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_ref", lambda s, tf, a: ref)
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_aday", lambda s, tf, a: aday)

    sonuc = S.canli_karsilastir(["THYAO"], ["4h"], referans="sahte_ref",
                                adaylar=["sahte_aday"])

    assert sonuc[0]["olcek"] == "gün"
    assert sonuc[0]["karar"] == "geç"


def test_tvdatafeed_yoksa_kurulum_ipucu_yazar():
    bilgi = S.tani(kok="")
    bilgi["importlar"]["tvdatafeed"] = "ModuleNotFoundError: No module named 'tvDatafeed'"
    bilgi["izler"]["tvdatafeed"] = ["ModuleNotFoundError: No module named 'tvDatafeed'"]

    metin = S.tani_markdown(bilgi)

    assert "tvDataFeed kurulu değil" in metin
    assert "rongardF/tvdatafeed@e6f6aaa7de43" in metin


def test_tvdatafeed_varsa_kurulum_ipucu_yazmaz():
    bilgi = S.tani(kok="")
    bilgi["importlar"]["tvdatafeed"] = "ok"

    assert "tvDataFeed kurulu değil" not in S.tani_markdown(bilgi)
