"""bot/lifecycle_events.py — main.py'den taşındı (modülerleştirme, davranış aynı).
Yama yüzeyi main.py namespace'inde kalır; okumalar _pkg.X üzerinden."""

import os
import re
import sys
import time
import json
import signal
import logging
import math
import random
import socket
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID okur
except ImportError:
    pass

from config import (ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES, BIST_OPEN,
                    SCAN_DELAY_AFTER_CLOSE_MIN, STALE_BAR_UYARI_DK, VERI_YOK_MODU_ESIK_DK,
                    OFFSESSION_CACHE_MAX_AGE_DAYS,
                    TARAMA_SURESI_UYARI_DK, SCAN_REQUEST_BATCH_SIZE,
                    SCAN_REQUEST_DELAY_MIN_SEC, SCAN_REQUEST_DELAY_MAX_SEC,
                    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD,
                    SCAN_BATCH_PAUSE_MIN_SEC, SCAN_BATCH_PAUSE_MAX_SEC,
                    SCAN_RETRY_BACKOFF_MIN_SEC, SCAN_RETRY_BACKOFF_MAX_SEC,
                    SUMMARY_HOURS, DEFERRED_ALERT_DIGEST_TIME, DEFERRED_ALERT_DIGEST_LIMIT,
                    POST_CLOSE_ANALYSIS_TIME, ACIL_KUYRUK_BOSALTMA_ARALIK_SN,
                    HEARTBEAT_MIN_ARALIK_SN, HEARTBEAT_UZAK_ARALIK_SN,
                    PUBLIC_MIN_QUALITY,
                    MORNING_PRELOAD_HOUR, MORNING_PRELOAD_MINUTE, EVREN_BUYUME_UYARI_ESIGI,
                    TELEGRAM_WEBHOOK_SECRET, TELEGRAM_WEBHOOK_URL, RENDER_EXTERNAL_URL,
                    TERMINAL_TAZE_BAR,
                    DM_MIN_DEVLAMLILIK)
from data import (StockDequeManager, tarama_penceresi_acik_mi, tarama_animi_mi,
                  islem_gunu_mu,
                  son_kapanan_mum_ani, time_until_next_open, is_bist_open,
                  resample_all_timeframes, resample_ohlcv, fetch_yfinance_1h, fetch_yfinance_1d,
                  fetch_last_bar,
                  select_yfinance_1h_period, tamamlanmis_mumlar,
                  mum_kapanis_ani, bar_kapandi_mi)
from scan_pacer import YahooRequestPacer
from patterns import PatternLifecycleManager
from telegram_alert_flow import DeferredAlertBuffer, WATCH_STATES
from notifier import TelegramNotifier, devamlilik_puani
import config
import ampirik_referans as ampirik
from notification_context import (
    format_domain_context, domain_bolumleri, karsi_deliller,
)
from karne import (KarneDefteri, atr_hesapla, hafta_damgasi, karne_gunu_mu, karne_uret)
from supabase_store import SupabaseStore
from health_server import start_render_health_server
from live_state import LiveState
from telegram_commands import TelegramCommandListener, ArkaPlanYaniti

# Batch 8 / C2: raporlama katmanı `reporting/format.py`'ye ayrıldı. Burada eski
# iç adlar (`_sayi`, `_panel_*`) alias olarak korunuyor: main döngüsü ve testler
# aynı isimlerle çalışmaya devam eder, davranış değişmez.
from reporting.panel import panel_raporu
from reporting.format import (
    STATE_TR, PANEL_TIMEFRAMES, PANEL_MESAJ_SINIRI,
    PANEL_DURUM_PUANI, PANEL_IPUCU, son_bar_yasi_dakika_str,
    sayi as _sayi, gecen_sure as _gecen_sure,
    filtrele_formasyonlar as _filtrele_formasyonlar, break_ok as _break_ok,
    veri_durumu_satiri as _veri_durumu_satiri,
    kisa_durum as _kisa_durum, tf_kisa as _tf_kisa,
    panel_kalite as _panel_kalite, panel_sembol as _panel_sembol,
    panel_hucre as _panel_hucre, panel_aday_puani as _panel_aday_puani,
    panel_kritik_anahtar as _panel_kritik_anahtar,
    panel_filtre_coz as _panel_filtre_coz,
    panel_durum_sayilari as _panel_durum_sayilari,
    panel_kritik_listesi as _panel_kritik_listesi,
    panel_sigdir as _panel_sigdir,
    mum_kapanis_metni as _mum_bilgisi,
    format_deferred_alert_summary as _format_deferred_alert_summary,
    format_urgent_alert_queue_summary as _format_urgent_queue_summary,
)

from state import persistence as _state_persistence
from state import paths as _state_paths
from transport import telegram as _transport_telegram

import main as _pkg  # geç bağlama: yamalı adlar _pkg.X (plan §3)

def _event_field(event, name, default=None):
    return event.get(name, default) if isinstance(event, dict) else getattr(event, name, default)


def _event_bar_number(event):
    try:
        return int(_pkg._event_field(event, "bar"))
    except (TypeError, ValueError, OverflowError):
        return None


def _event_local_time(event, fallback=None):
    raw = _pkg._event_field(event, "time")
    if raw is None:
        raw = fallback
    if raw is None:
        return None
    try:
        if isinstance(raw, _pkg.datetime):
            value = raw
        else:
            value = _pkg.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if value.tzinfo is None:
            return ISTANBUL_TZ.localize(value)
        return value.astimezone(ISTANBUL_TZ)
    except (TypeError, ValueError, OverflowError):
        return None


def _classified_lifecycle_events(snap, fallback_bar_time=None):
    """Map existing lifecycle event rows to Telegram-summary event categories.

    The engine keeps one terminal BREAK_FAILED type for both unconfirmed
    attempts and later invalidations. A failure only qualifies as invalidation
    when a prior same-formation, same-direction BREAK_CONFIRMED event exists.
    """
    events = getattr(snap, "events", None) or []
    if not isinstance(events, (list, tuple)):
        return []
    ordered = sorted(
        (event for event in events if isinstance(event, dict)),
        key=lambda event: (_pkg._event_bar_number(event) if _pkg._event_bar_number(event) is not None else -1),
    )
    confirmed: Dict[tuple, List[tuple[int, int]]] = {}
    classified = []
    for event in ordered:
        event_type = str(_pkg._event_field(event, "type", "") or "").strip().upper()
        event_state = str(_pkg._event_field(event, "state", "") or "").strip().upper()
        stable_id = str(_pkg._event_field(event, "stable_id", "") or "").strip()
        bar = _pkg._event_bar_number(event)
        direction = _pkg._event_field(event, "direction", 0)
        try:
            direction = int(direction)
        except (TypeError, ValueError, OverflowError):
            direction = 0

        if event_state == "KIRILIM_TEYITLI" and event_type in _pkg._LIFECYCLE_CONFIRMATION_TYPES:
            if stable_id and bar is not None and direction in (-1, 1):
                confirmed.setdefault((stable_id, direction), []).append((bar, len(classified)))
            classified.append(("KIRILIM_TEYITLI", event))
            continue
        if event_state == "RETEST_BASARILI" and event_type == "RETEST_OK":
            prior = confirmed.get((stable_id, direction), ())
            if stable_id and bar is not None and any(confirm_bar < bar for confirm_bar, _ in prior):
                classified.append(("RETEST_BASARILI", event))
            continue
        if event_state == "BASARISIZ_KIRILIM" and event_type == "BREAK_FAILED":
            prior = confirmed.get((stable_id, direction), ())
            if stable_id and bar is not None and any(confirm_bar < bar for confirm_bar, _ in prior):
                classified.append(("KIRILIM_GECERSIZLESTI", event))
                continue
    # Materialize fallback event time only for the latest-bar event. Older rows
    # need their own timestamps for daily bucketing and are never guessed.
    output = []
    latest_bar = getattr(snap, "bar_index", None)
    for state, event in classified:
        fallback = fallback_bar_time if _pkg._event_bar_number(event) == latest_bar else None
        output.append((state, event, _pkg._event_local_time(event, fallback)))
    return output


def _record_daily_lifecycle_events(stock, timeframe, snap, fallback_bar_time=None):
    """Count today's real transitions once; never count pre-confirmation failures."""
    changed = False
    for event_state, event, event_time in _pkg._classified_lifecycle_events(snap, fallback_bar_time):
        if event_time is None or event_time.date() != _pkg.datetime.now(ISTANBUL_TZ).date():
            continue
        event_type = str(_pkg._event_field(event, "type", "") or "").strip().upper()
        event_bar = _pkg._event_bar_number(event)
        stable_id = str(_pkg._event_field(event, "stable_id", "") or "").strip()
        event_identity = stable_id or str(event_bar if event_bar is not None else event_time.isoformat())
        key = "|".join((str(stock).upper(), str(timeframe).lower(), event_identity,
                        event_state, event_type, event_time.isoformat()))
        if key in _pkg._daily_lifecycle_event_keys:
            continue
        _pkg._daily_lifecycle_event_keys.add(key)
        changed = True
        counter = _pkg._LIFECYCLE_EVENT_COUNTERS[event_state]
        _pkg.daily_stats[counter] = int(_pkg.daily_stats.get(counter) or 0) + 1

    if changed:
        _pkg._gunluk_sayac_kaydet()


def _invalidation_event_for_snapshot(snap, active):
    """Return only a fresh, post-confirmation return-inside transition."""
    if (getattr(snap, "state", None) != "BASARISIZ_KIRILIM"
            or getattr(snap, "invalid_reason", None) not in _pkg._CONFIRMED_INVALIDATION_REASONS
            or active is None):
        return None
    stable_id = str(getattr(active, "stable_id", "") or "").strip()
    if not stable_id:
        return None
    latest_bar = getattr(snap, "bar_index", None)
    failures = []
    for event_state, event, _event_time_value in _pkg._classified_lifecycle_events(snap):
        if event_state != "KIRILIM_GECERSIZLESTI":
            continue
        if str(_pkg._event_field(event, "stable_id", "") or "").strip() != stable_id:
            continue
        event_bar = _pkg._event_bar_number(event)
        if event_bar is None or latest_bar is None or event_bar > latest_bar:
            continue
        if latest_bar - event_bar > max(0, int(TERMINAL_TAZE_BAR)):
            continue
        failures.append(event)
    if not failures:
        return None
    return max(failures, key=lambda event: _pkg._event_bar_number(event) or -1)


def _invalidation_confirmation_delivered(notifier, formation_id) -> bool:
    """Tur 2a: KIRILIM_GECERSIZLESTI push'undan önce aynı formation_id'li
    KIRILIM_TEYITLI kaydının gerçekten teslim edilip edilmediğini doğrula."""
    from config import invalidation_require_delivered_confirm
    if not invalidation_require_delivered_confirm():
        return True
    if not formation_id:
        return False
    kontrol = getattr(notifier, "teyit_teslim_edildi_mi", None)
    if callable(kontrol):
        return bool(kontrol(formation_id))
    delivery = getattr(notifier, "_delivery", None)
    if delivery is not None and callable(getattr(delivery, "confirmation_delivered", None)):
        return bool(delivery.confirmation_delivered(formation_id))
    return True


def _closed_formation_event_confirmed(state, break_dir, close_price, break_level):
    """KIRILIM/RETEST push'u ancak mum kapanışı ilgili sınırın ötesindeyse geçer."""
    if state not in {"KIRILIM_TEYITLI", "RETEST_BASARILI"}:
        return True
    try:
        close = float(close_price)
        level = float(break_level)
    except (TypeError, ValueError, OverflowError):
        return False
    if not (math.isfinite(close) and math.isfinite(level)):
        return False
    strict_break = state == "KIRILIM_TEYITLI"
    if break_dir == 1:
        return close > level if strict_break else close >= level
    if break_dir == -1:
        return close < level if strict_break else close <= level
    return False


def _capture_digest_lifecycle_baseline() -> None:
    """18:45 özeti gönderildiğinde mevcut teyit/geçersizleşme mühürlerini baz al (V2)."""
    global _digest_event_keys_snapshot
    setattr(_pkg, "_digest_event_keys_snapshot", set(_pkg._daily_lifecycle_event_keys))
    _pkg._gunluk_sayac_kaydet()


