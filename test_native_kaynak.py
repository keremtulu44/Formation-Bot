# -*- coding: utf-8 -*-
"""Native 1h/2h/4h/1d çekim zinciri için AĞSIZ regresyonlar.

Yahoo/TradingView'a tek istek atılmaz; sağlayıcı çağrıları sahte istemci ve
DataFrame ile değiştirilir. Amaç: 2h/4h'nin 1h'den resample edilmediğini,
manifest/probe/raporun kaynak/TF etiketlerini taşıdığını ve TV kurulumu
yokken betiğin fail-closed durduğunu kilitlemek.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts.backfill import native_kaynak as nk  # noqa: E402

_SCRIPT = KOK / "scripts" / "backfill" / "yahoo_backfill.py"


def _modul():
    spec = importlib.util.spec_from_file_location("native_yahoo_backfill_test_mod", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


yb = _modul()


def _frame(fiyat: float = 100.0, *, adet: int = 2, tz: str = "UTC") -> pd.DataFrame:
    idx = pd.date_range("2026-11-17 07:00", periods=adet, freq="h", tz=tz)
    return pd.DataFrame({
        "Symbol": ["THYAO"] * adet,
        "Open": [fiyat - 1] * adet,
        "High": [fiyat + 1] * adet,
        "Low": [fiyat - 2] * adet,
        "Close": [fiyat] * adet,
        "Volume": [1000.0] * adet,
    }, index=idx)


def _normalize_tv_frame(fiyat: float = 55.0, *, adet: int = 2) -> pd.DataFrame:
    """tv_ham_cek'in döndürdüğü biçim: UTC-aware index + lowercase OHLCV."""
    idx = pd.date_range("2026-11-17 07:00", periods=adet, freq="h", tz="UTC")
    return pd.DataFrame({
        "open": [fiyat - 1] * adet,
        "high": [fiyat + 1] * adet,
        "low": [fiyat - 2] * adet,
        "close": [fiyat] * adet,
        "volume": [1000.0] * adet,
    }, index=idx)


def _hizli_tempo():
    return yb.Tempo(
        grup=100,
        log=lambda *_: None,
        sleep_fn=lambda *_: None,
        uniform_fn=lambda *_a, **_k: 0.0,
        monotonic_fn=lambda: 0.0,
        soguma_suresi_sn=0.0,
    )


class _SahteTempo:
    def __init__(self, **_kwargs):
        self.dur = False
        self.toplam_istek = 0
        self.soguma_sayisi = 0

    def bekle(self):
        self.toplam_istek += 1

    def istek_bitti(self):
        return None

    def basarili(self):
        return None

    def gecici_hata(self, _sebep):
        return None


# ---------------------------------------------------------------------------
# Yardımcı modül sözleşmesi
# ---------------------------------------------------------------------------
def test_native_kaynak_modul_seviyesinde_agir_import_yok():
    """Termux'ta --help/list TV paketi kurulu olmadan da çalışabilmeli."""
    agac = ast.parse((KOK / "scripts/backfill/native_kaynak.py").read_text(encoding="utf-8"))
    yasakli = {"pandas", "numpy", "yfinance", "tvDatafeed"}
    ihlal = []
    for dugum in agac.body:
        if isinstance(dugum, ast.Import):
            ihlal += [a.name.split(".")[0] for a in dugum.names if a.name.split(".")[0] in yasakli]
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            if dugum.module.split(".")[0] in yasakli:
                ihlal.append(dugum.module.split(".")[0])
    assert not ihlal, ihlal


def test_kaynak_plani_dort_native_tf_ve_tv_araliklari():
    assert nk.ZAMAN_DILIMLERI == ("1h", "2h", "4h", "1d")
    assert nk.KAYNAK_PLANI == {
        "1h": "yahoo", "2h": "tvdatafeed", "4h": "tvdatafeed", "1d": "yahoo",
    }
    assert nk.TV_ARALIK["2h"] == "in_2_hour" and nk.TV_ARALIK["4h"] == "in_4_hour"
    ozet = nk.kaynak_plani_ozeti()
    assert [s["timeframe"] for s in ozet] == ["1h", "2h", "4h", "1d"]
    assert all(s["native"] is True for s in ozet)
    assert ozet[1]["kaynak"] == "tvdatafeed"
    assert ozet[1]["provider_interval"] == "in_2_hour"


def test_tv_sembol_eslemesi_ve_makro_kapsam_disi():
    assert nk.tv_sembol("THYAO") == "THYAO"
    assert nk.tv_sembol("XU30") == "XU030"
    assert nk.tv_sembol("BRENT") is None


@pytest.mark.parametrize("metin,beklenen", [
    ("Connection to remote host was lost", True),
    ("boş veya geçersiz sağlayıcı verisi", True),
    ("ReadTimeout: WS timeout", True),
    ("429 Too Many Requests", True),
    ("tvDatafeed kurulu değil", False),
    ("symbol not found", False),
    ("TV aralığı desteklenmiyor: 9h", False),
    ("beklenmedik bilinmeyen hata", False),
])
def test_tv_hata_siniflandirmasi(metin, beklenen):
    assert nk.tv_hata_gecici_mi(metin) is beklenen


def test_tv_ham_cek_utc_aware_yi_istanbula_cevirir_ve_kolonlari_normalize_eder(monkeypatch):
    cagri = {}

    class SahteClient:
        @staticmethod
        def get_hist(**kwargs):
            cagri.update(kwargs)
            return _frame(123.0, adet=3, tz="UTC")

    monkeypatch.setattr(nk, "tv_client_yukle", lambda: SahteClient())
    df, hata, gecici = nk.tv_ham_cek("THYAO", "2h", 7, exchange="BIST")
    assert hata == "" and gecici is False
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert str(df.index.tz) == "Europe/Istanbul"
    assert float(df.close.iloc[-1]) == 123.0
    assert cagri == {
        "symbol": "THYAO", "exchange": "BIST",
        "interval": "in_2_hour", "n_bars": 7,
    }
    df, hata, gecici = nk.tv_ham_cek("BRENT", "4h", 7)
    assert df is None and "BIST dışı" in hata and gecici is False


# ---------------------------------------------------------------------------
# Probe: iki sağlayıcı da doğrulanmadan sembol listeye girmez
# ---------------------------------------------------------------------------
def test_probe_yahoo_ve_tv_native_i_birlikte_dogrular(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "tv_hazirlik_raporu", lambda: {
        "hazir": True, "dagitim": "tradingview-datafeed", "surum": "2.1.1",
    })

    def sahte_yahoo(_ticker, _period, _interval):
        return _frame(10.0, adet=1), "", False

    def sahte_tv(sembol, interval, _n_bars, *, exchange):
        if sembol == "BAD":
            return None, "TV symbol not found", False
        return _frame(20.0, adet=1, tz="UTC"), "", False

    monkeypatch.setattr(yb, "_ham_cek", sahte_yahoo)
    monkeypatch.setattr(nk, "tv_ham_cek", sahte_tv)

    sonuc = yb.probe(
        ["THYAO", "BAD"], tmp_path, _hizli_tempo(), log=lambda *_: None,
        tv_bar_sayisi=5, tv_exchange="BIST",
    )
    assert sonuc["gecerli"] == ["THYAO"]
    assert "BAD" in sonuc["gecersiz"]
    assert sonuc["kaynak_plani"]["2h"] == "tvdatafeed"
    assert sonuc["tv_dagitim"]["hazir"] is True
    assert (tmp_path / "dogrulanmis_semboller.txt").read_text(encoding="utf-8") == "THYAO\n"
    rapor = json.loads((tmp_path / "probe_sonucu.json").read_text(encoding="utf-8"))
    assert rapor["mod"] == "native-karma"
    assert rapor["kaynak_ozeti"]["THYAO"] == {"yahoo": "ok", "tvdatafeed": "ok"}


# ---------------------------------------------------------------------------
# sembol_cek + main: dört native dosya, kaynak etiketli manifest/rapor
# ---------------------------------------------------------------------------
def test_sembol_cek_tv_native_dosya_yazar(tmp_path, monkeypatch):
    fake_nk = SimpleNamespace(
        KAYNAK_PLANI=nk.KAYNAK_PLANI,
        TV_ARALIK=nk.TV_ARALIK,
        TV_DISI_SEMBOLLER=nk.TV_DISI_SEMBOLLER,
        tv_sembol=lambda sembol: "THYAO",
    )

    def sahte_tv(sembol, interval, n_bars, *, exchange):
        assert (sembol, interval, n_bars, exchange) == ("THYAO", "4h", 11, "BIST")
        return _normalize_tv_frame(55.0, adet=2), "", False

    fake_nk.tv_ham_cek = sahte_tv
    monkeypatch.setattr(yb, "_native_kaynak_yukle", lambda: fake_nk)

    kayit = yb.sembol_cek(
        "THYAO", "4h", "", tmp_path, _SahteTempo(), deneme=1,
        log=lambda *_: None, tv_bar_sayisi=11, tv_exchange="BIST",
        kaynak="tvdatafeed",
    )
    assert kayit["durum"] == "ok"
    assert kayit["kaynak"] == "tvdatafeed" and kayit["native"] is True
    assert kayit["provider_interval"] == "in_4_hour"
    assert kayit["bar_sayisi_istek"] == 11
    assert kayit["dosya"] == "THYAO_4h.csv.gz"
    assert (tmp_path / "THYAO_4h.csv.gz").exists()


def test_main_dort_native_tf_yazar_ve_kaynak_raporu_uretur(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "tv_hazirlik_raporu", lambda: {
        "hazir": True, "dagitim": "tradingview-datafeed", "surum": "2.1.1",
    })
    monkeypatch.setattr(yb, "Tempo", _SahteTempo)

    def sahte_sembol_cek(sembol, interval, _period, hedef, _tempo, *, deneme,
                         log, tv_bar_sayisi, tv_exchange, kaynak):
        dosya = hedef / f"{sembol}_{interval}.csv.gz"
        dosya.write_bytes(b"native")
        return {
            "sembol": sembol, "interval": interval, "durum": "ok",
            "kaynak": kaynak, "native": True, "satir": 10,
            "dosya": dosya.name, "ilk_bar": "2026-01-01 09:30:00+03:00",
            "son_bar": "2026-01-01 12:30:00+03:00", "deneme": 1,
            "sure_sn": 0.1, "kalite": {},
        }

    monkeypatch.setattr(yb, "sembol_cek", sahte_sembol_cek)

    cikti = yb.main([
        "--hedef", str(tmp_path),
        "--semboller", "TEST",
        "--interval", "1h,2h,4h,1d",
        "--tv-bar-sayisi", "5",
    ])
    assert cikti == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["native_zorunlu"] is True
    assert manifest["arsiv_modu"] == "native"
    assert manifest["kaynak_plani"]["4h"] == "tvdatafeed"
    assert len(manifest["kayitlar"]) == 4
    assert all(v["durum"] == "ok" and v["native"] is True for v in manifest["kayitlar"].values())
    assert {v["kaynak"] for v in manifest["kayitlar"].values()} == {"yahoo", "tvdatafeed"}

    rapor = json.loads((tmp_path / "kaynak_raporu.json").read_text(encoding="utf-8"))
    assert rapor["arsiv_modu"] == "native" and rapor["native_zorunlu"] is True
    assert rapor["sembol_sayisi"] == 1
    assert rapor["beklenen_dosya_sayisi"] == 4
    assert rapor["diskteki_dosya_sayisi"] == 4
    assert rapor["eksik_dosya_sayisi"] == 0
    assert rapor["resample_kullanildi"] is False
    assert "4h|tvdatafeed|ok" in rapor["kayit_durum_ozeti"]


def test_main_tv_kurulum_yoksa_ag_cagrisi_yapmadan_durur(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "tv_hazirlik_raporu", lambda: {
        "hazir": False, "hata": "ModuleNotFoundError: tvDatafeed kurulu değil",
    })
    cikti = yb.main([
        "--hedef", str(tmp_path),
        "--semboller", "TEST",
    ])
    assert cikti == 2
    assert not (tmp_path / "manifest.json").exists()
