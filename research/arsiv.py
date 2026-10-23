"""``backfill_data/`` arşivini ölçüm için çerçevelere çevirir.

Arşiv 177 sembol x 2 interval (1h, 1d) CSV.gz dosyasıdır. Araştırma dört
zaman diliminde ölçüm ister (1h, 2h, 4h, 1d); 2h ve 4h repo'nun kendi
``data.resample_ohlcv`` fonksiyonuyla 1h'den türetilir. Bu fonksiyon BIST
seansına (09:30) hizalıdır; pandas'in varsayılan gece yarısı hizalaması
2H/4H mumlarını bir saat kaydırır ve TradingView pivotlarıyla uyuşmaz.

``1d`` için arşivdeki **native günlük** seri kullanılır, 1h'den
resample edilmiş olan değil. Gerekçe: 1h serisinin 09:30 barı açılış
seansı müzayede barıdır ve barların %94.6'sında hacmi sıfırdır; oradan
türetilen günlük açık, Yahoo'nun native günlük açılışıyla birebir
örtüşmez. Her zaman dilimi zaten bağımsız ölçülür ve rapor zaman
dilimine göre ayrılır, dolayısıyla bu seçim karşılaştırmayı bozmaz.

``BRENT`` havuzlanmış (cross-symbol) istatistikten çıkarılır: 327 gün,
günde 23 bar ve yaklaşık 24 saat işlem görür. BIST seans yapısı
taşımadığı için seansa hizalı resample ve seans içi bar sayımları onda
anlamsızdır. Sembol bazında ölçülür ama havuz ortalamalarına katılmaz.
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
    "HAVUZ_DISI_SEMBOLLER",
    "arsiv_koku",
    "manifest_oku",
    "arsiv_sembolleri",
    "ham_frame",
    "tf_frame",
    "temizle",
]

#: Ölçüm yapılacak zaman dilimleri. Rapor her biri için ayrı üretilir.
ARASTIRMA_TIMEFRAMELERI: tuple[str, ...] = ("1h", "2h", "4h", "1d")

#: Her zaman diliminin hangi arşiv intervalinden türediği.
KAYNAK_INTERVAL: dict[str, str] = {"1h": "1h", "2h": "1h", "4h": "1h", "1d": "1d"}

#: Havuzlanmış istatistiğe katılmayan semboller ve gerekçeleri.
HAVUZ_DISI_SEMBOLLER: dict[str, str] = {
    "BRENT": "BIST seans yapısı yok; ~24s işlem, günde 23 bar",
}

_ONTAMPI = Path(__file__).resolve().parent.parent
_OBELLEK: dict[tuple[str, str], pd.DataFrame] = {}


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
    """``manifest.json`` içeriğini döndürür; yoksa ya da bozuksa boş sözlük.

    Bozuk JSON'a tolerans gösterilir çünkü arşivin kendisi ölçümün girdisidir
    ve manifest yokluğu ölçümü durdurmamalıdır; yalnız denetim raporunda
    "manifest okunamadı" olarak görünür.
    """
    return temizle_json(arsiv_koku(kok) / "manifest.json") or {}


def arsiv_sembolleri(kok: str | Path | None = None) -> list[str]:
    """Arşivde 1h dosyası bulunan sembolleri alfabetik döndürür."""
    root = arsiv_koku(kok)
    if not root.exists():
        return []
    semboller = sorted(p.name[: -len("_1h.csv.gz")] for p in root.glob("*_1h.csv.gz"))
    return semboller


def ham_frame(sembol: str, interval: str, kok: str | Path | None = None) -> pd.DataFrame:
    """Arşivdeki ham intervali DatetimeIndex'li OHLCV çerçevesi olarak okur.

    ``bar_time`` metin olarak saklanır (repo kuralı: timestamptz değil) ve
    ``+03:00`` ofsetlidir. Sıra korunur; arşiv zaten kronolojik yazılır.
    """
    anahtar = (sembol, f"raw:{interval}")
    if anahtar in _OBELLEK:
        return _OBELLEK[anahtar]
    yol = arsiv_koku(kok) / f"{sembol}_{interval}.csv.gz"
    if not yol.exists():
        raise FileNotFoundError(f"arşiv dosyası yok: {yol}")
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
    _OBELLEK[anahtar] = ham
    return ham


def tf_frame(sembol: str, timeframe: str, kok: str | Path | None = None) -> pd.DataFrame:
    """Sembol için istenen zaman diliminin çerçevesini üretir (önbellekli)."""
    anahtar = (sembol, timeframe)
    if anahtar in _OBELLEK:
        return _OBELLEK[anahtar]
    kaynak = KAYNAK_INTERVAL[timeframe]
    ham = ham_frame(sembol, kaynak, kok)
    if timeframe == kaynak:
        frame = ham.copy()
    else:
        from data import resample_ohlcv

        # DatetimeIndex KORUNARAK verilir: resample_ohlcv kova çapasını
        # İstanbul saatine göre SABİT 09:30'a bağlar (FAZ düzeltmesi,
        # 2026-10-23); tz bilgisi bunun için şarttır. UTC girdi, çapa
        # İstanbul'da hesaplanıp UTC'ye geri çevrilerek aynen korunur.
        # Int index verilirse fonksiyon boş DataFrame döndürür
        # (sessiz veri kaybı) — o yüzden index'e dokunulmuyor.
        frame = resample_ohlcv(ham, timeframe)
        if not isinstance(frame.index, pd.DatetimeIndex):
            if "timestamp" in frame.columns:
                frame = frame.set_index("timestamp")
            else:
                raise ValueError(f"{sembol}/{timeframe}: resample DatetimeIndex üretmedi")
        frame = frame.sort_index()
    frame = temizle(frame)
    if frame is None or len(frame) == 0:
        # Sessiz sıfır yerine gürültülü hata: boş frame "ölçülecek zone yok"
        # ile karışır ve raporda yanlışlıkla sıfır gözlem olarak görünür.
        raise ValueError(f"{sembol}/{timeframe}: resample/temizlik sonrası boş frame (kaynak {kaynak}, {len(ham)} bar)")
    _OBELLEK[anahtar] = frame
    return frame


def temizle(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN OHLC satırlarını ve pozitif olmayan yüksek/düşük tutarsızlığını ayıklar.

    Kalite bayrağı düşürmek yerine satırı tamamen çıkarmak burada güvenlidir:
    arşivin NaN OHLC sayısı ölçümde **sıfır** bulundu. Yine de ileriye dönük
    koruma olarak tutulur; hacim sıfırlığı ise *çıkarılmaz*, çünkü BIST açılış
    müzayede barı sistemli olarak sıfır hacimlidir ve çıkarılırsa seans
    yapısı bozulur. VP tarafında bu durum ``volume_usable`` bayrağıyla taşınır.
    """
    if frame is None or len(frame) == 0:
        return pd.DataFrame()
    temiz = frame.dropna(subset=["open", "high", "low", "close"])
    temiz = temiz[(temiz["high"] > 0) & (temiz["low"] > 0)]
    # high < low olan satır veri hatasıdır; uzanım ölçümünü ters çevirir.
    temiz = temiz[temiz["high"] >= temiz["low"]]
    return temiz


def temizle_json(yol: str | Path) -> Any:
    """Yardımcı: JSON dosyasını toleranslı okur (bozuk dosya -> ``None``)."""
    try:
        with Path(yol).open("r", encoding="utf-8") as dosya:
            return json.load(dosya)
    except Exception:
        return None
