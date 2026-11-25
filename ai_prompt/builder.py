"""Seçili dört TF grafik bağlamını ve nedensel replay'i AI promptuna derle.

Bu offline araç ağ isteği yapmaz, alarm/Telegram göndermez ve canlı motor
state'ine yazmaz. Kullanıcı talimatı ile sabit araştırma dosyaları sürümlüdür.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from enum import Enum
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from config import sembol_turu
from data import (beklenen_son_kapanis_ani, mum_kapanis_ani, ohlcv_girdi_sorunlari,
                  sureklilik_sorunlari_bul,
                  resample_ohlcv, tamamlanmis_mumlar)
from directional_zone_replay import (
    _normalize_frame, build_touch_episodes, compute_wilder_atr, replay_fvg_zones, replay_ob_zones,
)
from domain_engines.runner import run_domain_engines, run_stabil_domain
from domain_engines.bar_quality import bar_is_completed
from research.olcum import yukseklik_kovasi
from .stabil_replay import daily_support_replay
import chart_experience
import grafik
import grafik_uret
from notification_context import _VOLUME_STATE_LABELS, _VOLUME_LEVEL_LABELS

TF_ORDER = ("1h", "2h", "4h", "1d")
ROOT = Path(__file__).resolve().parent
PROMPT_LIMIT = 120_000
STATE_LABELS = {
    "STATE_BULLISH": "yukarı yönlü", "STATE_BEARISH": "aşağı yönlü",
    "STATE_TRANSITION_UP": "yukarı geçişte", "STATE_TRANSITION_DOWN": "aşağı geçişte",
    "STATE_NEUTRAL": "nötr", "STATE_UNAVAILABLE": "hazır değil",
}
PATTERN_STATES = {
    "KIRILIM_ADAYI": "kırılım adayı", "KIRILIM_DENEMESI": "kırılım denemesi",
    "KIRILIM_TEYITLI": "kırılım teyitli", "RETEST_BEKLENIYOR": "retest bekleniyor",
    "FORMASYON_TAMAMLANDI": "tamamlandı", "SIKISMA_GUCLENIYOR": "sıkışma güçleniyor",
    "OLGUNLASIYOR": "olgunlaşıyor", "KIRILIM_BASARISIZ": "kırılım başarısız",
}


EVENT_LABELS = {"CONFIRMED": "teyitli", "CANDIDATE_FAILED": "aday başarısız",
    "VALID": "geçerli", "FAILED": "başarısız", "CURRENT": "güncel",
    "SUPERSEDED": "yerini sonraki olaya bıraktı", "HISTORICAL": "tarihsel",
    "PENDING": "takip bekleniyor", "FOLLOW_THROUGH_CONFIRMED": "devam teyitli",
    "OBSERVED": "gözlendi"}
EVIDENCE_LABELS = {"CHOCH_DOWN_WAITING_BOS": "aşağı CHoCH, BOS bekleniyor",
    "CHOCH_UP_WAITING_BOS": "yukarı CHoCH, BOS bekleniyor",
    "TRANSITION_DOWN_FAILED": "aşağı geçiş başarısız", "TRANSITION_UP_FAILED": "yukarı geçiş başarısız",
    "TRANSITION_CONFIRMED_BY_BOS": "geçiş BOS ile teyitli", "BOS_CONFIRMED": "BOS teyitli",
    "TRANSITION_BOS_CONFIRMED": "geçiş BOS ile teyitli", "INITIAL_STRUCTURE_ESTABLISHED": "ilk yapı kuruldu"}
STABIL_LABELS = {"WEEKLY_PENDING": "hazır değil", "WEEKLY_UP_STABLE": "yükseliş istikrarlı",
    "WEEKLY_UP_WEAKENING": "yükseliş zayıflıyor", "WEEKLY_TRANSITION": "geçişte",
    "WEEKLY_NOT_UP": "yükselişte değil", "WEEKLY_UP_PARABOLIC": "parabolik yükseliş",
    "DAILY_PENDING": "hazır değil", "DAILY_HEALTHY_ADVANCE": "sağlıklı ilerleme",
    "DAILY_CONTROLLED_PULLBACK": "kontrollü geri çekilme", "DAILY_BASE_BUILDING": "taban oluşumu",
    "DAILY_PULLBACK_TOO_DEEP": "çok derin geri çekilme", "DAILY_DISTRIBUTION_RISK": "dağılım riski",
    "DAILY_STRUCTURE_BROKEN": "yapı bozuldu", "DAILY_NEUTRAL": "nötr", "DAILY_BEARISH_BALANCE": "aşağı yönlü denge",
    "DAILY_GAP_WATCH": "boşluk izleniyor", "DAILY_PARABOLIC": "parabolik", "DAILY_LOCAL_RECOVERY": "yerel toparlanma",
    "DAILY_LOCAL_OVERHEAT": "yerel aşırı ısınma", "H4_PENDING": "hazır değil", "H4_NO_RECOVERY": "toparlanma yok",
    "H4_SELLING_WEAKENING": "satış zayıflıyor", "H4_BUYERS_EMERGING": "alıcılar beliriyor",
    "H4_RECOVERY_CONFIRMED": "toparlanma teyitli", "H4_RECOVERY_FAILED": "toparlanma başarısız"}

def _label(mapping: dict, value: str) -> str:
    return mapping.get(value, value)


def _name(value: Any) -> str:
    if value is None:
        return "bilinmiyor"
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _fmt(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "bilinmiyor"
    # Common feeds serialize float32 artefacts (21.100000381...). If a value
    # is exactly float32, print its shortest float32-round-trippable decimal;
    # otherwise keep 12 significant digits. No fixed 2-decimal price rounding.
    if abs(number) <= float(np.finfo(np.float32).max) and float(np.float32(number)) == number:
        text = np.format_float_positional(np.float32(number), unique=True, trim="-")
    else:
        text = format(number, ".12g")
    if "e" in text.lower() and -12 <= Decimal(text).adjusted() <= 12:
        text = format(Decimal(text), "f")
    if "e" not in text.lower():
        whole, dot, fraction = text.partition(".")
        text = whole + "." + fraction.ljust(2, "0") if dot else whole + ".00"
    return text.replace(".", ",")


def _fmt_metric(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "bilinmiyor"
    # Derived metrics are approximate; categorical buckets use the raw value.
    return _fmt(float(format(number, ".6g")))


def _ts(value: Any) -> str:
    if value is None:
        return "bilinmiyor"
    return pd.Timestamp(value).tz_convert("Europe/Istanbul").strftime("%d.%m.%y %H:%M")


def _asof(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("Kesim zamanı geçerli ve zaman dilimli olmalı (ör. 2026-09-25T18:30:00+03:00).")
    return stamp.tz_convert("Europe/Istanbul")


def _clean_frame(frame: pd.DataFrame | None, tf: str, cutoff: pd.Timestamp) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy(deep=True)
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError(f"{tf}: zaman dilimli DatetimeIndex gerekli")
    frame.index = frame.index.tz_convert("Europe/Istanbul")
    frame.columns = [str(c).lower() for c in frame.columns]
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError(f"{tf}: zaman sırası bozuk veya tekrarlı mum var")
    # Önce filtre: gelecekteki/açık mumlar validasyon veya resample'a giremez.
    frame = tamamlanmis_mumlar(frame, tf, now=cutoff).copy()
    if frame.empty:
        return frame
    if any(flag in frame.columns for flag in ("is_closed", "is_complete")):
        if any(not bar_is_completed(row) for row in frame.to_dict("records")):
            raise ValueError(f"{tf}: tamamlanmamış veya durumu bilinmeyen mum var; yeniden örneklenemez")
    problems = ohlcv_girdi_sorunlari(frame)
    if problems:
        raise ValueError(f"{tf}: geçersiz OHLCV: {', '.join(problems)}")
    return frame


def _direction(value: Any) -> str:
    number = _num(value.value if isinstance(value, Enum) else value)
    if number is None:
        return "bilinmiyor"
    if number == 0:
        return "nötr"
    return "yukarı" if number > 0 else "aşağı"


def _safe_status(result: Any) -> str | None:
    if result is None:
        return "sonuç alınmadı"
    if result.error:
        return "hesaplama hatası; sonuç bilinmiyor"
    if result.skipped:
        return f"çalıştırılmadı ({result.reason or 'neden belirtilmedi'}); sonuç bilinmiyor"
    return None


def _cand_frame(candidate: Any, state: str | None, frame: pd.DataFrame, warning: list[str]) -> dict:
    if candidate is None:
        return {"status": "error" if any("hata" in w for w in warning) else "absent", "warnings": warning}
    def stamp_index(value: Any) -> str | None:
        try:
            index = int(value)
            return frame.index[index].isoformat() if 0 <= index < len(frame) else None
        except (ValueError, TypeError):
            return None
    return {
        "status": "available", "type": candidate.pattern_type, "state": state,
        "quality": _num(getattr(candidate, "effective_quality", None)),
        "known_bar_open": stamp_index(getattr(candidate, "known_bar", None)),
        "upper_now": _num(getattr(candidate, "upper_now", None)),
        "lower_now": _num(getattr(candidate, "lower_now", None)),
        "classic_direction": _direction(getattr(candidate, "classic_dir", None)),
        "break_direction": _direction(getattr(candidate, "break_snapshot_direction", None))
            if getattr(candidate, "break_snapshot_bar", None) is not None else None,
        "break_bar_open": stamp_index(getattr(candidate, "break_snapshot_bar", None)),
        "break_boundary": _num(getattr(candidate, "break_snapshot_price", None)),
    }


def _ms(result: Any) -> dict:
    status = _safe_status(result)
    if status:
        return {"status": status}
    export = result.export
    scopes = {}
    for label, attr in (("dış", "external_scope"), ("iç", "internal_scope")):
        s = getattr(export, attr, None)
        scopes[label] = None if s is None else {
            "state": STATE_LABELS.get(_name(s.state), _name(s.state)),
            "evidence": _name(getattr(s, "evidence_text", None)),
        }
    # En son seçilmiş BOS/CHoCH olayları ve son sweep; tarih sırası korunur.
    events = sorted(list(getattr(export, "events", ()) or ()),
                    key=lambda e: (pd.Timestamp(e.confirmed_at).value if e.confirmed_at is not None else -1,
                                   str(getattr(e, "event_uid", ""))))
    structural = [e for e in events if _name(getattr(e, "event_type", "")) in ("EVENT_BOS", "EVENT_CHOCH")]
    # Prefer the latest still-current structural event per scope. If none is
    # current, retain the latest historical event with its explicit status.
    recent = []
    for scope in ("EXTERNAL", "INTERNAL"):
        scoped = [e for e in structural if _name(e.scope) == scope]
        current = [e for e in scoped if _name(e.relevance) == "CURRENT"]
        if current or scoped:
            recent.append((current or scoped)[-1])
    # Preserve the latest current sweep and failed transition separately;
    # neither is a BOS/CHoCH structural confirmation.
    for kind in ("EVENT_SWEEP", "EVENT_TRANSITION_FAIL"):
        extras = [e for e in events if _name(getattr(e, "event_type", "")) == kind
                  and _name(getattr(e, "relevance", "")) == "CURRENT"]
        if extras:
            recent.append(extras[-1])
    recent.sort(key=lambda e: (pd.Timestamp(e.confirmed_at).value if e.confirmed_at is not None else -1,
                               str(getattr(e, "event_uid", ""))))
    out = []
    for e in recent:
        out.append({"bar_open": None if e.confirmed_at is None else pd.Timestamp(e.confirmed_at).isoformat(),
                    "scope": {"EXTERNAL": "dış", "INTERNAL": "iç"}.get(_name(e.scope), _name(e.scope)),
                    "type": _name(e.event_type).removeprefix("EVENT_"),
                    "direction": _direction(e.direction), "level": _num(e.broken_level),
                    "confirmation": _name(e.confirmation_status), "validity": _name(e.validity),
                    "relevance": _name(e.relevance), "outcome": _name(e.outcome)})
    return {"status": "available", "scopes": scopes, "events": out}


def _volume(result: Any) -> dict:
    status = _safe_status(result)
    if status:
        return {"status": status}
    e = result.export
    return {"status": "available", "state": _name(getattr(e, "state", None)),
            "quality": _name(result.data_quality), "rvol": _num(getattr(e, "rvol", None)),
            "level": _name(getattr(e, "volume_level", None)),
            "support_direction": _direction(getattr(e, "support_direction", None))}


def _stabil(result: Any) -> dict:
    status = _safe_status(result)
    if status:
        return {"status": status}
    out = result.result
    support = getattr(out, "support_snapshot", None)
    trend = getattr(out, "trend_context", None)
    roles = {}
    for name in ("weekly", "daily", "h4"):
        obj = getattr(trend, name, None)
        if obj is not None:
            roles[name] = {"state": _name(getattr(obj, "state", None)),
                           "ready": getattr(obj, "data_ready", None)}
    return {"status": "available", "quality": _name(result.data_quality),
            "support": _num(getattr(support, "support_level", None)),
            "support_status": _name(getattr(support, "validity", None)),
            "support_asof": None if getattr(support, "as_of", None) is None else pd.Timestamp(support.as_of).isoformat(),
            "roles": roles}


def _stabil_daily_replay(result: Any) -> dict:
    status = _safe_status(result)
    if status:
        return {"status": status}
    output = result.result
    if output is None:
        return {"status": "Stabil destek çıktısı yok"}
    return daily_support_replay(getattr(output, "support_observations", ()),
                                getattr(output, "support_timeline", ()))


def _fvg_status(result: Any) -> dict:
    status = _safe_status(result)
    if status:
        return {"status": status}
    if _name(result.data_quality) != "OK":
        return {"status": f"hazır değil veya kalite kısıtlı ({_name(result.data_quality)}); yok sayılmamalı"}
    details = result.details or {}
    if not all(key in details for key in ("active_bullish_fvg", "active_bearish_fvg")):
        return {"status": "yaşam döngüsü kayıtları yok; sayı bilinmiyor"}
    def counts(value: Any) -> tuple[int, int, int]:
        if value is None:
            return 0, 0, 0
        records = value if isinstance(value, (tuple, list)) else [value]
        active = candidates = unknown = 0
        for record in records:
            state = record.get("state") if isinstance(record, dict) else getattr(record, "state", None)
            if isinstance(state, Enum):
                state = state.name
            elif isinstance(state, int):
                from domain_engines.fvg.fvg_engulfing_models import FvgState
                try:
                    state = FvgState(state).name
                except ValueError:
                    state = None
            state = str(state).upper() if state is not None else ""
            if state == "CANDIDATE":
                candidates += 1
            elif state in {"ACTIVE", "FIRST_TEST", "PARTIAL_FILL", "DEEP_TEST", "FAILED_REACTION"}:
                active += 1
            else:
                unknown += 1
        return active, candidates, unknown
    bull = counts(details.get("active_bullish_fvg"))
    bear = counts(details.get("active_bearish_fvg"))
    return {"status": "available", "bull_count": bull[0], "bear_count": bear[0],
            "bull_candidates": bull[1], "bear_candidates": bear[1],
            "bull_unknown": bull[2], "bear_unknown": bear[2]}


def _zones(view: dict, results: dict, limit: int | None = None) -> list[dict]:
    """Keep all chart-visible regions by default; order by state and distance.

    An optional limit reserves both directions and an FVG where possible; it is
    not used in normal prompt generation. The chart already has its own quotas,
    so this is still not an exhaustive native ledger.
    """
    rows = []
    price = _num(view.get("son_kapanis"))
    for z in (view.get("zone") or {}).get("cizilen", ()):
        family = str(z.get("tip", "")).upper()
        if family not in ("OB", "FVG") or _safe_status(results.get("order_block" if family == "OB" else "fvg")):
            continue
        lower, upper = _num(z.get("alt")), _num(z.get("ust"))
        if price is None or lower is None or upper is None:
            distance = math.inf
        else:
            distance = max(lower - price, 0.0, price - upper)
        rows.append({"family": family, "direction": {1: "pozitif", -1: "negatif"}.get(z.get("yon"), "bilinmiyor"),
                     "lower": lower, "upper": upper, "distance": distance,
                     "source_open": z.get("zaman"), "source_index": z.get("kaynak"),
                     "terminal": chart_experience.terminal(z), "state": _name(z.get("durum"))})
    rows.sort(key=lambda row: (row["terminal"], row["distance"], row["source_open"] or "", row["family"]))
    if limit is None:
        return [{key: value for key, value in row.items() if key != "distance"} for row in rows]
    if limit < 0:
        raise ValueError("Bölge sınırı negatif olamaz")
    selected: list[dict] = []
    # Active/candidate chart regions always take precedence over terminal ones.
    for terminal in (False, True):
        pool = [row for row in rows if row["terminal"] == terminal]
        for direction in ("pozitif", "negatif"):
            if not any(row["direction"] == direction for row in selected):
                item = next((row for row in pool if row["direction"] == direction), None)
                if item is not None and len(selected) < limit:
                    selected.append(item)
        if len(selected) < limit and not any(row["family"] == "FVG" for row in selected):
            item = next((row for row in pool if row["family"] == "FVG" and row not in selected), None)
            if item is not None:
                selected.append(item)
        for row in pool:
            if len(selected) >= limit:
                break
            if row not in selected:
                selected.append(row)

    ordered = sorted(selected, key=lambda row: (row["terminal"], row["distance"], row["source_open"] or "", row["family"]))
    return [{key: value for key, value in row.items() if key != "distance"} for row in ordered]


def _matching_zone(display: dict, zones: list[dict]) -> dict | None:
    if display["direction"] not in ("pozitif", "negatif"):
        return None
    wanted = "bullish" if display["direction"] == "pozitif" else "bearish"
    matches = [z for z in zones if z["active_at_asof"] and z["direction"] == wanted
               and z["origin_index"] == display["source_index"]
               and display["lower"] is not None and display["upper"] is not None
               and math.isclose(z["zone_lower"], display["lower"], rel_tol=1e-10, abs_tol=1e-12)
               and math.isclose(z["zone_upper"], display["upper"], rel_tol=1e-10, abs_tol=1e-12)]
    return matches[0] if len(matches) == 1 else None


def _replay(symbol: str, tf: str, frame: pd.DataFrame, displays: list[dict], results: dict) -> dict:
    """Yalnız görüntülenen aktif bölgeleri eşle; eşleşmeme sıfır temas değildir."""
    data = _normalize_frame(frame)
    by_family: dict[str, list[dict] | None] = {}
    errors: dict[str, str] = {}
    for family, domain in (("OB", "order_block"), ("FVG", "fvg")):
        selected = [z for z in displays if z["family"] == family]
        if not selected:
            continue
        status = _safe_status(results.get(domain))
        if status:
            errors[family] = status
            continue
        try:
            if family == "OB":
                by_family[family] = replay_ob_zones(symbol, tf, data)
            else:
                by_family[family], quality, _ = replay_fvg_zones(symbol, tf, data)
                if quality != "OK":
                    errors[family] = f"replay veri kalitesi: {quality}"
                    by_family.pop(family, None)
        except Exception:
            errors[family] = "replay hesaplama hatası; temas geçmişi bilinmiyor"
    all_zones = [z for zones in by_family.values() for z in zones]
    try:
        episodes = build_touch_episodes(all_zones, {(symbol, tf): data})
    except Exception:
        # A broken episode calculation must never turn into zero contacts.
        episodes = []
        for family in tuple(by_family):
            errors[family] = "temas epizotları hesaplanamadı; geçmiş bilinmiyor"
            del by_family[family]
    try:
        atr_by_bar = compute_wilder_atr(data)
    except Exception:
        # Contact history can still be useful when birth ATR is unavailable.
        atr_by_bar = [None] * len(data)
    per_zone: dict[str, list] = defaultdict(list)
    for ep in episodes:
        per_zone[ep["zone_id"]].append(ep)
    selected_out = []
    for z in displays:
        matches = by_family.get(z["family"])
        row = {**z}
        if matches is None:
            row.update(replay_status=errors.get(z["family"], "hesaplanmadı"), episodes=None)
        else:
            native = _matching_zone(z, matches)
            if native is None:
                reason = ("FVG adayı replay'de sayılmaz; temas geçmişi bilinmiyor"
                          if z["family"] == "FVG" and z["state"] == "CANDIDATE"
                          else "grafik bölgesiyle replay eşleşmedi; bilinmiyor")
                row.update(replay_status=reason, episodes=None)
            else:
                ep_list = per_zone[native["zone_id"]]
                observations = []
                for ep in ep_list[-2:]:
                    start, end = int(ep["touch_start_index"]), int(ep["touch_end_index"])
                    # Maximum last 3 touch closes, explicitly marked if earlier bars omitted.
                    closes = [{"bar_open": data.at[i, "timestamp"].isoformat(),
                               "close": _num(data.at[i, "close"])}
                              for i in range(max(start, end - 2), end + 1)]
                    after = None
                    if end + 1 < len(data):
                        after = {"bar_open": data.at[end + 1, "timestamp"].isoformat(),
                                 "close": _num(data.at[end + 1, "close"])}
                    observations.append({"number": ep["touch_number_for_zone"],
                                         "start_open": pd.Timestamp(ep["touch_start"]).isoformat(),
                                         "end_open": pd.Timestamp(ep["touch_end"]).isoformat(),
                                         "end_age_bars": len(data) - 1 - end,
                                         "bar_count": ep["touch_bar_count"], "closes": closes,
                                         "closes_truncated": ep["touch_bar_count"] > len(closes),
                                         "next_bar_close": after, "ongoing_at_cut": end == len(data) - 1})
                birth_index = native["origin_index"]
                birth_atr = atr_by_bar[birth_index] if 0 <= birth_index < len(atr_by_bar) else None
                ratio = ((native["zone_upper"] - native["zone_lower"]) / birth_atr
                         if birth_atr is not None and birth_atr > 0 else None)
                row.update(replay_status="ok", episodes=len(ep_list), recent_episodes=observations,
                           birth_atr=_num(birth_atr), width_atr_birth=_num(ratio),
                           width_atr_bucket=yukseklik_kovasi(ratio),
                           available_open=pd.Timestamp(native["available_at"]).isoformat(),
                           remaining_lower=_num(native["current_remaining_lower"]),
                           remaining_upper=_num(native["current_remaining_upper"]))
        selected_out.append(row)
    return {"zones": selected_out, "errors": errors}


def _research(cutoff: pd.Timestamp, mode: str) -> list[dict]:
    if mode not in ("strict", "retrospective"):
        raise ValueError("Araştırma modu strict veya retrospective olmalı")
    records = json.loads((ROOT / "arastirma.json").read_text(encoding="utf-8"))
    results = []
    for row in records:
        recorded, through = row["recorded_at"], row["data_through"]
        # Gün bazlı tarihte aynı günün tam yayın saati bilinmediği için < (eşit değil).
        known = bool(recorded and through and pd.Timestamp(recorded).date() < cutoff.date()
                     and pd.Timestamp(through).date() < cutoff.date())
        future = any(v and pd.Timestamp(v).date() > cutoff.date() for v in (recorded, through))
        relation = "kesitten önce belgeli" if known else ("kesitten sonra" if future else "zamanı tam doğrulanamıyor")
        results.append({**row, "timeline": relation,
                        "included": bool(known or mode == "retrospective")})
    return results


def build_from_frames(symbol: str, hourly: pd.DataFrame, *, as_of: Any,
                      main_tf: str = "4h", daily: pd.DataFrame | None = None,
                      research_mode: str = "strict", source: str = "çağıranın yerel OHLCV verisi") -> dict:
    symbol = str(symbol).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,12}", symbol):
        raise ValueError("Sembol yalnız A-Z ve 0-9 içermeli; uzantı veya dosya yolu verilmez")
    if sembol_turu(symbol) != "hisse":
        raise ValueError("Bu ilk sürüm yalnız BIST hisse verisi içindir; makro ve endeks desteklenmiyor")
    if main_tf not in TF_ORDER:
        raise ValueError(f"Ana TF {TF_ORDER} değerlerinden biri olmalı")
    cutoff = _asof(as_of)
    hourly = _clean_frame(hourly, "1h", cutoff)
    if len(hourly) < 5:
        raise ValueError("Kesime kadar en az 5 tamamlanmış saatlik mum gerekli")
    frames = {"1h": hourly}
    for tf in ("2h", "4h"):
        frames[tf] = _clean_frame(resample_ohlcv(hourly, tf), tf, cutoff)
    native_daily = _clean_frame(daily, "1d", cutoff)
    if len(native_daily) > 1:
        frames["1d"] = _clean_frame(grafik_uret._gunluk_cerceve_onar_ve_olcekle(native_daily, sembol=symbol), "1d", cutoff)
        daily_source = "yerel günlük önbellek"
    else:
        frames["1d"] = _clean_frame(resample_ohlcv(hourly, "1d"), "1d", cutoff)
        daily_source = "saatlik önbellekten türetilmiş"
        if daily is not None:
            daily_source += f" (kesimde bağımsız günlük kayıt sayısı {len(native_daily)}, yetersiz)"
    if frames[main_tf].empty:
        raise ValueError("Ana TF için kesimde tamamlanmış mum yok")
    raw_rows = hourly.reset_index().rename(columns={hourly.index.name or "index": "timestamp"}).to_dict("records")
    try:
        quality_notes = [str(item["mesaj"]) for item in sureklilik_sorunlari_bul(raw_rows)]
    except Exception:
        quality_notes = ["Saatlik veri sürekliliği doğrulanamadı."]
    result: dict[str, Any] = {"quality_notes": quality_notes, "schema": "ai-prompt-local-v1", "symbol": symbol,
        "as_of": cutoff.isoformat(), "main_tf": main_tf, "source": source,
        "daily_source": daily_source, "research_mode": research_mode,
        "kind": "tarihsel veya isteğe bağlı kesit; gerçek alarm doğrulanmadı",
        "research": _research(cutoff, research_mode), "timeframes": {}}
    for tf in TF_ORDER:
        frame = frames[tf]
        if frame.empty:
            result["timeframes"][tf] = {"status": "kesime kadar tamamlanmış mum yok"}
            continue
        end = mum_kapanis_ani(frame.index[-1], tf)
        candidate, state, warning = grafik_uret._formasyon_tara_ayrintili(frame, tf=tf)
        domains = run_domain_engines(symbol, tf, frame, isolated=True)
        # Stabil yalnız bu TF'nin son tamamlanmış mumunun kapanışında bilinen üst TF'leri alır.
        daily_cut = _clean_frame(frames["1d"], "1d", pd.Timestamp(end))
        h4_cut = _clean_frame(frames["4h"], "4h", pd.Timestamp(end))
        domains["stabil"] = run_stabil_domain(symbol, tf, frame, daily_frame=daily_cut,
                    h4_frame=h4_cut, as_of_close=end, isolated=True)
        # The chart's resistance layer requires independent native daily data;
        # never substitute a daily aggregation of this hourly cache.
        from domain_engines.stabil.chart_bridge import resistance_for_chart
        domains["stabil_direnc"] = resistance_for_chart(
            symbol, tf, frame,
            daily_frame=_clean_frame(native_daily, "1d", pd.Timestamp(end)) if len(native_daily) > 1 else None,
            hourly_frame=_clean_frame(hourly, "1h", pd.Timestamp(end)), as_of_close=end)
        # Use the renderer's sanitization, short-TF Stabil visibility, view
        # mode and final price-frame filter; never select events from the full
        # native ledger for the prompt.
        from grafik.indicators import _grafik_dis_yapi, _grafik_zone
        from grafik.render import olay_kadrajini_hazirla
        snapshot = grafik.anlik_goruntu(candidate, tf, frame,
                                        sembol=symbol, sonuclar=domains, simdi=cutoff)
        # Match /grafik: scanner state is attached after snapshot construction,
        # without creating an alarm marker for this historical view.
        if state and snapshot.get("formasyon"):
            snapshot["formasyon"]["state"] = state
        snapshot = {**snapshot, "zone": _grafik_zone(snapshot.get("zone") or {}),
                    "olay": _grafik_dis_yapi(snapshot.get("olay") or {})}
        if tf in {"1h", "2h"}:
            snapshot = {**snapshot, "stabil": None, "stabil_direnc": None}
        view = chart_experience.prepare_view(snapshot, os.environ.get("GRAFIK_GORUNUM", "odak"),
                              max_distance_atr=max(.1, grafik._ortam_sayi("GRAFIK_ODAK_MESAFE_ATR", 3.0)))
        if grafik._ortam_bayrak("GRAFIK_SADE"):
            view = {**view, "zone": {}, "serit": {}, "stabil": None, "stabil_direnc": None,
                    "gorunum": {**view.get("gorunum", {}), "mod": "sade"},
                    "olay": {**(view.get("olay") or {}), "swinglar": [], "seviyeler": [], "olaylar": []}}
        view, extra_prices, _, stabil_visible, resistance_visible = olay_kadrajini_hazirla(view, len(view.get("kapanis") or []))
        zones = _zones(view, domains)
        chart_events = []
        for event in (view.get("olay") or {}).get("olaylar", []):
            idx = event.get("kaynak_bar")
            if isinstance(idx, int) and 0 <= idx < len(frame):
                chart_events.append({"bar_open": frame.index[idx].isoformat(), "age_bars": len(frame) - 1 - idx,
                    "type": event.get("tur"), "direction": "yukarı" if event.get("yon") == "ust" else "aşağı",
                    "level": _num(event.get("seviye"))})
        # RVOL values in the internal ribbon are not necessarily drawn: the
        # renderer shows only selected badges. Measure the actual normal
        # offline rendering rather than treating the last raw value as visible.
        # The temporary image is removed immediately; no chart is sent.
        with tempfile.TemporaryDirectory(prefix="ai_prompt_chart_") as directory:
            chart_path, chart_meta = grafik.ciz(snapshot, tf, {
                "cikti": str(Path(directory) / "chart.png"), "serit": True,
            })
        draw_errors = set(chart_meta.get("eksik_katmanlar") or ())
        fallback = any("çökme modu" in str(w) for w in chart_meta.get("uyarilar", ()))
        if not chart_path or "cizim" in draw_errors or fallback:
            result["timeframes"][tf] = {"status": "grafik çizilemedi; görünür katmanlar bilinmiyor"}
            continue
        if "zone" in draw_errors:
            zones = []
        if "ms" in draw_errors:
            chart_events = []
        drawn_badges = []
        for badge in (chart_meta.get("serit") or {}).get("rozetler", []):
            bar = badge.get("bar")
            stamps = view.get("zamanlar") or []
            if isinstance(bar, int) and 0 <= bar < len(stamps) and stamps[bar] is not None:
                stamp = pd.Timestamp(stamps[bar])
                idx = frame.index.get_indexer([stamp])[0]
                drawn_badges.append({"bar_open": stamp.isoformat(),
                                      "age_bars": len(frame) - 1 - int(idx) if idx >= 0 else None,
                                      "direction": badge.get("yon"), "value": badge.get("deger")})
        ribbon = view.get("serit") or {}
        chart_levels = [{"label": level.get("etiket"), "price": _num(level.get("fiyat"))}
                        for level in (view.get("olay") or {}).get("seviyeler", [])] if "ms" not in draw_errors else []
        price_range = grafik._yatay_aralik(list(view.get("kapanis") or []) + list(view.get("yuksek") or [])
                                          + list(view.get("dusuk") or []), extra_prices)
        def last_visible(layer, visible):
            if not visible:
                return None
            level = _num((layer or {}).get("son_seviye"))
            series = (layer or {}).get("seviyeler") or []
            if not series or _num(series[-1]) != level or level is None:
                return None
            return level if price_range[0] <= level <= price_range[1] else None
        drawn_layers = chart_meta.get("cizgiler") or {}
        stabil_level = last_visible(view.get("stabil"), stabil_visible) if (drawn_layers.get("stabil") or {}).get("cizildi") and "stabil" not in draw_errors else None
        resistance_level = last_visible(view.get("stabil_direnc"), resistance_visible) if (drawn_layers.get("stabil_direnc") or {}).get("cizildi") and "stabil_direnc" not in draw_errors else None
        try:
            expected = beklenen_son_kapanis_ani(tf, now=cutoff)
            delay = max(0, int((expected - pd.Timestamp(end)).total_seconds() / 60)) if expected is not None else None
        except Exception:
            delay = None
        pattern = _cand_frame(candidate, state, frame, warning)
        # Chart header uses quality, then effective_quality, then raw_quality.
        # Keep raw candidates in the packet, but render the value the view uses.
        chart_pattern = view.get("formasyon") or {}
        if pattern["status"] == "available":
            chart_quality = next((chart_pattern[k] for k in ("quality", "effective_quality", "raw_quality")
                                  if chart_pattern.get(k) is not None), None)
            pattern["quality"] = _num(chart_quality)
        entry = {"status": "available", "bars": len(frame), "expected_delay_minutes": delay, "last_open": frame.index[-1].isoformat(),
                 "last_close_time": pd.Timestamp(end).isoformat(), "last_close": _num(frame.close.iloc[-1]),
                 "pattern": ({"status": "error", "warnings": ["çizim hatası"]} if "formasyon" in draw_errors else
                             {**pattern,
                              "upper_touches": (view.get("formasyon") or {}).get("upper_touches"),
                              "lower_touches": (view.get("formasyon") or {}).get("lower_touches"),
                              "contraction": _num((view.get("formasyon") or {}).get("contraction"))}),
                 "market_structure": _ms(domains.get("market_structure")),
                 "chart_events": chart_events, "chart_levels": chart_levels, "chart_volume_badges": drawn_badges,
                 "chart_rvol_source": ribbon.get("kaynak"),
                 "chart_stabil_support": stabil_level, "chart_stabil_resistance": resistance_level,
                 "volume": _volume(domains.get("volume_participation")),
                 "fvg": _fvg_status(domains.get("fvg")),
                 "ob_quality": _name(getattr(domains.get("order_block"), "data_quality", None)),
                 "ob_status": _safe_status(domains.get("order_block")),
                 "chart_warnings": list(dict.fromkeys(list(view.get("uyarilar") or []) + list(view.get("eksik_katmanlar") or []) + list((view.get("zone") or {}).get("hata") or []) + list(chart_meta.get("eksik_katmanlar") or []))),
                 "stabil": _stabil(domains.get("stabil")),
                 "stabil_daily_replay": _stabil_daily_replay(domains.get("stabil")), "zones": zones,
                 "zone_selection_omitted": max(0, len((view.get("zone") or {}).get("cizilen") or ()) - len(zones)),
                 "replay": _replay(symbol, tf, frame, zones, domains)}
        result["timeframes"][tf] = entry
    return result


def build_from_local_cache(symbol: str, *, as_of: Any, main_tf: str = "4h",
                           data_dir: str = "bot_data", research_mode: str = "strict") -> dict:
    symbol = str(symbol).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,12}", symbol):
        raise ValueError("Geçersiz sembol")
    directory = Path(data_dir)
    if not directory.is_dir():
        raise ValueError("Yerel veri dizini bulunamadı")
    # Yalnız açık yerel JSON'a izin ver; seed fallback, pickle veya remote okuması yok.
    if not (directory / f"{symbol}.json").is_file():
        raise ValueError(f"{symbol} için yerel saatlik JSON yok")
    def read_json(path: Path, tf: str) -> pd.DataFrame:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"{tf}: JSON boş veya liste değil")
        rows = pd.DataFrame(raw)
        if "timestamp" not in rows:
            raise ValueError(f"{tf}: timestamp yok")
        stamps = [pd.Timestamp(x) for x in rows.pop("timestamp")]
        if any(pd.isna(x) or x.tzinfo is None for x in stamps):
            raise ValueError(f"{tf}: zaman dilimli timestamp gerekli")
        rows.index = pd.DatetimeIndex([x.tz_convert("Europe/Istanbul") for x in stamps], name="timestamp")
        return rows
    cutoff = _asof(as_of)
    hourly = _clean_frame(read_json(directory / f"{symbol}.json", "1h"), "1h", cutoff).tail(360)
    daily_file = directory / f"{symbol}_gunluk.json"
    daily = _clean_frame(read_json(daily_file, "1d"), "1d", cutoff).tail(500) if daily_file.is_file() else None
    return build_from_frames(symbol, hourly, as_of=cutoff, main_tf=main_tf, daily=daily,
                             research_mode=research_mode, source=f"yerel {symbol}.json; sağlayıcı bilinmiyor")


def _same_level(a: Any, b: Any) -> bool:
    fa, fb = _num(a), _num(b)
    return fa is not None and fb is not None and math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-9)


def _render_pattern(p: dict) -> str:
    if p["status"] == "absent":
        return "Formasyon: grafikte kullanılabilir aday yok."
    if p["status"] == "error":
        return "Formasyon: hesaplama veya çizim hatası; yok sonucu değildir."
    from reporting.format import sayi
    quality = _num(p.get("quality"))
    text = f"Formasyon: {p['type']}, {PATTERN_STATES.get(p['state'], p['state'])}"
    if quality is not None:
        text += f", kalite {int(round(quality))}/100"
    text += "."
    break_dir = p.get("break_direction")
    if break_dir in ("yukarı", "aşağı"):
        if p.get("state") in {"KIRILIM_ADAYI", "KIRILIM_DENEMESI"}:
            text += f" Aday kırılım yönü: {break_dir} (teyitli değil)."
        elif p.get("state") in {"KIRILIM_TEYITLI", "RETEST_BEKLENIYOR", "FORMASYON_TAMAMLANDI", "KIRILIM_BASARISIZ"}:
            text += f" Kırılım yönü: {break_dir}."
    if p.get("contraction") is not None:
        text += f" Daralma %{sayi(100 * p['contraction'], 0)}."
    if p.get("upper_touches") is not None or p.get("lower_touches") is not None:
        text += f" Bant teması üst {p.get('upper_touches') if p.get('upper_touches') is not None else 'bilinmiyor'}, alt {p.get('lower_touches') if p.get('lower_touches') is not None else 'bilinmiyor'}."
    # The lines are visible as geometry but the precise engine values at the
    # last bar are not labelled on the chart; do not present them as labels.
    return text


def _render_event(event: dict) -> str:
    flags = "/".join(_label(EVENT_LABELS, event[key]) for key in ("confirmation", "validity", "relevance", "outcome"))
    kind = "geçiş başarısızlığı, olay yönü" if event['type'] == "TRANSITION_FAIL" else event['type']
    return f"{_ts(event['bar_open'])} {event['scope']} {kind} {event['direction']} {_fmt(event['level'])} [{flags}]."


def _render_zone(z: dict) -> str:
    status = f"; durum {_label(chart_experience.STATUS_LABELS, z['state'])}" if z['state'] not in ("bilinmiyor", "") else ""
    if z['terminal']:
        status += " (geçmiş/terminal kayıt)"
    return (f"{z['direction'].capitalize()} {z['family']} bölgesi {_fmt(z['lower'])}–{_fmt(z['upper'])}; "
            f"kaynak mum {_ts(z['source_open'])}{status}.")


def _render_tf(tf: str, row: dict) -> list[str]:
    lines = [f"\n{tf.upper()} GRAFİK"]
    if row["status"] != "available":
        return lines + [f"Veri yok: {row['status']}."]
    lines.append(f"Kapanış {_ts(row['last_close_time'])}: {_fmt(row['last_close'])}.")
    if row.get("chart_events"):
        lines.append("Dış yapı: " + "; ".join(
            f"{_ts(e['bar_open'])} {e['type']} {e['direction']} {_fmt(e['level'])}"
            for e in row["chart_events"]) + ".")
    if row.get("chart_levels"):
        lines.append("Dış seviyeler: " + "; ".join(f"{level['label']} {_fmt(level['price'])}" for level in row["chart_levels"]) + ".")
    if row["zones"]:
        lines.append("Bölgeler: " + "; ".join(
            f"{z['direction']} {z['family']} {_fmt(z['lower'])}–{_fmt(z['upper'])} (kaynak {_ts(z['source_open'])}"
            + (f", {_label(chart_experience.STATUS_LABELS, z['state'])}" if z['state'] not in ("bilinmiyor", "") else "")
            + (", terminal" if z['terminal'] else "") + ")" for z in row["zones"]) + ".")
    lines.append(_render_pattern(row["pattern"]))
    if row["expected_delay_minutes"] is None:
        lines.append("Beklenen son mum zamanı doğrulanamadı.")
    elif row["expected_delay_minutes"]:
        lines.append(f"Veri gecikmesi: {row['expected_delay_minutes']} dakika.")
    if row["ob_status"] or row["ob_quality"] != "OK":
        lines.append(f"OB: {row['ob_status'] or row['ob_quality']}; sonuç kısıtlı.")
    if row["fvg"]["status"] != "available":
        lines.append(f"FVG: {row['fvg']['status']}.")
    if row.get("chart_volume_badges"):
        badges = list(row["chart_volume_badges"])
        if all(b.get("bar_open") is not None for b in badges):
            try:
                badges.sort(key=lambda b: pd.Timestamp(b["bar_open"]))
            except (TypeError, ValueError):
                pass
        labels = "; ".join(f"{_ts(b['bar_open'])} {'artış' if b['direction'] == 'artis' else 'kuruma'} ×{b['value']}"
                           for b in badges)
        lines.append(f"Grafik hacim rozetleri ({row.get('chart_rvol_source') or 'kaynak bilinmiyor'}): {labels}.")
    if row.get("chart_stabil_support") is not None:
        lines.append(f"Grafikte Stabil destek: {_fmt(row['chart_stabil_support'])}.")
    if row.get("chart_stabil_resistance") is not None:
        lines.append(f"Grafikte Stabil direnç: {_fmt(row['chart_stabil_resistance'])}.")
    return lines


def _render_replay(tf: str, row: dict) -> list[str]:
    lines = [f"\n{tf.upper()} REPLAY"]
    if row["status"] != "available":
        return lines + ["Hesaplanmadı: zaman diliminde veri yok."]
    replay = row["replay"]
    if not replay["zones"]:
        return lines + ["Gösterilen bölge seçilmedi; geçmişin sıfır olduğu anlamına gelmez."]
    selected = replay['zones'] if tf == row.get('_main_tf') else replay['zones'][:1]
    if len(selected) < len(replay['zones']):
        lines.append('Diğer görüntülenen bölgeler bu özette seçilmedi.')
    for z in selected:
        label = f"{z['direction'].capitalize()} {z['family']} {_fmt(z['lower'])}–{_fmt(z['upper'])}"
        if z["replay_status"] != "ok":
            lines.append(f"{label}: {z['replay_status']}.")
            continue
        atr = (f"; doğum ATR≈{_fmt_metric(z['birth_atr'])}, yükseklik/ATR≈{_fmt_metric(z['width_atr_birth'])} (grup {z['width_atr_bucket']})"
               if z["width_atr_birth"] is not None else "; doğum ATR hesaplanamadı")
        close, lower, upper = (_num(row.get('last_close')), _num(z.get('lower')), _num(z.get('upper')))
        position = ""
        if close is not None and lower is not None and upper is not None and lower <= upper:
            relation = "altında" if close < lower else "üzerinde" if close > upper else "içinde veya sınırında"
            position = f"; son {tf} kapanışı orijinal bölgenin {relation}"
        lines.append(f"{label}: {z['episodes']} epizot; kullanılabilir {_ts(z['available_open'])}; kalan {_fmt(z['remaining_lower'])}–{_fmt(z['remaining_upper'])}{atr}{position}.")
        for ep in z["recent_episodes"]:
            start, end = _ts(ep['start_open']), _ts(ep['end_open'])
            if start == end:
                interval = start
            elif start[:8] == end[:8] and start != "bilinmiyor":
                interval = start + "–" + end[9:]
            else:
                interval = start + "–" + end
            closes = ", ".join(f"{_ts(x['bar_open'])}={_fmt(x['close'])}" for x in ep["closes"])
            more = " (son 3 mum)" if ep["closes_truncated"] else ""
            follow = ep["next_bar_close"]
            after = f"; sonraki mum {_ts(follow['bar_open'])} kapanışı {_fmt(follow['close'])}" if follow else "; sonraki kapanmış mum yok"
            ongoing = "; epizot devam ediyor olabilir" if ep["ongoing_at_cut"] else ""
            lines.append(f"  {ep['number']}. epizot {interval} ({ep['bar_count']} mum); temas kapanışları{more}: {closes}{after}{ongoing}.")
    return lines


def _render_stabil_daily_replay(replay: dict) -> list[str]:
    lines = ["\nSTABİL GÜNLÜK DESTEK REPLAY"]
    if replay["status"] != "ok":
        return lines + [f"Günlük temas sırası bilinmiyor: {replay['status']}."]
    details = (f"Destek {_fmt(replay['support_level'])}; kullanıma giriş günlük kapanış "
               f"{_ts(replay['support_available_at'])}; pencere içinde başlangıç {_ts(replay['window_identity_start'])}.")
    lines.append(details)
    if not replay["atr_complete_for_separation"]:
        lines.append("Günlük fiyat, destek veya ayrılma için gereken ATR eksikliği nedeniyle temas sırası güvenle sayılamıyor.")
    elif replay["sequence_known"]:
        lines.append(f"Günlük bağımsız temas sırası: {replay['observed_count']}.")
    else:
        reason = ("destek kimliği aradan sonra tekrar göründüğünden" if replay.get("unknown_reason") == "tekrar_gorunen_kimlik"
                  else "ilk destek kimliği olduğundan")
        lines.append(f"Pencerede gözlenen günlük bağımsız temas: {replay['observed_count']}; {reason} önceki geçmiş ve gerçek sıra bilinmiyor.")
    if replay["recent_touch_days"]:
        for day in replay["recent_touch_days"]:
            lines.append(f"Günlük temas-kapanış {_ts(day['daily_close_time'])}: {_fmt(day['close'])}.")
    return lines


def render_prompt(packet: dict) -> str:
    lines = [(ROOT / "talimat.txt").read_text(encoding="utf-8").strip(), "\nGRAFİK VERİSİ",
             f"{packet['symbol']} — kesit {_ts(packet['as_of'])}; ana zaman dilimi {packet['main_tf']}; {packet['kind']}.",
             f"Kaynak: {packet['source']}; günlük: {packet['daily_source']}. Fiyat her TF'nin son tamamlanmış kapanışıdır; farklı kapanış saatleri farklı fiyatlar verebilir.",
             "Saatler İstanbul; kapanış dışındaki zamanlar mum açılışıdır, bilgi kapanışta bilinir. İlk türetilen kova eksik, son seans mumu kısa olabilir; görünüm tüm geçmiş değildir. Süreklilik kontrolü tüm eksik seansları doğrulamaz."]
    if packet["quality_notes"]:
        lines.append("Veri sürekliliği uyarıları: " + "; ".join(packet["quality_notes"]) + ".")
    chart_warnings: dict[str, list[str]] = {}
    for tf in TF_ORDER:
        for warning in packet["timeframes"][tf].get("chart_warnings", []):
            chart_warnings.setdefault(str(warning), []).append(tf)
    for warning, timeframes in chart_warnings.items():
        lines.append(f"Grafik uyarısı ({'/'.join(timeframes)}): {warning}.")
    for tf in TF_ORDER:
        lines.extend(_render_tf(tf, packet["timeframes"][tf]))
    lines.append("\nGRAFİĞE ÖZEL REPLAY — ana TF, seçili bölgeler: OB teması orijinal bantla OHLC örtüşmesi; FVG kendi motor kuralı. Ardışık temas mumları bir epizot; yalnız bu pencere gözlendi, öncesi bilinmez. Son iki epizot ayrıntılıdır. Doğum ATR: Wilder(14); yükseklik orijinal banttır, grup ham orandan (alt dahil, üst hariç) hesaplanır.")
    tf = packet["main_tf"]
    row = {**packet["timeframes"][tf], "_main_tf": tf}
    lines.extend(_render_replay(tf, row))
    if (row["status"] == "available" and row.get("chart_stabil_support") is not None
            and _same_level(row["stabil_daily_replay"].get("support_level"), row["chart_stabil_support"])):
        lines.append("\nStabil günlük replay: OHLC desteği kapsar ve kapanış altında değildir; bağımsız temaslar arası ≥0,35 günlük ATR uzaklaşma gerekir. Aynı gün ilk bilinen destek önceden bilinen test değildir; günlük sayım 4s temas veya ret teyidi değildir.")
        lines.extend(_render_stabil_daily_replay(row["stabil_daily_replay"]))
    # Research is a separate, labelled retrospective context. Include only
    # studies applicable to the visible main-TF evidence; never transfer daily
    # FVG or 4h Stabil results to a different timeframe.
    families = {z["family"] for z in row.get("zones", [])}
    stabil_applicable = (tf == "4h" and row.get("chart_stabil_support") is not None
                         and _same_level(row.get("stabil_daily_replay", {}).get("support_level"), row.get("chart_stabil_support")))
    def relevant(item):
        ident = item["id"]
        return ((ident.startswith("ob-") and "OB" in families)
                or (ident.startswith("fvg-") and tf == "1d" and "FVG" in families)
                or (ident.startswith("stabil-") and stabil_applicable)
                or (ident.startswith("ms-") and tf == "4h" and any(e["type"] == "BOS" for e in row.get("chart_events", []))))
    studies = [item for item in packet["research"] if relevant(item)]
    if studies:
        lines.append("\nGENEL ARAŞTIRMA — grafiğe özel sonuç veya kişisel olasılık değildir.")
        if packet["research_mode"] == "retrospective":
            lines.append("Geriye dönük: kesit sonrası/belirsiz çalışmalar etiketlidir; o tarihte biliniyor sayma.")
        for item in studies:
            text = item["text"] if item["included"] else "Bu kesitte kullanılabilirliği doğrulanmadı; bulgu verilmedi."
            # Full source paths remain in packet / arastirma.json; the ID
            # ties this concise model-facing text back to that manifest.
            lines.append(f"{item['id']} [{item['timeline']}; rapor={item['recorded_at'] or 'bilinmiyor'}, veri sonu={item['data_through'] or 'bilinmiyor'}]: {text}")
    prompt = "\n".join(lines).strip() + "\n"
    if len(prompt) > PROMPT_LIMIT:
        raise ValueError(f"Prompt üst sınırı aşıyor: {len(prompt)} > {PROMPT_LIMIT}; sessiz kırpma yapılmadı")
    return prompt
