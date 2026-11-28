"""Session-aware fetch validation. A nonempty HTTP response is not fresh data.

No network, no synthetic candles, and no fixed wall-clock age across weekends.
Only explicit live callers opt in; historical/research fetches stay unchanged.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

import config


def hourly_fetch_validator(symbol, observed_at):
    """Freeze the expected close once per request, allowing provider publication lag."""
    if config.sembol_turu(symbol) == "makro":
        return None
    from bist_calendar import SessionStatus, bist_session_for
    from data import beklenen_son_kapanis_ani, mum_kapanis_anlari, seans_sonu_saati

    observed = pd.Timestamp(observed_at)
    observed = (observed.tz_localize(config.ISTANBUL_TZ) if observed.tzinfo is None
                else observed.tz_convert(config.ISTANBUL_TZ))
    # During the configured publication grace, the previous close is still valid.
    cutoff = observed - timedelta(minutes=config.SCAN_DELAY_AFTER_CLOSE_MIN)
    session = bist_session_for(observed.to_pydatetime())
    expected = (None if session.status is SessionStatus.UNKNOWN else
                beklenen_son_kapanis_ani("1h", cutoff.to_pydatetime()))

    def validate(frame):
        if expected is None:
            return False, "XIST beklenen kapanış doğrulanamadı"
        if not isinstance(frame, pd.DataFrame) or frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
            return False, "geçersiz saatlik veri"
        index = frame.index
        index = (index.tz_localize(config.ISTANBUL_TZ) if index.tz is None
                 else index.tz_convert(config.ISTANBUL_TZ))
        required = expected
        # Yahoo :30 and native TV :00 are different hourly grids. Never demand
        # a nonexistent :30 candle from a consistently whole-hour provider.
        if set(index.minute) == {0}:
            required = expected.floor("h")
            if expected.date() == cutoff.date():
                end = seans_sonu_saati(cutoff.to_pydatetime())
                session_end = cutoff.normalize() + pd.Timedelta(hours=end.hour, minutes=end.minute)
                required = min(cutoff.floor("h"), session_end)
            if required.date() == observed.date() and required.hour < 11:
                required = beklenen_son_kapanis_ani(
                    "1h", observed.normalize().to_pydatetime())
        if required is None:
            return False, "XIST beklenen kapanış doğrulanamadı"
        closes = mum_kapanis_anlari(index, "1h")
        completed = closes[closes <= observed]
        if len(completed) == 0 or completed.max() < required:
            actual = completed.max().isoformat() if len(completed) else "yok"
            # Classified as transient: one bounded retry, not an infinite backfill.
            return False, f"veri gecikmesi: beklenen kapanış {required.isoformat()}, gelen {actual}"
        return True, ""

    return validate
