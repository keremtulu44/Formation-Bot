# -*- coding: utf-8 -*-
"""tvDatafeed erişimi için tek, güvenli yardımcı katman (2026-11-18).

Neden ayrı modül: ``tvDatafeed`` 2.1.x ailesi POSIX bar zamanlarını
``datetime.fromtimestamp`` ile **çalışan makinenin yerel saati** olarak, TZ
bilgisi olmadan döndürür. Ölçüm aracı bu naive damgayı doğrudan İstanbul
sanmış, çapraz piyasa arşivi ise süreç genelinde ``TZ=UTC`` değiştirerek
düzeltmeye çalışmıştı. İkinci yol Windows'ta (``time.tzset`` yok) çalışmaz ve
çok iş parçacıklı kullanımda süreç TZ'sini bozar.

Bu yardımcı:

* yalnızca doğrulanmış iki dağıtımı kabul eder (PyPI çatallaması ve sabit
  GitHub commit'i; ikisi de aynı ``tvDatafeed`` import adını sağlar),
* naive yerel damgayı ``dateutil.tz.tzlocal()`` ile gerçek UTC'ye çevirir
  (süreç TZ'sini DEĞİŞTİRMEZ; POSIX/Windows aynı davranır),
* tz-aware dönen yeni sürümleri de UTC'ye çevirir,
* her çağrıdan sonra açık kalan WebSocket'i kapatır.

2026-11-18 itibarıyla üretim `data/fetch.py` da bu modülü kullanır: Yahoo
birincil sağlayıcı veri döndürmediğinde reaktif TV yedeği olarak çağrılır
(yalnızca o durumda; Yahoo başarılıyken hiçbir WS açılmaz). Ölçüm ve araştırma
arşivi scriptleri de aynı yardımcıyı kullanır.
"""
from __future__ import annotations

import logging
from importlib import metadata as _metadata
from typing import Dict, Tuple

import pandas as pd
from dateutil.tz import tzlocal

LOGGER = logging.getLogger(__name__)

IMPORT_MODULU = "tvDatafeed"

#: Doğrulanmış dağıtım adı -> kabul edilen sürümler. PyPI'de ``tvdatafeed``
#: adıyla paket YOK; aynı import modülünü sağlayan çatalın adı farklıdır.
#: Sabit GitHub commit'inin ``setup.py`` sürümü 2.1.0'dır.
BILINEN_DAGITIMLAR: Dict[str, set[str]] = {
    "tvdatafeed": {"2.1.0"},
    "tradingview-datafeed": {"2.1.1"},
}

KURULUM_IPUCLARI = (
    "python -m pip install tradingview-datafeed==2.1.1",
    'python -m pip install "git+https://github.com/rongardF/tvdatafeed@e6f6aaa7de43"',
)

# Anonim WS tek seferde "Connection to remote host was lost / no data"
# döndürebiliyor (2026-11-18 EREGL 4h). Sınırlı, yeni istemcili bir yeniden
# deneme; sonsuz döngü yok, her denemede WS kapatılır.
DENEME_SINIRI = 2


def _gecerli_cerceve(ham) -> bool:
    """Boş/None/DataFrame-olmayan yanıtı sessizce kabul etme."""
    return (ham is not None and isinstance(ham, pd.DataFrame)
            and isinstance(ham.index, pd.DatetimeIndex) and len(ham) > 0)


def surumleri_oku() -> Dict[str, str]:
    """Bilinen dağıtımların kurulu sürümlerini teşhis için döndürür."""
    bulunan: Dict[str, str] = {}
    for ad in BILINEN_DAGITIMLAR:
        try:
            bulunan[ad] = _metadata.version(ad)
        except _metadata.PackageNotFoundError:
            continue
    return bulunan


def dogrulanmis_surum() -> Tuple[str, str]:
    """``(dağıtım, sürüm)`` döndürür; doğrulanmamış kurulumda hata verir."""
    bilinmeyen = []
    for ad, surumler in BILINEN_DAGITIMLAR.items():
        try:
            surum = _metadata.version(ad)
        except _metadata.PackageNotFoundError:
            continue
        if surum in surumler:
            return ad, surum
        bilinmeyen.append(f"{ad}=={surum}")
    ipucu = " veya ".join(f"`{komut}`" for komut in KURULUM_IPUCLARI)
    if bilinmeyen:
        raise RuntimeError(
            f"doğrulanmamış tvDatafeed dağıtımı: {', '.join(bilinmeyen)}; {ipucu}"
        )
    raise ModuleNotFoundError(f"tvDatafeed kurulu değil; {ipucu}")


def _ws_kapat(client) -> None:
    """Üçüncü taraf istemcinin açık WebSocket'ini sonuçtan bağımsız kapat."""
    ws = getattr(client, "ws", None)
    if ws is None:
        return
    try:
        ws.close()
    except Exception as exc:  # noqa: BLE001 - kapanış hatası veri sonucunu değiştirmemeli
        LOGGER.debug("tvDatafeed WebSocket kapanış hatası: %s", exc)


def get_hist(
    *,
    symbol: str,
    exchange: str = "BIST",
    interval: str = "in_daily",
    n_bars: int = 500,
) -> pd.DataFrame:
    """TradingView geçmişini UTC-aware ``DatetimeIndex`` ile döndürür.

    ``interval`` ``Interval`` enum üyesinin ADIDIR (örn. ``in_4_hour``).
    Boş/geçersiz yanıt, doğrulanmamış sürüm veya kapalı bağlantı sessizce
    kabul edilmez; çağıran hata olarak raporlar.
    """
    dogrulanmis_surum()
    try:
        from tvDatafeed import Interval, TvDatafeed
    except ImportError as exc:
        raise ModuleNotFoundError(
            "tvDatafeed import edilemedi; " + " veya ".join(
                f"`{komut}`" for komut in KURULUM_IPUCLARI
            )
        ) from exc
    try:
        aralik = getattr(Interval, interval)
    except AttributeError as exc:
        raise ValueError(f"tvDatafeed aralığı desteklenmiyor: {interval}") from exc

    ham = None
    son_hata: Exception | None = None
    for deneme in range(1, DENEME_SINIRI + 1):
        client = None
        try:
            client = TvDatafeed()  # Anonim: kullanıcı adı/parola/token istenmez.
            ham = client.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=aralik,
                n_bars=n_bars,
            )
            son_hata = None
        except Exception as exc:  # noqa: BLE001 - ağ hatası rapora düşsün
            ham = None
            son_hata = exc
        finally:
            _ws_kapat(client)
        if _gecerli_cerceve(ham):
            break
        if deneme < DENEME_SINIRI:
            LOGGER.warning(
                "tvDatafeed %s/%s deneme %s/%s boş/hatalı (%s); yeniden deneniyor",
                symbol, exchange, deneme, DENEME_SINIRI,
                son_hata or "boş yanıt")

    if son_hata is not None:
        raise son_hata
    if not _gecerli_cerceve(ham):
        raise ValueError("boş veya geçersiz sağlayıcı verisi")

    veri = ham.copy()
    idx = pd.DatetimeIndex(veri.index)
    if idx.tz is None:
        # 2.1.x: datetime.fromtimestamp → yerel naive duvar saati. Yerel TZ'yi
        # süreç genelinde değiştirmeden o duvar saatini gerçek UTC'ye çevir.
        idx = idx.tz_localize(
            tzlocal(), ambiguous="NaT", nonexistent="shift_forward"
        ).tz_convert("UTC")
        gecerli = ~idx.isna()
        if not gecerli.all():
            veri = veri.loc[gecerli].copy()
            idx = idx[gecerli]
    else:
        idx = idx.tz_convert("UTC")
    veri.index = idx
    veri.columns = [str(c).strip().lower() for c in veri.columns]
    return veri
