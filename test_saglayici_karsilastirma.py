# -*- coding: utf-8 -*-
"""Sağlayıcı karşılaştırma aracının sözleşmeleri (ağsız).

Araç canlı modda Yahoo/borsapy'ye gider; bu testler **ağa çıkmadan** mantığı
kilitler: normalize, karşılaştırma, karar kapısı, arşiv kalite sayımı ve
ulaşılamayan sağlayıcının rapora düşmesi.
"""
from __future__ import annotations

import json
import os
import sys
import types
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
    """Eşikler gizli değişmesin: karar kapısı bu sayılara bağlı."""
    assert S.ESIK_ORTAK_BAR == 0.98
    assert S.ESIK_ORTak_BAR == S.ESIK_ORTAK_BAR  # eski yazım geriye uyumlu
    assert S.ESIK_MEDYAN_FARK_PCT == 0.05
    assert S.ESIK_MAX_FARK_PCT == 0.50


def test_adayda_sifir_hacim_artisi_gec_kararini_engeller():
    ref = S.normalize(_seri([10, 11, 12], hacim=1000))
    aday_ham = _seri([10, 11, 12], hacim=1000)
    aday_ham.loc[aday_ham.index[0], "volume"] = 0

    metrik = S.karsilastir(ref, S.normalize(aday_ham))

    assert metrik["sifir_hacim_ref_pct"] == 0.0
    assert metrik["sifir_hacim_aday_pct"] > 0
    assert metrik["karar"].startswith("red")
    assert "sıfır hacim" in metrik["karar"]


def test_adayda_kisa_bar_artisi_gec_kararini_engeller():
    temel = {"ortak_oran": 1.0, "medyan_fark_pct": 0.0, "max_fark_pct": 0.0,
             "sifir_hacim_ref_pct": 0.0, "sifir_hacim_aday_pct": 0.0,
             "ref_kisa_pct": 0.0, "aday_kisa_pct": 5.0}

    assert "kısa bar" in S.karar_ver(temel)
    assert S.karar_ver({**temel, "aday_kisa_pct": 0.0}) == "geç"


def test_kalite_metrigi_eksikse_karar_capisi_cokmez():
    metrik = {"ortak_oran": 1.0, "medyan_fark_pct": 0.0, "max_fark_pct": 0.0,
              "sifir_hacim_ref_pct": None, "sifir_hacim_aday_pct": None}
    assert S.karar_ver(metrik) == "geç"


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
    # PyPI çatalı ve sabit GitHub dağıtımı ayrı adlarla raporlanmalı.
    assert "tvdatafeed" in bilgi["paketler"]
    assert "tradingview-datafeed" in bilgi["paketler"]
    assert "tv_surum_durumu" in bilgi
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


@pytest.mark.parametrize("ek_argumanlar,beklenen", [
    ([], False),
    (["--tanis-dene", "1"], True),
])
def test_cli_tanis_varsayilan_ag_siz(monkeypatch, capsys, ek_argumanlar, beklenen):
    """``--mod tanis`` ağ denemesini yalnızca açık bayrakla yapmalı."""
    temel = S.tani(kok="")
    yakalanan = {}

    def sahte_tani(**kwargs):
        yakalanan.update(kwargs)
        return dict(temel)

    monkeypatch.setattr(S, "tani", sahte_tani)
    assert S.main(["--mod", "tanis", *ek_argumanlar]) == 0
    assert yakalanan["dene"] is beklenen
    assert "Ortam teşhisi" in capsys.readouterr().out


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
    assert S._tv_aralik("4h") == "in_4_hour"
    with pytest.raises(ValueError, match="desteklenmiyor"):
        S._tv_aralik("5h")


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


def test_tvdatafeed_yoksa_iki_kurulum_ipucu_yazar():
    bilgi = S.tani(kok="")
    bilgi["importlar"]["tvdatafeed"] = "ModuleNotFoundError: No module named 'tvDatafeed'"
    bilgi["izler"]["tvdatafeed"] = ["ModuleNotFoundError: No module named 'tvDatafeed'"]

    metin = S.tani_markdown(bilgi)

    assert "tvDataFeed kurulu değil" in metin
    assert "tradingview-datafeed==2.1.1" in metin
    assert "rongardF/tvdatafeed@e6f6aaa7de43" in metin


def test_tvdatafeed_varsa_kurulum_ipucu_yazmaz():
    bilgi = S.tani(kok="")
    bilgi["importlar"]["tvdatafeed"] = "ok"
    bilgi["tv_surum_durumu"] = "ok"
    bilgi["tv_dagitim"] = "tradingview-datafeed"
    bilgi["tv_surum"] = "2.1.1"

    metin = S.tani_markdown(bilgi)
    assert "tvDataFeed kurulu değil" not in metin
    assert "doğrulandı" in metin


def test_tvdatafeed_ortak_istemci_utc_doner_ve_tz_bozulmaz(istanbul_tz, monkeypatch):
    """Ölçüm aracı naive TV damgasını İstanbul sanmamalı; normalize geri çevirmeli."""
    import importlib.metadata as package_metadata

    def fake_version(name):
        if name == "tradingview-datafeed":
            return "2.1.1"
        raise package_metadata.PackageNotFoundError(name)

    monkeypatch.setattr(package_metadata, "version", fake_version)
    istemciler = []
    cagri = {}

    class WS:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True

    class TV:
        def __init__(self):
            self.ws = WS()
            istemciler.append(self)
        def get_hist(self, **kwargs):
            cagri.update(kwargs)
            idx = pd.date_range("2026-11-02", periods=2, freq="4h")
            return pd.DataFrame({
                "Symbol": ["THYAO"] * 2, "Open": 100.0, "High": 101.0,
                "Low": 99.0, "Close": 100.5, "Volume": 1000,
            }, index=idx)

    modul = types.SimpleNamespace(
        TvDatafeed=TV,
        Interval=types.SimpleNamespace(in_1_hour="1H", in_2_hour="2H",
                                       in_4_hour="4H", in_daily="1D"),
    )
    monkeypatch.setitem(sys.modules, "tvDatafeed", modul)

    veri = S._tvdatafeed("THYAO", "4h", 2)

    assert str(veri.index.tz) == "UTC"
    assert veri.index[0] == pd.Timestamp("2026-11-01 21:00", tz="UTC")
    assert os.environ["TZ"] == "Europe/Istanbul"
    assert cagri["interval"] == "4H" and cagri["n_bars"] == 2
    assert istemciler[0].ws.closed is True
    norm = S.normalize(veri)
    assert norm.index[0] == pd.Timestamp("2026-11-02 00:00", tz=IST)


# ---------------- CANLI ÖLÇÜM (2026-11-18) REGRESYONLARI ------------------
def _coklu_kolon_seri(idx, kapanislar=(10.0, 11.0, 12.0)):
    """yfinance 1.7+ çıktısı: ``('Close','THYAO.IS')`` biçiminde MultiIndex."""
    return pd.DataFrame(
        [[k, k * 1.01, k * 0.99, k + 0.5, 1000] for k in kapanislar],
        index=idx,
        columns=pd.MultiIndex.from_tuples([
            ("Open", "THYAO.IS"), ("High", "THYAO.IS"), ("Low", "THYAO.IS"),
            ("Close", "THYAO.IS"), ("Volume", "THYAO.IS")]),
    )


def test_normalize_yfinance_multiindex_kolonlarini_duzlestirir():
    """Gerçek canlı çıktıdaki KeyError: str(tuple).lower() kolon adı değildir."""
    idx = pd.date_range("2026-11-02", periods=3, freq="D", tz=IST)
    df = S.normalize(_coklu_kolon_seri(idx))

    assert list(df.columns) == S.KOLONLAR
    assert df["close"].tolist() == [10.5, 11.5, 12.5]
    assert str(df.index.tz) == IST


def test_normalize_ticker_ilk_multiindex_kolonunu_da_duzlestirir():
    """Bazı yfinance sürümleri ('THYAO.IS','Close') sırasını kullanır."""
    idx = pd.date_range("2026-11-02", periods=3, freq="D", tz=IST)
    ham = _coklu_kolon_seri(idx)
    ham.columns = pd.MultiIndex.from_tuples([(b, a) for a, b in ham.columns])

    df = S.normalize(ham)

    assert list(df.columns) == S.KOLONLAR
    assert df["close"].tolist() == [10.5, 11.5, 12.5]


def test_yahoo_4s_turetimi_coklu_kolonla_patlamiyor(monkeypatch):
    """4s referansı türetilmeden önce normalize edilmeli; yoksa KeyError."""
    idx = pd.date_range("2026-11-02 09:30", periods=8, freq="h", tz=IST)
    ham = _coklu_kolon_seri(idx, tuple(range(10, 18)))
    sahte_yfinance = types.SimpleNamespace(
        Ticker=lambda ticker: types.SimpleNamespace(history=lambda **kw: ham))
    monkeypatch.setitem(sys.modules, "yfinance", sahte_yfinance)

    df = S._yahoo("THYAO", "4h", 0)

    assert df is not None and len(df) >= 1
    assert list(df.columns) == S.KOLONLAR
    assert str(df.index.tz) == IST


def _gunluk_barlar(kayma_saat=0):
    gunler = pd.date_range("2026-10-01", periods=5, freq="D", tz=IST)
    kapanis = [10.0, 11.0, 12.0, 13.0, 14.0]
    frame = pd.DataFrame({
        "open": kapanis, "high": [k + 1 for k in kapanis],
        "low": [k - 1 for k in kapanis], "close": kapanis,
        "volume": [1000] * len(kapanis),
    }, index=gunler)
    if kayma_saat:
        frame.index = frame.index + pd.Timedelta(hours=kayma_saat)
    return frame


def test_1g_tv_utc_kaymasi_damga_kesisimini_sifirlar_ama_gun_eslesir():
    """Yahoo 00:00 etiketi ↔ TV 00:00 UTC (= 03:00 İstanbul): aynı gün."""
    ref = _gunluk_barlar(0)
    aday = _gunluk_barlar(3)

    damga = S.karsilastir(ref, aday)
    assert damga["ortak_bar"] == 0                      # eski hatalı yol
    assert damga["ref_ilk_damga"] != damga["aday_ilk_damga"]

    gun = S.karsilastir_gunluk(ref, aday)
    assert gun["olcek"] == "gün"
    assert gun["ortak_bar"] == 5
    assert gun["karar"] == "geç"


def test_canli_1g_gun_izgarasina_duser(monkeypatch):
    """main'in 1g satırı artık karsilastir_gunluk kullanmalı (0 ortak bar yok)."""
    ref, aday = _gunluk_barlar(0), _gunluk_barlar(3)
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_ref", lambda s, tf, a: ref)
    monkeypatch.setitem(S.SAGLAYICILAR, "sahte_aday", lambda s, tf, a: aday)

    sonuc = S.canli_karsilastir(["GARAN"], ["1d"], referans="sahte_ref",
                                adaylar=["sahte_aday"])

    assert sonuc[0]["olcek"] == "gün"
    assert sonuc[0]["ortak_bar"] == 5
    assert sonuc[0]["karar"] == "geç"


def test_tani_sifir_bar_basari_sayilmaz():
    """'0 bar geldi ✅' operatörü yanlış yönlendirir; uyarı olmalı."""
    bilgi = {"python": "3.12.0", "onerilen_python": "3.11/3.12",
             "calisan_python": "python", "venv": None, "platform": "Windows",
             "paketler": {}, "importlar": {}, "surum_uyari": None,
             "denemeler": {"yahoo": {"bar": 0}}}

    metin = S.tani_markdown(bilgi)

    assert "0 bar geldi ✅" not in metin
    assert "0 bar" in metin and "⚠️" in metin and "başarı değil" in metin


def test_hizasizlik_ipucu_rapora_duser():
    metin = S.rapor_markdown([{
        "sembol": "GARAN", "tf": "1d", "ortak_bar": 0,
        "karar": "red (karşılaştırılabilir ortak bar yok)",
        "ref_ilk_damga": "2026-10-01 00:00:00+03:00",
        "aday_ilk_damga": "2026-10-01 03:00:00+03:00",
    }])
    assert "Zaman damgası hizası" in metin
    assert "03:00:00+03:00" in metin


def test_main_referans_secimini_aktarir(monkeypatch):
    """Yahoo boş döndüğünde operatör --referans ile çapraz kontrol edebilmeli."""
    yakalanan = {}

    def sahte_canli(semboller, tfs, adet=360, referans="yahoo", adaylar=()):
        yakalanan["referans"] = referans
        yakalanan["adaylar"] = list(adaylar)
        return []

    monkeypatch.setattr(S, "canli_karsilastir", sahte_canli)

    assert S.main(["--mod", "canli", "--tf", "1g", "--sembol", "GARAN",
                   "--aday", "tvdatafeed", "--referans", "borsapy"]) == 0
    assert yakalanan["referans"] == "borsapy"
    assert yakalanan["adaylar"] == ["tvdatafeed"]


def test_yahoo_ham_kapanis_ister_temettu_duzeltmesi_kapali(monkeypatch):
    """tvDatafeed 'splits' ayarlı; auto_adjust=True temettüyü de düzeltir.

    Canlı 2026-11-18 ölçümünde GARAN %4,04 / AKBNK %3,21 sabit fark (medyan
    == max, 206/360 gün) bu yüzden çıktı; elma ile armut kıyaslanıyordu.
    """
    idx = pd.date_range("2026-11-02 09:30", periods=3, freq="h", tz=IST)
    ham = _coklu_kolon_seri(idx, (10.0, 11.0, 12.0))
    cagri = {}

    class History:
        def __call__(self, **kw):
            cagri.update(kw)
            return ham

    sahte = types.SimpleNamespace(
        Ticker=lambda ticker: types.SimpleNamespace(history=History()))
    monkeypatch.setitem(sys.modules, "yfinance", sahte)

    assert S._yahoo("THYAO", "1d", 0) is not None
    assert cagri["auto_adjust"] is False
    assert cagri["actions"] is False


def test_gunluk_kalite_toleransi_bar_sayisindan_hesaplanir():
    ref = S.turet(_saatlik_gun(), 240)
    idx = pd.DatetimeIndex(["2026-11-02 10:00", "2026-11-02 14:00"]).tz_localize(IST)
    aday = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.0, "volume": 1000}, index=idx)

    metrik = S.karsilastir_gunluk(ref, aday, tf_dakika=240)

    assert metrik["kalite_tolerans_pct"] > S.ESIK_KALITE_TOLERANS_PCT
    assert "adayda kısa bar fazla" not in metrik["karar"]


def test_dinamik_tolerans_tek_bar_gurultusunu_yutar_ama_kotulesmeyi_yakalar():
    metrik = {"ortak_oran": 1.0, "medyan_fark_pct": 0.01,
              "max_fark_pct": 0.2, "sifir_hacim_ref_pct": 0.0,
              "sifir_hacim_aday_pct": 0.0,
              "ref_kisa_pct": 33.15, "aday_kisa_pct": 33.33,
              "kalite_tolerans_pct": 1.38}

    assert S.karar_ver(metrik) == "geç"          # canlı ölçümdeki 0,18 puan
    metrik["aday_kisa_pct"] = 50.0
    assert S.karar_ver(metrik) == "red (adayda kısa bar fazla)"


def test_karsilastir_kaymis_izgarada_sahte_ortak_bar_uretmez():
    """pandas'ın freq'li intersection hızlı yolu sahte eşleşme vermemeli.

    09:30 ızgarası ile 10:00 ızgarasının hiç ortak damgası yoktur; değer bazlı
    eşleşme 0 dönmeli, aksi halde olmayan fiyatlarla sahte "geç" üretilir.
    """
    idx = pd.date_range("2026-11-02 09:30", periods=6, freq="h", tz=IST)
    kapanis = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    ref = pd.DataFrame({
        "open": kapanis, "high": [k + 1 for k in kapanis],
        "low": [k - 1 for k in kapanis], "close": kapanis,
        "volume": [1000] * len(kapanis),
    }, index=idx)
    aday = ref.copy()
    aday.index = idx + pd.Timedelta(minutes=30)

    metrik = S.karsilastir(ref, aday)

    assert metrik["ortak_bar"] == 0
    assert metrik["medyan_fark_pct"] is None
    assert metrik["karar"].startswith("red")
