"""Offline günlük çapraz piyasa araştırması; canlı karara bağlanmaz.

Bilinmeyen sağlayıcı kapanışı varsayılan olarak UNKNOWN'dur. Opsiyonel tarih
gecikmesi SADECE keşif varsayımıdır, doğrulanmış erişim zamanı değildir.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from patterns.indicators import calculate_atr
from research.arsiv import arsiv_sembolleri, arsiv_koku
from config import BIST_OPEN, sembol_turu

MACRO = ("XU100", "XU30", "XU50", "XBANK", "XUSIN", "XUTUM", "BRENT",
         "USDTRY", "XAUUSD", "XAGUSD", "XAU_FUT", "XAG_FUT")
GRAM = ("XAU_GRAM_TRY", "XAG_GRAM_TRY")
THRESHOLDS = (0.5, 1.0, 1.5)
HORIZONS = (1, 5, 10)
UNKNOWN = "UNKNOWN"


def read_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, compression="gzip")
    if df.empty:
        raise ValueError(f"{path.name}: boş seri")
    required = {"bar_time", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError(f"{path.name}: eksik OHLC alanları")
    idx = pd.to_datetime(df.pop("bar_time"), utc=True, errors="coerce").dt.tz_convert("Europe/Istanbul")
    if idx.isna().any() or idx.duplicated().any() or not idx.is_monotonic_increasing:
        raise ValueError(f"{path.name}: boş/yinelenen/sırasız tarih")
    df.index = pd.DatetimeIndex(idx, name="timestamp")
    for key in ("open", "high", "low", "close", "volume"):
        df[key] = pd.to_numeric(df[key], errors="coerce")
    return df


def quality(frame):
    o, h, l, c = (frame[x] for x in ("open", "high", "low", "close"))
    bad = (~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(l) | ~np.isfinite(c) |
           (o <= 0) | (h <= 0) | (l <= 0) | (c <= 0) |
           (h < o) | (h < c) | (h < l) | (l > o) | (l > c))
    bad |= (c / c.shift(1) - 1).abs() > .30
    # Wilder ATR sonsuz bellek taşır; kirli mumdan sonra yalnızca 14 bar
    # maskelemek yeterli değil. Temiz segment başında ATR tamamen yeniden tohumlanır.
    atr = pd.Series(np.nan, index=frame.index, dtype=float)
    segments = bad.cumsum()
    for _, segment in frame.loc[~bad].groupby(segments.loc[~bad]):
        if len(segment) >= 14:
            atr.loc[segment.index] = calculate_atr(segment, 14)
    return bad, ~np.isfinite(atr) | (atr <= 0), atr


def label(delta, atr, threshold):
    if not np.isfinite(delta) or not np.isfinite(atr) or atr <= 0:
        return UNKNOWN
    return "UP" if delta > threshold * atr else "DOWN" if delta < -threshold * atr else "FLAT"


def macro_load(root: Path):
    manifest = json.loads((root / "manifest.json").read_text())
    data, report = {}, {}
    for s in MACRO:
        record = manifest.get("series", {}).get(s, {})
        path = root / f"{s}_1d.csv.gz"
        try:
            if record.get("status") != "ok" or not path.is_file():
                raise ValueError("manifest/dosya eksik")
            if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256"):
                raise ValueError("checksum uyuşmuyor")
            df = read_frame(path)
            bad, invalid_atr, atr = quality(df)
            data[s] = (df, bad, invalid_atr, atr)
            report[s] = {"rows": len(df), "invalid_bars": int(bad.sum()),
                         "closed_at_verified": bool(record.get("closed_at_verified")),
                         "provider": record.get("provider", "yahoo"),
                         "provider_symbol": record.get("provider_symbol", record.get("ticker")),
                         "first": str(df.index[0]), "last": str(df.index[-1])}
        except (OSError, ValueError, KeyError) as e:
            report[s] = {"error": str(e)}
    for s in GRAM:
        report[s] = {"error": "Eşzamanlı gram/TL OHLC doğrulanmadı; ons high × kur high kullanılmaz"}
    return data, report


def availability_load(path):
    """Dışarıdan sağlanan erişim anları; doğruluğu sağlayıcıyla ayrıca denetlenir."""
    df = pd.read_csv(path, dtype=str)
    if not {"symbol", "bar_time", "available_at"}.issubset(df.columns):
        raise ValueError("Erişim dosyasında symbol, bar_time, available_at gerekli")
    result = {}
    for symbol, group in df.groupby("symbol"):
        labels, available = [], []
        for row in group.itertuples():
            label_ts, available_ts = pd.Timestamp(row.bar_time), pd.Timestamp(row.available_at)
            if label_ts.tzinfo is None or available_ts.tzinfo is None:
                raise ValueError("Erişim ve bar zamanlarında saat dilimi zorunlu")
            label_ts, available_ts = label_ts.tz_convert("UTC"), available_ts.tz_convert("UTC")
            if available_ts < label_ts:
                raise ValueError("Erişim zamanı bar etiketinden önce olamaz")
            labels.append(label_ts)
            available.append(available_ts)
        if pd.DatetimeIndex(labels).has_duplicates:
            raise ValueError("Erişim dosyasında yinelenen bar etiketi")
        result[str(symbol)] = pd.Series(available, index=pd.DatetimeIndex(labels))
    return result


def macro_context(data, days, multiplier, assume_lag_days=None, max_age_days=7, availability=None):
    """Takvim tarihi varsayımı, provider closure kanıtı DEĞİLDİR."""
    out = pd.DataFrame(index=pd.DatetimeIndex(days))
    for s in MACRO:
        out[s] = UNKNOWN
        if s not in data:
            continue
        frame, bad, invalid_atr, atr = data[s]
        dates = pd.DatetimeIndex(frame.index.date)
        if dates.has_duplicates or not dates.is_monotonic_increasing:
            continue
        supplied = (availability or {}).get(s)
        if supplied is not None:
            times = supplied.reindex(frame.index.tz_convert("UTC"))
            # Eksik/ters sırada bilinen erişim zamanlarını tahmin etme.
            if times.isna().any() or not pd.DatetimeIndex(times).is_monotonic_increasing:
                continue
            known_at = pd.DatetimeIndex(times).tz_convert("UTC")
        elif assume_lag_days is None:
            continue
        else:
            known_at = None
        for day in out.index:
            if known_at is not None:
                decision = day.tz_localize("Europe/Istanbul") + pd.Timedelta(hours=BIST_OPEN.hour, minutes=BIST_OPEN.minute)
                p = int(known_at.searchsorted(decision.tz_convert("UTC"), side="left") - 1)
            else:
                cutoff = day - pd.Timedelta(days=assume_lag_days)
                p = int(dates.searchsorted(cutoff, side="right") - 1)
            if p < 1 or (day - dates[p]).days > max_age_days or bad.iloc[p] or bad.iloc[p-1] or invalid_atr.iloc[p]:
                continue
            out.at[day, s] = label(float(frame.close.iloc[p] - frame.close.iloc[p-1]), float(atr.iloc[p]), multiplier)
    for s in GRAM:
        out[s] = UNKNOWN
    return out


def stock_events(frame, threshold, horizon):
    """t seans başı: önceki kapanış/ATR → t+h-1 kapanışı, tam mum koşuluyla."""
    bad, bad_atr, atr = quality(frame)
    rows = []
    idx = frame.index
    for i in range(1, len(frame)):
        day = pd.Timestamp(idx[i].date())
        end = i + horizon - 1
        before = i - 1
        outcome, end_day, reason = UNKNOWN, None, "CENSORED"
        if end < len(frame):
            end_day = pd.Timestamp(idx[end].date())
            reason = "QUALITY"
            if not bad.iloc[before:end + 1].any() and not bad_atr.iloc[before]:
                outcome = label(float(frame.close.iloc[end] - frame.close.iloc[before]), float(atr.iloc[before]), threshold)
                if outcome != UNKNOWN:
                    reason = "VALID"
        rows.append({"day": day, "end_day": end_day, "outcome": outcome, "reason": reason})
    return pd.DataFrame(rows).set_index("day")


def combinations(names, max_order=None):
    for size in range(1, min(len(names), max_order or len(names)) + 1):
        yield from itertools.combinations(names, size)


def cells(events, context, names, split, max_order=None):
    """Yalnız gözlenen sınıflar yazılır; sıfır gözlemli durumlar meta'dadır."""
    data = events.join(context[list(names)], how="left").fillna({s: UNKNOWN for s in names})
    for part in ("discovery", "validation"):
        if part == "discovery":
            part_data = data[(data.index < split) & (data.end_day < split)]
        else:
            part_data = data[data.index >= split]
        known_outcome = part_data.outcome != UNKNOWN
        base = part_data[known_outcome].outcome.value_counts()
        base_n = int(known_outcome.sum())
        for subset in combinations(names, max_order):
            group = part_data.groupby(list(subset), dropna=False, sort=False)
            for values, g in group:
                if not isinstance(values, tuple): values = (values,)
                counts = g.outcome.value_counts()
                valid = int((g.outcome != UNKNOWN).sum())
                yield {"part": part, "combination": "+".join(subset),
                       "condition": " & ".join(f"{k}={v}" for k, v in zip(subset, values)),
                       "condition_known": UNKNOWN not in values, "rows": len(g), "n": valid,
                       "unknown_or_censored": int(len(g) - valid),
                       "quality_unknown": int((g.reason == "QUALITY").sum()),
                       "censored": int((g.reason == "CENSORED").sum()),
                       "up": int(counts.get("UP", 0)), "flat": int(counts.get("FLAT", 0)),
                       "down": int(counts.get("DOWN", 0)), "up_pct": float(counts.get("UP", 0) / valid) if valid else None,
                       "baseline_n": base_n, "baseline_up_pct": float(base.get("UP", 0) / base_n) if base_n else None,
                       "baseline_flat_pct": float(base.get("FLAT", 0) / base_n) if base_n else None,
                       "baseline_down_pct": float(base.get("DOWN", 0) / base_n) if base_n else None,
                       "first_day": str(g.index.min().date()), "last_day": str(g.index.max().date())}


def stock_symbols(root=None):
    return [s for s in arsiv_sembolleri(root) if sembol_turu(s) == "hisse"]


def run(symbols, output: Path, *, root=None, macro_root=None, names=MACRO + GRAM,
        assume_lag_days=None, max_order=None, availability_path=None):
    """Hücreleri dosyaya akıtarak bellek kullanımını sınırlar."""
    import csv
    root = arsiv_koku(root).resolve()
    macro_root = Path(macro_root or root.parent / "capraz_piyasa_data").resolve()
    target = output.resolve()
    if target in (root.parent, root, macro_root) or root in target.parents or macro_root in target.parents:
        raise ValueError("Çıktı repo kökü veya ham arşiv klasörü olamaz")
    output.mkdir(parents=True, exist_ok=True)
    data, diagnostics = macro_load(macro_root)
    if any(s not in MACRO + GRAM for s in names) or len(set(names)) != len(names):
        raise ValueError("Bilinmeyen veya yinelenen makro sembol")
    if any(not s.isascii() or not s.isalnum() or sembol_turu(s) != "hisse" for s in symbols):
        raise ValueError("Yalnız geçerli hisse sembolleri kullanılabilir")
    if assume_lag_days is not None and assume_lag_days < 2:
        raise ValueError("Keşif varsayımında en az iki takvim günü gecikme gerekir")
    if max_order is not None and not 1 <= max_order <= len(names):
        raise ValueError("Geçersiz birleşim derecesi")
    availability = availability_load(availability_path) if availability_path else None
    mode = ("UNVERIFIED_EXPLORATION" if assume_lag_days is not None else
            "EXTERNAL_AVAILABILITY" if availability else "STRICT_UNKNOWN")
    summary = {"mode": mode, "availability_note": "Dış erişim dosyasının doğruluğu bağımsız denetlenmedi",
               "availability_sha256": hashlib.sha256(Path(availability_path).read_bytes()).hexdigest() if availability_path else None,
               "assumed_lag_days": assume_lag_days, "max_age_days": 7,
               "names": list(names), "all_subset_count": sum(1 for _ in combinations(names, max_order)),
               "zero_observation_cells": "CSV'de yok; gözlenmeyen yön durumları sıfırdır",
               "thresholds": THRESHOLDS, "horizons": HORIZONS, "symbols": {}, "sources": diagnostics,
               "interpretation": "keşif; çoklu test/bağımlılık kontrolü yok, doğrulanmış bulgu değildir"}
    path = output / "cells.csv"
    fields = ["symbol", "macro_atr", "stock_atr", "horizon", "split", "part", "combination", "condition", "condition_known", "rows", "n", "unknown_or_censored", "quality_unknown", "censored", "up", "flat", "down", "up_pct", "baseline_n", "baseline_up_pct", "baseline_flat_pct", "baseline_down_pct", "first_day", "last_day"]
    with path.open("w", newline="", encoding="utf8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for symbol in symbols:
            try:
                frame = read_frame(root / f"{symbol}_1d.csv.gz")
                days = pd.DatetimeIndex([pd.Timestamp(x.date()) for x in frame.index])
                if days.has_duplicates: raise ValueError("günlük yinelenen tarih")
                split = days[int(len(days) * .7)]
                split_counts = {}
                for horizon in HORIZONS:
                    ev = stock_events(frame, THRESHOLDS[0], horizon)
                    train = ev.index < split
                    split_counts[str(horizon)] = {
                        "discovery_boundary_purged": int((train & ev.end_day.notna() & (ev.end_day >= split)).sum()),
                        "discovery_right_censored": int((train & ev.end_day.isna()).sum()),
                        "validation_right_censored": int((~train & ev.end_day.isna()).sum()),
                    }
                summary["symbols"][symbol] = {"rows": len(frame), "split": str(split.date()),
                    "sha256": hashlib.sha256((root / f"{symbol}_1d.csv.gz").read_bytes()).hexdigest(),
                    "horizon_counts": split_counts}
                for mt in THRESHOLDS:
                    context = macro_context(data, days, mt, assume_lag_days, availability=availability)
                    for st in THRESHOLDS:
                        for horizon in HORIZONS:
                            events = stock_events(frame, st, horizon)
                            for cell in cells(events, context, names, split, max_order):
                                writer.writerow({"symbol": symbol, "macro_atr": mt, "stock_atr": st,
                                                 "horizon": horizon, "split": str(split.date()), **cell})
            except (ValueError, OSError, KeyError) as e:
                summary["symbols"][symbol] = {"error": str(e)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
    return summary


def select_discovery(output: Path, min_n=30):
    """Keşifte seç, sabit kuralın doğrulama satırını eşleştir; anlamlılık iddia etme.

    Çoklu test/dönem bağımlılığı düzeltilmedi. Büyük tüm-kombinasyon koşularında
    bu isteğe bağlı adım çok bellek kullanabilir.
    """
    import csv
    path = output / "cells.csv"
    chosen = {}
    tested = {}
    with path.open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            if row["part"] != "discovery" or row["condition_known"] != "True":
                continue
            n, base_n = int(row["n"]), int(row["baseline_n"])
            if n < min_n or base_n < min_n:
                continue
            key = (row["symbol"], row["horizon"], row["combination"])
            tested[key] = tested.get(key, 0) + 1
            diffs = {d: int(row[d]) / n - float(row[f"baseline_{d}_pct"]) for d in ("up", "flat", "down")}
            score = max(abs(v) for v in diffs.values())
            if key not in chosen or score > chosen[key][0]:
                chosen[key] = (score, row, diffs)
    validation = {}
    with path.open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            if row["part"] != "validation": continue
            key = (row["symbol"], row["horizon"], row["combination"])
            item = chosen.get(key)
            if item is not None and all(row[k] == item[1][k] for k in ("condition", "macro_atr", "stock_atr")):
                validation[key] = row
    fields = ["symbol", "horizon", "combination", "condition", "macro_atr", "stock_atr",
              "tested_cells", "discovery_n", "discovery_score", "discovery_up_diff", "discovery_down_diff",
              "validation_n", "validation_up_diff", "validation_down_diff", "status"]
    with (output / "selected.csv").open("w", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for key, (score, row, diffs) in chosen.items():
            v = validation.get(key)
            n = int(v["n"]) if v else 0
            base = int(v["baseline_n"]) if v else 0
            usable = bool(v and n >= min_n and base >= min_n)
            writer.writerow({"symbol": row["symbol"], "horizon": row["horizon"],
                "combination": row["combination"], "condition": row["condition"],
                "macro_atr": row["macro_atr"], "stock_atr": row["stock_atr"],
                "tested_cells": tested[key], "discovery_n": row["n"], "discovery_score": score,
                "discovery_up_diff": diffs["up"], "discovery_down_diff": diffs["down"],
                "validation_n": n,
                "validation_up_diff": int(v["up"]) / n - float(v["baseline_up_pct"]) if usable else "",
                "validation_down_diff": int(v["down"]) / n - float(v["baseline_down_pct"]) if usable else "",
                "status": "UNADJUSTED_EXPLORATORY" if usable else "INSUFFICIENT_VALIDATION"})
    return len(chosen)
