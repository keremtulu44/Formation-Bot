"""Telegram komutları için paylaşılan canlı durum (thread-safe).

Neden ayrı modül: tarama döngüsü ana thread'de çalışır, Telegram komut
dinleyicisi ayrı bir thread'de. İki thread aynı anda okuma/yazma yapacağı için
tek bir kilit altında yalnızca **kopyalama/atama** yapılır; ağ isteği, biçimlendirme
veya hesap kilidin içinde yapılmaz (yoksa tarama yavaşlar).

Davranış:
- `begin_scan()` → yeni liste geçici tampona yazılır, ESKİ liste yayında kalır.
  Böylece tarama sürerken `/formasyonlar` yarım listeyi göstermez.
- `finish_scan()` → tampon yayına alınır (tek atama, atomik).
- `snapshot()` / `hydrate()` → son liste restart/uyku sonrası geri yüklenebilir;
  yarım tarama ve geçici süreç durumları geri yüklenmez.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SON_TARAMA_SURUMU = 1
_SNAPSHOT_STATUS_ALANLARI = (
    "son_tarama_baslangic",
    "son_tarama_bitis",
    "son_tarama_suresi_dk",
    "son_tarama_hissesi",
    "son_tarama_formasyonu",
    "tarama_sayisi",
)


class LiveState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._formations: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._status: Dict[str, Any] = {
            "tarama_suruyor": False,
            "tarama_sayisi": 0,
            "son_tarama_baslangic": None,
            "son_tarama_bitis": None,
            "son_tarama_suresi_dk": None,
            "son_tarama_hissesi": None,
            "son_tarama_hatasi": None,
            "manuel_tarama": False,
            "baslangic": None,
            "snapshot_yuklendi": False,
            "snapshot_zamani": None,
            "snapshot_formasyon": 0,
        }

    # --- tarama tarafı (main thread) -----------------------------------
    def mark_started(self, ts: Optional[datetime] = None) -> None:
        with self._lock:
            if self._status["baslangic"] is None:
                self._status["baslangic"] = (ts or datetime.now()).isoformat()

    def begin_scan(self, ts: Optional[datetime] = None, manuel: bool = False) -> None:
        with self._lock:
            self._pending = {}
            self._status["tarama_suruyor"] = True
            self._status["manuel_tarama"] = bool(manuel)
            self._status["snapshot_yuklendi"] = False
            self._status["son_tarama_baslangic"] = (ts or datetime.now()).isoformat()
            self._status["son_tarama_hatasi"] = None
            self._status["tarama_sayisi"] = int(self._status.get("tarama_sayisi") or 0) + 1

    def record_formation(self, record: Dict[str, Any]) -> None:
        stock = str(record.get("stock", "")).upper()
        timeframe = str(record.get("timeframe", "")).lower()
        if not stock or not timeframe:
            return
        with self._lock:
            self._pending[f"{stock}|{timeframe}"] = dict(record)

    def mark_alert_sent(self, stock: str, timeframe: str) -> None:
        key = f"{str(stock).upper()}|{str(timeframe).lower()}"
        with self._lock:
            kayit = self._pending.get(key) or self._formations.get(key)
            if kayit is not None:
                kayit["alert_gonderildi"] = True

    def finish_scan(self, ts: Optional[datetime] = None, **extra: Any) -> None:
        with self._lock:
            self._formations = self._pending
            self._pending = {}
            self._status["tarama_suruyor"] = False
            self._status["son_tarama_bitis"] = (ts or datetime.now()).isoformat()
            for anahtar, deger in extra.items():
                if deger is not None:
                    self._status[anahtar] = deger

    def fail_scan(self, hata: str, ts: Optional[datetime] = None) -> None:
        with self._lock:
            self._pending = {}
            self._status["tarama_suruyor"] = False
            self._status["son_tarama_hatasi"] = str(hata)[:200]
            self._status["son_tarama_bitis"] = (ts or datetime.now()).isoformat()

    # --- son tamamlanan taramanın kalıcı kopyası -----------------------
    def snapshot(self) -> dict:
        """Yalnızca yayındaki listeyi kopyalar; yarım tarama kayda girmez.

        JSON/disk/ağ işlemleri bu kilidin dışında, çağıran tarafta yapılır.
        """
        with self._lock:
            formations = [dict(v) for v in self._formations.values()]
            durum = dict(self._status)
        durum["tarama_suruyor"] = False
        durum.pop("snapshot_yuklendi", None)
        return {
            "surum": SON_TARAMA_SURUMU,
            "kayit_zamani": datetime.now(timezone.utc).isoformat(),
            "status": durum,
            "formations": formations,
        }

    def hydrate(self, veri: Any) -> int:
        """Kayıtlı listeyi yükler; geçici/çalışan süreç durumunu geri yüklemez."""
        if not isinstance(veri, dict) or not isinstance(veri.get("formations"), list):
            return 0
        kayitlar = {}
        for kayit in veri["formations"]:
            if not isinstance(kayit, dict):
                continue
            stock, timeframe = kayit.get("stock"), kayit.get("timeframe")
            if not isinstance(stock, str) or not isinstance(timeframe, str):
                continue
            stock, timeframe = stock.strip().upper(), timeframe.strip().lower()
            if not stock or not timeframe:
                continue
            kopya = dict(kayit)
            kopya.update(stock=stock, timeframe=timeframe)
            kayitlar[f"{stock}|{timeframe}"] = kopya
        durum = veri.get("status")
        if not isinstance(durum, dict):
            durum = {}
        with self._lock:
            self._formations = kayitlar
            self._pending = {}
            for alan in _SNAPSHOT_STATUS_ALANLARI:
                if durum.get(alan) is not None:
                    self._status[alan] = durum[alan]
            self._status["tarama_suruyor"] = False
            self._status["snapshot_yuklendi"] = bool(kayitlar)
            self._status["snapshot_zamani"] = veri.get("kayit_zamani")
            self._status["snapshot_formasyon"] = len(kayitlar)
        return len(kayitlar)

    # --- komut tarafı (listener thread) --------------------------------
    def formations(self) -> List[Dict[str, Any]]:
        with self._lock:
            kayitlar = [dict(v) for v in self._formations.values()]
        kayitlar.sort(key=lambda r: float(r.get("quality") or 0.0), reverse=True)
        return kayitlar

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)
