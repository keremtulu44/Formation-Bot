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

# Yaşam döngüsü durumlarının Türkçe görüntüleme adları (TEK ORTAK KAYNAK).
# main.py (panel/digest) ve notifier.py (DM izleme satırları) aynı sözlüğü
# kullanır; bilinmeyen durum kodu karşılıksız bırakılır, uydurulmaz.
STATE_TR = {
    "ADAY_OLUSUYOR": "Aday oluşuyor",
    "GEOMETRI_ADAYI": "Geometri adayı",
    "FORMASYON_TANIMLANDI": "Formasyon tanımlandı",
    "OLGUNLASIYOR": "Olgunlaşıyor",
    "SIKISMA_GUCLENIYOR": "Sıkışma güçleniyor",
    "KIRILIM_HAZIRLIGI": "Kırılım hazırlığı",
    "KIRILIM_DENEMESI": "Kırılım denemesi",
    "KIRILIM_ADAYI": "Kırılım adayı",
    "KIRILIM_TEYITLI": "Kırılım teyitli",
    "RETEST_BEKLENIYOR": "Retest bekleniyor",
    "RETEST_EDILIYOR": "Retest ediliyor",
    "RETEST_BASARILI": "Retest başarılı",
    "FORMASYON_TAMAMLANDI": "Formasyon tamamlandı",
}

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

    def snapshot(self, now: datetime) -> dict:
        """Serialize only current-day watch state; records remain Formation-native."""
        self._ensure_day(now)
        return {
            "date": self._date.isoformat(),
            "pending": [dict(record) for record in self._pending.values()],
            "reported": [list(key) for key in sorted(self._reported)],
        }

    def restore(self, snapshot: Optional[dict], now: datetime) -> int:
        """Restore a same-day snapshot; reject malformed/stale schema safely."""
        self.clear(now)
        if not isinstance(snapshot, dict) or snapshot.get("date") != now.date().isoformat():
            return 0
        restored = 0
        raw_pending = snapshot.get("pending", ())
        raw_reported = snapshot.get("reported", ())
        if not isinstance(raw_pending, (list, tuple)):
            raw_pending = ()
        if not isinstance(raw_reported, (list, tuple)):
            raw_reported = ()
        for record in raw_pending:
            if not isinstance(record, dict):
                continue
            key = _key(record)
            if not key[0] or not key[1] or key[3] not in WATCH_STATES:
                continue
            stored = dict(record)
            stored.update(stock=key[0], timeframe=key[1], state=key[3])
            self._pending[key] = stored
            restored += 1
        for raw_key in raw_reported:
            if not isinstance(raw_key, (list, tuple)) or len(raw_key) != 4:
                continue
            key = tuple(str(part) for part in raw_key)
            if key[3] in WATCH_STATES:
                self._reported.add(key)  # type: ignore[arg-type]
        return restored

    def clear(self, now: datetime) -> None:
        """Gün değişiminde çağrılabilir; asıl sıfırlama _ensure_day ile yapılır."""
        self._date = now.date()
        self._pending.clear()
        self._reported.clear()

    def __len__(self) -> int:
        return len(self._pending)
