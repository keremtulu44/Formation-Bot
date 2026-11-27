"""Nedensel günlük Stabil destek temas özeti.

STB-BHV-C02 çalışmasındaki *günlük* temas sırasını aynalar. Bu, 4s temas
sayısı veya aynı raporun sonuç/ileri getiri ölçümü değildir. İlk destek
kimliğinin pencere öncesi geçmişi bilinmediğinden tam sıra iddia edilmez.
"""
from __future__ import annotations

import math
from typing import Any


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def daily_support_replay(observations: Any, snapshots: Any) -> dict:
    obs_list, snap_list = list(observations or ()), list(snapshots or ())
    if len(obs_list) != len(snap_list):
        return {"status": "destek gözlemleri ve durum çizelgesi eşleşmiyor"}
    if not obs_list:
        return {"status": "günlük destek geçmişi yok"}

    current = None
    seen_first = False
    seen_identities: set = set()
    start_known = False
    sequence_trustworthy = True
    unknown_reason = None
    touching = False
    count = 0
    touch_days: list[dict] = []
    started_at = None
    for obs, snap in zip(obs_list, snap_list):
        identity = obs.support_identity
        if identity is None:
            current = None
            continue
        if identity != current:
            # A disappearing and later reappearing identity is not necessarily
            # a fresh episode; avoid overstating a reset as a full history.
            start_known = seen_first and identity not in seen_identities
            unknown_reason = ("tekrar_gorunen_kimlik" if identity in seen_identities
                              else "ilk_destek" if not seen_first else None)
            seen_first = True
            seen_identities.add(identity)
            current = identity
            sequence_trustworthy = True
            touching = False
            count = 0
            touch_days = []
            started_at = obs.timestamp

        support, low, high, close = map(_number, (snap.support_level, obs.low, obs.high, obs.close))
        if None in (support, low, high, close):
            sequence_trustworthy = False
            continue
        atr = _number(obs.atr)
        # Same-day OHLC crossing and close-above test as the research; the
        # support may first become known at that day's close, not at its open.
        hit = low <= support <= high and not snap.close_below_support
        if hit:
            if not touching:
                count += 1
                touching = True
            touch_days.append({"daily_close_time": str(obs.timestamp), "close": close,
                               "sequence_in_window": count})
        elif not snap.close_below_support and touching:
            if atr is None or atr <= 0:
                sequence_trustworthy = False
            elif (close - support) / atr >= 0.35:
                touching = False

    last = obs_list[-1]
    if last.support_identity is None:
        return {"status": "kesitte günlük destek kimliği yok"}
    return {"status": "ok", "support_level": _number(snap_list[-1].support_level),
            "support_available_at": str(last.support_available_at) if last.support_available_at is not None else None,
            "window_identity_start": str(started_at) if started_at is not None else None,
            "sequence_known": start_known and sequence_trustworthy,
            "unknown_reason": unknown_reason,
            "start_known": start_known, "atr_complete_for_separation": sequence_trustworthy,
            "observed_count": count, "recent_touch_days": touch_days[-2:],
            "touching_at_cut": touching}
