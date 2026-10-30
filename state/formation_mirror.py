"""Faz 2.6: Formation History Durable Mirror, Queue & Hydration.

Mimari rol:
    Formation Motoru -> Local Formation History (Source of Truth)
                    -> Supabase Mirror Queue (Transport Buffer)
                    -> Supabase f2_* Tabloları (Durable Storage / Recovery)

Kritik ilkeler:
    1. Local JSON history daima birincil ve authoritative'dir.
    2. Supabase erişilemez olduğunda bot kesintisiz çalışmaya devam eder.
    3. bar_time alanları TEXT formatında korunur (kesinlikle timestamptz yapılmaz).
       Mevcut `_konum_bul` string eşitliği kullandığı için ISO 'T' dönüşümü
       hydration sonrası SID eşleşmesini bozar.
    4. Write amplification önlenir: Diff-gating sayesinde değişmeyen terminal
       formation'lar her taramada tekrar diske/Supabase'e gönderilmez.
    5. Kuyruk türetilmiş transport durumudur; hiçbir koşulda local history'nin
       yerine geçmez veya local history'yi silemez.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from config import DATA_DIR
from state import formation_history as fh
from state import formation_schema as schema
from state.paths import formation_history_yolu

logger = logging.getLogger(__name__)

# Kuyruk ve flush sabitleri
MAX_QUEUE_ITEMS = 5000         # Disk kuyruğu için uyarı eşiği; satır atılmaz
FLUSH_BATCH_SIZE = 100         # Tek PostgREST isteğindeki azami satır
DEFAULT_BACKOFF_INITIAL = 30.0 # İlk hata beklemesi (sn)
DEFAULT_BACKOFF_MAX = 600.0    # Azami bekleme (10 dk)
POISON_ESIK = 5                # Tekrarlayan 400/422 için ek hata uyarısı; satır atılmaz
KUYRUK_DOSYA_ADI = "f2_kuyruk.json"  # eski sürümden geçiş
KUYRUK_SQLITE_ADI = "f2_kuyruk.sqlite3"

# BAR_ALANLARI int dönüşüm garantisi için
BAR_ALANLARI = frozenset({
    "start_bar", "end_bar", "known_bar", "apex_bar",
    "hb1", "hb2", "lb1", "lb2",
    "pole_start_bar", "pole_end_bar",
    "break_snapshot_bar",
})


def _guvenli_int(val: Any) -> Optional[int]:
    """Hydration ve diff sırasında integer tip güvenliği sağlar."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float('inf')) — sessizce None olmalı, patlamamalı
        return None


def _guvenli_float(val: Any) -> Optional[float]:
    """Hydration ve diff sırasında float tip güvenliği sağlar.

    Sonlu olmayan değer (NaN/inf) None'a iner: Python `json` NaN'i geçersiz
    `NaN` literali olarak yazar, PostgREST gövdeyi 400 ile reddeder ve
    batch kuyruk başında zehre dönüşür (2026-10-23 Supabase denetimi:
    f2_snapshots sequence'i aylardır 1'de — istek INSERT'e hiç varamıyor).
    """
    if val is None:
        return None
    try:
        sayi = float(val)
    except (TypeError, ValueError, OverflowError):
        return None
    return sayi if math.isfinite(sayi) else None


def _kuyruk_yolu(data_dir: Optional[str] = None) -> str:
    kok = data_dir or DATA_DIR
    return os.path.join(kok, KUYRUK_DOSYA_ADI)


# ============================================================================
# 1) DIFF EXTRACTION VE PARMAK İZİ (Write Amplification Koruması)
# ============================================================================

def defter_fingerprint(defter: Dict[str, Any]) -> Tuple:
    """Defterin içerik parmak izini üretir.

    son_gorulme ve benzeri transient zaman damgaları hariç tutulur.
    Böylece içeriği değişmeyen (ör. terminal) formation'lar her scan'de
    yeniden kuyruğa atılmaz.
    """
    if not isinstance(defter, dict):
        return ()
    kayitlar = defter.get("kayitlar") or {}
    parcalar = []
    for sid in sorted(kayitlar.keys()):
        rec = kayitlar[sid]
        snap_bilgisi = tuple(
            (s.get("tur"), str(s.get("bar_time")))
            for s in rec.get("snapshotlar", [])
        )
        olay_sayisi = len(rec.get("olaylar", []))
        sonuc_durum = (rec.get("sonuc") or {}).get("durum")
        parcalar.append((
            sid,
            rec.get("durum"),
            rec.get("terminal_state"),
            rec.get("terminal_zamani"),
            snap_bilgisi,
            olay_sayisi,
            sonuc_durum,
        ))
    return tuple(parcalar)


def extract_diff(
    defter: Dict[str, Any],
    bilinen_ozet: Optional[Tuple] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Defterden Supabase f2_* tabloları için satır bazlı kayıtları çıkarır.

    Dönen yapı:
        {
            "f2_formations": [...],
            "f2_snapshots": [...],
            "f2_events": [...],
            "f2_outcome_links": [...]
        }
    """
    diff: Dict[str, List[Dict[str, Any]]] = {
        "f2_formations": [],
        "f2_snapshots": [],
        "f2_events": [],
        "f2_outcome_links": [],
    }
    if not isinstance(defter, dict):
        return diff

    stock = defter.get("stock") or ""
    tf = defter.get("timeframe") or ""
    kayitlar = defter.get("kayitlar") or {}

    for sid, rec in kayitlar.items():
        if not isinstance(rec, dict) or not sid:
            continue

        dogum = rec.get("dogum") or {}
        alanlar = dogum.get("alanlar") or {}

        # 1) f2_formations satırı
        # bar_time TEXT olarak birebir korunur (kesinlikle timestamptz yapılmaz!)
        raw_q = _guvenli_float(alanlar.get("raw_quality"))
        geo_atr = _guvenli_float(alanlar.get("geometry_atr"))
        pole_q = _guvenli_float(alanlar.get("pole_quality"))
        s_bar = _guvenli_int(alanlar.get("start_bar") or dogum.get("bar_index"))
        c_dir = _guvenli_int(alanlar.get("classic_dir") or 0) or 0

        form_row = {
            "stable_id": sid,
            "stock": stock,
            "timeframe": tf,
            "family": alanlar.get("family"),
            "pattern_type": alanlar.get("pattern_type"),
            "classic_dir": c_dir,
            "durum": rec.get("durum") or "acik",
            "terminal_state": rec.get("terminal_state"),
            "dogum_bar_time": str(dogum.get("bar_time")) if dogum.get("bar_time") else None,
            "dogum_bar_index": _guvenli_int(dogum.get("bar_index")),
            "raw_quality": raw_q,
            "geometry_atr": geo_atr,
            "pole_quality": pole_q,
            "start_bar": s_bar,
            "ilk_gorulme": rec.get("ilk_gorulme"),
            "son_gorulme": rec.get("son_gorulme"),
            "terminal_zamani": rec.get("terminal_zamani"),
            "dogum_alanlar": {k: schema.json_guvenli(v) for k, v in alanlar.items()},
        }
        diff["f2_formations"].append(form_row)

        # 2) f2_snapshots satırları
        for snap in rec.get("snapshotlar", []):
            if not isinstance(snap, dict):
                continue
            s_tur = snap.get("tur")
            s_btime = snap.get("bar_time")
            if not s_tur or not s_btime:
                continue
            s_alanlar = snap.get("alanlar") or {}

            snap_row = {
                "stable_id": sid,
                "tur": s_tur,
                "bar_time": str(s_btime),  # TEXT
                "bar_index": _guvenli_int(snap.get("bar")),
                "state": snap.get("state"),
                "raw_quality": _guvenli_float(s_alanlar.get("raw_quality")),
                "geometry_score": _guvenli_float(s_alanlar.get("geometry_score")),
                "contraction_score": _guvenli_float(s_alanlar.get("contraction_score")),
                "maturity_score": _guvenli_float(s_alanlar.get("maturity_score")),
                "touch_score": _guvenli_float(s_alanlar.get("touch_score")),
                "slope_shape_score": _guvenli_float(s_alanlar.get("slope_shape_score")),
                "break_strength": _guvenli_float(s_alanlar.get("break_strength")),
                "break_confirmation_strength": _guvenli_float(s_alanlar.get("break_confirmation_strength")),
                "frozen_raw_quality": _guvenli_float(s_alanlar.get("frozen_raw_quality")),
                "alanlar": {k: schema.json_guvenli(v) for k, v in s_alanlar.items()},
            }
            diff["f2_snapshots"].append(snap_row)

        # 3) f2_events satırları
        for ev in rec.get("olaylar", []):
            if not isinstance(ev, dict):
                continue
            e_type = ev.get("type")
            e_name = ev.get("name")
            if not e_type or not e_name:
                continue
            e_btime = str(ev.get("time")) if ev.get("time") else None
            ev_row = {
                "stable_id": sid,
                "type": str(e_type),
                "name": str(e_name),
                "bar": _guvenli_int(ev.get("bar")),
                "bar_time": e_btime,      # TEXT
                "state": ev.get("state"),
                "quality": _guvenli_float(ev.get("quality")),
                "direction": _guvenli_int(ev.get("direction")),
                "price": _guvenli_float(ev.get("price")),
                "payload": {k: schema.json_guvenli(v) for k, v in ev.items()},
            }
            diff["f2_events"].append(ev_row)

        # 4) f2_outcome_links satırları
        sonuc = rec.get("sonuc")
        if isinstance(sonuc, dict) and sonuc.get("durum"):
            out_row = {
                "stable_id": sid,
                "durum": str(sonuc.get("durum")),
                "deneme": _guvenli_int(sonuc.get("deneme")) or 0,
                "kaynak": str(sonuc.get("kaynak")) if sonuc.get("kaynak") else None,  # TEXT
                "outcome": {k: schema.json_guvenli(v) for k, v in (sonuc.get("outcome") or {}).items()},
            }
            diff["f2_outcome_links"].append(out_row)

    return diff


# ============================================================================
# 2) THREAD-SAFE QUEUE (Memory + Disk Backup)
# ============================================================================

class FormationMirrorQueue:
    """Disk-backed, coalescing mirror queue. Local history remains authoritative.

    SQLite bounds RAM even during a long Supabase outage; it is still only as
    durable as DATA_DIR (Render's /tmp does not survive a redeploy).
    """

    _TABLE_KEYS = {
        "f2_formations": ("stable_id",),
        "f2_snapshots": ("stable_id", "tur", "bar_time"),
        "f2_events": ("stable_id", "type", "name", "bar", "bar_time"),
        "f2_outcome_links": ("stable_id",),
    }
    _CONFLICTS = {
        "f2_formations": ("stable_id", "resolution=merge-duplicates,return=minimal"),
        "f2_snapshots": ("stable_id,tur,bar_time", "resolution=ignore-duplicates,return=minimal"),
        "f2_events": ("stable_id,type,name,bar,bar_time", "resolution=ignore-duplicates,return=minimal"),
        "f2_outcome_links": ("stable_id", "resolution=merge-duplicates,return=minimal"),
    }

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR
        self._lock = threading.RLock()
        self._backoff_delay = DEFAULT_BACKOFF_INITIAL
        self._retry_after = 0.0
        self._poison_sayac: Dict[str, int] = {}
        self._last_error = None
        self._sent_count = 0
        self._fingerprints: Dict[str, Tuple] = {}
        # Cache only confirmed rows in this process; pending rows remain in SQLite.
        # This is not an automatic reconciliation of pre-existing missing history.
        self._sent: Dict[Tuple[str, str], str] = {}
        self._over_limit = False
        os.makedirs(self.data_dir, exist_ok=True)
        self._db = sqlite3.connect(os.path.join(self.data_dir, KUYRUK_SQLITE_ADI), timeout=10,
                                   check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS queue ("
                         "id INTEGER PRIMARY KEY, tab TEXT NOT NULL, key TEXT NOT NULL, "
                         "payload TEXT NOT NULL, UNIQUE(tab, key))")
        self._db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY)")
        self._db.commit()
        self.load_from_disk()

    @classmethod
    def _row_key(cls, table: str, row: Dict[str, Any]) -> str:
        return json.dumps([row.get(k) for k in cls._TABLE_KEYS[table]],
                          ensure_ascii=False, separators=(",", ":"))

    def size(self) -> int:
        with self._lock:
            return self._db.execute("SELECT count(*) FROM queue").fetchone()[0]

    def status(self) -> Dict[str, Any]:
        """Heartbeat için sırsız kuyruk ve son aktarım durumu."""
        with self._lock:
            counts = dict(self._db.execute("SELECT tab,count(*) FROM queue GROUP BY tab"))
            return {"bekleyen": sum(counts.values()), "tablolar": counts,
                    "gonderilen": self._sent_count, "son_hata": self._last_error}

    def _insert_rows(self, diff: Dict[str, List[Dict[str, Any]]]) -> int:
        changed = 0
        for table, rows in diff.items():
            if table not in self._TABLE_KEYS:
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = self._row_key(table, row)
                payload = json.dumps(row, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False)
                if self._sent.get((table, key)) == payload:
                    # A newer pending row must not be removed just because an
                    # earlier version happens to equal the last sent version.
                    pending = self._db.execute(
                        "SELECT 1 FROM queue WHERE tab=? AND key=?", (table, key)).fetchone()
                    if not pending:
                        continue
                cur = self._db.execute(
                    "INSERT INTO queue(tab,key,payload) VALUES(?,?,?) "
                    "ON CONFLICT(tab,key) DO UPDATE SET payload=excluded.payload "
                    "WHERE queue.payload != excluded.payload", (table, key, payload))
                changed += cur.rowcount
        return changed

    def enqueue_diff(self, diff: Dict[str, List[Dict[str, Any]]]) -> int:
        if not diff:
            return 0
        with self._lock, self._db:
            added = self._insert_rows(diff)
            count = self.size()
            if count > MAX_QUEUE_ITEMS and not self._over_limit:
                logger.warning("FormationMirrorQueue %d satıra ulaştı; disk kuyruğunda "
                               "tutuluyor, satır atılmadı (DATA_DIR kalıcılığını kontrol edin)", count)
                self._over_limit = True
            elif count <= MAX_QUEUE_ITEMS:
                self._over_limit = False
            return added

    def enqueue_from_defter(self, defter: Dict[str, Any]) -> int:
        if not isinstance(defter, dict):
            return 0
        key = f"{defter.get('stock') or ''}_{defter.get('timeframe') or ''}"
        fp = defter_fingerprint(defter)
        with self._lock:
            if self._fingerprints.get(key) == fp:
                return 0
            # Only mark after a committed enqueue; disk errors must be retryable.
            added = self.enqueue_diff(extract_diff(defter))
            self._fingerprints[key] = fp
            return added

    def save_to_disk(self) -> bool:
        # Every mutation is committed transactionally; retained for callers.
        with self._lock:
            self._db.commit()
        return True

    def load_from_disk(self) -> int:
        """Import the old JSON queue once, atomically with a migration marker."""
        with self._lock:
            if self._db.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
                return 0
            path = _kuyruk_yolu(self.data_dir)
            if not os.path.isfile(path):
                # Mark even if absent; an unrelated stale file must not be
                # imported over an already active SQLite queue later.
                with self._db:
                    self._db.execute("INSERT INTO metadata VALUES('legacy_imported')")
                return 0
            try:
                with open(path, encoding="utf-8") as source:
                    data = json.load(source)
                if not isinstance(data, dict):
                    raise ValueError("kuyruk JSON nesnesi değil")
                with self._db:
                    count = self._insert_rows({t: rows for t, rows in data.items()
                                               if t in self._TABLE_KEYS and isinstance(rows, list)})
                    self._db.execute("INSERT INTO metadata VALUES('legacy_imported')")
                logger.info("Eski mirror kuyruğu SQLite'a aktarıldı: %d satır", count)
                return count
            except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
                # Keep the old file and retry on next process start.
                logger.warning("Eski mirror kuyruğu aktarılamadı; dosya korundu: %s", exc)
                return 0

    def flush(self, store=None, max_batches: int = 10) -> int:
        if store is None or not getattr(store, "enabled", False) or not getattr(store, "writable", True):
            return 0
        if time.monotonic() < self._retry_after:
            return 0
        sent = 0
        temporary_error = False
        with self._lock:
            for table, (conflict, prefer) in self._CONFLICTS.items():
                batches = 0
                while batches < max_batches:
                    batch = self._db.execute(
                        "SELECT id,key,payload FROM queue WHERE tab=? ORDER BY id LIMIT ?",
                        (table, FLUSH_BATCH_SIZE)).fetchall()
                    if not batch:
                        break
                    if table != "f2_formations":
                        # A limited formation batch may leave parents pending.
                        # Do not send children before those parents exist remotely.
                        pending_parents = {
                            json.loads(row[0])[0] for row in self._db.execute(
                                "SELECT key FROM queue WHERE tab='f2_formations'")
                        }
                        batch = [row for row in batch
                                 if json.loads(row[2]).get("stable_id") not in pending_parents]
                        if not batch:
                            break
                    items = [json.loads(row[2]) for row in batch]
                    try:
                        request = getattr(store, "request_table_for_mirror", store.request_table)
                        resp = request(table, "POST", params={"on_conflict": conflict},
                                       json=items, headers={"Prefer": prefer})
                    except Exception as exc:
                        # Exception messages from transports can contain URLs or keys.
                        logger.warning("Supabase %s flush exception: %s", table, type(exc).__name__)
                        resp = None
                    status = getattr(resp, "status_code", None)
                    if status is not None and 200 <= status < 300:
                        with self._db:
                            self._db.executemany("DELETE FROM queue WHERE id=? AND payload=?",
                                                 [(row[0], row[2]) for row in batch])
                        for _, key, payload in batch:
                            self._sent[(table, key)] = payload
                        sent += len(batch)
                        batches += 1
                        self._backoff_delay = DEFAULT_BACKOFF_INITIAL
                        self._poison_sayac[table] = 0
                        if self._last_error and self._last_error.get("tablo") == table:
                            self._last_error = None
                        continue
                    self._last_error = {"tablo": table, "durum": status, "batch": len(batch)}
                    logger.warning("Supabase %s flush reddedildi (durum=%s, batch=%d)",
                                   table, status, len(batch))
                    if status in (400, 422):
                        count = self._poison_sayac.get(table, 0) + 1
                        self._poison_sayac[table] = count
                        if count >= POISON_ESIK:
                            # A batch error does not identify its bad row; never
                            # discard the entire batch (or its healthy neighbours).
                            logger.error("Supabase %s: batch %d kez reddedildi; "
                                         "kayıtlar disk kuyruğunda korunuyor", table, count)
                            self._poison_sayac[table] = 0
                    temporary_error = True
                    break
        if temporary_error:
            self._retry_after = time.monotonic() + self._backoff_delay
            self._backoff_delay = min(self._backoff_delay * 2.0, DEFAULT_BACKOFF_MAX)
        with self._lock:
            self._sent_count += sent
        if sent:
            logger.debug("Mirror flush tamamlandı: %d satır Supabase'e yazıldı", sent)
        return sent

# Global singleton instance
_GLOBAL_QUEUE: Optional[FormationMirrorQueue] = None
_QUEUE_LOCK = threading.RLock()
_MIRROR_WRITES_ENABLED = True


def set_mirror_writes_enabled(enabled: bool) -> None:
    """Disable mirror enqueue in read-only bot mode; existing disk data is kept."""
    global _MIRROR_WRITES_ENABLED
    with _QUEUE_LOCK:
        _MIRROR_WRITES_ENABLED = bool(enabled)


def get_mirror_queue(data_dir: Optional[str] = None) -> FormationMirrorQueue:
    global _GLOBAL_QUEUE
    with _QUEUE_LOCK:
        if _GLOBAL_QUEUE is None:
            _GLOBAL_QUEUE = FormationMirrorQueue(data_dir=data_dir)
        return _GLOBAL_QUEUE


def mirror_kaydet(defter: Dict[str, Any], store=None, data_dir: Optional[str] = None) -> int:
    """Tek yazım noktası: local defterdeki diff'i kuyruğa alır ve flush dener.

    Asla exception fırlatmaz, botu düşürmez.
    """
    if not _MIRROR_WRITES_ENABLED or (store is not None and not getattr(store, "writable", True)):
        return 0
    try:
        q = get_mirror_queue(data_dir)
        eklenen = q.enqueue_from_defter(defter)
        if store is not None and eklenen > 0:
            q.flush(store)
        return eklenen
    except Exception as exc:
        logger.warning("Mirror kuyruğuna yazılamadı (%s); yerel defter korunur", type(exc).__name__)
        return 0


# ============================================================================
# 3) HYDRATION (Local-First Recovery)
# ============================================================================

def hydrate_stock_tf(
    stock: str,
    tf: str,
    store=None,
    data_dir: Optional[str] = None,
    force: bool = False,
) -> int:
    """Supabase f2_* tablolarından local history'yi doldurur.

    Kritik ilkeler:
      1. Local history doluysa authoritative'dir; overwrite edilmez!
      2. Yalnızca local defter boşsa (veya force=True ise) hydrate yapılır.
      3. bar_time TEXT olarak korunur (kesinlikle ISO T'ye dönüştürülmez).
      4. BAR_ALANLARI int tip güvenliği ile aktarılır.
    """
    if store is None or not getattr(store, "enabled", False):
        return 0

    defter_yerel = fh.yukle(stock, tf, data_dir)
    mevcut_kayitlar = fh._kayitlar(defter_yerel)

    # Local doluysa ve zorlama yoksa dokunma
    if mevcut_kayitlar and not force:
        return 0

    try:
        # 1) Formations çek
        # Sadece bu hisse ve timeframe için
        resp = store.request_table(
            "f2_formations",
            "GET",
            params={
                "select": "*",
                "stock": f"eq.{stock}",
                "timeframe": f"eq.{tf}",
            },
        )
        if resp is None or not (200 <= resp.status_code < 300):
            return 0
        form_rows = resp.json()
        if not isinstance(form_rows, list) or not form_rows:
            return 0

        sids = [r.get("stable_id") for r in form_rows if r.get("stable_id")]
        if not sids:
            return 0

        # 2) Snapshots çek
        snap_rows = []
        resp_snap = store.request_table(
            "f2_snapshots",
            "GET",
            params={
                "select": "*",
                "stable_id": f"in.({','.join(sids)})",
                "order": "id.asc",
            },
        )
        if resp_snap is None or not (200 <= resp_snap.status_code < 300):
            logger.warning("Hydration iptal: f2_snapshots okunamadı (%s %s)", stock, tf)
            return 0
        res_json = resp_snap.json()
        if not isinstance(res_json, list):
            logger.warning("Hydration iptal: f2_snapshots yanıtı geçersiz (%s %s)", stock, tf)
            return 0
        snap_rows = res_json

        # 3) Events çek
        event_rows = []
        resp_ev = store.request_table(
            "f2_events",
            "GET",
            params={
                "select": "*",
                "stable_id": f"in.({','.join(sids)})",
                "order": "id.asc",
            },
        )
        if resp_ev is None or not (200 <= resp_ev.status_code < 300):
            logger.warning("Hydration iptal: f2_events okunamadı (%s %s)", stock, tf)
            return 0
        res_json = resp_ev.json()
        if not isinstance(res_json, list):
            logger.warning("Hydration iptal: f2_events yanıtı geçersiz (%s %s)", stock, tf)
            return 0
        event_rows = res_json

        # 4) Outcome links çek
        out_rows = {}
        resp_out = store.request_table(
            "f2_outcome_links",
            "GET",
            params={
                "select": "*",
                "stable_id": f"in.({','.join(sids)})",
            },
        )
        if resp_out is None or not (200 <= resp_out.status_code < 300):
            logger.warning("Hydration iptal: f2_outcome_links okunamadı (%s %s)", stock, tf)
            return 0
        res_json = resp_out.json()
        if not isinstance(res_json, list):
            logger.warning("Hydration iptal: f2_outcome_links yanıtı geçersiz (%s %s)", stock, tf)
            return 0
        for row in res_json:
            if row.get("stable_id"):
                out_rows[row["stable_id"]] = row

        # Snapshots ve events SID'e göre grupla
        snaps_by_sid: Dict[str, list] = {}
        for s in snap_rows:
            sid = s.get("stable_id")
            if sid:
                snaps_by_sid.setdefault(sid, []).append(s)

        events_by_sid: Dict[str, list] = {}
        for e in event_rows:
            sid = e.get("stable_id")
            if sid:
                events_by_sid.setdefault(sid, []).append(e)

        # Local defter oluştur
        hydrate_edilen_sayi = 0
        for r in form_rows:
            sid = r.get("stable_id")
            if not sid:
                continue

            # Doğum alanları
            dogum_alanlar = r.get("dogum_alanlar") or {}
            if not isinstance(dogum_alanlar, dict):
                dogum_alanlar = {}

            # Tip güvenliği düzeltmeleri
            dogum_alanlar_temiz: Dict[str, Any] = {}
            for k, v in dogum_alanlar.items():
                if k in BAR_ALANLARI:
                    dogum_alanlar_temiz[k] = _guvenli_int(v)
                elif isinstance(v, (int, float, str, bool)) or v is None:
                    dogum_alanlar_temiz[k] = v
                else:
                    dogum_alanlar_temiz[k] = schema.json_guvenli(v)

            # Snapshots listesini yerel formata dönüştür
            yerel_snapshots = []
            for s in snaps_by_sid.get(sid, []):
                s_alanlar = s.get("alanlar") or {}
                if not isinstance(s_alanlar, dict):
                    s_alanlar = {}
                s_alanlar_temiz = {
                    k: (_guvenli_int(v) if k in BAR_ALANLARI else v)
                    for k, v in s_alanlar.items()
                }
                snap_rec: Dict[str, Any] = {
                    "tur": s.get("tur"),
                    "bar_time": str(s.get("bar_time")),  # TEXT
                    "alanlar": s_alanlar_temiz,
                    "stable_id": sid,
                    "state": s.get("state"),
                    "bar": _guvenli_int(s.get("bar_index")),
                }
                yerel_snapshots.append(snap_rec)

            # Events listesini yerel formata dönüştür
            yerel_events = []
            for e in events_by_sid.get(sid, []):
                payload = e.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {}
                ev_rec = {
                    "type": e.get("type"),
                    "name": e.get("name"),
                    "bar": _guvenli_int(e.get("bar")),
                    "time": str(e.get("bar_time")) if e.get("bar_time") else None,
                    "state": e.get("state"),
                    "quality": _guvenli_float(e.get("quality")),
                    "direction": _guvenli_int(e.get("direction")),
                    "price": _guvenli_float(e.get("price")),
                    "stable_id": sid,
                }
                # Payload'daki ek alanları koru
                for pk, pv in payload.items():
                    if pk not in ev_rec:
                        ev_rec[pk] = pv
                yerel_events.append(ev_rec)

            # Doğum kaydı
            b_index = _guvenli_int(r.get("dogum_bar_index"))
            b_time = str(r.get("dogum_bar_time")) if r.get("dogum_bar_time") else None

            rec: Dict[str, Any] = {
                "stable_id": sid,
                "durum": r.get("durum") or "acik",
                "ilk_gorulme": r.get("ilk_gorulme"),
                "son_gorulme": r.get("son_gorulme"),
                "terminal_state": r.get("terminal_state"),
                "terminal_zamani": r.get("terminal_zamani"),
                "dogum": {
                    "bar_time": b_time,  # TEXT birebir!
                    "bar_index": b_index,
                    "alanlar": dogum_alanlar_temiz,
                },
                "olaylar": yerel_events,
                "snapshotlar": yerel_snapshots,
            }

            # Outcome linki varsa ekle
            if sid in out_rows:
                orow = out_rows[sid]
                rec["sonuc"] = {
                    "durum": orow.get("durum"),
                    "deneme": _guvenli_int(orow.get("deneme")) or 0,
                    "kaynak": str(orow.get("kaynak")) if orow.get("kaynak") else None,
                    "outcome": orow.get("outcome") or {},
                }

            mevcut_kayitlar[sid] = rec
            hydrate_edilen_sayi += 1

        if hydrate_edilen_sayi > 0:
            fh.kaydet(defter_yerel, data_dir)
            logger.info(
                "Hydration tamamlandı: %s %s -> %d formasyon Supabase'ten yüklendi",
                stock, tf, hydrate_edilen_sayi,
            )
        return hydrate_edilen_sayi

    except Exception as exc:
        logger.warning("Hydration hatası (%s %s): %s", stock, tf, exc)
        return 0


def hydrate_all_open(store=None, data_dir: Optional[str] = None) -> int:
    """Tüm aktif evren için yerel defteri boş olanları Supabase'ten doldurur."""
    if store is None or not getattr(store, "enabled", False):
        return 0
    from config import ACTIVE_STOCKS
    tfler = ("1h", "2h", "4h", "1d")
    toplam = 0
    for stock in ACTIVE_STOCKS:
        for tf in tfler:
            toplam += hydrate_stock_tf(stock, tf, store=store, data_dir=data_dir, force=False)
    return toplam


# ============================================================================
# 4) READ REPOSITORY (Minimal Local-First Abstraction)
# ============================================================================

class LocalFormationRepository:
    """Local JSON history için salt-okunur minimal repository arayüzü.

    UI doğrudan Supabase veya JSON detaylarına bağlanmasın diye arayüz sağlar.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR

    def get_formation(self, stable_id: str, stock: Optional[str] = None,
                      timeframe: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """stable_id ile tek formation kaydını döner."""
        if not stable_id:
            return None
        if stock and timeframe:
            defter = fh.yukle(stock, timeframe, self.data_dir)
            return fh.kayit_getir(defter, stable_id)

        # stock/timeframe verilmediyse dizindeki tüm defterleri tara
        klasor = os.path.join(self.data_dir, fh.FORMATION_HISTORY_ALT_DOSYA)
        if not os.path.isdir(klasor):
            return None
        for fn in os.listdir(klasor):
            if fn.endswith(".json") and "_" in fn:
                s, t = fn[:-5].rsplit("_", 1)
                defter = fh.yukle(s, t, self.data_dir)
                rec = fh.kayit_getir(defter, stable_id)
                if rec is not None:
                    return rec
        return None

    def get_formations(self, stock: str, timeframe: str,
                       durum: Optional[str] = None) -> List[Dict[str, Any]]:
        """Verilen stock ve timeframe için kayıtları filtreler."""
        defter = fh.yukle(stock, timeframe, self.data_dir)
        kayitlar = fh.kayitlar(defter)
        if durum:
            return [r for r in kayitlar if r.get("durum") == durum]
        return kayitlar

    def get_open_formations(self, stock: str, timeframe: str) -> List[Dict[str, Any]]:
        """Açık (terminal olmayan) formasyonları döner."""
        defter = fh.yukle(stock, timeframe, self.data_dir)
        return [r for r in fh.kayitlar(defter) if r.get("durum") != fh.DURUM_TERMINAL]

    def get_timeline(self, stable_id: str, stock: Optional[str] = None,
                     timeframe: Optional[str] = None) -> List[Dict[str, Any]]:
        """Snapshot ve olayları kronolojik sıra ile tek zaman çizelgesinde birleştirir."""
        rec = self.get_formation(stable_id, stock, timeframe)
        if not rec:
            return []
        items = []
        for s in rec.get("snapshotlar", []):
            items.append({
                "kategori": "snapshot",
                "tur": s.get("tur"),
                "bar_time": s.get("bar_time"),
                "bar": s.get("bar"),
                "state": s.get("state"),
                "alanlar": s.get("alanlar", {}),
            })
        for ev in rec.get("olaylar", []):
            items.append({
                "kategori": "olay",
                "tur": ev.get("type"),
                "bar_time": ev.get("time"),
                "bar": ev.get("bar"),
                "state": ev.get("state"),
                "name": ev.get("name"),
                "quality": ev.get("quality"),
            })
        items.sort(key=lambda x: str(x.get("bar_time") or ""))
        return items

    def get_outcome(self, stable_id: str, stock: Optional[str] = None,
                    timeframe: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Formation'a bağlı outcome kaydını döner."""
        rec = self.get_formation(stable_id, stock, timeframe)
        if rec and isinstance(rec.get("sonuc"), dict):
            return rec["sonuc"]
        return None

    def get_recent(self, limit: int = 20, stock: Optional[str] = None,
                   timeframe: Optional[str] = None) -> List[Dict[str, Any]]:
        """En son görülen kayıtları döner."""
        tum: List[Dict[str, Any]] = []
        if stock and timeframe:
            tum = self.get_formations(stock, timeframe)
        else:
            klasor = os.path.join(self.data_dir, fh.FORMATION_HISTORY_ALT_DOSYA)
            if os.path.isdir(klasor):
                for fn in os.listdir(klasor):
                    if fn.endswith(".json") and "_" in fn:
                        s, t = fn[:-5].rsplit("_", 1)
                        tum.extend(self.get_formations(s, t))
        tum.sort(key=lambda r: str(r.get("son_gorulme") or ""), reverse=True)
        return tum[:limit]
