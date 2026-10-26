"""Chart-only presentation contracts. No engine replay, network, or alerts.

Readiness is engine-specific. Freshness compares completed bar labels with the
existing exchange calendar and candle-close contract, never wall-clock age alone.
All returned payloads are JSON-compatible and independent of native engine state.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import math
from typing import Any, Mapping

from reporting.format import sayi

POLICY = "chart-trust-focus-v3"
TERMINAL = frozenset({"REACTION", "FULL_FILL", "INVALID", "SUPERSEDED", "EXPIRED",
                      "CONTINUATION_CONFIRMED"})
STATUS_LABELS = {
    "ACTIVE": "aktif", "CANDIDATE": "aday", "FIRST_TEST": "ilk test",
    "PARTIAL_FILL": "kısmi dolum", "DEEP_TEST": "derin test",
    "FAILED_REACTION": "tepki başarısız", "PARTIAL_RETRACE": "kısmi dönüş",
    "WEAKENED": "zayıfladı", "REACTION": "tepki kaydı",
    "FULL_FILL": "tam doldu", "INVALID": "geçersiz",
    "SUPERSEDED": "yerini yenisi aldı", "EXPIRED": "süresi doldu",
    "CONTINUATION_CONFIRMED": "devam teyitli",
}
DOMAIN_LABELS = {"market_structure": "Dış yapı", "order_block": "OB",
                 "fvg": "FVG", "volume_participation": "Hacim"}


def field(obj, key, default=None):
    try:
        return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)
    except Exception:
        return default


def enum_name(value):
    return str(getattr(value, "name", value) or "")


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def local_time(value):
    from bist_calendar import as_istanbul_datetime
    if value is None:
        return None
    try:
        if not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return as_istanbul_datetime(value)
    except (TypeError, ValueError):
        return None


def date_text(value, *, daily=False):
    stamp = local_time(value)
    if stamp is None:
        return "bilinmiyor"
    month = ("", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")[stamp.month]
    return f"{stamp.day:02d} {month} {stamp.year}" + ("" if daily else stamp.strftime(" %H:%M")) + " TSİ"


def zone_status(zone):
    native = enum_name(zone.get("durum")).upper()
    if native in STATUS_LABELS:
        return STATUS_LABELS[native]
    if zone.get("tamamlandi"):
        return "geçmiş kayıt"
    if zone.get("kayit_kaynagi") == "active_records":
        return "aktif"
    return "durum bilinmiyor"


def terminal(zone):
    return bool(zone.get("tamamlandi")) or enum_name(zone.get("durum")).upper() in TERMINAL


def proximity(zone, price, atr):
    """Interval distance is zero *inside*; center distance is a separate metric."""
    lower, upper, price, atr = map(finite, (zone.get("alt"), zone.get("ust"), price, atr))
    if lower is None or upper is None or price is None or lower > upper:
        return {"konum": "bilinmiyor", "sinir_mesafe": None,
                "sinir_mesafe_atr": None, "merkez_mesafe_atr": None}
    distance = max(lower - price, price - upper, 0.0)
    center = abs((lower + upper) / 2 - price)
    return {"konum": "içinde" if lower <= price <= upper else "üstünde" if price > upper else "altında",
            "sinir_mesafe": distance,
            "sinir_mesafe_atr": distance / atr if atr and atr > 0 else None,
            "merkez_mesafe_atr": center / atr if atr and atr > 0 else None}


def readiness(results):
    output = {}
    for name in DOMAIN_LABELS:
        native = field(results, name)
        metrics = field(field(native, "details", {}) or {}, "latest_metrics")
        quality = enum_name(field(native, "data_quality"))
        if native is None:
            state, label = "UNKNOWN", "veri yok"
        elif field(native, "error"):
            state, label = "ERROR", "hata"
        elif field(native, "skipped", False):
            reason = str(field(native, "reason", ""))
            state = "SKIPPED"
            label = "bu TF desteklenmiyor" if "supports only" in reason else "bu akışta kapalı"
        elif name == "volume_participation" and metrics is not None:
            if field(metrics, "data_ready", False):
                state, label = "READY", "hazır"
            else:
                state, label = "WARMUP", "hazır değil"
        elif quality in {"WARMUP", "INSUFFICIENT_DATA"}:
            state, label = "WARMUP", "geçmiş yetersiz"
        elif quality and quality not in {"OK", "READY"} and name != "volume_participation":
            state, label = "DEGRADED", "veri sınırlı"
        elif field(native, "result") is not None or quality == "OK":
            state, label = "READY", "hazır"
        else:
            state, label = "UNKNOWN", "hazırlık bilinmiyor"
        output[name] = {"ad": DOMAIN_LABELS[name], "durum": state, "etiket": label,
                        "native_quality": quality or None,
                        # Internal exception text and provider paths are not public UI.
                        "volume_usable": field(metrics, "volume_usable"),
                        "capital_usable": field(metrics, "capital_usable")}
    return output


def expected_bar(now, tf, anchor):
    """Find last due label using known sessions and existing close semantics.

    Intraday anchor comes from the input series, not a guessed provider offset.
    Five minutes of ingestion grace avoids declaring a just-closed bar missing.
    Calendar errors/unknown dates fail visibly to UNKNOWN, not 'current'.
    """
    from bist_calendar import SessionStatus, bist_session_for
    from data import mum_kapanis_ani
    now, anchor = local_time(now), local_time(anchor)
    hours = {"1h": 1, "2h": 2, "4h": 4}
    if now is None or anchor is None or tf not in (*hours, "1d"):
        return None
    cutoff = now - timedelta(minutes=5)
    for offset in range(45):
        day = now.date() - timedelta(days=offset)
        session = bist_session_for(day)
        if session.status is SessionStatus.UNKNOWN:
            return None
        if session.status is not SessionStatus.TRADING:
            continue
        labels = []
        if tf == "1d":
            labels = [now.replace(year=day.year, month=day.month, day=day.day,
                                  hour=0, minute=0, second=0, microsecond=0)]
        elif session.close_time and session.open_time:
            # Preserve observed session alignment (e.g. 09:30), including 2h/4h.
            stamp = now.replace(year=day.year, month=day.month, day=day.day,
                                hour=anchor.hour, minute=anchor.minute, second=0, microsecond=0)
            end = stamp.replace(hour=session.close_time.hour, minute=session.close_time.minute)
            while stamp < end:
                labels.append(stamp)
                stamp += timedelta(hours=hours[tf])
        due = [label for label in labels if local_time(mum_kapanis_ani(label, tf)) <= cutoff]
        if due:
            return due[-1]
    return None


def trust_payload(snapshot, results, *, now, source=None, historical=False, anchor=None):
    last = local_time(snapshot.get("son_bar_ts"))
    now = local_time(now)
    expected = None
    state, label = "UNKNOWN", "güncellik bilinmiyor"
    if historical:
        state, label = "HISTORICAL", "TARİHSEL / OFFLINE"
    elif last and now:
        try:
            expected = expected_bar(now, str(snapshot.get("tf")), anchor or last)
            if last > now:
                state, label = "FUTURE", "veri zamanı gelecekte"
            elif expected is not None:
                # Daily label time is not a physical close time.
                current = last.date() >= expected.date() if snapshot.get("tf") == "1d" else last >= expected
                state, label = ("CURRENT", "analiz anında güncel") if current else ("STALE", "VERİ GECİKMİŞ")
        except Exception:  # noqa: BLE001, S110 - chart survives; UNKNOWN is visible, never a green success
            pass
    source_text = "kaynak belirtilmedi"
    if source:
        # Paths identify infrastructure, not the market-data provider.
        source_text = "demo · sentetik" if "sentetik" in str(source) else (
            "saatlikten türetildi" if "resample(" in str(source) else "bellek / önbellek")
    return {"surum": 1, "durum": state, "etiket": label,
            "analiz_zamani": now.isoformat() if now else None,
            "son_mum_etiketi": last.isoformat() if last else None,
            "beklenen_son_mum": expected.isoformat() if expected else None,
            "saat_dilimi": "Europe/Istanbul", "kaynak": source_text,
            "mum_sayisi": int(snapshot.get("bar_sayisi") or 0),
            "motorlar": readiness(results)}


def prepare_view(snapshot, mode="odak", *, max_distance_atr=3.0):
    """Copy-only viewport selection. Complete regions remain in details payload.

    'baglam' includes terminal/distant records within existing per-side quotas.
    'odak' suppresses terminal/distant boxes; never silently shows history as live.
    Unknown ATR uses the visible candle range, not a fabricated ATR distance.
    """
    view = deepcopy(dict(snapshot))
    zone = view.get("zone") or {}
    pool = [dict(z) for z in zone.get("tum", zone.get("cizilen", []))
            if str(z.get("tip")) in {"ob", "fvg"}]
    price, atr = finite(view.get("son_kapanis")), finite(zone.get("atr"))
    candles = [finite(x) for name in ("dusuk", "yuksek") for x in view.get(name, [])]
    candles = [x for x in candles if x is not None]
    low, high = (min(candles), max(candles)) if candles else (None, None)
    mode = mode if mode in {"odak", "baglam"} else "odak"
    cap = zone.get("kapak") or {"ust": 3, "alt": 3}
    for z in pool:
        z.update(proximity(z, price, atr))
    pool.sort(key=lambda z: (terminal(z), enum_name(z.get("durum")) == "CANDIDATE",
                             z.get("sinir_mesafe") if z.get("sinir_mesafe") is not None else math.inf,
                             -(finite(z.get("kaynak")) or 0)))
    eligible = []
    for z in pool:
        distance = z.get("sinir_mesafe_atr")
        near = distance <= max_distance_atr if distance is not None else (
            low is not None and finite(z.get("alt")) is not None and finite(z.get("ust")) is not None
            and z["alt"] <= high and z["ust"] >= low)
        z["gorunum_nedeni"] = "geçmiş durum" if mode == "odak" and terminal(z) else (
            "uzak bölge" if mode == "odak" and not near else "görünüm kotası")
        if z["gorunum_nedeni"] == "görünüm kotası":
            eligible.append(z)
    shown = []
    for side in ("ust", "alt"):
        candidates = [z for z in eligible if ("ust" if price is None or
            (z["alt"] + z["ust"]) / 2 >= price else "alt") == side]
        capacity = int(cap.get(side, 3))
        # Preserve the existing active-FVG visibility slot when capacity permits.
        reserved = next((z for z in candidates if z["tip"] == "fvg" and not terminal(z)), None)
        chosen = [reserved] if capacity >= 2 and reserved is not None else []
        for z in candidates:
            if len(chosen) >= capacity:
                break
            if z not in chosen:
                chosen.append(z)
        shown.extend(chosen)
    for z in pool:
        z["gorunur"] = z in shown
        if z["gorunur"]:
            z["gorunum_nedeni"] = "gösteriliyor"
    zone.update({"cizilen": shown, "tum": pool, "etiket_ic": False,
                 "sirala": zone.get("sirala") or "zone verisi yok",
                 "elenen": len(pool) - len(shown), "gorunum": mode,
                 "kaynak_disi": sum(1 for z in shown if z.get("kaynak") is not None
                                    and z["kaynak"] < int(view.get("sol") or 0))})
    view["zone"] = zone
    event = view.get("olay") or {}
    original_levels = list(event.get("seviyeler") or [])
    kept_levels = original_levels
    if mode == "odak" and low is not None:
        if atr and atr > 0 and price is not None:
            kept_levels = [z for z in original_levels if finite(z.get("fiyat")) is not None
                           and abs(z["fiyat"] - price) <= max_distance_atr * atr]
        else:
            kept_levels = [z for z in original_levels if finite(z.get("fiyat")) is not None
                           and low <= z["fiyat"] <= high]
    # Historical off-window events belong in timeline, not as labels at x=0.
    kept_events = [e for e in event.get("olaylar", []) if finite(e.get("bar")) is not None
                   and 0 <= e["bar"] < len(view.get("zamanlar") or [])]
    view["olay"] = {**event, "seviyeler": kept_levels, "olaylar": kept_events}
    view["gorunum"] = {"mod": mode, "gosterilen": len(shown), "toplam": len(pool),
                       "gizlenen": len(pool) - len(shown),
                       "uzak_seviye": len(original_levels) - len(kept_levels),
                       "odak_esigi_atr": max_distance_atr}
    return view


def detail_payload(snapshot, view):
    """Public explainability: exact ranges, native status, provenance, timeline."""
    zones = []
    for z in (view.get("zone") or {}).get("tum", []):
        zones.append({k: z.get(k) for k in (
            "tip", "yon", "alt", "ust", "zaman", "kaynak", "durum", "tamamlandi",
            "kayit_kaynagi", "mitigated_percentage", "konum", "sinir_mesafe_atr",
            "merkez_mesafe_atr", "gorunur", "gorunum_nedeni")})
        zones[-1]["durum_etiketi"] = zone_status(z)
    levels = []
    visible_levels = (view.get("olay") or {}).get("seviyeler", [])
    for level in (snapshot.get("olay") or {}).get("seviyeler", []):
        if str(level.get("scope") or "EXTERNAL").upper() != "EXTERNAL":
            continue
        levels.append({k: level.get(k) for k in ("etiket", "rol", "fiyat", "zaman", "kaynak_bar")})
        levels[-1]["gorunur"] = level in visible_levels
    events = []
    for e in (snapshot.get("olay") or {}).get("zaman_cizelgesi",
                (snapshot.get("olay") or {}).get("olaylar", [])):
        if str(e.get("scope", "EXTERNAL")).upper() != "EXTERNAL":
            continue
        events.append({k: e.get(k) for k in ("tur", "yon", "seviye", "zaman", "yas",
                                             "kaynak_bar", "teyit", "gecerlilik", "guncellik")})
    return {"surum": 1, "politika": POLICY, "sembol": snapshot.get("sembol"),
            "tf": snapshot.get("tf_kisa") or snapshot.get("tf"),
            "guven": deepcopy(snapshot.get("guven") or {}),
            "gorunum": deepcopy(view.get("gorunum") or {}), "bolgeler": zones, "seviyeler": levels,
            "olaylar": sorted(events, key=lambda e: e.get("kaynak_bar") or 0, reverse=True),
            "sozluk": {"ok": "Bölge oku oluşum yönüdür; fiyat tahmini değildir.",
                       "dolum": "Dolum yüzdesi başarı olasılığı değildir.",
                       "rvol": "RVOL ↑ hacim artışı, ↓ hacim kuruması; al/sat yönü değildir.",
                       "kritik": "Son seçilen dış BOS/CHoCH olayının referans seviyesi; stop veya hedef değildir."}}


def trust_lines(snapshot):
    trust = snapshot.get("guven") or {}
    volume = (trust.get("motorlar") or {}).get("volume_participation") or {}
    source = (snapshot.get("serit") or {}).get("kaynak") or ("gösterilmiyor" if snapshot.get("sade") else "yok")
    line1 = f"{trust.get('etiket', 'güncellik bilinmiyor')} · {trust.get('kaynak', 'kaynak belirtilmedi')} · {trust.get('mum_sayisi', snapshot.get('bar_sayisi', 0))} mum"
    labels = []
    for name in ("market_structure", "order_block", "fvg"):
        info = (trust.get("motorlar") or {}).get(name) or {}
        labels.append(f"{DOMAIN_LABELS[name]}: {info.get('etiket', 'bilinmiyor')}")
    labels.append(f"Hacim: {volume.get('etiket', 'bilinmiyor')} / RVOL: {source}")
    return [line1, " · ".join(labels)]
