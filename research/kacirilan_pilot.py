"""Fiyat merkezli küçük offline pilot; canlı sinyal/teslim sonucu değildir."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from directional_zone_replay import replay_ob_zones
from patterns.lifecycle import ArgentEngine
from research.capraz_piyasa import quality, read_frame

HORIZON = 10
THRESHOLD = 2.0
WARMUP = 80
STRIDE = 10


def price_outcomes(frame, anchor, atr, horizon=HORIZON, threshold=THRESHOLD):
    """Kapanış bazlı son ve yol içi uç; karar anındaki ATR sabit."""
    base = float(frame.close.iloc[anchor])
    future = frame.close.iloc[anchor + 1:anchor + horizon + 1].to_numpy(dtype=float)
    if len(future) < horizon or not np.isfinite(future).all():
        return None
    normalized = (future - base) / atr
    return {"end_up": bool(normalized[-1] >= threshold),
            "end_down": bool(normalized[-1] <= -threshold),
            "path_up": bool(np.max(normalized) >= threshold),
            "path_down": bool(np.min(normalized) <= -threshold)}


def zone_context(zones, t, price, atr, direction):
    """As-of aktif, özgün sınırına en çok 1 ATR mesafede yönlü OB var mı?"""
    expected = "bullish" if direction == "up" else "bearish"
    for zone in zones:
        terminal = zone["native_terminal_index"]
        if zone["available_index"] > t or (terminal is not None and terminal <= t):
            continue
        if zone["direction"] != expected: continue
        lo, hi = zone["zone_lower"], zone["zone_upper"]
        dist = max(lo - price, price - hi, 0.0)
        if dist <= atr: return True
    return False


def series(symbol, timeframe, path: Path, max_bars):
    frame = read_frame(path).iloc[-max_bars:].copy()
    if len(frame) < WARMUP + HORIZON:
        raise ValueError("yetersiz geçmiş")
    bad, bad_atr, atr = quality(frame)
    zones = replay_ob_zones(symbol, timeframe, frame)
    engine = ArgentEngine(timeframe=timeframe)
    states = []
    for i in range(len(frame)):
        snap = engine.process(frame.iloc[:i + 1])
        states.append((bool(snap.active), str(snap.state), int(snap.break_dir or 0)))
    split = int(len(frame) * .7)
    rows = []
    for i in range(WARMUP - 1, len(frame) - HORIZON, STRIDE):
        if i < split <= i + HORIZON: continue  # keşif-hedef doğrulama sızıntısı
        if bad.iloc[i - WARMUP + 1:i + HORIZON + 1].any() or bad_atr.iloc[i]: continue
        p, a = float(frame.close.iloc[i]), float(atr.iloc[i])
        outcomes = price_outcomes(frame, i, a)
        active, state, break_dir = states[i]
        item = {"symbol": symbol, "tf": timeframe, "anchor": str(frame.index[i]),
                "period": "discovery" if i < split else "validation", "anchor_close": p,
                "anchor_atr": a, "pattern_active": active,
                "pattern_recent10": any(s[0] for s in states[max(0, i - 9):i + 1]), "pattern_state": state,
                "break_dir": break_dir, **outcomes}
        for direction in ("up", "down"):
            item[f"ob_{direction}"] = zone_context(zones, i, p, a, direction)
            item[f"break_{direction}"] = (active and state in {"KIRILIM_ADAYI", "KIRILIM_DENEMESI", "KIRILIM_TEYITLI"}
                                               and break_dir == (1 if direction == "up" else -1))
        rows.append(item)
    return rows, {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "rows": len(frame), "from": str(frame.index[0]), "to": str(frame.index[-1]),
                  "zones": len(zones), "split_bar": split, "anchors": len(rows)}


def summarize(observations):
    """Yön ve tanım ayrı: aday pencereler + sinyal olmayan kontrol pencereleri."""
    out = []
    for tf in sorted(observations.tf.unique()):
        for period in ("discovery", "validation"):
            group = observations[(observations.tf == tf) & (observations.period == period)]
            for method in ("end", "path"):
                for direction in ("up", "down"):
                    target = group[f"{method}_{direction}"].astype(bool)
                    for feature in ("pattern_active", "pattern_recent10", f"ob_{direction}", f"break_{direction}"):
                        observed = group[feature].astype(bool)
                        tp = int((target & observed).sum())
                        positives, negatives = int(target.sum()), int((~target).sum())
                        out.append({"tf": tf, "period": period, "method": method, "direction": direction,
                                    "feature": feature, "windows": len(group), "positive": positives,
                                    "negative": negatives, "signal": int(observed.sum()), "true_coverage": tp,
                                    "missed": positives - tp, "control_signal": int((~target & observed).sum()),
                                    "coverage": tp / positives if positives else None,
                                    "control_rate": int((~target & observed).sum()) / negatives if negatives else None})
    return pd.DataFrame(out)
