"""Fail-closed, chart-only adapter for the independent Stabil resistance.

No alarm decisions or support results are changed here.  Sources are read-only:
the native daily frame and, for intraday charts, the original 1H constituents.
The adapter detects known holes and mismatched aggregates; a provider that omits
or mislabels information can still be wrong in ways no local check can prove.
"""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any, Mapping, MutableMapping, Sequence

import numpy as np
import pandas as pd

from bist_calendar import SessionStatus, bist_session_for
from config import sembol_turu
from data import (
    gunluk_bolunme_normalize_et,
    mum_kapanis_anlari,
    ohlcv_girdi_sorunlari,
    seans_sonu_saati,
)
from .resistance import StabilResistanceOutput, evaluate_stabil_resistance
from .runtime import StabilRoleStatus

log = logging.getLogger(__name__)
_PRICE_COLUMNS = ("open", "high", "low", "close", "volume")
_INTRADAY_HOURS = {"1h": 1, "2h": 2, "4h": 4}
# Kırpma sonrası çizgi için en az bu kadar kesintisiz kova gerekir; iki noktadan
# azı çizgi değil tek noktadır ve "hazır" demek yanıltıcı olur.
_MIN_CONTINUOUS_BUCKETS = 2


class _UnsafeSource(ValueError):
    """A detected source problem, recorded in the chart instead of guessed."""


def _istanbul(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise _UnsafeSource("invalid_cutoff")
    return ts.tz_localize("Europe/Istanbul") if ts.tzinfo is None else ts.tz_convert("Europe/Istanbul")


def _frame_index(frame: Any) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise _UnsafeSource("missing_source")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise _UnsafeSource("invalid_timestamp")
    idx = frame.index
    # NaT cannot be classified as future. Duplicates/order are checked *after*
    # the causal slice so a valid future row cannot change a historical chart.
    if idx.isna().any():
        raise _UnsafeSource("invalid_timestamp")
    idx = idx.tz_localize("Europe/Istanbul") if idx.tz is None else idx.tz_convert("Europe/Istanbul")
    out = frame.copy(deep=True)
    out.columns = [str(c).lower() for c in out.columns]
    if out.columns.has_duplicates:
        raise _UnsafeSource("invalid_columns")
    out.index = idx
    return out


def _closed(frame: Any, tf: str, cutoff: pd.Timestamp, *, start: pd.Timestamp | None = None) -> pd.DataFrame:
    """Filter by the repo's close time, then validate only the eligible slice."""
    out = _frame_index(frame)
    closes = mum_kapanis_anlari(out.index, tf)
    mask = np.asarray(closes <= cutoff, dtype=bool)
    if start is not None:
        mask &= np.asarray(out.index >= start, dtype=bool)
    out = out.loc[mask].copy()
    if out.empty:
        raise _UnsafeSource("no_completed_bars")
    if out.index.has_duplicates or not out.index.is_monotonic_increasing:
        raise _UnsafeSource("invalid_timestamp")
    for flag in ("is_closed", "is_complete"):
        if flag not in out.columns:
            continue
        # A string "False" is not True.  Do not let pandas' bool coercion turn
        # an explicitly partial constituent into a closed bar.
        for value in out[flag].to_numpy(dtype=object):
            if not isinstance(value, (bool, int, float, np.bool_, np.integer, np.floating)) or value != 1:
                raise _UnsafeSource("incomplete_or_invalid_flag")
    if ohlcv_girdi_sorunlari(out):
        raise _UnsafeSource("invalid_ohlcv")
    return out


def _session(day: date, *, intraday: bool = False):
    session = bist_session_for(day)
    if session.status is SessionStatus.UNKNOWN:
        raise _UnsafeSource("unknown_session")
    if intraday and session.status is SessionStatus.TRADING and session.is_half_day:
        # The chart and the engine use data.mum_kapanis_anlari.  If the
        # calendar knows an early close that that helper does not, don't guess.
        if session.close_time != seans_sonu_saati(day):
            raise _UnsafeSource("calendar_close_mismatch")
    return session


def _days(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def _drop_known_closed_daily_rows(frame: pd.DataFrame, *, symbol: str) -> pd.DataFrame:
    """Remove provider daily bars whose local dates are known BIST closures.

    A BIST-listed instrument cannot have a valid trading candle on a known
    holiday/weekend. Providers sometimes leave synthetic/stale daily rows on
    those labels. Exclude only calendar-confirmed CLOSED dates; an UNKNOWN date
    still fails closed, and missing real sessions are checked afterward.
    """
    if frame.empty:
        return frame
    closed_dates: set[date] = set()
    for day in {ts.date() for ts in frame.index}:
        session = _session(day)
        if session.status is SessionStatus.UNKNOWN:
            raise _UnsafeSource(f"unknown_session:{day.isoformat()}")
        if session.status is SessionStatus.CLOSED:
            closed_dates.add(day)
    if not closed_dates:
        return frame
    log.warning("%s: daily provider rows on known BIST closure dates excluded: %s",
                symbol, ", ".join(map(str, sorted(closed_dates))))
    return frame.loc[[ts.date() not in closed_dates for ts in frame.index]].copy()


def _daily_checked(frame: Any, cutoff: pd.Timestamp, *, equity: bool, symbol: str) -> pd.DataFrame:
    daily = _drop_known_closed_daily_rows(_closed(frame, "1d", cutoff), symbol=symbol)
    if daily.empty:
        raise _UnsafeSource("no_completed_bars")
    dates = [ts.date() for ts in daily.index]
    if len(set(dates)) != len(dates):
        raise _UnsafeSource("duplicate_daily_session")
    actual = set(dates)
    # Check through the target close, not through wall-clock time: a daily
    # candle closing *after* an intraday candle must not influence its result.
    expected: set[date] = set()
    for day in _days(dates[0], cutoff.date()):
        session = _session(day)
        if session.status is not SessionStatus.TRADING:
            if day in actual:
                # Preserve the failing label so a provider/timezone-corrupted
                # daily cache can be diagnosed without weakening fail-closed.
                raise _UnsafeSource(f"daily_on_closed_session:{day.isoformat()}")
            continue
        daily_label = pd.DatetimeIndex([pd.Timestamp(day, tz="Europe/Istanbul")])
        if mum_kapanis_anlari(daily_label, "1d")[0] <= cutoff:
            expected.add(day)
    if expected - actual:
        raise _UnsafeSource("missing_daily_session")
    # The existing normalization looks ahead within its split-detection
    # window and retroactively rescales history.  Do not plot it as if that
    # scale had been known at every past candle.  The raw daily source is
    # required and a detected scale change disables only this chart layer.
    if equity:
        _, split_count = gunluk_bolunme_normalize_et(daily)
        if split_count:
            raise _UnsafeSource("daily_split_scale_unverified")
    return daily


def _same_rows(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    if not left.index.equals(right.index):
        return False
    return bool(np.allclose(
        left[list(_PRICE_COLUMNS)].to_numpy(dtype=float),
        right[list(_PRICE_COLUMNS)].to_numpy(dtype=float),
        rtol=1e-9, atol=1e-8, equal_nan=False,
    ))


def _bucket_problem(row: pd.Series, label: pd.Timestamp, hourly: pd.DataFrame, tf: str) -> str | None:
    """Return the reason a target bucket cannot be certified, or None.

    A bucket is certifiable only if it holds exactly its expected 1H constituents
    and its OHLCV equals their aggregate. Nothing is filled in.
    """
    end = mum_kapanis_anlari(pd.DatetimeIndex([label]), tf)[0]
    expected_hours = []
    hour = label
    while hour < end:
        expected_hours.append(hour)
        hour += pd.Timedelta(hours=1)
    part = hourly.loc[(hourly.index >= label) & (hourly.index < end)]
    if list(part.index) != expected_hours:
        return "incomplete_hourly_bucket"
    aggregate = np.array([
        part["open"].iloc[0], part["high"].max(), part["low"].min(),
        part["close"].iloc[-1], part["volume"].sum(),
    ], dtype=float)
    if not np.allclose(row[list(_PRICE_COLUMNS)].to_numpy(dtype=float), aggregate,
                       rtol=1e-9, atol=1e-8, equal_nan=False):
        return "target_source_mismatch"
    return None


def _bucket_problems(target: pd.DataFrame, hourly: pd.DataFrame, tf: str) -> dict[pd.Timestamp, str]:
    """Map every uncertifiable target bucket (including grid holes) to a reason.

    Cheap grid comparison first, then a backward walk that stops at the first bad
    bucket: everything after it is proven contiguous and aggregate-consistent.
    """
    first, last = target.index[0], target.index[-1]
    hours = _INTRADAY_HOURS[tf]
    expected: list[pd.Timestamp] = []
    for day in _days(first.date(), last.date()):
        session = _session(day, intraday=True)
        if session.status is not SessionStatus.TRADING:
            continue
        start = pd.Timestamp(day, tz="Europe/Istanbul") + pd.Timedelta(hours=9, minutes=30)
        end_time = seans_sonu_saati(day)
        end = pd.Timestamp(day, tz="Europe/Istanbul") + pd.Timedelta(hours=end_time.hour, minutes=end_time.minute)
        while start < end:
            if first <= start <= last:
                expected.append(start)
            start += pd.Timedelta(hours=hours)
    actual = list(target.index)
    problems: dict[pd.Timestamp, str] = {}
    if expected != actual:
        grid, seen = set(expected), set(actual)
        for label in expected:
            if label not in seen:
                problems[label] = "eksik_hedef_kova"
        for label in actual:
            if label not in grid:
                problems[label] = "beklenmeyen_hedef_kova"
    son_sorun = max(problems) if problems else None
    for label in reversed(actual):
        if son_sorun is not None and label <= son_sorun:
            break
        if label in problems:
            continue
        kind = _bucket_problem(target.loc[label], label, hourly, tf)
        if kind is not None:
            problems[label] = kind
            break
    return problems


def _intraday_checked(target: pd.DataFrame, hourly_frame: Any, tf: str, cutoff: pd.Timestamp) -> pd.DataFrame:
    # Trim only the rolling source's initial *partial bucket*: retaining it
    # would turn missing prefix constituents into a fictitious complete bar.
    # A trailing bucket whose window ends after the last observed hourly bar is
    # dropped instead of being certified by its scheduled close (provider lag /
    # mid-session capture).
    #
    # Interior provider holes are never filled or invented. They are handled by
    # *trimming the prefix* up to the last bad bucket, so the drawn level always
    # comes from a contiguous, verified run of buckets (policy chosen 2026-11-08:
    # a whole-dark layer hid the feature for every window spanning a hole). The
    # trade-off is visible: the line starts later than the chart window.
    hourly = _closed(hourly_frame, "1h", cutoff, start=target.index[0])
    first_hourly = hourly.index[0]
    if target.index[0] < first_hourly:
        if mum_kapanis_anlari(pd.DatetimeIndex([target.index[0]]), tf)[0] <= first_hourly:
            raise _UnsafeSource("missing_hourly_source")
        target = target.iloc[1:].copy()
    if target.empty:
        raise _UnsafeSource("no_complete_target_bucket")
    hourly = hourly.loc[hourly.index >= target.index[0]]
    # Trailing bucket: a bucket whose window ends after the last observed hourly
    # bar cannot be certified, even if its scheduled close is already in the past
    # (provider lag / archive captured mid-session). Certifying it by its
    # scheduled close was the reason a *single* trailing partial bucket made the
    # whole 4h resistance layer fail as "incomplete_hourly_bucket". Such a
    # trailing bucket is dropped, never filled; interior holes still fail closed.
    while len(target) >= 1:
        last_label = target.index[-1]
        last_close = mum_kapanis_anlari(pd.DatetimeIndex([last_label]), tf)[0]
        last_hour_close = mum_kapanis_anlari(pd.DatetimeIndex([hourly.index[-1]]), "1h")[0]
        if last_close <= last_hour_close:
            break
        log.warning(
            "Stabil direnç: kapanmamış son kova atlandı (%s, kova kapanışı %s, son 1s kapanışı %s)",
            last_label, last_close, last_hour_close,
        )
        target = target.iloc[:-1].copy()
    if target.empty:
        raise _UnsafeSource("no_complete_target_bucket")
    # Sondaki kullanılamaz kovalar (sağlayıcı gecikmesi, eksik bileşen, uyuşmayan
    # toplam) çizgiyi kısaltır; içerideki bir boşluk ise öncesini bırakır.
    while True:
        problems = _bucket_problems(target, hourly, tf)
        if not problems:
            break
        if target.index[-1] in problems:
            log.warning(
                "Stabil direnç: kapanmamış/doğrulanamayan son kova atlandı (%s, neden=%s)",
                target.index[-1], problems[target.index[-1]],
            )
            target = target.iloc[:-1].copy()
            if target.empty:
                raise _UnsafeSource("no_complete_target_bucket")
            continue
        # İç boşluk: yalnız son sorunlu kovanın öncesi bırakılır. Kalan blok
        # kesintisiz ve doğrulanmıştır; boşluk doldurulmaz, kova uydurulmaz.
        # Politika 2026-11-08: boşluk yüzünden katmanın tamamını karartmak
        # yerine çizgi görünür pencerede daha geç başlar.
        son_sorun = max(problems)
        atilan = int((target.index <= son_sorun).sum())
        log.warning(
            "Stabil direnç: son sorunlu kovaya kadar kırpıldı (sorunlu kova=%s, neden=%s, "
            "atılan=%d, kalan=%d)",
            son_sorun, problems[son_sorun], atilan, len(target) - atilan,
        )
        target = target.loc[target.index > son_sorun].copy()
        if len(target) < _MIN_CONTINUOUS_BUCKETS:
            # Kırpma sonrası tek kova kalıyorsa çizgi yoktur: uydurma yerine söyle.
            raise _UnsafeSource("insufficient_continuous_buckets")
        break
    return target


def resistance_for_chart(
    symbol: str,
    timeframe: str,
    target_frame: Any,
    *,
    daily_frame: Any,
    hourly_frame: Any = None,
    as_of_close: Any = None,
) -> StabilResistanceOutput:
    """Calculate only after verifying the actual chart's completed sources.

    The daily frame must be native, not a 1H->1D fallback. Intraday bars are
    checked against their 1H constituents. Neither frame is modified.
    """
    name = str(symbol or "").strip().upper().replace(".IS", "")
    tf = str(timeframe or "").strip().lower()
    cutoff = None

    def unavailable(reason: str, *, data_error: bool = True) -> StabilResistanceOutput:
        status = StabilRoleStatus.DATA_ERROR if data_error else StabilRoleStatus.UNAVAILABLE
        return StabilResistanceOutput(name, tf, cutoff, status, reason)

    try:
        if tf not in {*_INTRADAY_HOURS, "1d"}:
            return unavailable("unsupported_timeframe")
        if sembol_turu(name) == "makro":
            return unavailable("unsupported_session", data_error=False)
        indexed = _frame_index(target_frame)
        closes = mum_kapanis_anlari(indexed.index, tf)
        cutoff = _istanbul(as_of_close) if as_of_close is not None else closes.max()
        target = _closed(indexed, tf, cutoff)
        # In case the supplied wall clock filtered a trailing target bar.
        cutoff = min(cutoff, mum_kapanis_anlari(target.index, tf)[-1])
        daily = _daily_checked(daily_frame, cutoff, equity=sembol_turu(name) == "hisse", symbol=name)
        if tf == "1d":
            target = _drop_known_closed_daily_rows(target, symbol=name)
            if target.empty:
                raise _UnsafeSource("no_completed_bars")
            matching = daily.reindex(target.index)
            if not _same_rows(target, matching):
                raise _UnsafeSource("daily_target_source_mismatch")
        else:
            target = _intraday_checked(target, hourly_frame, tf, cutoff)
        return evaluate_stabil_resistance(name, tf, target, daily_frame=daily, as_of_close=cutoff)
    except _UnsafeSource as exc:
        return unavailable(str(exc), data_error=str(exc) not in {"missing_source", "no_completed_bars"})
    except Exception as exc:  # noqa: BLE001 - chart-only failure cannot stop an alert
        log.warning("Stabil direnç kaynak kontrolü başarısız (%s %s): %s", name, tf, type(exc).__name__)
        return unavailable(f"chart_bridge_error:{type(exc).__name__}")


def alarm_chart_timeframes(main_tf: str, frames: Mapping[str, Any], limit: int, *,
                           public_tf: str | None = None, single: bool = False) -> list[str]:
    """Only the DM/public frames that can actually be emitted need a calculation."""
    main = str(main_tf)
    if single:
        return [main]
    ordered = [main] + [str(tf) for tf, frame in frames.items() if str(tf) != main and frame is not None]
    chosen = ordered[:max(1, int(limit))]
    if public_tf and frames.get(public_tf) is not None and public_tf not in chosen:
        chosen.append(public_tf)
    return chosen


def add_chart_resistance(
    symbol: str,
    frames: Mapping[str, Any],
    results: Any,
    *,
    daily_frame: Any,
    hourly_frame: Any,
    as_of_close: Any,
    timeframes: Sequence[str] | None = None,
    cache: MutableMapping[str, StabilResistanceOutput] | None = None,
) -> dict[str, Any]:
    """Copy per-TF results; an optional cache is local to one symbol/scan snapshot."""
    copied = dict(results) if isinstance(results, Mapping) else {}
    for tf in (timeframes if timeframes is not None else frames):
        target = frames.get(tf)
        if target is None:
            continue
        prior = copied.get(tf)
        per_tf = dict(prior) if isinstance(prior, Mapping) else {}
        if cache is not None and tf in cache:
            resistance = cache[tf]
        else:
            try:
                resistance = resistance_for_chart(
                    symbol, tf, target, daily_frame=daily_frame, hourly_frame=hourly_frame,
                    as_of_close=as_of_close,
                )
            except Exception as exc:  # noqa: BLE001 - even an adapter failure cannot drop the chart
                log.warning("Stabil direnç grafiği hesaplanamadı (%s %s): %s", symbol, tf, type(exc).__name__)
                resistance = StabilResistanceOutput(
                    str(symbol).upper(), str(tf), None, StabilRoleStatus.DATA_ERROR,
                    f"chart_bridge_error:{type(exc).__name__}",
                )
            if cache is not None:
                cache[tf] = resistance
        per_tf["stabil_direnc"] = resistance
        copied[tf] = per_tf
    return copied
