"""Offline filter ablation: unique events, zero days and pre-window cooldown.

No live imports, delivery, optimization or directional-success claims. The
legacy replay may emit two outcome directions for one event. Count it once;
use only direction-invariant 12-bar excursions as descriptive diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from research.alarm_politika import POLITIKALAR, _cooldown, seans_kapsami

KEY = ["symbol", "timeframe", "bar_index"]
INVARIANTS = ["bar_time", "kanallar", "bagl_sikisma", "bagl_gunici_kosu",
              "hacim_tier", "formasyon_state", "kontrol"]


def _boolean(value):
    if value is None or pd.isna(value):
        return None
    if value in (True, 1, "true", "True", "1"):
        return True
    if value in (False, 0, "false", "False", "0"):
        return False
    raise ValueError(f"Invalid outcome boolean: {value!r}")


def unique_events(rows):
    """Reject inconsistent pairs, and never let an outcome pick the event side."""
    if rows.empty:
        raise ValueError("No replay rows")
    output = []
    for _, group in rows.groupby(KEY, sort=False):
        for col in INVARIANTS:
            if group[col].map(lambda v: json.dumps(v, sort_keys=True)).nunique() != 1:
                raise ValueError(f"Inconsistent event {col}")
        if len(group) > 2 or group["yon"].duplicated().any():
            raise ValueError("Duplicate outcome direction/event")
        row = group.iloc[0].to_dict()
        event_any, event_both = [], []
        for _, side in group.iterrows():
            favorable = _boolean(side["yon_asim_100"])
            adverse = _boolean(side["ters_h12"])
            event_any.append(None if favorable is None or adverse is None else favorable or adverse)
            event_both.append(None if favorable is None or adverse is None else favorable and adverse)
        if len(set(event_any)) != 1 or len(set(event_both)) != 1:
            raise ValueError("Inconsistent paired excursions")
        row.update(any_1atr_12=event_any[0], both_1atr_12=event_both[0],
                   outcome_sides=len(group))
        output.append(row)
    result = pd.DataFrame(output)
    result["seans"] = pd.to_datetime(result.bar_time, utc=True).dt.tz_convert("Europe/Istanbul").dt.strftime("%Y-%m-%d")
    return result


def _no_repeat(row):
    # Proxy only: the live service also has quality and notification-state data
    # that this legacy replay does not record.
    channels = set(row["kanallar"])
    if row["formasyon_state"] in {"KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"}:
        channels.discard("FORMASYON")
    return bool(channels)


def _symmetric(row):
    run = row.get("bagl_gunici_kosu")
    ratio = row.get("bagl_sikisma")
    return ((run is not None and pd.notna(run) and abs(float(run)) >= 1)
            or ratio is None or pd.isna(ratio) or float(ratio) >= 1)


def measure(events, sessions, *, cooldown=6, rule=lambda row: True):
    """Select before cooldown; keep all history, then restrict the denominator."""
    if not sessions:
        raise ValueError("Empty session denominator")
    raw = events.loc[~events.kontrol]
    selected = raw.loc[raw.apply(rule, axis=1).astype(bool)] if len(raw) else raw
    kept = _cooldown(selected, bar=cooldown)
    raw_window = raw.loc[raw.seans.isin(sessions)]
    selected_window = selected.loc[selected.seans.isin(sessions)]
    cards = kept.loc[kept.seans.isin(sessions)]
    daily = cards.groupby("seans").size().reindex(sessions, fill_value=0)
    known = cards.any_1atr_12.dropna().astype(bool)
    both = cards.both_1atr_12.dropna().astype(bool)
    return {
        "raw_events": len(raw_window), "policy_pass": len(selected_window),
        "policy_rejected": len(raw_window) - len(selected_window),
        "cooldown_rejected": len(selected_window) - len(cards), "events": len(cards),
        "sessions": len(sessions), "daily_mean": float(daily.mean()),
        "daily_median": float(daily.median()), "daily_p90": float(daily.quantile(.9)),
        "daily_max": int(daily.max()), "zero_days": int((daily == 0).sum()),
        "measured_12": len(known), "unmeasured_12": len(cards) - len(known),
        "any_1atr_12_rate": float(known.mean()) if len(known) else None,
        "both_1atr_12_rate": float(both.mean()) if len(both) else None,
        "by_tf": {str(k): int(v) for k, v in cards.groupby("timeframe").size().items()},
    }, daily


def audit(events, sessions):
    policies = [(code, rule, 6) for code, _, rule in POLITIKALAR]
    p6 = dict((code, rule) for code, _, rule in POLITIKALAR)["P6"]
    policies += [("P0_no_cooldown", lambda row: True, 0),
                 ("P6_no_cooldown", p6, 0), ("P6_cd3", p6, 3),
                 ("P6_cd12", p6, 12),
                 ("P6_no_immediate_repeat_proxy", lambda row: p6(row) and _no_repeat(row), 6),
                 ("HYP_symmetric_run_NOT_LIVE", _symmetric, 6)]
    summary, daily = {}, pd.DataFrame(index=sessions)
    for name, rule, cooldown in policies:
        summary[name], daily[name] = measure(events, sessions, rule=rule, cooldown=cooldown)
    base = summary["P0"]["events"]
    for result in summary.values():
        result["change_vs_P0_pct"] = 100 * (result["events"] / base - 1) if base else None
    # A chronological sensitivity view, not a blind holdout (old policy selection
    # already used this period). Warm-up and cooldown still use all history.
    mid = len(sessions) // 2
    split = {}
    for label, subset in [("first_half", sessions[:mid]), ("second_half", sessions[mid:])]:
        if subset:
            split[label] = {name: measure(events, subset, rule=rule, cooldown=cd)[0]
                            for name, rule, cd in policies if name in {"P0", "P6", "P4", "HYP_symmetric_run_NOT_LIVE"}}
    raw = events.loc[(~events.kontrol) & events.seans.isin(sessions)]
    ratio = pd.to_numeric(raw.bagl_sikisma, errors="coerce")
    run = pd.to_numeric(raw.bagl_gunici_kosu, errors="coerce")
    diagnostics = {"events": len(raw), "paired_events": int((raw.outcome_sides == 2).sum()),
                   "ratio_missing": int(ratio.isna().sum()), "ratio_eq_1": int((ratio == 1).sum()),
                   "ratio_gt_1": int((ratio > 1).sum()), "run_ge_1": int((run >= 1).sum()),
                   "run_le_minus1": int((run <= -1).sum())}
    return {"policies": summary, "chronological_sensitivity": split, "context": diagnostics}, daily


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first", default="2026-10-19")
    parser.add_argument("--last", default="2026-11-18")
    args = parser.parse_args(argv)
    rows = pd.read_json(args.input / "tetikler.jsonl", lines=True, convert_dates=False)
    meta = pd.read_json(args.input / "meta.jsonl", lines=True, convert_dates=False)
    errors = args.input / "hatalar.jsonl"
    if errors.exists() and errors.stat().st_size:
        raise ValueError("Replay has errors; do not publish partial-universe averages")
    import config
    from config import ACTIVE_STOCKS
    from research.arsiv import arsiv_sembolleri
    symbols = set(ACTIVE_STOCKS) & set(arsiv_sembolleri(native_only=True))
    sessions = seans_kapsami(meta, symbols, args.first, args.last)
    rows = rows.loc[rows.symbol.isin(symbols)]
    events = unique_events(rows)
    result, daily = audit(events, sessions)
    root = Path(__file__).resolve().parents[1]
    tracked = ["research/alarm_filter_audit.py", "research/domain_alarm_replay.py",
               "research/alarm_politika.py", "research/kayit.py", "config.py",
               "bot/domain_alarm_service.py", "backfill_data/manifest.json"]
    result["manifest"] = {
        "schema": "alarm-filter-audit-v1", "unit": "unique_symbol_tf_bar_potential_event_not_delivery",
        "measurement_status": "legacy_reconstruction_NOT_causal_live_parity_validated",
        "local_config_not_production_proof": {name: getattr(config, name) for name in (
            "YENI_DOMAIN_ALARM", "YENI_DOMAIN_ALARM_POLITIKA", "YENI_DOMAIN_ALARM_COOLDOWN_BAR",
            "STABIL_GERI_ALIM_ALARM", "STABIL_ALARM_COOLDOWN_BAR", "ALERT_MIN_QUALITY",
            "DM_MIN_DEVLAMLILIK", "PUBLIC_MIN_DEVLAMLILIK", "MTF_ALERT_MERGE_HOURS",
            "INVALIDATION_CONFIRM_BARS_TF", "TELEGRAM_KART_SUZGEC")},
        "first": sessions[0], "last": sessions[-1], "session_dates": sessions,
        "symbols": sorted(symbols), "missing_active_symbols": sorted(set(ACTIVE_STOCKS) - symbols),
        "series": len(meta), "source_rows": len(rows), "unique_events_with_controls": len(events),
        "input_hashes": {p.name: file_hash(p) for p in [args.input / "tetikler.jsonl", args.input / "meta.jsonl"]},
        "code_hashes": {p: file_hash(root / p) for p in tracked},
        "archive_hashes": {f"{s}_{tf}.csv.gz": file_hash(root / "backfill_data" / f"{s}_{tf}.csv.gz")
                           for s in sorted(symbols) for tf in ("1h", "2h", "4h", "1d")},
        "limitations": ["native480 proxy, not full-history live dispatch",
                        "no live Stabil support/quality/freshness/public quota/MTF gate reconstruction",
                        "legacy replay direction inference is not reliable; no directional success reported",
                        "any/both excursions are not first-touch outcomes or trading returns",
                        "chronological split is sensitivity, not unseen holdout",
                        "count requires ATR and at least one future bar in legacy replay"],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    daily.to_csv(args.output / "daily.csv", index_label="session")
    print(pd.DataFrame(result["policies"]).T[["events", "daily_mean", "daily_median", "policy_rejected", "cooldown_rejected"]].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
