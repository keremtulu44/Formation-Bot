"""bot/counters.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

def _gunluk_sayac_kaydet() -> None:
    """Günlük sayaçların kalıcı kopyasını yazar (I/O hatası botu durdurmaz)."""
    try:
        patch = {
            "sayaclar": {ad: _pkg.daily_stats.get(ad, 0) for ad in _pkg._KALICI_SAYACLAR},
            "olay_muhurlari": sorted(_pkg._daily_lifecycle_event_keys),
        }
        if _pkg._digest_event_keys_snapshot is not None:
            patch["digest_olay_muhurlari"] = sorted(_pkg._digest_event_keys_snapshot)
        if not _state_persistence.gunluk_durum_yukle():
            # Gün döndü: yeni günün kaydı kurulurken dünün özet işaretleri
            # geçersiz sayılır (gunluk_durum_guncelle kaydı yeniden kurar).
            patch["ozet_gunleri"] = {}
        _state_persistence.gunluk_durum_guncelle(patch)
    except Exception as hata:  # noqa: BLE001
        _pkg.logger.debug("Günlük sayaç kaydı yazılamadı: %s", hata)


def _gunluk_sayac_yukle() -> None:
    """Aynı güne ait kalıcı sayaçları geri yükler (restart gün sürekliliği)."""
    try:
        veri = _state_persistence.gunluk_durum_yukle()
    except Exception as hata:  # noqa: BLE001
        _pkg.logger.debug("Günlük sayaç okunamadı: %s", hata)
        return
    # Aynı güne ait kayıt varsa gün değişimi sıfırlaması TETİKLENMESİN: restart
    # eden süreç, günün sayaçlarını devraldığı için "yeni gün" değildir.
    try:
        _pkg.daily_stats['last_reset'] = _pkg.datetime.now(ISTANBUL_TZ).date()
    except Exception:  # noqa: BLE001
        # Sayaç yazımı düşse de yedekleme akışı devam etsin; ama iz kalsın.
        _pkg.logger.debug("Günlük sayaç damgası yazılamadı", exc_info=True)
    event_keys = (veri or {}).get("olay_muhurlari")
    if isinstance(event_keys, list):
        _pkg._daily_lifecycle_event_keys.clear()
        _pkg._daily_lifecycle_event_keys.update(str(key) for key in event_keys if key)
    global _digest_event_keys_snapshot
    digest_keys = (veri or {}).get("digest_olay_muhurlari")
    if isinstance(digest_keys, list):
        setattr(_pkg, "_digest_event_keys_snapshot", {str(key) for key in digest_keys if key})
    sayaclar = (veri or {}).get("sayaclar") or {}
    if not sayaclar:
        return
    yuklenen = {}
    for ad in _pkg._KALICI_SAYACLAR:
        try:
            deger = int(sayaclar.get(ad) or 0)
        except (TypeError, ValueError):
            continue
        if deger:
            _pkg.daily_stats[ad] = deger
            yuklenen[ad] = deger
    # Başarısız kırılım tekilleştirmesi gün içinde tekrar saymasın: anahtar
    # kümesi dolu olamaz (olay detayı saklanmaz) ama sayaç tabanı korunur.
    global _daily_basarisiz_tabani
    if yuklenen.get('basarisiz_kirilim'):
        _pkg._daily_basarisiz_keys.add("__restart_tabani__")
        setattr(_pkg, "_daily_basarisiz_tabani", max(
            _pkg._daily_basarisiz_tabani, int(yuklenen['basarisiz_kirilim'])))
        _pkg.daily_stats['basarisiz_kirilim'] = _pkg._daily_basarisiz_tabani
    if yuklenen:
        _pkg.logger.info("Günlük sayaçlar restart'tan geri yüklendi: %s", yuklenen)


def _note_basarisiz_kirilim(stock: str, timeframe: str, bar_time=None) -> None:
    """Başarısız kırılımı günde bir kez sayar (public özet satırı için)."""
    anahtar = f"{str(stock).upper()}|{str(timeframe).lower()}|{bar_time}"
    if anahtar in _pkg._daily_basarisiz_keys:
        return
    _pkg._daily_basarisiz_keys.add(anahtar)
    # Restart tabanı varsa sayı onun üstüne eklenir (çift sayım olmaz).
    yeni = len(_pkg._daily_basarisiz_keys) - (
        1 if "__restart_tabani__" in _pkg._daily_basarisiz_keys else 0)
    _pkg.daily_stats['basarisiz_kirilim'] = _pkg._daily_basarisiz_tabani + yeni
    _pkg._gunluk_sayac_kaydet()


def _note_pattern_found(stock: str, timeframe: str) -> None:
    """Günlük BENZERSİZ formasyon sayacını güncelle (aynı hisse bir kez sayılır; A9 düzeltmesi).
    Mevcut TF davranışı (tarama, alert, digest) bozulmaz; sadece istatistik metrik düzeltilir.
    Aynı hisse farklı TF'de (1h, 2h, 4h, 1d) aynı formasyon gösterirse, tekrar sayılmaz."""
    # GÖREV 5 (A9): Multi-timeframe aynı formasyon tekrar sayılmasını önle
    # Yalnızca hisse adı (TF'den bağımsız) anahtar olarak kullanılır
    _pkg._daily_pattern_keys.add(f"{str(stock).upper()}")
    _pkg.daily_stats['patterns_found'] = len(_pkg._daily_pattern_keys)


def _note_unannounced_invalidation(
    stock: str, timeframe: str, formation_id=None, bar_time=None
) -> None:
    """Teslim edilmemiş teyidin geçersizleşmesini günde bir kez say (18:45 özeti için)."""
    kimlik = str(formation_id or bar_time or "").strip()
    anahtar = f"{str(stock).upper()}|{str(timeframe).lower()}|{kimlik}"
    if anahtar in _pkg._daily_unannounced_invalidation_keys:
        return
    _pkg._daily_unannounced_invalidation_keys.add(anahtar)
    _pkg.daily_stats['sessiz_gecersizlesme_sayisi'] = int(
        _pkg.daily_stats.get('sessiz_gecersizlesme_sayisi') or 0
    ) + 1
    _pkg._gunluk_sayac_kaydet()


def reset_daily_if_needed():
    """Gün değiştiyse günlük sayacı sıfırla"""
    global _daily_basarisiz_tabani
    today = _pkg.datetime.now(ISTANBUL_TZ).date()
    if today != _pkg.daily_stats['last_reset']:
        _pkg.logger.info(f"=== GÜNLÜK ÖZET {_pkg.daily_stats['last_reset']} ===")
        _pkg.logger.info(f"Taranan hisse: {_pkg.daily_stats['stocks_scanned']}, Bulunan formasyon: {_pkg.daily_stats['patterns_found']}, Gönderilen alert: {_pkg.daily_stats['alerts_sent']}, Hata: {_pkg.daily_stats['errors']}")
        # Sıfırla
        _pkg.daily_stats['stocks_scanned'] = 0
        _pkg.daily_stats['patterns_found'] = 0
        _pkg._daily_pattern_keys.clear()
        _pkg.daily_stats['basarisiz_kirilim'] = 0
        _pkg.daily_stats['sessiz_gecersizlesme_sayisi'] = 0
        for counter in _pkg._LIFECYCLE_EVENT_COUNTERS.values():
            _pkg.daily_stats[counter] = 0
        _pkg._daily_lifecycle_event_keys.clear()
        _pkg._daily_unannounced_invalidation_keys.clear()
        global _digest_event_keys_snapshot
        setattr(_pkg, "_digest_event_keys_snapshot", None)
        # Restart tabanı yalnızca AYNI günün devralınan sayısıdır; yeni güne
        # sıfırla (yoksa eski günün sayısı yeni güne taşınır ve sayaç şişer).
        setattr(_pkg, "_daily_basarisiz_tabani", 0)
        _pkg._daily_basarisiz_keys.clear()
        _pkg.daily_stats['tarama_sayisi'] = 0
        _pkg.daily_stats['alerts_sent'] = 0
        _pkg.daily_stats['alerts_attempted'] = 0
        _pkg.daily_stats['alerts_failed'] = 0
        _pkg.daily_stats['alerts_deferred'] = 0
        _pkg.daily_stats['alerts_below_threshold'] = 0
        _pkg.daily_stats['alerts_state_disabled'] = 0
        _pkg.daily_stats['alerts_bar_kapanmadi'] = 0
        _pkg.daily_stats['alerts_break_close_invalid'] = 0
        _pkg.daily_stats['alerts_digest_overflow'] = 0
        _pkg.daily_stats['alerts_kuyruk'] = 0
        _pkg.daily_stats['alerts_engel_cooldown'] = 0
        _pkg.daily_stats['alerts_engel_kap'] = 0
        _pkg.daily_stats['alerts_engel_tekrar'] = 0
        # Görsel sayaçları (§4): metin kotasından ayrı izlenir, gün sonunda sıfırlanır.
        _pkg.daily_stats['grafik_kare'] = 0
        _pkg.daily_stats['grafik_hata'] = 0
        _pkg.daily_stats['errors'] = 0
        _pkg.daily_stats['fetch_ok'] = 0
        _pkg.daily_stats['fetch_failures'] = 0
        _pkg.daily_stats['fetch_retries'] = 0
        _pkg.daily_stats['fetch_retry_recovered'] = 0
        _pkg.daily_stats['stale_stocks'] = 0
        _pkg.daily_stats['max_bar_age_min'] = None
        _pkg.daily_stats['data_stale'] = False
        _pkg.daily_stats['veri_yok_modu'] = False
        _pkg.daily_stats['split_atlanan'] = 0
        _pkg.daily_stats['son_tarama_suresi_dk'] = None
        _pkg.daily_stats['gunluk_bar_sayisi'] = None
        _pkg.daily_stats['last_reset'] = today
        # Yeni gün: sayaçlar sıfırlanır. Kalıcı kayda DOKUNULMAZ; gunluk_durum_*
        # katmanı gün damgasını kendisi denetler ve ilk yazımda yeni günün
        # kaydını kurar (aynı güne ait özet işaretleri yanlışlıkla silinmesin).
        _pkg._gunluk_sayac_kaydet()


