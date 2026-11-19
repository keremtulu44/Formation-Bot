"""``backfill_data/`` NATIVE arşivini ölçüm için çerçevelere çevirir.

Yeni arşiv 1h/2h/4h/1d için **dört ayrı native CSV.gz** taşır:

    1h  -> Yahoo
    2h  -> TradingView/tvDatafeed
    4h  -> TradingView/tvDatafeed
    1d  -> Yahoo

Eski koşularda 2h/4h ``data.resample_ohlcv`` ile 1h'den türetiliyordu; bu,
özellikle hacim ve açılış/kapanış fiyatlarında sağlayıcının gerçek mumundan
sapan bir kayma üretiyordu. Yeni ``manifest.json`` ``native_zorunlu=True`` ve
``arsiv_modu="native"`` taşır; ``tf_frame`` bu modda 2h/4h için **yalnız**
``<SEM>_2h.csv.gz`` / ``<SEM>_4h.csv.gz`` dosyalarını okur, eksikse açık hata
verir. Replay/rapor scriptleri ``legacy_resample=False`` ile çağırır; hiçbir
yeni ölçüm 1h'den türetilmiş 2h/4h barı görmez.

Geriye dönük uyumluluk: manifesti eski (native etiketsiz) arşivlerde doğrudan
``tf_frame`` çağıran eski yardımcı scriptler için 2h/4h fallback'i varsayılan
olarak açık kalır. Bu, yeni replay girdisinin bir parçası DEĞİLDİR;
``arsiv_modu() == "native"`` olan arşivde fallback otomatik kapalıdır ve
``legacy_resample=False`` her koşulda strict davranır.

``BRENT`` havuzlanmış (cross-symbol) istatistikten çıkarılır: BIST seans yapısı
taşımadığı için seansa hizalı ölçümler onda anlamsızdır. Ayrıca BIST
exchange'inde native 2h/4h karşılığı olmadığından yeni native sembol setine
alınmaz.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = [
    "ARASTIRMA_TIMEFRAMELERI",
    "KAYNAK_INTERVAL",
    "KAYNAK_PLANI",
    "HAVUZ_DISI_SEMBOLLER",
    "arsiv_koku",
    "manifest_oku",
    "arsiv_modu",
    "arsiv_kaynak_plani",
    "arsiv_sembolleri",
    "ham_frame",
    "tf_frame",
    "temizle",
]

#: Ölçüm yapılacak zaman dilimleri. Rapor her biri için ayrı üretilir.
ARASTIRMA_TIMEFRAMELERI: tuple[str, ...] = ("1h", "2h", "4h", "1d")

#: Her zaman diliminin hangi NATIVE arşiv intervalinden okunduğu (identity).
KAYNAK_INTERVAL: dict[str, str] = {tf: tf for tf in ARASTIRMA_TIMEFRAMELERI}

#: Native sağlayıcı etiketleri. Backfill manifestindeki planla birebir aynıdır.
KAYNAK_PLANI: dict[str, str] = {
    "1h": "yahoo",
    "2h": "tvdatafeed",
    "4h": "tvdatafeed",
    "1d": "yahoo",
}

#: Havuzlanmış istatistiğe katılmayan semboller ve gerekçeleri.
HAVUZ_DISI_SEMBOLLER: dict[str, str] = {
    "BRENT": "BIST seans yapısı yok; ~24s işlem, günde 23 bar",
}

_ONTAMPI = Path(__file__).resolve().parent.parent
_OBELLEK: dict[tuple[str, str, str, int, int], pd.DataFrame] = {}


def arsiv_koku(kok: str | Path | None = None) -> Path:
    """Arşiv kökünü döndürür. ``FB_ARSIV_KOKU`` ortam değişkeniyle ezilebilir."""
    import os

    if kok is not None:
        return Path(kok)
    ortam = os.environ.get("FB_ARSIV_KOKU")
    if ortam:
        return Path(ortam)
    return _ONTAMPI / "backfill_data"


def manifest_oku(kok: str | Path | None = None) -> dict[str, Any]:
    """``manifest.json`` içeriğini döndürür; yoksa ya da bozuksa boş sözlük."""
    return temizle_json(arsiv_koku(kok) / "manifest.json") or {}


def arsiv_modu(kok: str | Path | None = None) -> str:
    """``"native"`` veya ``"legacy"``.

    Yeni backfill manifesti üç işaretten biriyle native sayılır:
    ``native_zorunlu=True``, ``arsiv_modu="native"`` veya ``surum="native-*"``.
    Eski 1h+1d arşivlerinde manifestte bunlar yoktur; legacy uyumluluk modu
    döner.
    """
    meta = manifest_oku(kok)
    if meta.get("native_zorunlu") is True:
        return "native"
    if str(meta.get("arsiv_modu", "")).strip().lower() == "native":
        return "native"
    if str(meta.get("surum", "")).strip().lower().startswith("native-"):
        return "native"
    return "legacy"


def arsiv_kaynak_plani(kok: str | Path | None = None) -> dict[str, str]:
    """Manifestteki kaynak planını döndürür; yoksa yerel varsayılan plan."""
    plan = manifest_oku(kok).get("kaynak_plani")
    if isinstance(plan, dict) and all(tf in plan for tf in ARASTIRMA_TIMEFRAMELERI):
        return {tf: str(plan[tf]) for tf in ARASTIRMA_TIMEFRAMELERI}
    return dict(KAYNAK_PLANI)


def arsiv_sembolleri(
    kok: str | Path | None = None,
    *,
    native_only: bool | None = None,
) -> list[str]:
    """Arşivde ölçülebilecek sembolleri alfabetik döndürür.

    Native arşivde bir sembolün **dört** dosyasının da bulunması şarttır; eksik
    2h/4h dosyası olan sembol sessizce replay'e alınmaz. Eski manifestli
    arşivlerde (veya açık ``native_only=False``) 1h dosyası yeterlidir.
    """
    root = arsiv_koku(kok)
    if not root.exists():
        return []
    if native_only is None:
        native_only = arsiv_modu(kok) == "native"
    if not native_only:
        return sorted(p.name[: -len("_1h.csv.gz")] for p in root.glob("*_1h.csv.gz"))
    kumeler = [
        {
            p.name[: -len(f"_{tf}.csv.gz")]
            for p in root.glob(f"*_{tf}.csv.gz")
        }
        for tf in ARASTIRMA_TIMEFRAMELERI
    ]
    if not kumeler:
        return []
    return sorted(set.intersection(*kumeler))


def _anahtar(sembol: str, interval: str, tur: str, kok: str | Path | None) -> tuple:
    """Arşiv kökü ve kaynak dosya sürümü farklıysa eski frame kullanılmaz."""
    root = arsiv_koku(kok).resolve()
    yol = root / f"{sembol}_{interval}.csv.gz"
    try:
        stat = yol.stat()
    except FileNotFoundError:
        raise FileNotFoundError(f"arşiv dosyası yok: {yol}") from None
    return (str(root), sembol, tur, stat.st_mtime_ns, stat.st_size)


def _sakla(anahtar: tuple, frame: pd.DataFrame) -> pd.DataFrame:
    # Güncellenen aynı dosyanın eski sürümleri bellekte birikmesin.
    for eski in list(_OBELLEK):
        if eski[:3] == anahtar[:3] and eski != anahtar:
            _OBELLEK.pop(eski, None)
    _OBELLEK[anahtar] = frame
    return frame.copy(deep=True)


def ham_frame(sembol: str, interval: str, kok: str | Path | None = None) -> pd.DataFrame:
    """Arşivdeki NATIVE intervali DatetimeIndex'li OHLCV çerçevesi olarak okur."""
    anahtar = _anahtar(sembol, interval, f"raw:{interval}", kok)
    kayit = _OBELLEK.get(anahtar)
    if kayit is not None:
        return kayit.copy(deep=True)
    yol = Path(anahtar[0]) / f"{sembol}_{interval}.csv.gz"
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        ham = pd.read_csv(dosya)
    ham.columns = [str(c).lower() for c in ham.columns]
    eksik = {"bar_time", "open", "high", "low", "close", "volume"} - set(ham.columns)
    if eksik:
        raise ValueError(f"{sembol}/{interval}: eksik kolonlar {sorted(eksik)}")
    ham["timestamp"] = pd.DatetimeIndex(pd.to_datetime(ham["bar_time"], utc=True))
    ham = ham[["timestamp", "open", "high", "low", "close", "volume"]]
    ham = ham.set_index("timestamp").sort_index()
    ham = ham.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    ham = ham[~ham.index.duplicated(keep="first")]
    return _sakla(anahtar, ham)


def tf_frame(
    sembol: str,
    timeframe: str,
    kok: str | Path | None = None,
    *,
    legacy_resample: bool | None = None,
) -> pd.DataFrame:
    """Sembol için istenen NATIVE zaman diliminin çerçevesini üretir (önbellekli).

    ``legacy_resample=False`` replay sözleşmesidir: 2h/4h dosyası yoksa 1h'den
    türetim yapılmaz, ``FileNotFoundError`` fırlatılır. ``None`` ise karar
    manifest moduna bırakılır: yeni native arşiv strict, eski arşiv uyumluluk.
    """
    if timeframe not in KAYNAK_INTERVAL:
        raise KeyError(f"desteklenmeyen zaman dilimi: {timeframe!r}")
    kaynak = KAYNAK_INTERVAL[timeframe]
    if legacy_resample is None:
        legacy_resample = arsiv_modu(kok) == "legacy"
    root = arsiv_koku(kok)
    native_yol = root / f"{sembol}_{kaynak}.csv.gz"

    if native_yol.exists():
        anahtar = _anahtar(sembol, kaynak, f"native:{timeframe}", kok)
        kayit = _OBELLEK.get(anahtar)
        if kayit is not None:
            return kayit.copy(deep=True)
        ham = ham_frame(sembol, kaynak, kok)
        frame = ham.copy()
        kaynak_modu = f"native:{kaynak}"
    elif timeframe in ("2h", "4h") and legacy_resample:
        # YALNIZ eski manifest uyumluluğu. Yeni replay bu dala girmez.
        anahtar = _anahtar(sembol, "1h", f"legacy:{timeframe}", kok)
        kayit = _OBELLEK.get(anahtar)
        if kayit is not None:
            return kayit.copy(deep=True)
        ham = ham_frame(sembol, "1h", kok)
        from data import resample_ohlcv

        # DatetimeIndex KORUNARAK verilir: resample_ohlcv kova çapasını
        # İstanbul saatine göre SABİT 09:30'a bağlar; tz bilgisi şarttır.
        frame = resample_ohlcv(ham, timeframe)
        if not isinstance(frame.index, pd.DatetimeIndex):
            if "timestamp" in frame.columns:
                frame = frame.set_index("timestamp")
            else:
                raise ValueError(f"{sembol}/{timeframe}: resample DatetimeIndex üretmedi")
        frame = frame.sort_index()
        kaynak_modu = "legacy:1h"
    else:
        raise FileNotFoundError(
            f"native {timeframe} arşiv dosyası yok: {native_yol}. "
            "1h'den resample kapalı; önce Termux native çekimini çalıştır "
            "(docs/kurulum/TERMUX_BACKFILL.md)."
        )

    frame = temizle(frame)
    if frame is None or len(frame) == 0:
        raise ValueError(
            f"{sembol}/{timeframe}: {kaynak_modu} temizlik sonrası boş frame "
            f"({len(ham)} ham bar)"
        )
    return _sakla(anahtar, frame)


def temizle(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN OHLC satırlarını ve pozitif olmayan yüksek/düşük tutarsızlığını ayıklar.

    Hacim sıfırlığı çıkarılmaz: BIST açılış müzayede barı sistemli olarak sıfır
    hacimlidir ve çıkarılırsa seans yapısı bozulur. Native TV barlarında da aynı
    koruma geçerlidir.
    """
    if frame is None or len(frame) == 0:
        return pd.DataFrame()
    temiz = frame.dropna(subset=["open", "high", "low", "close"])
    temiz = temiz[(temiz["high"] > 0) & (temiz["low"] > 0)]
    temiz = temiz[temiz["high"] >= temiz["low"]]
    return temiz


def temizle_json(yol: str | Path) -> Any:
    """Yardımcı: JSON dosyasını toleranslı okur (bozuk dosya -> ``None``)."""
    try:
        with Path(yol).open("r", encoding="utf-8") as dosya:
            return json.load(dosya)
    except Exception:
        return None
