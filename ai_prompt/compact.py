"""Deneysel, sınırı açık kompakt grafik yorumu girdisi.

Veri seçimleri yalnız promptu etkiler: packet, grafik, motor ve alarm değişmez.
4.000 karakter hedeflenir; gerekli kanıtlarla 4.500 aşılıyorsa hata verilir.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd

import chart_experience
from .budget import COMPACT_PASTE_BUDGET, utf16_len
from .builder import ROOT, TF_ORDER, PATTERN_STATES, _fmt, _fmt_metric, _label, _num, _render_pattern, _same_level
from reporting.format import sayi

TARGET = COMPACT_PASTE_BUDGET.user_target
MAXIMUM = COMPACT_PASTE_BUDGET.user_hard_max


def _size(text: str) -> int:
    """En katı yaygın karakter sayımı: Unicode kod noktası veya UTF-16 birimi."""
    return utf16_len(text)


def _time(value: Any, year: int) -> str:
    if value is None:
        return "bilinmiyor"
    try:
        t = pd.Timestamp(value)
        if t.tzinfo is None or pd.isna(t):
            return "bilinmiyor"
        t = t.tz_convert("Europe/Istanbul")
        return t.strftime("%d.%m %H:%M" if t.year == year else "%d.%m.%Y %H:%M")
    except (ValueError, TypeError, OverflowError):
        return "bilinmiyor"


def _known_age(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _event_selection(events: list[dict], *, history_bars: int | None = None) -> tuple[list[dict], int]:
    """İki en yeni BOS, yön başına en yeni BOS ve CHoCH korunur.

    Eski olayların atılması grafik geçmişinin olmadığını söylemez. Güvenilir
    zaman olmayan veya yeni/alışılmadık türdeki olaylar sessizce çıkarılmaz.
    """
    if not events:
        return [], 0
    if any(_time(e.get("bar_open"), 2000) == "bilinmiyor" for e in events):
        return list(events), 0
    order = sorted(range(len(events)), key=lambda i: pd.Timestamp(events[i]["bar_open"]))
    selected = {i for i in order if events[i].get("type") not in {"BOS", "CHoCH"}
                or events[i].get("direction") not in {"yukarı", "aşağı"}}
    bos = [i for i in order if events[i].get("type") == "BOS"]
    selected.update(bos[-2:])
    for kind in ("BOS", "CHoCH"):
        for direction in ("yukarı", "aşağı"):
            matches = [i for i in order if events[i].get("type") == kind
                       and events[i].get("direction") == direction]
            if matches:
                selected.add(matches[-1])
    if history_bars is not None:
        selected.update(i for i in order if _known_age(events[i].get("age_bars")) is None)
        recent = [i for i in order if (age := _known_age(events[i].get("age_bars"))) is not None
                  and age < history_bars and events[i].get("type") in {"BOS", "CHoCH"}
                  and events[i].get("direction") in {"yukarı", "aşağı"}]
        diversity = {(events[i].get("type"), events[i].get("direction")) for i in recent}
        if len(recent) >= 2 and len(diversity) >= 2:
            # Old records are redundant only when the same kind and direction
            # are represented nearby. Keep both CHoCH directions as transitions.
            selected = {i for i in selected if i in recent
                        or _known_age(events[i].get("age_bars")) is None
                        or events[i].get("type") == "CHoCH"
                        or (events[i].get("type"), events[i].get("direction")) not in diversity}
    return [events[i] for i in order if i in selected], len(events) - len(selected)


def _range(z: dict) -> str:
    return f"{_fmt(z.get('lower'))}–{_fmt(z.get('upper'))}"


def _zone(z: dict) -> str:
    direction = {"pozitif": "+", "negatif": "−"}.get(z.get("direction"), "?")
    status = z.get("state")
    suffix = (f" [{_label(chart_experience.STATUS_LABELS, status)}]"
              if status not in (None, "", "bilinmiyor") else "")
    if z.get("terminal"):
        suffix += " [terminal/geçmiş]"
    return f"{direction}{z.get('family', '?')} {_range(z)}{suffix}"


def _pattern(p: dict) -> str:
    if p["status"] == "absent":
        return "Grafikte formasyon adayı yok."
    if p["status"] != "available":
        return _render_pattern(p)
    parts = [str(p["type"]), PATTERN_STATES.get(p["state"], str(p["state"]))]
    break_dir = p.get("break_direction")
    if break_dir in ("yukarı", "aşağı"):
        arrow = "↑" if break_dir == "yukarı" else "↓"
        if p.get("state") in {"KIRILIM_ADAYI", "KIRILIM_DENEMESI"}:
            parts.append(f"aday yön {arrow}")
        elif p.get("state") in {"KIRILIM_TEYITLI", "RETEST_BEKLENIYOR", "FORMASYON_TAMAMLANDI", "KIRILIM_BASARISIZ"}:
            parts.append(f"kırılım {arrow}")
    quality = _num(p.get("quality"))
    if quality is not None:
        parts.append(f"kalite {int(round(quality))}/100")
    if p.get("contraction") is not None:
        parts.append(f"daralma %{sayi(p['contraction'] * 100, 0)}")
    if p.get("upper_touches") is not None or p.get("lower_touches") is not None:
        upper = p.get("upper_touches") if p.get("upper_touches") is not None else "?"
        lower = p.get("lower_touches") if p.get("lower_touches") is not None else "?"
        parts.append(f"temas üst/alt {upper}/{lower}")
    return "Formasyon: " + "; ".join(parts) + "."


def _drawn_context(tf: str, row: dict, year: int, compact_volume: int = 0,
                   baseline: dict | None = None, history_bars: int | None = None) -> list[str]:
    lines = [f"\n{tf.upper()} GRAFİK"]
    if row["status"] != "available":
        return lines + [f"Grafik verisi bilinmiyor: {row['status']}."]
    if (tf != "1h" and baseline and baseline.get("status") == "available"
            and row.get("last_close_time") is not None and row.get("last_close") is not None
            and row.get("last_close_time") == baseline.get("last_close_time")
            and row.get("last_close") == baseline.get("last_close")):
        lines.append("Kapanış 1H ile aynı.")
    else:
        lines.append(f"Kapanış {_time(row.get('last_close_time'), year)}={_fmt(row.get('last_close'))}.")
    events, omitted = _event_selection(row.get("chart_events") or [], history_bars=history_bars)
    if events:
        labels = []
        for event in events:
            direction = {"yukarı": "↑", "aşağı": "↓"}.get(event.get("direction"), "?")
            age = _known_age(event.get("age_bars"))
            older = " [E]" if history_bars is not None and age is not None and age >= history_bars else ""
            labels.append(f"{_time(event.get('bar_open'), year)} {event.get('type')} {direction}{_fmt(event.get('level'))}{older}")
        lines.append("Dış yapı: " + "; ".join(labels) + ".")
    if omitted:
        lines.append(f"Dış yapı: {omitted} diğer grafik olayı özet dışı.")
    if row.get("chart_levels"):
        lines.append("Seviye: " + "; ".join(f"{x.get('label')} {_fmt(x.get('price'))}" for x in row["chart_levels"]) + ".")
    if row.get("zones"):
        lines.append("Bölge: " + "; ".join(_zone(z) for z in row["zones"]) + ".")
    lines.append(_pattern(row["pattern"]))
    delay = row.get("expected_delay_minutes")
    if delay is None:
        lines.append("Beklenen kapanış doğrulanamadı.")
    elif delay:
        lines.append(f"Veri gecikmesi: {delay} dk.")
    if row.get("ob_status") or row.get("ob_quality") != "OK":
        lines.append(f"OB: {row.get('ob_status') or row.get('ob_quality')}; sonuç kısıtlı.")
    if row["fvg"]["status"] != "available":
        status = row['fvg']['status']
        if tf == "1h" and "source supports only 2h, 4h, and 1d" in status:
            status = "desteklenmiyor; bilinmiyor"
        elif tf == "2h" and "requires explicit offline/replay opt-in" in status:
            status = "çalıştırılmadı; bilinmiyor"
        lines.append(f"FVG: {status}.")
    if row.get("chart_volume_badges"):
        source = row["chart_volume_badges"]
        selected = set(range(len(source)))
        valid = all(_time(b.get("bar_open"), year) != "bilinmiyor"
                    and _num(str(b.get("value", "")).replace(",", ".")) is not None for b in source)
        if history_bars is not None and valid:
            fresh = {i for i, b in enumerate(source)
                     if (age := _known_age(b.get("age_bars"))) is not None and age < history_bars}
            if len(fresh) >= 2:
                selected = fresh | {i for i, b in enumerate(source) if _known_age(b.get("age_bars")) is None
                                    or b.get("direction") not in ("artis", "dusus")}
                for direction in ("artis", "dusus"):
                    ids = [i for i, b in enumerate(source) if b.get("direction") == direction]
                    if ids:
                        selected.add(max(ids, key=lambda i: pd.Timestamp(source[i]["bar_open"])))
        max_badges = 2 if compact_volume >= 2 else 4
        if compact_volume and valid and len(selected) > max_badges:
            # Retain newest in each direction; stage 1 also retains strongest.
            chosen = set()
            for direction in ("artis", "dusus"):
                ids = [i for i in selected if source[i].get("direction") == direction]
                if ids:
                    chosen.add(max(ids, key=lambda i: pd.Timestamp(source[i]["bar_open"])))
                    if compact_volume == 1:
                        chosen.add((max if direction == "artis" else min)(ids, key=lambda i: float(str(source[i]["value"]).replace(",", "."))))
            chosen.update(i for i in selected if source[i].get("direction") not in ("artis", "dusus")
                          or _known_age(source[i].get("age_bars")) is None and history_bars is not None)
            selected = chosen
        ordered_indices = (
            sorted(selected, key=lambda i: pd.Timestamp(source[i]["bar_open"]))
            if valid else [i for i in range(len(source)) if i in selected]
        )
        badges = []
        for i in ordered_indices:
            badge = source[i]
            direction = {"artis": "A", "dusus": "K"}.get(badge.get("direction"), "?")
            age = _known_age(badge.get("age_bars"))
            older = " [E]" if history_bars is not None and age is not None and age >= history_bars else ""
            badges.append(f"{_time(badge.get('bar_open'), year)} {direction}×{badge['value']}{older}")
        omitted = len(source) - len(selected)
        suffix = f"; {omitted} diğer grafik rozeti özette yok" if omitted else ""
        lines.append(f"Hacim ({row.get('chart_rvol_source') or 'kaynak bilinmiyor'}): " + "; ".join(badges) + suffix + ".")
    for key, label in (("chart_stabil_support", "destek"), ("chart_stabil_resistance", "direnç")):
        if row.get(key) is not None:
            lines.append(f"Stabil {label}: {_fmt(row[key])}.")
    return lines


def _focus_indices(zones: list[dict], close: Any) -> set[int]:
    """Yakın pozitif ve negatif bölge ayrıntılarını yönleri karıştırmadan tut."""
    price = _num(close)
    if price is None:
        return set(range(len(zones)))  # safe: no arbitrary selection if unknown
    def distance(i):
        z = zones[i]
        lo, hi = _num(z.get("lower")), _num(z.get("upper"))
        if lo is None or hi is None or lo > hi:
            return float("inf")
        return max(lo - price, 0, price - hi)
    chosen: set[int] = set()
    for direction in ("pozitif", "negatif"):
        candidates = [i for i, z in enumerate(zones) if z.get("direction") == direction
                      and z.get("replay_status") == "ok" and not z.get("terminal")]
        if candidates:
            chosen.add(min(candidates, key=distance))
    # Each family/direction can be distinct evidence: do not let a nearby FVG
    # suppress the only opposing OB (or vice versa).
    keys = {(z.get("family"), z.get("direction")) for z in zones}
    for family, direction in keys:
        candidates = [i for i, z in enumerate(zones) if z.get("family") == family
                      and z.get("direction") == direction and z.get("replay_status") == "ok"
                      and not z.get("terminal")]
        if candidates and not any(zones[i].get("family") == family and zones[i].get("direction") == direction for i in chosen):
            chosen.add(min(candidates, key=distance))
    if not chosen and zones:
        chosen.add(min(range(len(zones)), key=distance))
    return chosen


def _replay(tf: str, row: dict, year: int, focus_only: bool, last_only: bool = False,
            history_bars: int | None = None, compact_header: bool = False) -> list[str]:
    if compact_header:
        header = f"\n{tf.upper()} REPLAY | OB: bant/OHLC; FVG: motor. Ardışık=grup (detay son 2); değer=kapanış."
    else:
        header = f"\n{tf.upper()} REPLAY | OB: orijinal bant/OHLC; FVG: motor kuralı. Ardışık temas=grup; sayım tüm pencere, detay son 2 grup. Değer=kapanış; sonraki=sonraki mum."
    lines = [header]
    if row["status"] != "available":
        return lines + ["Grafik çizilemedi; replay bilinmiyor."]
    zones = row["replay"]["zones"]
    if not zones:
        return lines + ["Grafikte replay bölgesi seçilmedi; bu sıfır geçmiş anlamına gelmez."]
    focus = _focus_indices(zones, row.get("last_close")) if focus_only else set(range(len(zones)))
    if tf == "1d" and any(z.get("family") == "FVG" and z.get("replay_status") == "ok" for z in zones):
        lines.append("FVG doğum oranı: orijinal yükseklik/Wilder ATR(14); grup alt sınırı dahil, üst sınırı hariç.")
    for i, z in enumerate(zones):
        label = _zone(z)
        if z.get("replay_status") != "ok":
            lines.append(f"{label}: {z.get('replay_status', 'bilinmiyor')}.")
            continue
        lo, hi, close = _num(z.get("lower")), _num(z.get("upper")), _num(row.get("last_close"))
        pos = ""
        if z.get("episodes") and (i in focus or not focus_only) and None not in (lo, hi, close) and lo <= hi:
            pos = "; son kapanış orijinal bant " + ("altında" if close < lo else "üstünde" if close > hi else "içinde/sınırında")
        atr = ""
        # The available ATR research is daily FVG only; an intraday ratio is
        # not needed to interpret it and remains in the underlying packet.
        if z.get("family") == "FVG" and tf == "1d":
            if z.get("width_atr_birth") is None:
                atr = "; doğum ATR oranı bilinmiyor"
            else:
                atr = f"; doğum yükseklik/ATR≈{_fmt_metric(z['width_atr_birth'])} (grup {z['width_atr_bucket']})"
        remaining_lo, remaining_hi = _num(z.get("remaining_lower")), _num(z.get("remaining_upper"))
        remaining = ("aynı" if None not in (lo, hi, remaining_lo, remaining_hi)
                     and math.isclose(remaining_lo, lo, rel_tol=1e-10, abs_tol=1e-12)
                     and math.isclose(remaining_hi, hi, rel_tol=1e-10, abs_tol=1e-12)
                     else f"{_fmt(remaining_lo)}–{_fmt(remaining_hi)}")
        line = (f"{label}: {z['episodes']} grup; kullanılabilir {_time(z.get('available_open'), year)}; "
                f"kalan {remaining}{pos}{atr}.")
        lines.append(line)
        episodes = z.get("recent_episodes") or []
        if (history_bars is not None and not z.get("terminal")
                and sum(1 for ep in episodes if (age := _known_age(ep.get("end_age_bars"))) is not None
                        and age < history_bars) >= 2):
            retained = [ep for ep in episodes if _known_age(ep.get("end_age_bars")) is None
                        or ep["end_age_bars"] < history_bars]
            omitted = len(episodes) - len(retained)
            if omitted:
                lines.append(f"  {omitted} eski temasın kapanış ayrıntısı özet dışında.")
            episodes = retained
        if i not in focus and episodes:
            retained = ([ep for ep in episodes if _known_age(ep.get("end_age_bars")) is None]
                        if history_bars is not None else [])
            if len(retained) < len(episodes):
                lines.append("  Bu bölgenin bazı temas kapanışları kısa özete alınmadı.")
            episodes = retained
        if last_only and len(episodes) > 1:
            retained = ([ep for ep in episodes[:-1] if _known_age(ep.get("end_age_bars")) is None]
                        if history_bars is not None else []) + episodes[-1:]
            if len(retained) < len(episodes):
                lines.append(f"  Önceki {len(episodes) - len(retained)} ayrıntı yok.")
            episodes = retained
        for ep in episodes:
            start = _time(ep.get("start_open"), year)
            end = _time(ep.get("end_open"), year)
            last_date = None
            def compact_close(bar):
                nonlocal last_date
                stamp = _time(bar.get("bar_open"), year)
                date, sep, clock = stamp.rpartition(" ")
                printed = clock if sep and date == last_date else stamp
                last_date = date if sep else None
                return f"{printed}={_fmt(bar.get('close'))}"
            closes = ", ".join(compact_close(x) for x in ep["closes"])
            truncated = bool(ep.get("closes_truncated"))
            interval = f"{start}–{end}; " if truncated and start != end else ""
            extra = f"{ep['bar_count']} mum, son 3: " if truncated else ""
            after = ep.get("next_bar_close")
            follow = f"; sonraki {compact_close(after)}" if after else "; sonraki kapanmış mum yok"
            ongoing = "; devam ediyor olabilir" if ep.get("ongoing_at_cut") else ""
            age = _known_age(ep.get("end_age_bars"))
            older = " [E]" if history_bars is not None and age is not None and age >= history_bars else ""
            lines.append(f"  {ep['number']}{older}: {interval}{extra}{closes}{follow}{ongoing}.")
    return lines


def _stabil(replay: dict, year: int, compact_note: bool = False) -> list[str]:
    if replay["status"] != "ok":
        return [f"Stabil günlük temas sırası bilinmiyor: {replay['status']}."]
    available = _time(replay['support_available_at'], year)
    window = _time(replay['window_identity_start'], year)
    timeline = f"bilinir ve pencere başlangıcı {available}" if available == window else f"bilinir {available}; pencere başlangıcı {window}"
    lines = [f"Stabil günlük destek {_fmt(replay['support_level'])}; {timeline}."]
    if not replay["atr_complete_for_separation"]:
        lines.append("Günlük fiyat/destek veya ATR eksik; temas sırası bilinmiyor.")
    elif replay["sequence_known"]:
        lines.append(f"Günlük bağımsız temas sırası: {replay['observed_count']}.")
    else:
        reason = ("kimlik aradan sonra tekrar görüldü" if replay.get("unknown_reason") == "tekrar_gorunen_kimlik" else "ilk destek kimliği")
        lines.append(f"Pencerede {replay['observed_count']} temas; {reason}, geçmiş ve gerçek sıra bilinmiyor.")
    for day in replay["recent_touch_days"]:
        lines.append(f"Günlük temas kapanışı {_time(day['daily_close_time'], year)}={_fmt(day['close'])}.")
    if compact_note:
        lines.append("Günlük temas: OHLC≥destek, kapanış üstü; bağımsız≥0,35 günlük ATR. İlk gün test, 4s teyit değil.")
    else:
        lines.append("Günlük temas: OHLC desteği kapsar, kapanış altında değil; bağımsız sayım ≥0,35 günlük ATR ayrılma ister. İlk gün bilinen test değil; 4s temas/ret teyidi değil.")
    return lines


_RESEARCH_SHORT = {
    "ob-temas-2026-10-21": "OB: 131.901 bölgede 17.048 (%12,9) 3+ temas; çok temasın zayıflattığı kanıtlanmaz.",
    "fvg-atr-2026-10-21": "Günlük FVG n=6.285; doğum yükseklik/ATR 0–<0,5 n=3.276, ≥2 n=162. Sonraki en çok 12 günlük mumda bölge kenarından ≥1 temas ATR yönlü uzanım sırasıyla %64,3/%71,0; payda tüm temaslar, eksik gelecek pencere olabilir. Başka TF'ye genelleme.",
    "stabil-temas-2026-11-01": "Stabil: ≥0,35 günlük ATR ayrılmalı günlük destek temas sırasına göre 4s temaslar; 8×4s tam ufuk 3+ grubu n=33, %81,8 tek sembol. Genellenemez; veri sonu bilinmiyor.",
    "ms-dis-bos-2026-10-21": "MS: 4s dış BOS grubu iç BOS, CHoCH veya başka TF'ye aktarılmaz; mevcut olayın sonucu belirlenmez.",
}


# A short text must never silently outlive a change to its source manifest.
# A changed finding falls back to the full text (or a clear budget error).
_RESEARCH_DIGEST = {
    "ob-temas-2026-10-21": "1edf5a9a5cb1f20290a76968c1a2b44b4579db1024f5223653b32bab9d707747",
    "fvg-atr-2026-10-21": "80e8d4adf4eea5a7d2fe3ed13e823ccffa045c3e394a5780bd3a492260318d94",
    "stabil-temas-2026-11-01": "66eec5a0dd9e8434a1cf886c21869ee3eb9456f0bdd4a31c0f4abfef08f5c084",
    "ms-dis-bos-2026-10-21": "8bbd9da1137120e1e30069bc2d9482754dc9ce98b9cf17d59372aabe2cc4ebe0",
}


def _research(packet: dict, row: dict, tf: str, abbreviated: bool = False) -> list[str]:
    families = {z["family"] for z in row.get("zones", [])}
    stabil = (tf == "4h" and row.get("chart_stabil_support") is not None
              and _same_level(row.get("stabil_daily_replay", {}).get("support_level"), row.get("chart_stabil_support")))
    def relevant(item):
        ident = item["id"]
        return ((ident.startswith("ob-") and "OB" in families)
                or (ident.startswith("fvg-") and tf == "1d" and "FVG" in families)
                or (ident.startswith("stabil-") and stabil)
                or (ident.startswith("ms-") and tf == "4h" and any(e["type"] == "BOS" for e in row.get("chart_events", []))))
    studies = [x for x in packet["research"] if relevant(x)]
    if not studies:
        return []
    lines = ["\nGENEL ARAŞTIRMA | Sembole özel olasılık değil."]
    if packet["research_mode"] == "retrospective":
        lines.append("Kesit sonrası/belirsiz bulgular o tarihte biliniyor sayılmaz.")
    omitted_studies = []
    for item in studies:
        # Keep numerical OB/FVG studies. Qualitative MS and small Stabil studies
        # can be omitted only as an explicit, labelled budget decision.
        if abbreviated and (item["id"].startswith("stabil-") or item["id"].startswith("ms-")):
            omitted_studies.append("Stabil" if item["id"].startswith("stabil-") else "MS")
            continue
        if item["included"]:
            digest = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
            text = (_RESEARCH_SHORT[item["id"]] if item["id"] in _RESEARCH_SHORT
                    and digest == _RESEARCH_DIGEST.get(item["id"]) else item["text"])
        else:
            text = "Bu kesitte kullanılabilirliği doğrulanmadı; bulgu verilmedi."
        label = {"ob-temas-2026-10-21": "OB", "fvg-atr-2026-10-21": "FVG",
                 "stabil-temas-2026-11-01": "Stabil", "ms-dis-bos-2026-10-21": "MS"}.get(item["id"], item["id"])
        prefix = label + ": "
        if text.startswith(prefix):
            text = text[len(prefix):]
        lines.append(f"{label} [{item['timeline']}; rapor {item.get('recorded_at') or '?'}, veri sonu {item.get('data_through') or 'bilinmiyor'}]: {text}")
    if omitted_studies:
        lines.append("Araştırma özeti dışında: " + ", ".join(omitted_studies) + ".")
    return lines


def _compose(packet: dict, stage: int = 0, history_bars: int | None = None) -> str:
    year = pd.Timestamp(packet["as_of"]).tz_convert("Europe/Istanbul").year
    kind = packet['kind']
    if kind == "tarihsel veya isteğe bağlı kesit; gerçek alarm doğrulanmadı":
        kind = "tarihsel/isteğe bağlı; alarm doğrulanmadı"
    lines = [(ROOT / "talimat_kisa.txt").read_text(encoding="utf-8").strip(),
             f"\nGRAFİK VERİSİ | {packet['symbol']} | kesit {_time(packet['as_of'], year)} (İstanbul) | ana TF {packet['main_tf']} | {kind}.",
             f"{packet['source']}; günlük: {packet['daily_source']}. Yıl {year}; kapanış dışı saat=açılış, bilgi kapanışta bilinir. İlk kova eksik, son mum kısa olabilir; tüm geçmiş değil, süreklilik tam doğrulanmadı.",
             "OB/FVG: + pozitif, − negatif. Hacim rozetinde A=artış, K=kuruma; fiyat yönü değildir."]
    if history_bars is not None:
        lines.append(f"TF başına son {history_bars} kapanmış mum öncelikli; [E]=daha eski.")
    if packet.get("quality_notes"):
        lines.append("Veri uyarısı: " + "; ".join(packet["quality_notes"]) + ".")
    warnings: dict[str, list[str]] = {}
    for tf in TF_ORDER:
        for warning in packet["timeframes"][tf].get("chart_warnings", []):
            warnings.setdefault(str(warning), []).append(tf)
    for warning, timeframes in warnings.items():
        if warning == "Stabil direnç gösterilemedi: gerekli günlük veya saatlik kaynak yok":
            warning = "Stabil direnç: günlük/saatlik kaynak eksik; gösterilemedi"
        lines.append(f"Grafik uyarısı ({'/'.join(timeframes)}): {warning}.")
    for tf in TF_ORDER:
        lines.extend(_drawn_context(tf, packet["timeframes"][tf], year,
                                    compact_volume=(2 if stage >= 5 else 1 if stage >= 4 else 0),
                                    baseline=packet["timeframes"]["1h"], history_bars=history_bars))
    tf = packet["main_tf"]
    row = packet["timeframes"][tf]
    lines.extend(_replay(tf, row, year, focus_only=stage >= 1, last_only=stage >= 3,
                         history_bars=history_bars, compact_header=stage >= 6))
    if (row["status"] == "available" and row.get("chart_stabil_support") is not None
            and _same_level(row["stabil_daily_replay"].get("support_level"), row["chart_stabil_support"])):
        lines.extend(_stabil(row["stabil_daily_replay"], year, compact_note=stage >= 6))
    lines.extend(_research(packet, row, tf, abbreviated=stage >= 2))
    return "\n".join(lines).strip() + "\n"


def render_compact_prompt(packet: dict, *, target: int = TARGET, maximum: int = MAXIMUM,
                          history_bars: int | None = 60) -> str:
    """Bar penceresiyle özetle; None eski seçimi kullanır, sığmazsa hata ver."""
    if not 0 < target <= maximum <= MAXIMUM:
        raise ValueError(f"Sınırlar 0 < hedef ≤ üst sınır ≤ {MAXIMUM} olmalı")
    if history_bars is not None and (not isinstance(history_bars, int) or isinstance(history_bars, bool) or history_bars < 1):
        raise ValueError("Geçmiş penceresi pozitif tamamlanmış mum sayısı olmalı")
    # 4.000 is a preference, not permission to discard evidence needlessly.
    # If the full summary fits the 4.500 safety cap, only use the first replay
    # compaction when it actually reaches the target. Otherwise retain detail.
    text = _compose(packet, stage=0, history_bars=history_bars)
    if target < _size(text) <= maximum:
        candidate = _compose(packet, stage=1, history_bars=history_bars)
        if _size(candidate) <= target:
            text = candidate
    elif _size(text) > maximum:
        for stage in range(1, 7):
            candidate = _compose(packet, stage=stage, history_bars=history_bars)
            if _size(candidate) < _size(text):
                text = candidate
            if _size(text) <= maximum:
                break
    if _size(text) > maximum:
        raise ValueError(f"Kompakt prompt {_size(text)} karakter/birim; güvenli üst sınır {maximum}. Önemli grafik verileri sessizce kesilmedi.")
    return text
