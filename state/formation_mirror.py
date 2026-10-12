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
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from config import DATA_DIR
from state import formation_history as fh
from state import formation_schema as schema
from state.paths import formation_history_yolu

logger = logging.getLogger(__name__)

# Kuyruk ve flush sabitleri
MAX_QUEUE_ITEMS = 5000         # Kuyruk bellek tavanı
FLUSH_BATCH_SIZE = 100         # Tek PostgREST isteğindeki azami satır
DEFAULT_BACKOFF_INITIAL = 30.0 # İlk hata beklemesi (sn)
DEFAULT_BACKOFF_MAX = 600.0    # Azami bekleme (10 dk)
KUYRUK_DOSYA_ADI = "f2_kuyruk.json"

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
    except (TypeError, ValueError):
        return None


def _guvenli_float(val: Any) -> Optional[float]:
    """Hydration ve diff sırasında float tip güvenliği sağlar."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


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
    """Thread-safe bellek ve disk yedekli taşıma kuyruğu.

    P2.6 Kuralı: Kuyruk türetilmiş durumdur, local history source of truth'tur.
    Render Free restart'ında disk kuyruğu korunur; redeploy'da ephemeral disk
    silinir (bu sınır belgelenmiştir).
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR
        self._lock = threading.RLock()
        # Tablo adına göre öğe kuyrukları: { "f2_formations": deque(), ... }
        self._queues: Dict[str, deque] = {
            "f2_formations": deque(),
            "f2_snapshots": deque(),
            "f2_events": deque(),
            "f2_outcome_links": deque(),
        }
        self._backoff_delay = DEFAULT_BACKOFF_INITIAL
        self._retry_after = 0.0
        self._fingerprints: Dict[str, Tuple] = {}
        self.load_from_disk()

    def size(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def enqueue_diff(self, diff: Dict[str, List[Dict[str, Any]]]) -> int:
        """Diff satırlarını kuyruğa ekler; tavan aşılırsa en eskileri atar."""
        if not diff:
            return 0
        eklenen = 0
        with self._lock:
            for table, rows in diff.items():
                if table not in self._queues:
                    continue
                q = self._queues[table]
                for row in rows:
                    q.append(row)
                    eklenen += 1

            # Tavan kontrolü
            toplam = self.size()
            if toplam > MAX_QUEUE_ITEMS:
                fazla = toplam - MAX_QUEUE_ITEMS
                logger.warning(
                    "FormationMirrorQueue kapasitesi aşıldı (%d > %d); "
                    "en eski %d satır atılıyor (local history korunuyor)",
                    toplam, MAX_QUEUE_ITEMS, fazla,
                )
                # En dolu kuyruklardan kırp
                atilan = 0
                while atilan < fazla:
                    en_dolu = max(self._queues.values(), key=len)
                    if not en_dolu:
                        break
                    en_dolu.popleft()
                    atilan += 1

            if eklenen > 0:
                self.save_to_disk()
        return eklenen

    def enqueue_from_defter(self, defter: Dict[str, Any]) -> int:
        """Defteri inceler; içerik parmak izi değiştiyse farkı kuyruğa alır."""
        if not isinstance(defter, dict):
            return 0
        stock = defter.get("stock") or ""
        tf = defter.get("timeframe") or ""
        key = f"{stock}_{tf}"

        fp = defter_fingerprint(defter)
        with self._lock:
            if self._fingerprints.get(key) == fp:
                return 0  # İçerik değişmedi -> sıfır write amplifikasyonu
            self._fingerprints[key] = fp

        diff = extract_diff(defter)
        return self.enqueue_diff(diff)

    def save_to_disk(self) -> bool:
        """Kuyruğu atomik olarak diske kaydeder."""
        try:
            yol = _kuyruk_yolu(self.data_dir)
            klasor = os.path.dirname(yol)
            if klasor:
                os.makedirs(klasor, exist_ok=True)
            with self._lock:
                snapshot = {
                    t: list(q) for t, q in self._queues.items()
                }
            tmp = yol + f".tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, yol)
            return True
        except Exception as exc:
            logger.debug("Mirror kuyruğu diske yazılamadı: %s", exc)
            return False

    def load_from_disk(self) -> int:
        """Diskteki kuyruğu yükler."""
        yol = _kuyruk_yolu(self.data_dir)
        if not os.path.isfile(yol):
            return 0
        try:
            with open(yol, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return 0
            yuklenen = 0
            with self._lock:
                for table, items in data.items():
                    if table in self._queues and isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                self._queues[table].append(it)
                                yuklenen += 1
            if yuklenen:
                logger.info("Mirror kuyruğu diskten yüklendi: %d öğe", yuklenen)
            return yuklenen
        except Exception as exc:
            logger.debug("Mirror kuyruğu diskten okunamadı: %s", exc)
            return 0

    def flush(self, store=None, max_batches: int = 10) -> int:
        """Kuyruktaki satırları Supabase'e gönderir.

        PostgREST batch endpoint'leri kullanılır:
            f2_formations: on_conflict=stable_id (merge-duplicates)
            f2_snapshots:  on_conflict=stable_id,tur,bar_time (ignore-duplicates)
            f2_events:     on_conflict=stable_id,type,name,bar,bar_time (ignore-duplicates)
            f2_outcome_links: on_conflict=stable_id (merge-duplicates)
        """
        if store is None:
            return 0
        if not getattr(store, "enabled", False):
            return 0

        simdi = time.monotonic()
        if simdi < self._retry_after:
            return 0  # Backoff süresi bekleniyor

        on_conflicts = {
            "f2_formations": ("stable_id", "resolution=merge-duplicates,return=minimal"),
            "f2_snapshots": ("stable_id,tur,bar_time", "resolution=ignore-duplicates,return=minimal"),
            "f2_events": ("stable_id,type,name,bar,bar_time", "resolution=ignore-duplicates,return=minimal"),
            "f2_outcome_links": ("stable_id", "resolution=merge-duplicates,return=minimal"),
        }

        gonderilen_toplam = 0
        hata_olustu = False

        with self._lock:
            for table, q in self._queues.items():
                if not q:
                    continue
                conf_key, prefer_val = on_conflicts.get(table, (None, "return=minimal"))
                params = {"on_conflict": conf_key} if conf_key else None
                headers = {"Prefer": prefer_val}

                batches_run = 0
                while q and batches_run < max_batches:
                    batch_size = min(len(q), FLUSH_BATCH_SIZE)
                    items = [q[i] for i in range(batch_size)]

                    try:
                        resp = store.request_table(
                            table,
                            "POST",
                            params=params,
                            json=items,
                            headers=headers,
                        )
                    except Exception as exc:
                        logger.warning("Supabase %s flush exception: %s", table, exc)
                        resp = None

                    if resp is not None and 200 <= resp.status_code < 300:
                        # Başarılı: gönderilen öğeleri kuyruktan çıkar
                        for _ in range(batch_size):
                            q.popleft()
                        gonderilen_toplam += batch_size
                        batches_run += 1
                        # Başarıda backoff sıfırla
                        self._backoff_delay = DEFAULT_BACKOFF_INITIAL
                    else:
                        hata_olustu = True
                        break

                if hata_olustu:
                    break

        if hata_olustu:
            self._retry_after = time.monotonic() + self._backoff_delay
            self._backoff_delay = min(self._backoff_delay * 2.0, DEFAULT_BACKOFF_MAX)
            logger.debug(
                "Mirror flush başarısız oldu; %.1f sn backoff devrede",
                self._backoff_delay,
            )

        if gonderilen_toplam > 0:
            self.save_to_disk()
            logger.debug("Mirror flush tamamlandı: %d satır Supabase'e yazıldı", gonderilen_toplam)

        return gonderilen_toplam


# Global singleton instance
_GLOBAL_QUEUE: Optional[FormationMirrorQueue] = None
_QUEUE_LOCK = threading.RLock()


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
    try:
        q = get_mirror_queue(data_dir)
        eklenen = q.enqueue_from_defter(defter)
        if store is not None and eklenen > 0:
            q.flush(store)
        return eklenen
    except Exception as exc:
        logger.debug("mirror_kaydet sessizce atlandı: %s", exc)
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
        if resp_snap is not None and 200 <= resp_snap.status_code < 300:
            res_json = resp_snap.json()
            if isinstance(res_json, list):
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
        if resp_ev is not None and 200 <= resp_ev.status_code < 300:
            res_json = resp_ev.json()
            if isinstance(res_json, list):
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
        if resp_out is not None and 200 <= resp_out.status_code < 300:
            res_json = resp_out.json()
            if isinstance(res_json, list):
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
