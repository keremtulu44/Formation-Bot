"""Causal domain-channel replay v2: freeze live channel decisions at each bar.

This is a research candidate stream, NOT a full live scan/delivery simulator.
Frozen v2 baseline: OB uses the old close-inside predicate. Current production
OB contact/recovery logic is evaluated by research.ob_alarm_event_study; do not
claim this v2 stream has current OB live parity after that change.
No final ledger/zone reconstruction, no global monkeypatch, no paired-direction
row explosion. Unknown/conflicting directions remain unknown. Features and
outcomes are separate so prefix checks never compare censored future labels.
"""
from __future__ import annotations

import math
from types import MethodType

import numpy as np
import pandas as pd

import config
from bot.domain_alarm_service import (
    _bolge_sebepleri, _bos_ve_choch_sebepleri, _formasyon_sebepleri,
    _hacim_bilgisi, _kanallar_from_sebepler,
)
from domain_engines.adapter import to_domain_frame
from domain_engines.fvg import FvgEngulfingConfig, FvgEngulfingEngine, SensitivityProfile
from domain_engines.market_structure import MarketStructureConfig, MarketStructureEngine
from domain_engines.order_block import OrderBlockEngine
from domain_engines.volume_participation import VolumeParticipationEngine
from patterns import ArgentEngine
from research.domain_alarm_replay import baglam_satiri
from directional_zone_replay import compute_wilder_atr

VERSION = "causal-alarm-channels-v2"
TIMEFRAMES = ("1h", "2h", "4h", "1d")
HORIZON = 12


def direction_from_reasons(reasons, formation_direction=0):
    """Never infer direction from a future zone, a price run, or the outcome."""
    directions = set()
    for reason in reasons:
        if "↑" in reason or "boğa" in reason:
            directions.add(1)
        if "↓" in reason or "ayı" in reason:
            directions.add(-1)
        if reason.startswith("formasyon") and formation_direction in (-1, 1):
            directions.add(int(formation_direction))
    if len(directions) == 1:
        return next(iter(directions)), "explicit"
    return 0, "conflict" if directions else "unknown"


def formation_snapshots(symbol, tf, frame, *, profile="Dengeli"):
    """Observe a private instance; do not patch the class used by live callers."""
    engine = ArgentEngine(profile=profile, timeframe=tf)
    # Keep _key unset: the lifecycle otherwise reads/writes live identity stores.
    engine._key = None
    original = engine._process_bar
    snapshots = {}

    def capture(self, index):
        previous = self.pattern_state
        start = len(self.events)
        original(index)
        snap = self._snapshot(previous, self.events[start:], frame.iloc[:index + 1])
        active = snap.active
        if active is None:
            return
        q = snap.effective_quality
        if q is None:
            q = active.raw_quality
        snapshots[index] = {
            "timeframe": tf, "state": snap.state, "notification_state": snap.state,
            "quality": float(q), "min_quality": float(config.ALERT_MIN_QUALITY.get(tf, config.ALERT_MIN_QUALITY_GLOBAL)),
            "pattern_name": str(active.pattern_type),
            "formation_id": f"{symbol}|{tf}|{active.identity}",
            "break_dir": int(snap.break_dir or 0),
        }

    engine._process_bar = MethodType(capture, engine)
    engine.process(frame, tam_yeniden=True)
    return snapshots


def _entry(engine, name):
    if name == "market_structure":
        return {"export": engine.export_contract}
    if name == "volume_participation":
        return {"export": engine.final_export,
                "details": {"latest_metrics": engine.metrics_history[-1] if engine.metrics_history else None}}
    return {"export": engine.export, "data_quality": engine.last_data_quality}


def channel_reasons(exports, tf, prefix, formations):
    """Frozen v2 channel predicates; OB occupancy is a historical baseline."""
    close = float(prefix.close.iloc[-1])
    reasons = _bos_ve_choch_sebepleri(exports, tf, len(prefix))
    reasons += _bolge_sebepleri(exports, tf, close)
    reasons += _formasyon_sebepleri(formations, tf)
    volume = _hacim_bilgisi(exports, tf, prefix)
    if volume["sebep"]:
        reasons.append(volume["sebep"])
    return sorted(set(reasons)), volume


def decision_snapshots(symbol, tf, frame, *, profile="Dengeli"):
    """One forward pass per domain. Return primitive snapshots and error ledger."""
    if tf not in TIMEFRAMES:
        raise ValueError("Unsupported timeframe")
    if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("Unique ordered DatetimeIndex required")
    # Adapted order must be identical to the positional feature timeline.
    adapted = to_domain_frame(frame)
    formations = formation_snapshots(symbol, tf, frame, profile=profile)
    engines = {"market_structure": MarketStructureEngine(config=MarketStructureConfig(profile=profile)),
               "order_block": OrderBlockEngine(), "volume_participation": VolumeParticipationEngine()}
    if tf != "1h":
        engines["fvg"] = FvgEngulfingEngine(FvgEngulfingConfig(timeframe=tf, sensitivity=SensitivityProfile(profile)))
    atrs = compute_wilder_atr(adapted)
    errors, snapshots = {}, []
    for index, bar in enumerate(adapted.to_dict("records")):
        per_tf = {}
        for name, engine in engines.items():
            if name in errors:
                continue
            try:
                engine.update(bar)
                per_tf[name] = _entry(engine, name)
            except Exception as exc:  # domain failure is evidence, not a clean negative
                errors[name] = {"first_bar": index, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        if index < 29:  # same minimum frame length as evaluate_domain_alarm_candidates
            continue
        prefix = frame.iloc[:index + 1]
        formation = formations.get(index)
        reasons, volume = channel_reasons({tf: per_tf}, tf, prefix, [formation] if formation else [])
        if not reasons:
            continue
        direction, status = direction_from_reasons(reasons, (formation or {}).get("break_dir", 0))
        snapshots.append({
            "schema": VERSION, "symbol": symbol, "timeframe": tf,
            "bar_index": index, "bar_time": pd.Timestamp(frame.index[index]).isoformat(),
            "reasons": reasons, "kanallar": sorted(_kanallar_from_sebepler(reasons)),
            "source_direction": direction, "direction_status": status,
            "formation": formation, "hacim_tier": volume["tier"],
            "rvol": volume["rvol"], "volume_source": volume["source"],
            "suspect_volume": bool(volume["veri_suphe"]),
            "unknown_domains": sorted(errors),
            **baglam_satiri(frame, index, atrs),
        })
    return snapshots, errors


def forward_outcome(frame, index, direction, atr, *, horizon=HORIZON):
    """Frozen entry ATR; next bar onward; both-hit bar is explicitly ambiguous."""
    empty = {"status": "RIGHT_CENSORED", "first_touch": None,
             "mfe_atr": None, "mae_atr": None, "close_atr": None,
             "touch_delay_bars": None}
    if atr is None or not math.isfinite(float(atr)) or atr <= 0:
        return {**empty, "status": "NO_ATR"}
    history = frame.iloc[max(0, index - 19):index + 1]
    if not _valid_bars(history):
        return {**empty, "status": "BAD_HISTORY"}
    future = frame.iloc[index + 1:index + 1 + horizon]
    if len(future) < horizon:
        return empty
    if not _valid_bars(future):
        return {**empty, "status": "BAD_FUTURE"}
    if direction not in (-1, 1):
        return {**empty, "status": "UNKNOWN_DIRECTION"}
    reference = float(frame.close.iloc[index])
    highs, lows = future.high.to_numpy(float), future.low.to_numpy(float)
    favorable = ((highs - reference) if direction == 1 else (reference - lows)) / atr
    adverse = ((reference - lows) if direction == 1 else (highs - reference)) / atr
    hit, delay = "NEITHER", None
    for j, (good, bad) in enumerate(zip(favorable, adverse), 1):
        if good >= 1 and bad >= 1:
            hit, delay = "AMBIGUOUS_SAME_BAR", j
            break
        if good >= 1 or bad >= 1:
            hit, delay = ("FAVORABLE_FIRST" if good >= 1 else "ADVERSE_FIRST"), j
            break
    return {"status": "VALID", "first_touch": hit, "touch_delay_bars": delay,
            "mfe_atr": float(max(0, favorable.max())), "mae_atr": float(max(0, adverse.max())),
            "close_atr": float(direction * (future.close.iloc[-1] - reference) / atr)}


def _valid_bars(frame):
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(float)
    if not np.isfinite(values).all():
        return False
    o, h, lo, c, v = values.T
    return bool(((lo > 0) & (v >= 0) & (lo <= np.minimum(o, c))
                 & (h >= np.maximum(o, c)) & (h >= lo)).all())


def measure_snapshots(frame, snapshots):
    atrs = compute_wilder_atr(to_domain_frame(frame))
    return [{**snapshot, "outcome_12": forward_outcome(frame, snapshot["bar_index"],
             snapshot["source_direction"], atrs[snapshot["bar_index"]])} for snapshot in snapshots]
