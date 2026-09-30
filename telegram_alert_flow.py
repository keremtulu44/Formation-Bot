"""Hafif önceliklendirilmiş Telegram uyarı kuyruğu (Supabase bağımsız).

Acil durumlar bu tamponda tutulmaz; yalnızca bekletilen adaylar tutulur.
Ana tarama geçerli bir sembol/zaman dilimini bitirdiğinde o slotun bekleyen
kaydı yenilenir veya kaldırılır. Günlük tampon Istanbul tarihinde bellekte yaşar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple


WATCH_STATES = frozenset({
    "SIKISMA_GUCLENIYOR",
    "KIRILIM_HAZIRLIGI",
    "KIRILIM_ADAYI",
    "KIRILIM_DENEMESI",
    "RETEST_BEKLENIYOR",
    "RETEST_EDILIYOR",
})

AlertKey = Tuple[str, str, str, str]


def _key(record: dict) -> AlertKey:
    return (
        str(record.get("stock") or "").strip().upper(),
        str(record.get("timeframe") or "").strip().lower(),
        str(record.get("pattern_name") or "").strip(),
        str(record.get("state") or "").strip().upper(),
    )


def _quality(record: dict) -> float:
    try:
        return float(record.get("quality") or 0.0)
    except (TypeError, ValueError):
        return 0.0


class DeferredAlertBuffer:
    """Gün içi düşük öncelikli adayları tek bir kapanış özetinde birleştirir."""

    def __init__(self) -> None:
        self._date = None
        self._pending: Dict[AlertKey, dict] = {}
        self._reported: set[AlertKey] = set()

    def _ensure_day(self, now: datetime) -> None:
        if self._date != now.date():
            self._date = now.date()
            self._pending.clear()
            self._reported.clear()

    @staticmethod
    def _same_slot(key: AlertKey, stock: str, timeframe: str) -> bool:
        return key[0] == stock and key[1] == timeframe

    def observe(self, stock: str, timeframe: str, record: Optional[dict], now: datetime) -> None:
        """Bir TF taraması başarıyla bittiğinde eski bekleyen slotu günceller."""
        self._ensure_day(now)
        stock = str(stock or "").strip().upper()
        timeframe = str(timeframe or "").strip().lower()
        if not stock or not timeframe:
            return

        for key in list(self._pending):
            if self._same_slot(key, stock, timeframe):
                self._pending.pop(key, None)

        if not isinstance(record, dict):
            return
        key = _key(record)
        if key[:2] != (stock, timeframe) or key[3] not in WATCH_STATES:
            return
        if key in self._reported:
            return

        stored = dict(record)
        stored["stock"] = stock
        stored["timeframe"] = timeframe
        stored["state"] = key[3]
        stored["watch_seen_at"] = now.isoformat()
        self._pending[key] = stored

    def items(self, now: datetime, limit: int = 12) -> List[dict]:
        """En anlamlı bekleyen adayları kopya olarak döndür; kendiliğinden tüketmez."""
        self._ensure_day(now)
        sirali = sorted(
            self._pending.items(),
            key=lambda item: (-_quality(item[1]), item[0][0], item[0][1], item[0][3]),
        )[:max(0, int(limit))]
        return [dict(record) for _key_value, record in sirali]

    def mark_reported(self, records: Iterable[dict], now: datetime) -> None:
        """Başarıyla iletilen bağlam/digest kayıtlarını gün içinde tekrar etme."""
        self._ensure_day(now)
        for record in records or []:
            if not isinstance(record, dict):
                continue
            key = _key(record)
            self._reported.add(key)
            self._pending.pop(key, None)

    def clear(self, now: datetime) -> None:
        """Gün değişiminde çağrılabilir; asıl sıfırlama _ensure_day ile yapılır."""
        self._date = now.date()
        self._pending.clear()
        self._reported.clear()

    # --- kalıcılık (Batch 5 / B3) -----------------------------------------
    # Neden: tampon bellekteydi; 18:45'ten önce restart olursa gün içi adaylar
    # sessizce kayboluyordu. Snapshot Supabase'e ve diske yazılır, açılışta geri
    # yüklenir. Snapshot biçimi sürümlenir; bilinmeyen sürüm sessizce yok sayılır.

    SURUM = 1

    def snapshot(self) -> dict:
        return {
            "surum": self.SURUM,
            "gun": self._date.isoformat() if self._date else None,
            "bekleyen": [dict(record) for record in self._pending.values()],
            "bildirilen": [list(key) for key in sorted(self._reported)],
        }

    def yukle(self, ham: Optional[dict]) -> int:
        """Kayıtlı tamponu geri yükler; kaç aday yüklendiğini döndürür.

        Gün bilgisi korunur: eski güne ait kayıtlar `gun()` ile ayırt edilir ve
        çağıran taraf kaçırılan kapanış özetini telafi edebilir.
        """
        if not isinstance(ham, dict):
            return 0
        try:
            surum = int(ham.get("surum") or 0)
        except (TypeError, ValueError):
            return 0
        if surum != self.SURUM:
            return 0
        gun = None
        if ham.get("gun"):
            try:
                gun = datetime.fromisoformat(str(ham["gun"])).date()
            except (TypeError, ValueError):
                gun = None
        bekleyen: Dict[AlertKey, dict] = {}
        for record in ham.get("bekleyen") or []:
            if not isinstance(record, dict):
                continue
            key = _key(record)
            if not all(key) or key[3] not in WATCH_STATES:
                continue
            bekleyen[key] = dict(record)
        bildirilen = set()
        for key in ham.get("bildirilen") or []:
            if isinstance(key, (list, tuple)) and len(key) == 4:
                bildirilen.add(tuple(str(parca) for parca in key))
        self._date = gun
        self._pending = bekleyen
        self._reported = bildirilen
        return len(bekleyen)

    def gun(self):
        """Tamponun ait olduğu İstanbul günü (date) veya None."""
        return self._date

    def __len__(self) -> int:
        return len(self._pending)
