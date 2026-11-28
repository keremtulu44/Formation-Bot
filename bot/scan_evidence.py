"""Bounded, local scan evidence; observation counts are NOT unique deliveries.

No provider calls, Telegram calls or Supabase writes. A damaged history is never
silently replaced. Snapshots are published only at the end of a scan.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import logging
from pathlib import Path
import threading

import config
from data.seed_cache import _atomic_json_write

log = logging.getLogger(__name__)
_LOCK = threading.RLock()
MAX_RUNS = 512
MAX_BYTES = 4_000_000


def evidence_path(directory=None):
    return Path(directory or config.DATA_DIR) / "scan_evidence.json"


def load_evidence(directory=None):
    path = evidence_path(directory)
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("tarama sicili boyut sınırını aştı")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("runs"), list):
        raise ValueError("tarama sicili şeması geçersiz")
    if any(not isinstance(row, dict) or not row.get("finished_at") for row in raw["runs"]):
        raise ValueError("tarama sicili satırı geçersiz")
    return raw["runs"]


def save_evidence(row, directory=None):
    try:
        with _LOCK:
            rows = load_evidence(directory)
            rows.append(row)
            _atomic_json_write(str(evidence_path(directory)), {"version": 1, "runs": rows[-MAX_RUNS:]})
        return True
    except (OSError, ValueError, TypeError):
        log.exception("Tarama sicili yazılamadı; mevcut dosya korunuyor")
        return False


def format_evidence(rows):
    if not rows:
        return "ℹ️ Henüz tarama sicili yok. Yeni taramalar kaydedildikçe /akis veri ve alarm akışını gösterir."
    row = rows[-1]
    data, main, domain = (row.get(key) or {} for key in ("data", "formation", "domain"))
    lines = [
        "🕯️ Mum ve alarm akışı",
        f"Son koşu: {row['finished_at']}",
        f"Kapsam: {row.get('processed', 0)}/{row.get('requested', 0)} · {row.get('mode')} · {row.get('policy')}",
        f"1H yanıt: {data.get('received', 0)} · hata {data.get('fetch_failed', 0)} · tekrar kurtardı {data.get('retry_recovered', 0)}",
        f"Kaynak: Yahoo {data.get('yahoo', 0)} · TV {data.get('tvdatafeed', 0)} · bilinmeyen {data.get('source_unknown', 0)}",
        f"Analiz: sağlayıcı {data.get('provider_used', 0)} · cache {data.get('cache_used', 0)} · atlanan {data.get('skipped', 0)}",
        f"Veri engeli: yetersiz {data.get('insufficient', 0)} · bayat {data.get('stale', 0)} · split {data.get('split', 0)} · cache reddi {data.get('cache_rejected', 0)}",
        f"Formasyon: eşik altı {main.get('below_threshold', 0)} · özete {main.get('deferred', 0)} · durum dışı {main.get('state_disabled', 0)}",
        f"Ana DM: deneme {main.get('attempted', 0)} · başarılı dönüş {main.get('sent', 0)} · başarısız/engelli {main.get('not_sent', 0)}",
        f"Domain: destek sonrası tetik {domain.get('triggered', 0)} · politika eledi {domain.get('policy_rejected', 0)} · aday {domain.get('candidates', 0)}",
        f"Domain sevk: tekrar/bütçe vb. filtre {domain.get('dispatch_filtered', 0)} · kart/özet başarılı dönüş {domain.get('dispatch_ok', 0)}",
    ]
    if row.get("problems"):
        lines.append("Sorun örnekleri: " + ", ".join(row["problems"]))
    days = {}
    for run in rows:
        if run.get("mode") != "scheduled_full":
            continue  # Manual/subset/analysis-only runs cannot inflate the daily comparison.
        day = run["finished_at"][:10]
        bucket = days.setdefault(day, Counter())
        bucket["runs"] += 1
        bucket["requested"] += run.get("requested", 0)
        bucket["processed"] += run.get("processed", 0)
        bucket["fetch_failed"] += (run.get("data") or {}).get("fetch_failed", 0)
        bucket["main_ok"] += (run.get("formation") or {}).get("sent", 0)
        bucket["domain_ok"] += (run.get("domain") or {}).get("dispatch_ok", 0)
        for name in ("triggered", "policy_rejected"):
            bucket[name] += (run.get("domain") or {}).get(name, 0)
    lines.append("\nSaklanan otomatik tam-evren koşuları (son 7 kayıtlı gün):")
    for day in sorted(days)[-7:]:
        d = days[day]
        lines.append(f"{day}: {d['runs']} tur · {d['processed']}/{d['requested']} analiz · veri hata {d['fetch_failed']} · tetik {d['triggered']} / eleme {d['policy_rejected']} · ana DM dönüş {d['main_ok']} / domain sevk {d['domain_ok']}")
    lines.append("Sayaçlar tarama gözlemidir; aynı olay yeniden görülebilir. Kart/özet dönüşü hedef başına Telegram teslim adedi değildir. Sicil başlangıcı/restart/disk kaybı nedeniyle tam gün garantisi yok; önceki 15→3–5 düşüşünü tek başına açıklamaz.")
    return "\n".join(lines)


def command_report(directory=None):
    try:
        with _LOCK:
            return format_evidence(load_evidence(directory))
    except (OSError, ValueError, TypeError):
        return "⚠️ Tarama sicili okunamadı; bozuk dosya korunuyor. Canlı tarama ve mevcut teslim sağlık kaydını /durum ile kontrol edin."


def new_snapshot(*, started_at, finished_at, requested, processed, mode, policy,
                 data, formation, domain, problems):
    # Stable plain-JSON schema; no raw provider errors, text, credentials or frames.
    datetime.fromisoformat(finished_at)
    return {"started_at": started_at, "finished_at": finished_at,
            "requested": requested, "processed": processed, "mode": mode,
            "policy": policy, "data": dict(data), "formation": dict(formation),
            "domain": dict(domain), "problems": list(problems)[:12]}
