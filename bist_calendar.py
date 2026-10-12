"""Fail-closed BIST/XIST exchange-session calendar helpers.

The XIST schedule is supplied by the pinned ``exchange-calendars`` package.
That project is a third-party calendar, not an official Borsa Istanbul API.
Dates outside its explicit support window (or a calendar load/query error) are
UNKNOWN; callers must not treat them as trading days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from functools import lru_cache
import logging
from typing import Optional

from config import (
    BIST_CLOSE,
    BIST_OPEN,
    BIST_YARIM_GUNLER,
    CANDLE_CLOSE_MINUTE,
    ISTANBUL_TZ,
    SCAN_DELAY_AFTER_CLOSE_MIN,
    TARAMA_PENCERE_SONU,
)

logger = logging.getLogger(__name__)

CALENDAR_START = date(2006, 10, 11)
# The XIST calendar's lunar-holiday observations in exchange-calendars currently
# extend through 2049. Beyond that, the safe result is UNKNOWN until refreshed.
CALENDAR_END = date(2049, 12, 31)
UNKNOWN_CALENDAR_RECHECK_SECONDS = 300.0
SCAN_WINDOW_GRACE_MINUTES = SCAN_DELAY_AFTER_CLOSE_MIN + 5
# A completed hourly bar may be labelled at its start or end. For the end-of-day
# completeness gate, allow one hourly bar plus the configured close-label offset.
POST_CLOSE_BAR_GRACE = timedelta(hours=1, minutes=CANDLE_CLOSE_MINUTE)


class SessionStatus(str, Enum):
    TRADING = "trading"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BistSession:
    session_date: date
    status: SessionStatus
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    reason: str = ""

    @property
    def is_trading_day(self) -> bool:
        return self.status is SessionStatus.TRADING

    @property
    def is_half_day(self) -> bool:
        return (
            self.status is SessionStatus.TRADING
            and self.close_time is not None
            and self.close_time < time(18, 0)
        )


@lru_cache(maxsize=1)
def _load_xist_calendar():
    """Load a deterministic, explicit calendar range; never fetch runtime data."""
    import exchange_calendars

    return exchange_calendars.get_calendar(
        "XIST",
        start=CALENDAR_START.isoformat(),
        end=CALENDAR_END.isoformat(),
    )


def as_istanbul_datetime(value: datetime) -> datetime:
    """Normalize a datetime to Europe/Istanbul without guessing naive UTC."""
    if value.tzinfo is None:
        return ISTANBUL_TZ.localize(value)
    return value.astimezone(ISTANBUL_TZ)


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return as_istanbul_datetime(value).date()
    if isinstance(value, date):
        return value
    raise TypeError("BIST session date must be a date or datetime")


@lru_cache(maxsize=8192)
def _session_for_date(day: date) -> BistSession:
    # Weekends are a known closure independently of the calendar library/range.
    if day.weekday() >= 5:
        return BistSession(day, SessionStatus.CLOSED, reason="weekend")

    if day < CALENDAR_START or day > CALENDAR_END:
        return BistSession(
            day,
            SessionStatus.UNKNOWN,
            reason=f"outside XIST calendar range {CALENDAR_START}..{CALENDAR_END}",
        )

    try:
        calendar = _load_xist_calendar()
        import pandas as pd

        label = pd.Timestamp(day)
        if not calendar.is_session(label):
            return BistSession(day, SessionStatus.CLOSED, reason="XIST calendar has no session")
        session = calendar.date_to_session(label, direction="none")
        open_at = calendar.session_open(session).to_pydatetime().astimezone(ISTANBUL_TZ)
        close_at = calendar.session_close(session).to_pydatetime().astimezone(ISTANBUL_TZ)
        calendar_close = close_at.time().replace(tzinfo=None)
        configured_half_day = BIST_YARIM_GUNLER.get(day)
        if configured_half_day is not None:
            # These explicit 2026 dates/cutoffs match Borsa Istanbul's published
            # 2026 official-holidays schedule. The finite local map is not asserted
            # exhaustive for other years; keep its configured close, not a guessed one.
            session_close = configured_half_day[1]
            reason = "XIST session; explicit configured half-day cutoff"
        elif calendar_close >= time(18, 0):
            # The app has historically scanned through the configured 18:10 cutoff
            # and final :30 bar. Retain that operating window when XIST reports
            # continuous trading close at 18:00.
            session_close = max(calendar_close, BIST_CLOSE)
            reason = "XIST session; existing configured full-day cutoff"
        else:
            session_close = calendar_close
            reason = "XIST calendar early close"
        return BistSession(
            day,
            SessionStatus.TRADING,
            open_time=max(open_at.time().replace(tzinfo=None), BIST_OPEN),
            close_time=session_close,
            reason=reason,
        )
    except Exception as exc:
        # Safe fallback: unknown prevents automated scans but not read-only reports.
        logger.error(
            "XIST calendar unavailable for %s; automated scanning is fail-closed (%s)",
            day,
            type(exc).__name__,
        )
        return BistSession(day, SessionStatus.UNKNOWN, reason="XIST calendar unavailable")


def bist_session_for(value: date | datetime) -> BistSession:
    """Return TRADING/CLOSED/UNKNOWN for the supplied Istanbul-local date."""
    return _session_for_date(_as_date(value))


def _local_now(now: Optional[datetime] = None) -> datetime:
    return as_istanbul_datetime(now or datetime.now(ISTANBUL_TZ))


def _at(day: date, at: time) -> datetime:
    return ISTANBUL_TZ.localize(datetime.combine(day, at))


def _first_scan_checkpoint(day: date) -> datetime:
    # Preserve the configured first :30 checkpoint and its existing 5-minute delay.
    return _at(day, BIST_OPEN) + timedelta(minutes=40)


def _last_scan_checkpoint(session: BistSession) -> datetime:
    close_at = _at(session.session_date, session.close_time)
    if session.is_half_day:
        # Preserve the existing configured half-day final scan at close + 5 min.
        return close_at
    last_due = _at(session.session_date, TARAMA_PENCERE_SONU) - timedelta(
        minutes=SCAN_DELAY_AFTER_CLOSE_MIN
    )
    checkpoint = last_due.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=CANDLE_CLOSE_MINUTE
    )
    if checkpoint > last_due:
        checkpoint -= timedelta(hours=1)
    return checkpoint


def bist_scan_window_open(now: Optional[datetime] = None) -> bool:
    """Whether the scheduled scan window is open on a known XIST session."""
    local_now = _local_now(now)
    session = bist_session_for(local_now)
    if session.status is not SessionStatus.TRADING:
        return False
    assert session.open_time is not None and session.close_time is not None
    start = max(BIST_OPEN, session.open_time)
    close_at = _at(session.session_date, session.close_time)
    end_at = close_at + timedelta(minutes=SCAN_WINDOW_GRACE_MINUTES)
    if not session.is_half_day:
        # Retain the repository's existing full-day 18:40 final scan window.
        configured_end = _at(session.session_date, TARAMA_PENCERE_SONU)
        end_at = max(end_at, configured_end)
    return _at(session.session_date, start) <= local_now <= end_at


def latest_session_checkpoint(now: Optional[datetime] = None) -> Optional[datetime]:
    """Latest configured :30 checkpoint, including the exchange's final close.

    The exchange close is added as a final checkpoint when it is not on :30.
    This keeps normal hourly timing intact while allowing an early close to be
    scanned once, after its actual session close.
    """
    local_now = _local_now(now)
    session = bist_session_for(local_now)
    if session.status is not SessionStatus.TRADING or session.close_time is None:
        return None

    candidate = local_now.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=CANDLE_CLOSE_MINUTE
    )
    if candidate > local_now:
        candidate -= timedelta(hours=1)

    close_at = _at(session.session_date, session.close_time)
    if session.is_half_day:
        if local_now >= close_at:
            candidate = max(candidate, close_at)
        elif candidate > close_at:
            candidate = close_at

    first_checkpoint = _first_scan_checkpoint(session.session_date)
    if candidate < first_checkpoint:
        return None
    return candidate


def bist_scan_due(
    now: Optional[datetime] = None,
    last_scanned_checkpoint: Optional[datetime] = None,
) -> bool:
    """True only for a due checkpoint inside a known session's scan window."""
    local_now = _local_now(now)
    if not bist_scan_window_open(local_now):
        return False
    checkpoint = latest_session_checkpoint(local_now)
    if checkpoint is None or local_now < checkpoint + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN):
        return False
    if last_scanned_checkpoint is not None:
        last = as_istanbul_datetime(last_scanned_checkpoint)
        if checkpoint <= last:
            return False
    return True


def next_bist_scan_at(now: Optional[datetime] = None) -> Optional[datetime]:
    """Next scheduled scan time on today's known session, if any."""
    local_now = _local_now(now)
    session = bist_session_for(local_now)
    if session.status is not SessionStatus.TRADING or session.open_time is None or session.close_time is None:
        return None
    if not bist_scan_window_open(local_now):
        return None

    first = _first_scan_checkpoint(session.session_date) + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)
    if local_now < first:
        return first

    checkpoint = latest_session_checkpoint(local_now)
    if checkpoint is None:
        return first
    if local_now < checkpoint + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN):
        return checkpoint + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)

    next_checkpoint = checkpoint + timedelta(hours=1)
    last_checkpoint = _last_scan_checkpoint(session)
    if next_checkpoint > last_checkpoint:
        next_checkpoint = last_checkpoint
    if next_checkpoint <= checkpoint:
        return None
    return next_checkpoint + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)


def seconds_until_next_bist_open(now: Optional[datetime] = None) -> Optional[float]:
    """Return seconds to the next known open; None means calendar is unknown."""
    local_now = _local_now(now)
    current = bist_session_for(local_now)
    if current.status is SessionStatus.UNKNOWN:
        return None
    if current.status is SessionStatus.TRADING and current.open_time is not None:
        opening = _at(current.session_date, current.open_time)
        if local_now < opening:
            return (opening - local_now).total_seconds()
        if current.close_time is not None and local_now < _at(current.session_date, current.close_time):
            return 0.0

    for offset in range(1, 370):
        day = local_now.date() + timedelta(days=offset)
        session = bist_session_for(day)
        if session.status is SessionStatus.UNKNOWN:
            return None
        if session.status is SessionStatus.TRADING and session.open_time is not None:
            opening = _at(day, session.open_time)
            return max(0.0, (opening - local_now).total_seconds())
    return None


def should_run_post_close_analysis(now: Optional[datetime] = None) -> tuple[bool, str]:
    """Only a known exchange session may trigger the scheduled full scan."""
    session = bist_session_for(_local_now(now))
    if session.status is SessionStatus.TRADING:
        return True, session.reason
    if session.status is SessionStatus.CLOSED:
        return False, session.reason
    return False, session.reason


def current_session_timestamp_issue(
    provider_timestamp,
    now: Optional[datetime] = None,
    *,
    after_close: bool = False,
) -> Optional[str]:
    """Validate one provider timestamp against the known current XIST session."""
    local_now = _local_now(now)
    session = bist_session_for(local_now)
    if session.status is SessionStatus.UNKNOWN:
        return "XIST takvim bilgisi bilinmiyor"
    if session.status is SessionStatus.CLOSED:
        return f"XIST seans kapalı ({session.reason})"

    try:
        stamp = provider_timestamp
        if hasattr(stamp, "to_pydatetime"):
            stamp = stamp.to_pydatetime()
        stamp = as_istanbul_datetime(stamp)
    except Exception:
        return "sağlayıcı son mum zaman damgası doğrulanamadı"

    if stamp.date() != local_now.date():
        return f"sağlayıcının son mumu bugüne ait değil ({stamp:%Y-%m-%d %H:%M %Z})"
    if stamp > local_now:
        return f"sağlayıcı geleceğe ait mum verdi ({stamp:%Y-%m-%d %H:%M %Z})"
    if not after_close and session.open_time is not None:
        earliest_session_label = _at(session.session_date, session.open_time) - timedelta(
            minutes=CANDLE_CLOSE_MINUTE
        )
        if stamp < earliest_session_label:
            return (
                f"sağlayıcının son mumu seans açılışından önce "
                f"({stamp:%H:%M} < {earliest_session_label:%H:%M} {ISTANBUL_TZ.zone})"
            )

    if after_close:
        if session.close_time is None:
            return "XIST kapanış saati bilinmiyor"
        close_at = _at(session.session_date, session.close_time)
        earliest = close_at - POST_CLOSE_BAR_GRACE
        if stamp < earliest:
            return (
                f"son sağlayıcı mumu seans kapanışına göre eski "
                f"({stamp:%H:%M} < {earliest:%H:%M} {ISTANBUL_TZ.zone})"
            )
    else:
        age_minutes = (local_now - stamp).total_seconds() / 60.0
        from config import STALE_BAR_UYARI_DK

        if age_minutes > STALE_BAR_UYARI_DK:
            return (
                f"son sağlayıcı mumu {age_minutes:.0f} dk yaşında "
                f"(eşik {STALE_BAR_UYARI_DK} dk)"
            )
    return None


def current_session_data_issue(
    provider_frame,
    now: Optional[datetime] = None,
    *,
    after_close: bool = False,
) -> Optional[str]:
    """Reject old/empty provider data for scheduled live-session analyses.

    Intraday runs require a valid same-day provider timestamp within the existing
    stale-bar warning limit. Post-close runs use the exchange close and one hourly
    bar plus the configured close-label offset, rather than wall-clock age.
    """
    local_now = _local_now(now)
    session = bist_session_for(local_now)
    if session.status is SessionStatus.UNKNOWN:
        return "XIST takvim bilgisi bilinmiyor"
    if session.status is SessionStatus.CLOSED:
        return f"XIST seans kapalı ({session.reason})"
    if provider_frame is None or getattr(provider_frame, "empty", False):
        return "sağlayıcı boş veya başarısız yanıt döndürdü"

    try:
        provider_index = provider_frame.index
        if len(provider_index) == 0:
            return "sağlayıcı zaman damgası yok"
        stamp = provider_index.max()
    except Exception:
        return "sağlayıcı son mum zaman damgası doğrulanamadı"

    return current_session_timestamp_issue(stamp, local_now, after_close=after_close)
