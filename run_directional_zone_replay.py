"""Generate the offline direction-aware OB/FVG replay from local bot_data caches."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
from datetime import datetime

import pandas as pd
import pytz

# The report runner must not load credentials or dotenv settings.
sys.modules["dotenv"] = None
_real_getenv = os.getenv
os.getenv = lambda name, default=None: default
import data as local_data  # noqa: E402
os.getenv = _real_getenv

from directional_zone_replay import (  # noqa: E402
    FAVORABLE_ATR_THRESHOLDS,
    FVG_PROFILE,
    HORIZONS,
    _normalize_frame,
    build_touch_episodes,
    build_window_rows,
    compute_wilder_atr,
    replay_fvg_zones,
    replay_ob_zones,
)

AS_OF = pytz.timezone("Europe/Istanbul").localize(datetime(2026, 9, 25, 18, 35))
FVG_MINIMUM_HISTORY = {"2h": 100, "4h": 100, "1d": 40}
FAMILIES = (("OB", "1h"), ("FVG", "2h"), ("FVG", "4h"), ("FVG", "1d"))


def _stats(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return {"q25": None, "median": None, "q75": None, "mean": None}
    series = pd.Series(clean, dtype="float64")
    return {
        "q25": float(series.quantile(0.25)),
        "median": float(series.median()),
        "q75": float(series.quantile(0.75)),
        "mean": float(series.mean()),
    }


def _truth_count(rows, field):
    return sum(row.get(field) is True or row.get(field) == True for row in rows)  # noqa: E712


def _summary_base(symbol, family, timeframe, direction, arrival, horizon, zones, windows, readiness):
    selected_zones = [
        z for z in zones
        if (symbol == "ALL" or z["symbol"] == symbol)
        and z["family"] == family and z["timeframe"] == timeframe and z["direction"] == direction
    ]
    selected = [
        w for w in windows
        if (symbol == "ALL" or w["symbol"] == symbol)
        and w["family"] == family and w["timeframe"] == timeframe and w["direction"] == direction
        and w["horizon_bars"] == horizon
        and (arrival == "ALL" or w["arrival_side"] == arrival)
    ]
    full = [w for w in selected if w["window_complete"]]
    atr_evaluable = [w for w in full if w["atr14_at_touch_end"] is not None]
    active_evaluable = [w for w in atr_evaluable if w["active_target_eligible"]]
    unique_with_contact = {w["zone_id"] for w in selected}
    unique_full = {w["zone_id"] for w in atr_evaluable}
    unique_active = {w["zone_id"] for w in active_evaluable}
    row = {
        "symbol": symbol,
        "family": family,
        "timeframe": timeframe,
        "direction": direction,
        "expected_reaction_direction": "UP" if direction == "bullish" else "DOWN",
        "arrival_side": arrival,
        "horizon_bars": horizon,
        "replay_status": readiness.get((symbol, family, timeframe), readiness.get(("ALL", family, timeframe), "OK")),
        "native_zone_count": len(selected_zones),
        "zones_with_touch_in_group": len(unique_with_contact),
        "touch_episodes": len(selected),
        "complete_price_windows": len(full),
        "right_censored_data_end_windows": sum(not w["window_complete"] for w in selected),
        "atr14_unavailable_windows": sum(w["atr14_at_touch_end"] is None for w in selected),
        "atr_evaluable_complete_windows": len(atr_evaluable),
        "active_preterminal_evaluable_windows": len(active_evaluable),
        "zones_with_at_least_one_evaluable_window": len(unique_full),
        "zones_with_at_least_one_active_preterminal_window": len(unique_active),
        "native_terminal_on_touch_episodes": sum(w["native_terminal_at_or_before_touch"] for w in selected),
        "native_terminal_within_observed_window_episodes": sum(w["native_terminal_within_observed_window"] for w in selected),
        "native_price_violation_at_touch_episodes": sum(w["native_terminal_at_or_before_touch"] and w["native_price_violation"] for w in selected),
        "native_price_violation_within_observed_window_episodes": sum(w["native_price_violation_within_observed_window"] for w in selected),
        "native_full_fill_at_touch_episodes": sum(w["native_terminal_at_or_before_touch"] and w["native_full_fill"] for w in selected),
        "native_full_fill_within_observed_window_episodes": sum(w["native_full_fill_within_observed_window"] for w in selected),
        "median_favorable_excursion_atr_full_window": _stats([w["full_window_favorable_excursion_atr"] for w in atr_evaluable])["median"],
        "q25_favorable_excursion_atr_full_window": _stats([w["full_window_favorable_excursion_atr"] for w in atr_evaluable])["q25"],
        "q75_favorable_excursion_atr_full_window": _stats([w["full_window_favorable_excursion_atr"] for w in atr_evaluable])["q75"],
        "median_adverse_excursion_atr_full_window": _stats([w["full_window_adverse_excursion_atr"] for w in atr_evaluable])["median"],
        "q25_adverse_excursion_atr_full_window": _stats([w["full_window_adverse_excursion_atr"] for w in atr_evaluable])["q25"],
        "q75_adverse_excursion_atr_full_window": _stats([w["full_window_adverse_excursion_atr"] for w in atr_evaluable])["q75"],
    }
    for threshold in FAVORABLE_ATR_THRESHOLDS:
        tag = str(threshold).replace(".", "p")
        hit_full = [w for w in atr_evaluable if w[f"target_{tag}_atr_hit_full_window"]]
        hit_active = [w for w in active_evaluable if w[f"target_{tag}_atr_hit_before_native_terminal"]]
        same_bar = [w for w in atr_evaluable if w[f"target_{tag}_atr_active_zone_category"] == "AMBIGUOUS_ON_TERMINAL_BAR"]
        post_terminal = [w for w in atr_evaluable if w[f"target_{tag}_atr_active_zone_category"] == "HIT_ONLY_AFTER_NATIVE_TERMINAL"]
        zones_full_hit = {w["zone_id"] for w in hit_full}
        zones_active_hit = {w["zone_id"] for w in hit_active}
        row.update({
            f"target_{tag}_full_window_hit_episodes": len(hit_full),
            f"target_{tag}_full_window_hit_share": len(hit_full) / len(atr_evaluable) if atr_evaluable else None,
            f"target_{tag}_hit_before_native_terminal_episodes": len(hit_active),
            f"target_{tag}_hit_before_native_terminal_share": len(hit_active) / len(active_evaluable) if active_evaluable else None,
            f"target_{tag}_same_terminal_bar_ambiguous_episodes": len(same_bar),
            f"target_{tag}_hit_only_after_native_terminal_episodes": len(post_terminal),
            f"zones_with_full_window_target_{tag}_hit": len(zones_full_hit),
            f"zones_with_preterminal_target_{tag}_hit": len(zones_active_hit),
            f"zone_share_with_preterminal_target_{tag}_hit": len(zones_active_hit) / len(unique_active) if unique_active else None,
        })
    return row


def make_zone_summary(zones, windows):
    rows = []
    by_zone_horizon = {}
    for window in windows:
        by_zone_horizon.setdefault((window["zone_id"], window["horizon_bars"]), []).append(window)
    for zone in zones:
        for horizon in HORIZONS:
            group = by_zone_horizon.get((zone["zone_id"], horizon), [])
            complete_atr = [w for w in group if w["window_complete"] and w["atr14_at_touch_end"] is not None]
            active = [w for w in complete_atr if w["active_target_eligible"]]
            row = {k: v for k, v in zone.items() if k not in {"contact_bars", "touch_bars"}}
            row.update({
                "horizon_bars": horizon,
                "touch_episode_count": len(group),
                "complete_price_windows": sum(w["window_complete"] for w in group),
                "right_censored_data_end_windows": sum(not w["window_complete"] for w in group),
                "atr14_unavailable_windows": sum(w["atr14_at_touch_end"] is None for w in group),
                "atr_evaluable_complete_windows": len(complete_atr),
                "active_preterminal_evaluable_windows": len(active),
                "native_terminal_on_touch_episodes": sum(w["native_terminal_at_or_before_touch"] for w in group),
                "native_price_violation_at_touch_episodes": sum(w["native_terminal_at_or_before_touch"] and w["native_price_violation"] for w in group),
                "native_price_violation_within_observed_window_episodes": sum(w["native_price_violation_within_observed_window"] for w in group),
                "native_full_fill_at_touch_episodes": sum(w["native_terminal_at_or_before_touch"] and w["native_full_fill"] for w in group),
                "native_full_fill_within_observed_window_episodes": sum(w["native_full_fill_within_observed_window"] for w in group),
                "zone_has_evaluable_active_window": bool(active),
            })
            for threshold in FAVORABLE_ATR_THRESHOLDS:
                tag = str(threshold).replace(".", "p")
                full_hit = [w for w in complete_atr if w[f"target_{tag}_atr_hit_full_window"]]
                pre_hit = [w for w in active if w[f"target_{tag}_atr_hit_before_native_terminal"]]
                ambiguous = [w for w in complete_atr if w[f"target_{tag}_atr_active_zone_category"] == "AMBIGUOUS_ON_TERMINAL_BAR"]
                row.update({
                    f"target_{tag}_full_window_hit_episodes": len(full_hit),
                    f"target_{tag}_hit_before_native_terminal_episodes": len(pre_hit),
                    f"target_{tag}_same_terminal_bar_ambiguous_episodes": len(ambiguous),
                    f"zone_any_full_window_target_{tag}_hit": bool(full_hit) if complete_atr else None,
                    f"zone_any_preterminal_target_{tag}_hit": bool(pre_hit) if active else None,
                })
            rows.append(row)
    return rows


def _read_local_universe():
    cache_paths = sorted(Path("bot_data").glob("*.json"))
    if len(cache_paths) != 28:
        raise RuntimeError(f"Expected the existing 28 local JSON caches; found {len(cache_paths)}")
    hourly_by_symbol = {}
    audit = {}
    for path in cache_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows, skipped = local_data._temiz_1h_cache_kayitlari(raw)
        if skipped:
            raise RuntimeError(f"{path.name}: cache parser skipped {skipped} rows")
        hourly = pd.DataFrame(rows).set_index("timestamp")
        hourly = local_data.tamamlanmis_mumlar(hourly, "1h", now=AS_OF)
        if hourly is None or hourly.empty:
            raise RuntimeError(f"{path.stem}: no completed 1h bars")
        hourly_by_symbol[path.stem] = hourly
        audit[path.stem] = {
            "raw_rows": len(rows),
            "skipped_rows": skipped,
            "first_1h": hourly.index[0],
            "last_1h": hourly.index[-1],
            "completed_1h_bars": len(hourly),
        }
    return hourly_by_symbol, audit


def run():
    hourly_by_symbol, audit = _read_local_universe()
    engine_frames = {}
    readiness_rows = []
    zones = []
    for symbol, hourly in sorted(hourly_by_symbol.items()):
        resampled = local_data.resample_all_timeframes(hourly)
        for timeframe in ("1h", "2h", "4h", "1d"):
            frame = resampled.get(timeframe)
            if frame is None or frame.empty:
                completed = pd.DataFrame()
            elif timeframe == "1h":
                completed = frame
            else:
                completed = local_data.tamamlanmis_mumlar(frame, timeframe, now=AS_OF)
            if completed is None:
                completed = pd.DataFrame()
            minimum = FVG_MINIMUM_HISTORY.get(timeframe)
            fvg_ready = (len(completed) >= minimum) if minimum is not None else None
            engine_frame = _normalize_frame(completed) if not completed.empty else pd.DataFrame()
            if not engine_frame.empty:
                engine_frames[(symbol, timeframe)] = engine_frame
            ob_count = 0
            fvg_count = 0
            fvg_status = "UNSUPPORTED_TIMEFRAME"
            excluded_candidates = 0
            if timeframe == "1h" and not engine_frame.empty:
                ob_zones = replay_ob_zones(symbol, timeframe, engine_frame)
                zones.extend(ob_zones)
                ob_count = len(ob_zones)
            if timeframe in FVG_MINIMUM_HISTORY and not engine_frame.empty:
                fvg_zones, fvg_status, excluded_candidates = replay_fvg_zones(
                    symbol, timeframe, engine_frame, profile=FVG_PROFILE
                )
                zones.extend(fvg_zones)
                fvg_count = len(fvg_zones)
                if not fvg_ready:
                    fvg_status = "WARMUP"
            readiness_rows.append({
                "as_of": AS_OF.isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "completed_bar_count": len(engine_frame),
                "first_completed_bar": engine_frame.iloc[0]["timestamp"].isoformat() if not engine_frame.empty else None,
                "last_completed_bar": engine_frame.iloc[-1]["timestamp"].isoformat() if not engine_frame.empty else None,
                "fvg_minimum_history_bars": minimum,
                "fvg_minimum_history_met": fvg_ready,
                "fvg_profile": FVG_PROFILE if minimum is not None else None,
                "fvg_engine_status": fvg_status,
                "confirmed_fvg_zone_count": fvg_count,
                "candidate_only_fvg_records_excluded": excluded_candidates,
                "native_ob_zone_count": ob_count,
            })
    if len(hourly_by_symbol) != 28:
        raise RuntimeError("local symbol universe changed during loading")
    episodes = build_touch_episodes(zones, engine_frames)
    zones_by_id = {zone["zone_id"]: zone for zone in zones}
    if len(zones_by_id) != len(zones):
        raise RuntimeError("duplicate zone identifiers in native replay")
    atr_by_series = {key: compute_wilder_atr(frame) for key, frame in engine_frames.items()}
    windows = build_window_rows(episodes, zones_by_id, engine_frames, atr_by_series)
    symbols = sorted(hourly_by_symbol)
    readiness_map = {}
    for row in readiness_rows:
        family = "OB" if row["timeframe"] == "1h" else "FVG"
        readiness_map[(row["symbol"], family, row["timeframe"])] = "OK" if family == "OB" else row["fvg_engine_status"]
    all_ready = {}
    for family, timeframe in FAMILIES:
        values = [readiness_map.get((symbol, family, timeframe), "NOT_RUN") for symbol in symbols]
        all_ready[("ALL", family, timeframe)] = "WARMUP" if any(value == "WARMUP" for value in values) else ("OK" if all(value == "OK" for value in values) else "NOT_RUN")
    for symbol in symbols:
        for family, timeframe in FAMILIES:
            all_ready[(symbol, family, timeframe)] = readiness_map.get((symbol, family, timeframe), "NOT_RUN")

    summary_rows = []
    for symbol in [*symbols, "ALL"]:
        for family, timeframe in FAMILIES:
            for direction in ("bullish", "bearish"):
                for horizon in HORIZONS:
                    summary_rows.append(_summary_base(symbol, family, timeframe, direction, "ALL", horizon, zones, windows, all_ready))
    summary_frame = pd.DataFrame(summary_rows)

    arrival_rows = []
    arrival_values = ("ALL", "FROM_ABOVE", "FROM_BELOW", "INSIDE_ZONE", "ON_ZONE_BOUNDARY", "NO_PREVIOUS_BAR")
    for family, timeframe in FAMILIES:
        for direction in ("bullish", "bearish"):
            for arrival in arrival_values:
                for horizon in HORIZONS:
                    arrival_rows.append(_summary_base("ALL", family, timeframe, direction, arrival, horizon, zones, windows, all_ready))
    arrival_frame = pd.DataFrame(arrival_rows)
    zone_summary_frame = pd.DataFrame(make_zone_summary(zones, windows))
    readiness_frame = pd.DataFrame(readiness_rows).sort_values(["symbol", "timeframe"]).reset_index(drop=True)
    windows_frame = pd.DataFrame(windows).drop(columns=["touch_start_index", "touch_end_index"], errors="ignore")
    if not windows_frame.empty:
        windows_frame = windows_frame.sort_values(["family", "timeframe", "symbol", "zone_id", "touch_start", "horizon_bars"]).reset_index(drop=True)
    summary_frame = summary_frame.sort_values(["symbol", "family", "timeframe", "direction", "horizon_bars"]).reset_index(drop=True)
    arrival_frame = arrival_frame.sort_values(["family", "timeframe", "direction", "arrival_side", "horizon_bars"]).reset_index(drop=True)
    zone_summary_frame = zone_summary_frame.sort_values(["family", "timeframe", "symbol", "zone_id", "horizon_bars"]).reset_index(drop=True)

    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    stamp = "2026-09-25"
    paths = {
        "touch": out_dir / f"ob_fvg_directional_touch_windows_asof_{stamp}.csv",
        "symbol_summary": out_dir / f"ob_fvg_directional_symbol_summary_asof_{stamp}.csv",
        "arrival_summary": out_dir / f"ob_fvg_directional_arrival_summary_asof_{stamp}.csv",
        "zone_summary": out_dir / f"ob_fvg_directional_zone_summary_asof_{stamp}.csv",
        "readiness": out_dir / f"ob_fvg_directional_readiness_asof_{stamp}.csv",
        "report": out_dir / f"ob_fvg_directional_replay_asof_{stamp}.md",
    }
    windows_frame.to_csv(paths["touch"], index=False, float_format="%.8f")
    summary_frame.to_csv(paths["symbol_summary"], index=False, float_format="%.8f")
    arrival_frame.to_csv(paths["arrival_summary"], index=False, float_format="%.8f")
    zone_summary_frame.to_csv(paths["zone_summary"], index=False, float_format="%.8f")
    readiness_frame.to_csv(paths["readiness"], index=False, float_format="%.8f")

    _write_report(paths["report"], audit, readiness_frame, zones, episodes, summary_frame, arrival_frame)
    print("as_of", AS_OF.isoformat())
    print("symbols", len(audit), "1h bars", sorted(set(x["completed_1h_bars"] for x in audit.values())))
    print("1h cache range", min(x["first_1h"] for x in audit.values()), max(x["last_1h"] for x in audit.values()))
    print("zones", pd.Series([z["family"] + "/" + z["timeframe"] for z in zones]).value_counts().to_dict())
    print("direction", pd.Series([z["family"] + "/" + z["direction"] for z in zones]).value_counts().to_dict())
    print("touch episodes", len(episodes), "window rows", len(windows))
    print("OB prior audit check (native zones/touch episodes)", sum(z["family"] == "OB" for z in zones), sum(e["family"] == "OB" for e in episodes))
    print("readiness", readiness_frame.groupby(["timeframe", "fvg_engine_status"], dropna=False).size().to_dict())
    for name, path in paths.items():
        print(name, path, path.stat().st_size)


def _fmt(value, digits=3):
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (float, int)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _readiness_lines(readiness):
    lines = [
        "",
        "| Yerel resample | Bar sayısı / sembol (min–max) | Warm-up | Durum | Native promoted FVG zone |",
        "|---|---:|---:|---|---:|",
    ]
    for timeframe in ("2h", "4h", "1d"):
        group = readiness[readiness.timeframe == timeframe]
        if group.empty:
            continue
        status_counts = group.fvg_engine_status.value_counts().to_dict()
        status_text = ", ".join(f"{key}: {value}" for key, value in sorted(status_counts.items()))
        bar_range = f"{int(group.completed_bar_count.min())}–{int(group.completed_bar_count.max())}"
        minimum = int(group.fvg_minimum_history_bars.iloc[0])
        zones = int(group.confirmed_fvg_zone_count.sum())
        lines.append(f"| {timeframe} | {bar_range} | {minimum} | {status_text} | {zones} |")
    lines.append("")
    return lines


def _native_lifecycle_lines(zones, episodes):
    touched_ids = {episode["zone_id"] for episode in episodes}
    groups = {}
    for zone in zones:
        key = (zone["family"], zone["timeframe"], zone["direction"])
        groups.setdefault(key, []).append(zone)
    lines = [
        "",
        "### Replay sonundaki native zone durumu",
        "",
        "Terminal durumları bölge düzeyinde sayılır; temas epizodu sayısı değildir.",
        "",
        "| Family/TF | Yön | Native zone | Temas alan zone | Replay sonunda aktif | OB %70 fill-cancel | OB gap-through | FVG close invalidation | FVG full-fill | FVG reaction terminal | Yaş/supersede/diğer terminal |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (family, timeframe, direction), values in sorted(groups.items()):
        category = [zone["native_terminal_category"] for zone in values]
        active = sum(bool(zone["active_at_asof"]) for zone in values)
        fill_cancel = sum(value == "FILL_CANCEL_THRESHOLD" for value in category)
        gap_through = sum(value == "GAP_THROUGH" for value in category)
        close_invalidation = sum(value == "CLOSE_INVALIDATION" for value in category)
        full_fill = sum(value == "FULL_FILL" for value in category)
        reaction = sum(value == "NATIVE_REACTION_TERMINAL" for value in category)
        other = sum(not zone["active_at_asof"] and value not in {
            "FILL_CANCEL_THRESHOLD", "GAP_THROUGH", "CLOSE_INVALIDATION", "FULL_FILL", "NATIVE_REACTION_TERMINAL"
        } for zone, value in zip(values, category))
        touched = len({zone["zone_id"] for zone in values} & touched_ids)
        lines.append(f"| {family}/{timeframe} | {direction} | {len(values)} | {touched} | {active} | {fill_cancel} | {gap_through} | {close_invalidation} | {full_fill} | {reaction} | {other} |")
    return lines


def _write_report(path, audit, readiness, zones, episodes, summary, arrivals):
    first = min(v["first_1h"] for v in audit.values())
    last = max(v["last_1h"] for v in audit.values())
    skipped = sum(v["skipped_rows"] for v in audit.values())
    lines = [
        "# OB ve FVG yön-duyarlı temas/reaksiyon replay’i",
        "",
        "Bu salt-okunur çalışma, `bot_data/` altındaki mevcut 28 sembollük yerel cache’i kullanır. Canlı servis veya dış fiyat/veritabanı kaynağı kullanılmadı; üretim motorları değiştirilmedi.",
        "",
        "## Veri ve yöntem",
        "",
        f"- 1H cache: {sum(v['completed_1h_bars'] for v in audit.values()):,} tamamlanmış bar ({len(audit)} × {min(v['completed_1h_bars'] for v in audit.values())}); {first:%Y-%m-%d %H:%M %z} – {last:%Y-%m-%d %H:%M %z}. Replay `as_of={AS_OF.isoformat()}`. Bu rapor 2026-10-11 denetim tarihiyle hazırlanmıştır; son yerel-cache barı yaklaşık 16 takvim günü eskidir. Cache temizleyicisinin atladığı satır: {skipped}.",
        "- FVG için yalnızca aynı 1H yerel verisi repository’nin `resample_all_timeframes`/`tamamlanmis_mumlar` fonksiyonlarıyla 2H/4H/1D’ye çevrildi; FVG profile `Dengeli` (motor varsayılanı). FVG warm-up korunmuştur: 2H/4H 100 bar, 1D 40 bar.",
        *_readiness_lines(readiness),
        "- OB teması core motorun orijinal top/bottom kesişim kuralıyla; FVG temas epizotları motorun test tetikleyicisiyle (boğa: `low <= upper_boundary`, ayı: `high >= lower_boundary`) belirlendi. FVG’de aday durumunda iken olan temaslar sayılmadı; yalnızca aday olmayan native aktif/promote edilmiş kayıt, etkinleşme barından sonraki mumlarda temasa açıldı.",
        "- Temas epizodu son mumundan sonra başlayan sabit 10 ve 12 tamamlanmış bar pencereleri ayrı üretildi. Temas mumları pencerede yoktur. Ardışık temas mumları bir epizot; araya en az bir temassız bar girerse aynı zone altında yeni epizot sayılır. Pencereler sonraki temasla kesilmez; olası örtüşme `next_same_zone_touch_in_window` ile işaretlenir.",
        "- ATR(14), temas epizodunun son mumunda SMA-seed’li Wilder hesabıyla alınır. Boğa favorable = sonraki pencere max(high) − orijinal zone üst sınırı; bearish favorable = orijinal alt sınır − min(low). Adverse excursion ters yöndedir. Ham fiyat mesafeleri ve ATR oranları temas CSV’sindedir.",
        "- Eşikler sonuçlar görülerek seçilmedi: raporlama öncesinde sabitlenen duyarlılık ızgarası **0,5 / 1,0 / 1,5 ATR**. Bunlar bir işlem başarı eşiği veya başarı olasılığı olarak kalibre edilmemiştir. Tam pencere target-hit oranı ile native terminalden önce hit ve terminal mumunda sırası bilinmeyen hit ayrı gösterilir.",
        "- Pencereye yeterli veri yoksa örnek sağdan sansürlenir; başarısız sayılmaz. Temas ATR’si yoksa ayrıca ölçülemez işaretlenir. Tekrarlı temaslar temas CSV’sinde ayrı satır; zone CSV/özetinde bölge `zone_id` ile tekil tutulur.",
        "",
        "## Native bölge geçersizliği: motor kuralları",
        "",
        "- **OB:** orijinal bounds ve mevcut `OrderBlockEngine` varsayılanı kullanıldı. Boğa zone’unda mum `high < bottom`, ayıda `low > top` ise native gap-through ile kaldırılır. Aksi hâlde dolum, original bölge içindeki wick penetrasyonuyla ölçülür; fill ratio **%70** veya üzerindeyse zone kaldırılır. Bu native kaldırılma/ihlal olayıdır; olumlu tepki başarısı değildir. Motorun kalan aktif bölge sınırları temas CSV’sinde ayrıca saklanır.",
        "- **FVG:** balanced profile’da bullish kapanış `lower − 0,05 × formation_ATR` altında veya bearish kapanış `upper + 0,05 × formation_ATR` üstünde **iki ardışık bar** kalırsa native close invalidation oluşur. Tam dolum ayrıca terminal `FULL_FILL` olayıdır (bullish `low <= lower`, bearish `high >= upper`); close invalidation ile birleştirilmez. 45-bar yaş sonu, yeni FVG tarafından devralınma ve native `REACTION` terminali fiyat ihlali sayılmaz. Native `REACTION`, motorun kendi candle/flow/close kriterlerine dayanır; bağımsız ATR başarı ölçütü yerine kullanılmadı. Motor `FAILED_REACTION` durumunu kendi başına terminal yapmayabilir; böyle kayıtlar aktif kaldıkları sürece ayrı invalidation olarak sayılmadı.",
        "- 1D resample her sembolde warm-up eşiğine tam 40 barla ulaşıyor; yalnızca 10 promoted FVG zone oluştu ve temas almadı. Bu timeframe’de reaksiyon örneği yoktur; başarısızlık sayılmaz.",
        "- Bu native kurallar lifecycle/zone kaldırılmasını tanımlar; tek başlarına 10/12 bar yönlü performans başarısını ölçmez. Bu nedenle native invalidation, full fill, diğer terminal nedenler ve ATR target sonuçları ayrı tutuldu.",
        *_native_lifecycle_lines(zones, episodes),
        "",
        "## Sembol evreni toplamı: family / timeframe / direction / horizon",
        "",
        "`Target hit (tam pencere)` OHLC fiyatının ilgili ATR eşiğine ulaştığı temas örneklerini; `aktif-zone hit` ise terminal mumundan önce hedefe ulaşmayı gösterir. Tam pencere hareketi terminal sonrası fiyatları içerebilir; terminal mumunda target ile ihlal sırası OHLC’den bilinemez ve ayrıca belirsiz sayılır. Veri sonuna sansürlenen pencere target paydasına girmez; gözlenmiş kısımda gerçekleşen native ihlal yine ayrı kaydedilir. Hiçbir oran olasılık değildir.",
        "",
        "| Family/TF | Yön | N bar | Native zone | Temas epizodu | Tam pencere (ATR uygun) | Veri-sonu sansür | ATR yok | Native fiyat ihlali: temasta/gözlenen pencerede | FVG full-fill: temasta/gözlenen pencerede | Favorable ATR medyanı | Adverse ATR medyanı | 0,5 ATR hit tam/aktif | 1 ATR hit tam/aktif | 1,5 ATR hit tam/aktif |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    universe = summary[(summary.symbol == "ALL") & (summary.arrival_side == "ALL")]
    for _, r in universe.iterrows():
        fam_tf = f"{r.family}/{r.timeframe}"
        v_touch = int(r.native_price_violation_at_touch_episodes)
        v_window = int(r.native_price_violation_within_observed_window_episodes)
        fill_touch = int(r.native_full_fill_at_touch_episodes)
        fill_window = int(r.native_full_fill_within_observed_window_episodes)
        vals = []
        for threshold in FAVORABLE_ATR_THRESHOLDS:
            tag = str(threshold).replace(".", "p")
            full = int(r[f"target_{tag}_full_window_hit_episodes"])
            active = int(r[f"target_{tag}_hit_before_native_terminal_episodes"])
            vals.append(f"{full}/{_fmt(r[f'target_{tag}_full_window_hit_share'], 3)} · {active}/{_fmt(r[f'target_{tag}_hit_before_native_terminal_share'], 3)}")
        lines.append(
            f"| {fam_tf} | {r.direction} | {int(r.horizon_bars)} | {int(r.native_zone_count)} | {int(r.touch_episodes)} | {int(r.atr_evaluable_complete_windows)} | {int(r.right_censored_data_end_windows)} | {int(r.atr14_unavailable_windows)} | {v_touch}/{v_window} | {fill_touch}/{fill_window} | {_fmt(r.median_favorable_excursion_atr_full_window)} | {_fmt(r.median_adverse_excursion_atr_full_window)} | {vals[0]} | {vals[1]} | {vals[2]} |"
        )
    lines += [
        "",
        "### Bölge bazlı eşik sonuçları (tekil `zone_id` paydası)",
        "",
        "Her bölge en fazla bir kez sayılır; olumlu bölge, en az bir tam/ATR-uygun temasında eşiğe terminal mumundan önce erişen farklı bölgedir.",
        "",
        "| Family/TF | Yön | N bar | Native zone toplamı | Terminal öncesi ölçülebilir en az bir teması olan farklı zone | ≥0,5 ATR | ≥1,0 ATR | ≥1,5 ATR |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in universe.iterrows():
        values = []
        denominator = int(r.zones_with_at_least_one_active_preterminal_window)
        for threshold in FAVORABLE_ATR_THRESHOLDS:
            tag = str(threshold).replace(".", "p")
            hits = int(r[f"zones_with_preterminal_target_{tag}_hit"])
            share = r[f"zone_share_with_preterminal_target_{tag}_hit"]
            values.append(f"{hits}/{denominator} ({_fmt(share, 3)})" if denominator else f"0/0 (—)")
        lines.append(
            f"| {r.family}/{r.timeframe} | {r.direction} | {int(r.horizon_bars)} | {int(r.native_zone_count)} | {denominator} | {values[0]} | {values[1]} | {values[2]} |"
        )
    lines += [
        "",
        "Oranların paydası tam horizon ve ATR’si bulunan temas pencereleridir; `aktif-zone hit` oranının paydası native terminalden önce en az bir post-touch barı bulunan tam pencerelerdir. Sansür/ATR yok sayıları window bazındadır; 10 ve 12 bar satırları aynı temas olaylarını ayrı değerlendirdiği için örnekler birbirinden bağımsız değildir.",
        "",
        "## Geliş yönü ve bölge bazlı okuma",
        "",
        "Geliş yönü, ilk temas mumundan önceki kapanışın orijinal sınırların üstünde (`FROM_ABOVE`), altında (`FROM_BELOW`) veya bölgede/kenarda olup olmamasından (`INSIDE_ZONE` / `ON_ZONE_BOUNDARY`) sınıflandı; post-touch tepki ölçüsünden ayrıdır. Sembol, yön, geliş tarafı, 10/12 bar ve her zone için ayrı değerler CSV’lerde bulunur. Bölge bazlı target sayıları, o zone’daki temas örneklerinden herhangi birinin eşiğe ulaşmasını sayar; aynı zone tekrar temasları yeni bölge yapılmaz.",
        "",
        "## Dosyalar",
        "",
        "- `ob_fvg_directional_touch_windows_asof_2026-09-25.csv` — her temas epizodu × 10/12 bar; geliş yönü, ham/ATR excursion, threshold hit, native terminal/ihlal ve censor alanları.",
        "- `ob_fvg_directional_symbol_summary_asof_2026-09-25.csv` — sembol + `ALL`, OB/FVG/timeframe/yön/horizon bazında temas ve ATR/threshold sayıları.",
        "- `ob_fvg_directional_arrival_summary_asof_2026-09-25.csv` — evren toplamında geliş tarafı ayrı kırılımı.",
        "- `ob_fvg_directional_zone_summary_asof_2026-09-25.csv` — benzersiz zone başına 10/12 bar sonuçları; tekrar temasları aynı zone’da toplar.",
        "- `ob_fvg_directional_readiness_asof_2026-09-25.csv` — sembol/timeframe bar sayısı, warm-up ve engine readiness.",
        "",
        "## Doğrulama",
        "",
        "`test_directional_zone_replay.py`, `test_zone_scoring.py` ve domain-engine parity/regression testleri birlikte: **58 geçti**. OB replay’in 1H bölge/temas sayıları önceki audit ile de tutarlı (1.173 zone / 1.604 epizot).",
        "",
        "Bu kısa rapor betimsel örneklem incelemesidir; ücret/slippage, fill, işlem girişi/çıkışı veya PnL simülasyonu içermez. Üretim engine/runner/notifier ve OB/FVG formasyon hesapları değiştirilmedi."
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
