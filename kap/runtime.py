"""Formation-Bot için KAP bağlamı çalışma zamanı köprüsü.

Sorumluluk sınırı:
  - Yalnızca genel sistem uyumu: arşiv dosya yolu (`DATA_DIR`), sembol/saat
    normalizasyonu, salt okunur alarm sorgusu ve senkron bot döngüsünü
    bloklamayan arka plan toplayıcı yaşam döngüsü (`KapBackgroundRunner`).
  - Varsayılan KAPALI (`config.KAP_BAGLAM_AKTIF = False`): operatör açıkça
    açmadıkça ağa çıkmaz, SQLite dosyası açmaz ve alarm akışına müdahale etmez.
  - Ayrıntılı AI prompt veya Telegram mesaj biçimlendirmesi burada yapılmaz.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import config
from state.paths import kap_arsiv_yolu as _default_kap_arsiv_yolu

from .baglam import (
    DEFAULT_MAX_AGE,
    KapCollectorService,
    Origin,
    PublishedRow,
    kap_baglami_ekle,
    open_archive,
)

logger = logging.getLogger(__name__)

_TRT_TZ = timezone(timedelta(hours=3), name="TRT")


def normalize_bist_ticker(symbol: Any) -> str:
    """BIST sembolünü KAP formatına normalize eder (örn. `THYAO.IS` -> `THYAO`)."""
    raw = str(symbol or "").strip().upper()
    if raw.endswith(".IS"):
        raw = raw[:-3]
    return raw


def active_kap_universe(stocks: Sequence[str] | None = None) -> tuple[str, ...]:
    """Formation-Bot aktif evreninden yalnızca BIST hisse KAP sembollerini üretir."""
    source = stocks if stocks is not None else getattr(config, "ACTIVE_STOCKS", ())
    tickers = [normalize_bist_ticker(s) for s in source]
    return tuple(
        dict.fromkeys(
            t for t in tickers
            if t and config.sembol_turu(t) == "hisse"
        )
    )


def kap_arsiv_yolu(data_dir: str | Path | None = None) -> Path:
    """KAP SQLite WAL arşiv yolunu döndürür (öncelik: `KAP_ARSIV_YOLU`, yoksa `DATA_DIR`)."""
    configured = str(getattr(config, "KAP_ARSIV_YOLU", "") or "").strip()
    if data_dir is None and configured:
        return Path(configured)
    return Path(_default_kap_arsiv_yolu(str(data_dir) if data_dir is not None else None))


def _normalize_trigger_time(tetik_zamani: datetime | None) -> datetime:
    if tetik_zamani is None:
        return datetime.now(timezone.utc)
    if tetik_zamani.tzinfo is None:
        return tetik_zamani.replace(tzinfo=_TRT_TZ).astimezone(timezone.utc)
    return tetik_zamani.astimezone(timezone.utc)


def _resolve_max_age(max_age_gun: int | None) -> timedelta:
    if max_age_gun is not None:
        return timedelta(days=max(1, int(max_age_gun)))
    configured = getattr(config, "KAP_MAX_YAS_GUN", None)
    if configured is None:
        return DEFAULT_MAX_AGE
    return timedelta(days=max(1, int(configured)))


def alarm_kap_baglami_ekle(
    yorum_istegi: dict[str, object],
    hisse: str,
    tetik_zamani: datetime | None = None,
    *,
    arsiv_yolu: str | Path | None = None,
    max_age_gun: int | None = None,
    origin: Origin = "kap_arsiv",
    force: bool = False,
    log: logging.Logger | None = None,
) -> dict[str, object] | None:
    """Formation-Bot alarm sözlüğüne (aktifse) salt-okunur KAP bağlamı ekler.

    - `config.KAP_BAGLAM_AKTIF` kapalıysa (`force=False`) önceki KAP anahtarlarını
      temizler ve ağ/disk erişimi yapmadan `None` döner.
    - Arşiv dosyası henüz yoksa veya hata oluşursa `'haber yok'` uydurmadan
      `None` döner; ana alarm akışını asla kesmez.
    """
    if not force and not config.kap_baglam_enabled():
        for key in ("kap_baglami", "kap_bekleyen_bildirim", "kap_sirket_profili", "kap_sessizlik"):
            yorum_istegi.pop(key, None)
        return None

    ticker = normalize_bist_ticker(hisse)
    if not ticker:
        return None
    path = Path(arsiv_yolu) if arsiv_yolu is not None else kap_arsiv_yolu()
    if not path.is_file():
        for key in ("kap_baglami", "kap_bekleyen_bildirim", "kap_sirket_profili", "kap_sessizlik"):
            yorum_istegi.pop(key, None)
        return None

    return kap_baglami_ekle(
        yorum_istegi,
        path,
        ticker,
        _normalize_trigger_time(tetik_zamani),
        max_age=_resolve_max_age(max_age_gun),
        origin=origin,
        logger=log or logger,
    )


def alarm_kap_baglami_oku(
    hisse: str,
    tetik_zamani: datetime | None = None,
    *,
    arsiv_yolu: str | Path | None = None,
    max_age_gun: int | None = None,
    origin: Origin = "kap_arsiv",
    force: bool = False,
) -> dict[str, object] | None:
    """Mevcut sözlüğü değiştirmeden tek hisse için salt-okunur KAP bağlamını okur."""
    hedef: dict[str, object] = {}
    return alarm_kap_baglami_ekle(
        hedef,
        hisse,
        tetik_zamani,
        arsiv_yolu=arsiv_yolu,
        max_age_gun=max_age_gun,
        origin=origin,
        force=force,
    )


def kap_arsiv_durumu(
    arsiv_yolu: str | Path | None = None,
    *,
    origin: Origin = "kap_arsiv",
) -> dict[str, Any]:
    """KAP arşivinin salt-okunur durum özeti (komutlar / tanılama için)."""
    path = Path(arsiv_yolu) if arsiv_yolu is not None else kap_arsiv_yolu()
    out: dict[str, Any] = {
        "enabled": config.kap_baglam_enabled(),
        "archive_path": str(path),
        "archive_exists": path.is_file(),
        "stats": None,
    }
    if not path.is_file():
        return out
    try:
        with open_archive(path) as arsiv:
            out["stats"] = arsiv.stats(origin=origin)
    except (ValueError, OSError, sqlite3.Error) as exc:
        out["error"] = str(exc)
    return out


class KapBackgroundRunner:
    """`KapCollectorService.run_forever()` için senkron bot uyumlu daemon thread sarmalayıcı."""

    def __init__(
        self,
        archive_path: str | Path | None = None,
        *,
        universe: Sequence[str] | None = None,
        statements: Sequence[PublishedRow] = (),
        interval_seconds: float | None = None,
        warmup_on_start: bool | None = None,
        origin: Origin = "kap_arsiv",
        kap: Any = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.archive_path = Path(archive_path) if archive_path is not None else kap_arsiv_yolu()
        self.universe = active_kap_universe(universe)
        self.statements = tuple(statements)
        self.interval_seconds = float(
            interval_seconds
            if interval_seconds is not None
            else getattr(config, "KAP_TARAMA_ARALIK_SN", 180)
        )
        self.warmup_on_start = (
            bool(warmup_on_start)
            if warmup_on_start is not None
            else bool(getattr(config, "KAP_WARMUP_ACILISTA", False))
        )
        self.origin: Origin = origin
        self._kap = kap
        self._log = log or logger

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Arka plan KAP toplayıcısını başlatır (zaten çalışıyorsa `False`)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self.archive_path.parent.mkdir(parents=True, exist_ok=True)
            self._ready.clear()
            self._last_error = None
            thread = threading.Thread(
                target=self._run_thread,
                name="kap-collector",
                daemon=True,
            )
            self._thread = thread
            thread.start()
        self._ready.wait(timeout=2.0)
        return True

    def _run_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stop_event = asyncio.Event()
        with self._lock:
            self._loop = loop
            self._stop_event = stop_event
        self._ready.set()

        service = KapCollectorService(
            self.archive_path,
            universe=self.universe,
            statements=self.statements,
            kap=self._kap,
            origin=self.origin,
            logger=self._log,
        )
        try:
            loop.run_until_complete(
                service.run_forever(
                    interval_seconds=self.interval_seconds,
                    warmup_on_start=self.warmup_on_start,
                    stop_event=stop_event,
                )
            )
        except Exception as exc:  # noqa: BLE001 - arka plan thread ana süreci düşürmez
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._log.warning("KAP arka plan toplayıcısı durdu: %s", self._last_error)
        finally:
            try:
                loop.close()
            except Exception as exc:  # noqa: BLE001
                self._log.debug("KAP event loop kapatma uyarısı: %s", exc)
            with self._lock:
                self._loop = None
                self._stop_event = None

    def stop(self, timeout: float = 5.0) -> None:
        """Arka plan KAP toplayıcısını nazikçe durdurur."""
        with self._lock:
            loop = self._loop
            stop_event = self._stop_event
            thread = self._thread
        if loop is not None and stop_event is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError as exc:
                self._log.debug("KAP stop sinyali atlandı (loop kapalı): %s", exc)
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            if self._thread is thread and not thread.is_alive():
                self._thread = None

    def status(self) -> Mapping[str, Any]:
        return {
            "running": self.is_running,
            "archive_path": str(self.archive_path),
            "universe_size": len(self.universe),
            "interval_seconds": self.interval_seconds,
            "warmup_on_start": self.warmup_on_start,
            "last_error": self._last_error,
        }
