"""bot/heartbeat.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

def _heartbeat_icerik_ozeti(payload: dict) -> str:
    """`last_scan` dışındaki alanların özeti: değişiklik tespiti için."""
    return json.dumps({k: v for k, v in payload.items() if k != "last_scan"},
                      ensure_ascii=False, sort_keys=True, default=str)


def _heartbeat_yasi_sn(simdi: _pkg.datetime = None) -> float:
    """heartbeat.json'daki `last_scan` damgasının yaşı (saniye); okunamazsa None.

    Denetim B-4: /health artık botun canlı olup olmadığını bu değerle raporlar.
    Dosya yoksa/bozuksa uydurma değer üretilmez, None döner ('bilinmiyor').
    """
    try:
        with open(_pkg._heartbeat_yolu(), "r", encoding="utf-8") as f:
            ham = json.load(f).get("last_scan")
        if not ham:
            return None
        damga = _pkg.datetime.fromisoformat(str(ham))
        if damga.tzinfo is None:
            damga = ISTANBUL_TZ.localize(damga)
        return max(0.0, ((simdi or _pkg.datetime.now(ISTANBUL_TZ)) - damga).total_seconds())
    except Exception:
        return None


def _heartbeat_yolu() -> str:
    """write_heartbeat ile AYNI dizin çözümlemesini kullanır (tek davranış)."""
    try:
        from config import DATA_DIR
        data_dir = DATA_DIR
    except ImportError:  # pragma: no cover - config her zaman var; güvenlik ağı
        data_dir = "./bot_data"
    return os.path.join(data_dir, "heartbeat.json")


def write_heartbeat(data_dir: str = None, notifier=None, force: bool = False):
    """Botun yaşadığını dışarıdan anlamak için heartbeat dosyası.
    Dışarıdan izleme: `jq .last_scan bot_data/heartbeat.json` 2 saatten eskiyse bot takılmış/kapanmıştır."""
    global _son_heartbeat_zamani, _son_heartbeat_icerik, _son_heartbeat_uzak_zamani
    if not force and time.time() - _pkg._son_heartbeat_zamani < HEARTBEAT_MIN_ARALIK_SN:
        return
    if data_dir is None:
        try:
            from config import DATA_DIR
            data_dir = DATA_DIR
        except ImportError:
            data_dir = "./bot_data"
    try:
        heartbeat_path = os.path.join(data_dir, "heartbeat.json")
        os.makedirs(data_dir, exist_ok=True)
        payload = {
            "last_scan": _pkg.datetime.now(ISTANBUL_TZ).isoformat(),
            "profile": PROFILE,
            "stocks_scanned": _pkg.daily_stats['stocks_scanned'],
            "patterns_found": _pkg.daily_stats['patterns_found'],
            "alerts_sent": _pkg.daily_stats['alerts_sent'],
            "errors": _pkg.daily_stats['errors'],
            "active_stocks": len(_pkg.ACTIVE_STOCKS),
            # --- veri sağlığı (FAZ 1) ---
            "fetch_ok": _pkg.daily_stats['fetch_ok'],
            "fetch_failures": _pkg.daily_stats['fetch_failures'],
            "fetch_retries": _pkg.daily_stats['fetch_retries'],
            "fetch_retry_recovered": _pkg.daily_stats['fetch_retry_recovered'],
            "stale_stocks": _pkg.daily_stats['stale_stocks'],
            "max_bar_age_min": _pkg.daily_stats['max_bar_age_min'],
            "data_stale": _pkg.daily_stats['data_stale'],
            "veri_yok_modu": _pkg.daily_stats['veri_yok_modu'],
            "split_atlanan": _pkg.daily_stats['split_atlanan'],
            "son_tarama_suresi_dk": _pkg.daily_stats['son_tarama_suresi_dk'],
            "gunluk_bar_sayisi": _pkg.daily_stats['gunluk_bar_sayisi'],
            "telegram_kap": (notifier.kap_durumu() if notifier is not None
                             else (_pkg._notifier_ref.kap_durumu() if _pkg._notifier_ref else None)),
            # --- GÖNDERİM SAĞLIĞI (A6) ---
            # "Bot çalışıyor ama hiçbir mesaj gitmiyor" durumu dışarıdan görünsün:
            # token/chat_id yokluğu, son başarılı gönderim, son hata ve engel sayaçları.
            "notifier_enabled": (notifier.enabled if notifier is not None
                                 else (getattr(_pkg._notifier_ref, "enabled", None) if _pkg._notifier_ref else None)),
            # Public hedef doğrulaması (açılışta bir kez yapılır; buradan ağa çıkılmaz)
            "public_hedef": (getattr(notifier, "public_hedef_bilgi", None)
                             if notifier is not None
                             else getattr(_pkg._notifier_ref, "public_hedef_bilgi", None)),
            "telegram_gonderim": (notifier.gonderim_durumu() if notifier is not None
                                  else (getattr(_pkg._notifier_ref, "gonderim_durumu", lambda: None)()
                                        if _pkg._notifier_ref else None)),
            # Bekleyen gün içi aday (18:45 digest) ve engellenen acil kuyruğu:
            # restart/tıkanma durumunda "içeride ne var" dışarıdan görünsün.
            "bekleyen_bildirim": len(_pkg._deferred_alert_buffer),
            "digest_son_gonderim_gun": _pkg._digest_son_gonderim_gun,
            "acil_kuyruk": (notifier.gonderim_durumu().get("acil_kuyruk")
                            if notifier is not None
                            else (getattr(_pkg._notifier_ref, "kuyruk_durumu", lambda: None)()
                                  if _pkg._notifier_ref else None)),
            # B5 telemetrisi: kaç uzak yazım yapıldı / kaçı gereksizdi
            "uzak_yazma": (_pkg._deque_manager_ref.uzak_yazma_durumu()
                           if _pkg._deque_manager_ref else None),
            # --- ADAY HUNİSİ (B1) ---
            "alerts_attempted": _pkg.daily_stats['alerts_attempted'],
            "alerts_failed": _pkg.daily_stats['alerts_failed'],
            "aday_hunisi": {
                "push": _pkg.daily_stats['alerts_sent'],
                "digest_ertelenen": _pkg.daily_stats['alerts_deferred'],
                "state_kapsam_disi": _pkg.daily_stats['alerts_state_disabled'],
                "esik_alti": _pkg.daily_stats['alerts_below_threshold'],
                "bar_kapanmadi": _pkg.daily_stats['alerts_bar_kapanmadi'],
                "kapanis_teyidi_yok": _pkg.daily_stats['alerts_break_close_invalid'],
                "digest_tasmasi": _pkg.daily_stats['alerts_digest_overflow'],
                "engel_cooldown": _pkg.daily_stats['alerts_engel_cooldown'],
                "engel_kap": _pkg.daily_stats['alerts_engel_kap'],
                "kuyruga_alindi": _pkg.daily_stats['alerts_kuyruk'],
            },
            "cift_ornek": {
                "uyari": _pkg._cift_ornek_durumu.get("uyari", False),
                "instance_id": _pkg.INSTANCE_ID,
                "canli_digerleri": _pkg._cift_ornek_durumu.get("canli_digerleri", []),
                "son_kontrol": (_pkg._cift_ornek_durumu["son_kontrol"].isoformat()
                                if _pkg._cift_ornek_durumu.get("son_kontrol") else None),
            },
            "veri_sorunlari": ({k: [x['tip'] for x in v]
                               for k, v in _pkg._deque_manager_ref.sureklilik_sorunlari.items()}
                              if _pkg._deque_manager_ref else {}),
        }
        icerik = _pkg._heartbeat_icerik_ozeti(payload)
        simdi = time.time()
        if _pkg._supabase_store_ref is not None and (
                force
                or icerik != _pkg._son_heartbeat_icerik
                or simdi - _pkg._son_heartbeat_uzak_zamani >= HEARTBEAT_UZAK_ARALIK_SN):
            if _pkg._supabase_store_ref.upsert("state:heartbeat", payload):
                setattr(_pkg, "_son_heartbeat_uzak_zamani", simdi)
        setattr(_pkg, "_son_heartbeat_icerik", icerik)
        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        setattr(_pkg, "_son_heartbeat_zamani", simdi)
    except Exception as e:
        _pkg.logger.warning(f"Heartbeat yazılamadı: {e}")


