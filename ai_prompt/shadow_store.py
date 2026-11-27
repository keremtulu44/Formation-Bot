"""Gölge (shadow) AI yorum + gizli 5-filtre kayıt ve ileri ölçüm katmanı.

- Varsayılan olarak TAMAMEN YEREL ve SALT-OKUNUR güvenlidir: Supabase'e yazım
  yalnızca `allow_supabase_write=True` VE yazılabilir (`writable=True`) bir
  `SupabaseStore` verildiğinde yapılır.
- Hiçbir harici AI API çağrısı yapmaz ve Telegram'a mesaj göndermez.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .kap_bridge import format_kap_for_prompt
from .verdict import VERDICT_FIELDS, parse_ai_response

logger = logging.getLogger(__name__)

AI_YORUM_TEST_TABLE = "ai_yorum_test"
AI_YORUM_TEST_VIEW = "v_ai_yorum_test_ozet"
DEFAULT_LOCAL_SHADOW_FILE = "ai_yorum_test.json"

DEFAULT_HORIZON_BARS: dict[str, int] = {
    "1h": 16,
    "2h": 12,
    "4h": 10,
    "1d": 5,
}
DIRECTION_HIT_MIN_PCT = 0.5


def _iso_utc(ts: Any) -> str:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("Europe/Istanbul")
    return stamp.tz_convert("UTC").isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def _context_summary(packet: Mapping[str, Any]) -> dict[str, Any]:
    main_tf = str(packet.get("main_tf") or "")
    row = (packet.get("timeframes") or {}).get(main_tf) or {}
    ms = (row.get("market_structure") or {}).get("scopes") or {}
    ext = ms.get("dış") if isinstance(ms, Mapping) else None
    pat = row.get("pattern") if isinstance(row.get("pattern"), Mapping) else None
    vol = row.get("volume") if isinstance(row.get("volume"), Mapping) else None
    return {
        "source": packet.get("source"),
        "daily_source": packet.get("daily_source"),
        "research_mode": packet.get("research_mode"),
        "external_ms_state": ext.get("state") if isinstance(ext, Mapping) else None,
        "volume_state": vol.get("state") if isinstance(vol, Mapping) else None,
        "pattern_name": (pat.get("type") or pat.get("name")) if isinstance(pat, Mapping) else None,
        "pattern_state": pat.get("state") if isinstance(pat, Mapping) else None,
        "pattern_break_direction": pat.get("break_direction") if isinstance(pat, Mapping) else None,
        "stabil_support": _safe_float(row.get("chart_stabil_support")),
        "stabil_resistance": _safe_float(row.get("chart_stabil_resistance")),
    }


def make_shadow_key(
    symbol: str,
    tf: str,
    as_of: Any,
    *,
    prompt_surumu: str = "api-v1",
    model_adi: str = "",
) -> str:
    model_slug = (model_adi or "bilinmiyor").strip().lower().replace("|", "_")
    version_slug = (prompt_surumu or "api-v1").strip().lower().replace("|", "_")
    return f"{str(symbol).strip().upper()}|{str(tf).strip().lower()}|{_iso_utc(as_of)}|{version_slug}|{model_slug}"


def build_shadow_record(
    packet: Mapping[str, Any],
    raw_ai_text: str,
    *,
    model_adi: str = "",
    prompt_surumu: str = "api-v1",
    system_sha256: str = "",
    kaynak_turu: str = "manuel",
    tetikleyici_tur: str | None = None,
    kap_context: Mapping[str, Any] | None = None,
    telegrama_gitti: bool = False,
    min_words: int = 80,
    max_words: int = 220,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Packet + ham AI yanıtından `public.ai_yorum_test` satırı ve ayrıştırma sonucu üretir."""
    parsed = parse_ai_response(raw_ai_text, require_verdict=False, min_words=min_words, max_words=max_words)
    symbol = str(packet["symbol"]).strip().upper()
    main_tf = str(packet["main_tf"]).strip().lower()
    as_of_iso = _iso_utc(packet["as_of"])
    row_main = (packet.get("timeframes") or {}).get(main_tf) or {}
    ref_price = _safe_float(row_main.get("last_close"))
    verdict = parsed["verdict"] or {}
    now_iso = datetime.now(timezone.utc).isoformat()
    context_summary = _context_summary(packet)
    if kap_context is not None:
        kap_info = format_kap_for_prompt(kap_context, as_of=packet.get("as_of"))
        if kap_info["meta_summary"] is not None:
            context_summary["kap"] = kap_info["meta_summary"]

    record: dict[str, Any] = {
        "anahtar": make_shadow_key(
            symbol,
            main_tf,
            as_of_iso,
            prompt_surumu=prompt_surumu,
            model_adi=model_adi,
        ),
        "sembol": symbol,
        "tf": main_tf,
        "kesit_zamani": as_of_iso,
        "referans_fiyat": ref_price,
        "kaynak_turu": str(kaynak_turu or "manuel"),
        "tetikleyici_tur": str(tetikleyici_tur) if tetikleyici_tur else None,
        "egilim": verdict.get("egilim"),
        "guc": verdict.get("guc"),
        "mtf_uyum": verdict.get("mtf_uyum"),
        "risk": verdict.get("risk"),
        "yayin_degeri": verdict.get("yayin_degeri"),
        "filtreler": {k: verdict[k] for k in VERDICT_FIELDS if k in verdict},
        "temiz_yorum": parsed["visible_text"],
        "ham_sonuc_blogu": parsed["raw_verdict_block"],
        "dogrulama": {
            "verdict_valid": parsed["verdict_valid"],
            "verdict_errors": parsed["verdict_errors"],
            "valid_structure": parsed["validation"]["valid_structure"],
            "word_count": parsed["validation"]["word_count"],
            "section_word_counts": parsed["validation"]["section_word_counts"],
            "warnings": parsed["validation"]["warnings"],
            "error": parsed["validation"]["error"],
            "ok_for_telegram": parsed["ok_for_telegram"],
            "ok_for_shadow_log": parsed["ok_for_shadow_log"],
        },
        "model_adi": model_adi.strip() or None,
        "prompt_surumu": prompt_surumu.strip() or "api-v1",
        "system_sha256": system_sha256.strip() or None,
        "telegrama_gitti": bool(telegrama_gitti),
        "baglam_ozet": context_summary,
        "sonuc": None,
        "olcum_zamani": None,
        "updated_at": now_iso,
    }
    return record, parsed


def load_local_shadow_records(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Yerel AI gölge defteri okunamadı (%s): %s", file_path, exc)
        return []
    rows = data.get("kayitlar") if isinstance(data, Mapping) else data
    return [dict(r) for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []


def save_local_shadow_records(records: Sequence[Mapping[str, Any]], path: str | os.PathLike[str]) -> int:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_local_shadow_records(file_path)
    by_key = {str(r["anahtar"]): dict(r) for r in existing if r.get("anahtar")}
    written = 0
    for rec in records:
        key = str(rec.get("anahtar") or "").strip()
        if not key:
            continue
        by_key[key] = dict(rec)
        written += 1
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "kayitlar": list(by_key.values()),
    }
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, file_path)
    return written


def write_shadow_records_to_supabase(
    records: Sequence[Mapping[str, Any]],
    store: Any,
    *,
    allow_supabase_write: bool = False,
) -> int:
    """Kayıtları `public.ai_yorum_test` tablosuna UPSERT eder.

    Güvenlik: `allow_supabase_write=True` VE `store.writable=True` değilse
    hiçbir ağ isteği yapılmaz ve `0` döner.
    """
    if not allow_supabase_write or store is None:
        return 0
    if not getattr(store, "writable", False):
        logger.debug("Supabase store salt okunur; ai_yorum_test yazımı atlandı.")
        return 0

    rows = [dict(r) for r in records if isinstance(r, Mapping) and r.get("anahtar") and r.get("kesit_zamani")]
    if not rows:
        return 0
    try:
        response = store.request_table(
            AI_YORUM_TEST_TABLE,
            "POST",
            params={"on_conflict": "anahtar"},
            json=rows,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    except Exception as exc:  # noqa: BLE001 - gölge kayıt hatası akışı bozmamalı
        logger.warning("ai_yorum_test tablosuna yazılamadı: %s", exc)
        return 0
    return len(rows) if response is not None else 0


def save_shadow_record(
    record: Mapping[str, Any],
    *,
    store: Any = None,
    local_path: str | os.PathLike[str] | None = None,
    allow_supabase_write: bool = False,
) -> dict[str, Any]:
    """Tek gölge kaydını yerel JSON'a ve (yalnız açık izinle) Supabase'e kaydeder."""
    local_saved = False
    if local_path is not None:
        local_saved = save_local_shadow_records([record], local_path) > 0
    supabase_saved = write_shadow_records_to_supabase(
        [record], store, allow_supabase_write=allow_supabase_write,
    ) > 0
    return {
        "anahtar": record.get("anahtar"),
        "local_saved": local_saved,
        "supabase_saved": supabase_saved,
    }


def fetch_shadow_summary(store: Any) -> list[dict[str, Any]] | None:
    """`v_ai_yorum_test_ozet` görünümünden salt-okunur kalibrasyon özeti okur."""
    if store is None:
        return None
    try:
        response = store.request_table(AI_YORUM_TEST_VIEW, "GET", params={"select": "*"})
        if response is None:
            return None
        data = response.json()
        return data if isinstance(data, list) else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("v_ai_yorum_test_ozet okunamadı: %s", exc)
        return None


def _col(frame: pd.DataFrame, name: str) -> pd.Series | None:
    if name in frame.columns:
        return frame[name]
    low = name.lower()
    for col in frame.columns:
        if str(col).lower() == low:
            return frame[col]
    return None


def evaluate_shadow_outcome(
    record: Mapping[str, Any],
    future_frame: pd.DataFrame | None,
    *,
    horizon_bars: int | None = None,
    min_hit_pct: float = DIRECTION_HIT_MIN_PCT,
) -> dict[str, Any] | None:
    """Kesit sonrası kapanmış barlara bakarak AI gizli kararının ileri performansını ölçer.

    Yalnızca `bar_open > kesit_zamani` olan barları kullanır (gelecek sızıntısı yok).
    Yeterli ileri bar yoksa `None` döner.
    """
    if future_frame is None or len(future_frame) == 0:
        return None
    ref_price = _safe_float(record.get("referans_fiyat"))
    if ref_price is None or ref_price <= 0:
        return None
    tf = str(record.get("tf") or "4h").lower()
    needed = int(horizon_bars) if horizon_bars is not None else DEFAULT_HORIZON_BARS.get(tf, 10)
    if needed < 1:
        raise ValueError("horizon_bars pozitif olmalı")

    cut = pd.Timestamp(record["kesit_zamani"])
    if cut.tzinfo is None:
        cut = cut.tz_localize("Europe/Istanbul")
    cut_utc = cut.tz_convert("UTC")

    idx = pd.DatetimeIndex(future_frame.index)
    if idx.tz is None:
        idx = idx.tz_localize("Europe/Istanbul")
    idx_utc = idx.tz_convert("UTC")

    after = future_frame.loc[idx_utc > cut_utc]
    if len(after) < needed:
        return None
    window = after.iloc[:needed]

    close_s = _col(window, "Close")
    high_s = _col(window, "High")
    low_s = _col(window, "Low")
    if close_s is None or high_s is None or low_s is None:
        return None
    end_close = _safe_float(close_s.iloc[-1])
    max_high = _safe_float(high_s.max())
    min_low = _safe_float(low_s.min())
    if end_close is None or max_high is None or min_low is None:
        return None

    pct = round((end_close - ref_price) / ref_price * 100.0, 3)
    max_up = round((max_high - ref_price) / ref_price * 100.0, 3)
    max_down = round((min_low - ref_price) / ref_price * 100.0, 3)

    egilim = record.get("egilim")
    if egilim == "yukari":
        aligned_pct: float | None = pct
        hit: bool | None = pct >= float(min_hit_pct)
    elif egilim == "asagi":
        aligned_pct = round(-pct, 3)
        hit = (-pct) >= float(min_hit_pct)
    else:
        aligned_pct = None
        hit = None

    last_bar = pd.Timestamp(window.index[-1])
    if last_bar.tzinfo is None:
        last_bar = last_bar.tz_localize("Europe/Istanbul")

    return {
        "bar_sayisi": needed,
        "son_bar": last_bar.tz_convert("UTC").isoformat(),
        "son_fiyat": round(end_close, 4),
        "yuzde": pct,
        "yon_uyumlu_yuzde": aligned_pct,
        "max_yukari_yuzde": max_up,
        "max_asagi_yuzde": max_down,
        "yon_isabet": hit,
    }
