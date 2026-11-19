#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIST arşivi için NATIVE 1h/2h/4h/1d kaynak planı ve TV çekim yardımcısı.

Yahoo ``2h``/``4h`` intervalini desteklemediği için bu iki zaman dilimi
TradingView/tvDatafeed WS üzerinden **kendi mumları** olarak çekilir. Yahoo
yalnız ``1h`` ve ``1d`` için kullanılır. Bu modül ağır bağımlılıkları modül
seviyesinde import ETMEZ: ``--help``/liste modları ve ağsız testler çıplak
yorumlayıcıda çalışabilir.

Çıktı sözleşmesi: tüm sağlayıcılar Europe/Istanbul (+03:00) tz-aware
``DatetimeIndex`` ve ``open/high/low/close/volume`` kolonları döndürür. 1h'den
resample YOKTUR; türetilmiş bar üretilmez.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ZAMAN_DILIMLERI: tuple[str, ...] = ("1h", "2h", "4h", "1d")

#: Her TF'nin NATIVE sağlayıcısı. Bu eşleme manifest, probe ve arşiv
#: okuyucusunda aynı etiketi taşır.
KAYNAK_PLANI: dict[str, str] = {
    "1h": "yahoo",
    "2h": "tvdatafeed",
    "4h": "tvdatafeed",
    "1d": "yahoo",
}

#: tvDatafeed ``Interval`` enum üyelerinin ADLARI.
TV_ARALIK: dict[str, str] = {
    "1h": "in_1_hour",
    "2h": "in_2_hour",
    "4h": "in_4_hour",
    "1d": "in_daily",
}

TV_VARSAYILAN_EXCHANGE = "BIST"

#: BIST endekslerinde TradingView sembolü Yahoo ticker'ından farklı olabilir.
TV_SEMBOL_ESLEMESI: dict[str, str] = {
    "XU30": "XU030",
    "XU030": "XU030",
    "XU100": "XU100",
}

#: BIST exchange'inde karşılığı olmayan makro semboller. Yahoo 1h/1d verse
#: bile native 2h/4h seti tamamlanamayacağı için probe bunları doğrulanmış
#: listeye ALMAZ; ``research.arsiv`` de dört dosyası olmayan sembolü replay'e
#: sokmaz.
TV_DISI_SEMBOLLER: dict[str, str] = {
    "BRENT": "BIST dışı makro; TradingView BIST exchange'inde native 2h/4h karşılığı yok",
}

_GECICI_ISARETLER = (
    "timeout", "timed out", "connection", "remotedisconnected", "remote end closed",
    "websocket", "ws ", "closed", "lost", "no data", "boş", "geçersiz",
    "429", "500", "502", "503", "504", "temporarily", "temporary",
    "name resolution", "getaddrinfo", "ssl", "eof", "protocol", "max retries",
    "incomplete read", "chunkedencoding",
)
_KALICI_ISARETLER = (
    "symbol not found", "not found", "404", "aralığı desteklenmiyor",
    "doğrulanmamış", "kurulu değil", "import edilemedi", "eksik OHLCV",
    "naive zaman", "kapsam dışı",
)


def _repo_koku() -> Path:
    return Path(__file__).resolve().parents[2]


def tv_client_yukle():
    """Ortak ``scripts.tvdatafeed_client`` modülünü lazy yükler.

    Betik ``python scripts/backfill/yahoo_backfill.py`` ile çalıştırıldığında
    ``sys.path[0]`` script dizinidir; repo kökünü eklemeden ``scripts`` namespace
    paketi bulunamaz. Süreç TZ'si değiştirilmez.
    """
    kok = str(_repo_koku())
    if kok not in sys.path:
        sys.path.insert(0, kok)
    try:
        from scripts import tvdatafeed_client
    except Exception as exc:  # noqa: BLE001 - kurulum hatası rapora düşsün
        raise RuntimeError(
            "tvdatafeed istemcisi yüklenemedi; "
            "python -m pip install tradingview-datafeed==2.1.1 websocket-client==1.9.2"
        ) from exc
    return tvdatafeed_client


def tv_dagitim() -> dict[str, str]:
    """Doğrulanmış TV dağıtımını döndürür; kurulu değilse hata verir."""
    ad, surum = tv_client_yukle().dogrulanmis_surum()
    return {"dagitim": ad, "surum": surum}


def tv_hazirlik_raporu() -> dict[str, Any]:
    """Probe/manifest için kurulum teşhisi; ağ çağrısı yapmaz."""
    try:
        return {"hazir": True, **tv_dagitim()}
    except Exception as exc:  # noqa: BLE001 - teşhis sonucu olarak döner
        return {"hazir": False, "hata": f"{type(exc).__name__}: {exc}"}


def tv_sembol(sembol: str) -> str | None:
    """Repo sembolünü TradingView BIST sembolüne çevirir; kapsam dışı -> None."""
    anahtar = str(sembol or "").strip().upper()
    if anahtar in TV_DISI_SEMBOLLER:
        return None
    return TV_SEMBOL_ESLEMESI.get(anahtar, anahtar)


def tv_hata_gecici_mi(metin: str) -> bool:
    """TV WS hatalarını sınıflandırır; bilinmeyen hata kalıcı sayılır."""
    t = str(metin or "").lower()
    if any(m in t for m in _KALICI_ISARETLER):
        return False
    return any(m in t for m in _GECICI_ISARETLER)


def kaynak_plani_ozeti() -> list[dict[str, Any]]:
    """Manifest/probe raporunda taşınacak kaynak/TF etiketleri."""
    satirlar: list[dict[str, Any]] = []
    for tf in ZAMAN_DILIMLERI:
        kaynak = KAYNAK_PLANI[tf]
        satirlar.append({
            "timeframe": tf,
            "kaynak": kaynak,
            "native": True,
            "provider_interval": TV_ARALIK[tf] if kaynak == "tvdatafeed" else tf,
        })
    return satirlar


def tv_ham_cek(
    sembol: str,
    interval: str,
    n_bars: int,
    *,
    exchange: str = TV_VARSAYILAN_EXCHANGE,
) -> tuple[Any | None, str, bool]:
    """Tek native TV isteği: (DataFrame|None, hata_metni, gecici_mi).

    Ortak istemci UTC-aware döndürür; burada İstanbul'a çevrilir. Kolonlar
    normalize edilir, ``symbol`` gibi fazla kolonlar atılır, tz'siz/boş/eksik
    OHLCV yanıtı sessizce kabul edilmez.
    """
    import pandas as pd

    anahtar = str(interval or "").strip().lower()
    if anahtar not in TV_ARALIK:
        return None, f"TV aralığı desteklenmiyor: {interval!r}", False
    tv_symbol = tv_sembol(sembol)
    if tv_symbol is None:
        sebep = TV_DISI_SEMBOLLER.get(str(sembol or "").strip().upper(), "TV kapsam dışı")
        return None, sebep, False
    try:
        ham = tv_client_yukle().get_hist(
            symbol=tv_symbol,
            exchange=exchange,
            interval=TV_ARALIK[anahtar],
            n_bars=max(1, int(n_bars)),
        )
    except Exception as exc:  # noqa: BLE001 - ağ/kurulum hatası rapora düşsün
        sebep = f"{type(exc).__name__}: {exc}"
        return None, sebep, tv_hata_gecici_mi(sebep)

    if ham is None or not isinstance(ham, pd.DataFrame) or len(ham) == 0:
        return None, "TV boş veri döndürdü", True
    if not isinstance(ham.index, pd.DatetimeIndex):
        return None, "TV DatetimeIndex döndürmedi", False
    veri = ham.copy()
    veri.columns = [str(c).strip().lower() for c in veri.columns]
    if "symbol" in veri.columns:
        veri = veri.drop(columns=["symbol"])
    gerekli = ["open", "high", "low", "close", "volume"]
    eksik = [c for c in gerekli if c not in veri.columns]
    if eksik:
        return None, f"TV eksik OHLCV sütunları: {eksik}", False
    veri = veri[gerekli]
    if veri.index.tz is None:
        return None, "TV naive zaman damgası reddedildi (UTC-aware zorunlu)", False
    try:
        veri.index = veri.index.tz_convert("Europe/Istanbul")
    except Exception as exc:  # noqa: BLE001
        return None, f"TV zaman dilimi dönüşümü başarısız: {type(exc).__name__}: {exc}", False
    veri = veri[~veri.index.duplicated(keep="first")].sort_index()
    if len(veri) == 0:
        return None, "TV temizlik sonrası boş", True
    return veri, "", False


__all__ = [
    "ZAMAN_DILIMLERI", "KAYNAK_PLANI", "TV_ARALIK", "TV_VARSAYILAN_EXCHANGE",
    "TV_SEMBOL_ESLEMESI", "TV_DISI_SEMBOLLER", "tv_client_yukle", "tv_dagitim",
    "tv_hazirlik_raporu", "tv_sembol", "tv_hata_gecici_mi",
    "kaynak_plani_ozeti", "tv_ham_cek",
]
