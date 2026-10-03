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
    "son_tarama_durumu",
    "son_tarama_beklenen_hisse",
    "son_tarama_hata_hisse",
    "son_tarama_veri_zamani",
    "son_tarama_en_eski_veri_yasi_dk",
    "son_tarama_taze_veri",
    "son_tarama_fetch_hatasi",
    "son_is_baslangic",
    "son_is_bitis",
    "son_is_suresi_dk",
    "son_is_hisse_istek",
    "son_is_hisse_basarili",
    "tarama_sayisi",
)


class LiveState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._formations: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._pending_scope: Optional[set[str]] = None
        self._pending_replace_all = True
        self._status: Dict[str, Any] = {
            "tarama_suruyor": False,
            "tarama_sayisi": 0,
            "son_tarama_baslangic": None,
            "son_tarama_bitis": None,
            "son_tarama_suresi_dk": None,
            "son_tarama_hissesi": None,
            "son_tarama_hatasi": None,
            "son_tarama_durumu": "yok",
            "son_is_baslangic": None,
            "son_is_bitis": None,
            "son_is_suresi_dk": None,
            "son_is_hisse_istek": None,
            "son_is_hisse_basarili": None,
            "son_tarama_beklenen_hisse": None,
            "son_tarama_hata_hisse": 0,
            "son_tarama_veri_zamani": None,
            "son_tarama_en_eski_veri_yasi_dk": None,
            "son_tarama_taze_veri": 0,
            "son_tarama_fetch_hatasi": 0,
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

    def begin_scan(self, ts: Optional[datetime] = None, manuel: bool = False,
                   beklenen_hisse: Optional[int] = None, scope=None,
                   replace_all: bool = True) -> None:
        with self._lock:
            self._pending = {}
            self._pending_scope = {str(s).upper() for s in scope} if scope is not None else None
            self._pending_replace_all = bool(replace_all)
            baslangic = (ts or datetime.now()).isoformat()
            self._status["tarama_suruyor"] = True
            self._status["manuel_tarama"] = bool(manuel)
            self._status["son_tarama_durumu"] = "calisiyor"
            self._status["son_is_baslangic"] = baslangic
            self._status["son_tarama_baslangic"] = baslangic
            self._status["son_is_hisse_istek"] = beklenen_hisse
            self._status["son_is_hisse_basarili"] = 0
            self._status["son_tarama_hata_hisse"] = 0
            self._status["son_tarama_hatasi"] = None
            self._status["snapshot_yuklendi"] = False
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
        """Başarılı/işlenebilir bir taramayı atomik olarak yayımla."""
        with self._lock:
            bitis = (ts or datetime.now()).isoformat()
            if self._pending_replace_all or self._pending_scope is None:
                self._formations = self._pending
            else:
                # Hisseye özel başarılı analiz yalnızca o kapsamın eski slotlarını
                # değiştirir; evrenin geri kalan son başarılı sonuçları korunur.
                self._formations = {
                    key: value for key, value in self._formations.items()
                    if key.split("|", 1)[0] not in self._pending_scope
                }
                self._formations.update(self._pending)
            self._pending = {}
            self._pending_scope = None
            self._pending_replace_all = True
            self._status["tarama_suruyor"] = False
            self._status["son_tarama_durumu"] = extra.pop("son_tarama_durumu", "tamamlandi")
            self._status["son_is_bitis"] = bitis
            self._status["son_tarama_bitis"] = bitis
            for anahtar, deger in extra.items():
                if deger is not None:
                    self._status[anahtar] = deger
            if self._status.get("son_tarama_suresi_dk") is not None:
                self._status["son_is_suresi_dk"] = self._status["son_tarama_suresi_dk"]

    def fail_scan(self, hata: str, ts: Optional[datetime] = None,
                  hata_hisse: Optional[int] = None, islenen_hisse: Optional[int] = None,
                  istek_hisse: Optional[int] = None, sure_dk: Optional[float] = None) -> None:
        """Başarısız taramada son geçerli sonuç korunur, başarısız boş liste yayımlanmaz."""
        with self._lock:
            self._pending = {}
            self._pending_scope = None
            self._pending_replace_all = True
            bitis = (ts or datetime.now()).isoformat()
            self._status["tarama_suruyor"] = False
            self._status["son_tarama_durumu"] = "basarisiz"
            self._status["son_tarama_hatasi"] = str(hata)[:200]
            self._status["son_is_bitis"] = bitis
            if hata_hisse is not None:
                self._status["son_tarama_hata_hisse"] = int(hata_hisse)
            if islenen_hisse is not None:
                self._status["son_is_hisse_basarili"] = int(islenen_hisse)
            if istek_hisse is not None:
                self._status["son_is_hisse_istek"] = int(istek_hisse)
            if sure_dk is not None:
                self._status["son_is_suresi_dk"] = float(sure_dk)

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
            # Not: `stable_id` burada bilinçli olarak EKLENMEZ. Eski (stable_id'siz)
            # son_tarama kayıtları olduğu gibi okunur; okuyan taraf alanı `.get()`
            # ile okur (komutlar/panel/karne), bu yüzden eksik anahtar crash üretmez.
            # Böylece hydrate() "kaydı olduğu gibi geri yükler" sözleşmesi korunur.
            kayitlar[f"{stock}|{timeframe}"] = kopya
        durum = veri.get("status")
        if not isinstance(durum, dict):
            durum = {}
        with self._lock:
            self._formations = kayitlar
            self._pending = {}
            self._pending_scope = None
            self._pending_replace_all = True
            for alan in _SNAPSHOT_STATUS_ALANLARI:
                if durum.get(alan) is not None:
                    self._status[alan] = durum[alan]
            self._status["tarama_suruyor"] = False
            if self._status.get("son_tarama_durumu") == "yok" and self._status.get("son_tarama_bitis"):
                self._status["son_tarama_durumu"] = "tamamlandi"
            # An explicitly empty list is a valid "0 candidate" snapshot;
            # a non-empty list containing only malformed entries is not.
            self._status["snapshot_yuklendi"] = bool(kayitlar) or not veri["formations"]
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
