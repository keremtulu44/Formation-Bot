"""bot paketi — ana sistem modülleri (2026-10-26 modülerleştirme).

Bu __init__ bilinçli olarak bir **namespace yüzeyi**dir: `main.py` buradan
`from bot import *` ile tüm dış API'yi ve yama yüzeyini (test_patch_yuzeyi.py)
tek satırda alır. Yamalı adlar (monkeypatch.setattr(main, X)) main'in
namespace'inde tek sahipli kalır; bot/* alt modülleri bunları `_pkg.X` ile
çağrı anında okur (docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md §3).

Modüller: statestore, counters, heartbeat, commands, lifecycle_events, scan,
security, summary, app.
"""

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

from bot.statestore import (  # noqa: F401  (geç bağlama — modülerleştirme)
    DIGEST_PENDING_DOSYA,
    DIGEST_PENDING_SUPABASE_KEY,
    ILERI_TEST_GECE_SAAT,
    IMMEDIATE_ALERT_STATES,
    INSTANCE_ID,
    KARNE_UZAK_YAZMA_ARALIK_SN,
    ORNEK_KONTROL_ARALIK_SN,
    SON_TARAMA_DOSYA,
    SON_TARAMA_SUPABASE_KEY,
    SUMMARY_MARKERS_SUPABASE_KEY,
    TARAMA_UYARI_ESIK_TUR,
    TEKRAR_SIFIRLA_STATELER,
    WATCH_CONTEXT_HAVUZU,
    _CONFIRMED_INVALIDATION_REASONS,
    _DOMAIN_TIMEFRAMES,
    _GORELI_MUM,
    _GRAFIK_GORUNUM,
    _GRAFIK_HEDEF_SN,
    _GRAFIK_SEMBOL,
    _GRAFIK_TF,
    _KALICI_SAYACLAR,
    _LIFECYCLE_CONFIRMATION_TYPES,
    _LIFECYCLE_EVENT_COUNTERS,
    _MESAJ_GUVENLI_SINIR,
    _POST_CLOSE_DIFF_LABELS,
    _UST_TF,
    _analiz_hatasi_kaydi,
    _ardisik_basarisiz_tur,
    _cache_verisi_kullanilabilir,
    _cift_ornek_durumu,
    _daily_basarisiz_keys,
    _daily_basarisiz_tabani,
    _daily_lifecycle_event_keys,
    _daily_pattern_keys,
    _daily_unannounced_invalidation_keys,
    _deferred_alert_buffer,
    _deque_manager_ref,
    _digest_event_keys_snapshot,
    _digest_pending_yolu,
    _digest_son_gonderim_gun,
    _domain_runner_cache,
    _gece_denetim_son_gun,
    _grafik_aktif_is,
    _grafik_is_kilidi,
    _health_server_ref,
    _ileri_test_son_gece,
    _islem_gunu_loglandi,
    _karne_al,
    _karne_defteri,
    _karne_son_uzak_yazma,
    _kayit_zamani,
    _komut_modu,
    _lifecycle_manager_ref,
    _live_state,
    _ms_hata_sayaci,
    _notifier_ref,
    _scan_istegi,
    _scan_job_active,
    _scan_job_request,
    _scan_last_result,
    _scan_request_lock,
    _shutdown_requested,
    _son_heartbeat_icerik,
    _son_heartbeat_uzak_zamani,
    _son_heartbeat_zamani,
    _son_tarama_data_dir,
    _son_tarama_uyari_gun,
    _son_tarama_yolu,
    _supabase_store_ref,
    _telegram_api_cagri,
    _telegram_listener_ref,
    _telegram_update_processor_ref,
    _telegram_webhook_kilidi,
    _telegram_yanit_oku,
    _webhook_adres_gizle,
    _yeni_snapshot,
    daily_stats,
    digest_tamponu_kaydet,
    digest_tamponu_yukle,
    last_run_stats,
    son_tarama_kaydet,
    son_tarama_yukle,
)
from bot.counters import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _gunluk_sayac_kaydet,
    _gunluk_sayac_yukle,
    _note_basarisiz_kirilim,
    _note_pattern_found,
    _note_unannounced_invalidation,
    reset_daily_if_needed,
)
from bot.heartbeat import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _heartbeat_icerik_ozeti,
    _heartbeat_yasi_sn,
    _heartbeat_yolu,
    write_heartbeat,
)

from bot.summary import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _acil_kuyruk_acilista_isle,
    _acil_kuyruk_gonderim_penceresi_acik,
    _build_active_formations_for_summary,
    _daily_summary_payload,
    _effective_summary_hours,
    _format_post_close_diff_report,
    _gece_denetimi,
    _gece_onerisi_gonder,
    _gece_raporu_yaz,
    _gun_sayacini_gonderimle_hizala,
    _haftalik_karne_ekle,
    _haftalik_karne_kisa,
    _ileri_test_gece,
    _ileri_test_kaydet,
    _kacirilan_digest_ozeti,
    _karne_dolu,
    _karne_gonderildi_isaretle,
    _karne_olay_kaydet,
    _karne_outcome_bagla,
    _karne_seri_saglayici,
    _karne_uzak_kaydet,
    _karneyle_gonder,
    _ozet_isaret_kaydet,
    _ozet_isaretlerini_yukle,
    _ozet_slot_gonderilmeli,
    _parse_deferred_alert_digest_time,
    _parse_post_close_analysis_time,
    _parse_summary_hours,
    _public_turu_kapat,
    _successful_full_scan_today,
    evening_maintenance,
    morning_preload,
)
from bot.app import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _logging_kuruldu,
    _render_test_sender,
    main_loop,
    setup_logging,
    signal_handler,
)



# Import anında yalnız logger nesnesi alınır; handler'lar setup_logging() ile
# bağlanır (yukarıdaki nota bakın).
logger = logging.getLogger(__name__)




from bot.lifecycle_events import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _capture_digest_lifecycle_baseline,
    _classified_lifecycle_events,
    _closed_formation_event_confirmed,
    _event_bar_number,
    _event_field,
    _event_local_time,
    _invalidation_confirmation_delivered,
    _invalidation_event_for_snapshot,
    _record_daily_lifecycle_events,
)
from bot.scan import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _completed_domain_frames,
    _domain_results_for_notification,
    _endekse_gore_guc,
    _evren_olcek_uyarisi,
    _formation_history_baslangic_kontrolu,
    _goreli_guc_satiri,
    _grafikleri_tur_sonunda,
    _is_full_universe_scan,
    _load_domain_runner,
    _tarama_saglik_kontrolu,
    _tekil_ornek_kontrolu,
    create_yahoo_pacer,
    fetch_1h_stocks_paced,
    scan_all_stocks,
)
from bot.security import (  # noqa: F401  (geç bağlama — modülerleştirme)
    _alarm_izni_var,
    _alert_break_level,
)






signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


























































from bot.commands import (  # noqa: F401  (geç bağlama — modülerleştirme)
    KOMUT_YARDIM,
    TELEGRAM_KOMUTLARI,
    _bekle_veya_tarama,
    _bos_analiz_mesaji,
    _calistir_istek_taramasi,
    _grafik_isi_calistir,
    _grafik_isi_yurut,
    _grafik_ozet_metni,
    _istek_tam_evrende_tamamlandi,
    _kare_altyazisi,
    _kismi_kapsam_notu,
    _komut_backtest,
    _komut_canli,
    _komut_durum,
    _komut_durumu,
    _komut_evet,
    _komut_formasyonlar,
    _komut_grafik,
    _komut_hayir,
    _komut_karne,
    _komut_kirilim,
    _komut_olcum,
    _komut_oneri_cevabi,
    _komut_ozet,
    _komut_panel,
    _komut_retest,
    _komut_sikisanlar,
    _komut_tamamlanan,
    _komut_tara,
    _komut_yardim,
    _manuel_tarama_istegi,
    _manuel_tarama_tamamla,
    _ms_hata_kaydet,
    _ms_hata_satiri,
    _onceki_sonuc_uyarisi,
    _panel_raporu,
    _saglik_ozeti,
    _sonuc_yok_mesaji,
    _telegram_delete_webhook,
    _telegram_komut_katmanini_kur,
    _telegram_set_webhook,
    _telegram_token_al,
    _telegram_webhook_isle,
    _telegram_webhook_secret_ayikla,
    _telegram_webhook_url_olustur,
)
















































































# === SON TARAMA KALICILIĞI ===
# Render'ın diski geçicidir; aynı liste mevcut bot_store tablosunda da tutulur.
# LiveState kilidinden yalnızca kopya alınır, disk/ağ I/O'su kilit dışında yapılır.
# Batch 8 / C2 (8.4): son tarama kalıcılığı `state/persistence.py`'ye taşındı.
# Aşağıdaki fonksiyonlar eski imzalarını koruyan ince adaptörlerdir (global
# durumu toplar, işi katmana bırakır).
from state import persistence as _state_persistence
from state import paths as _state_paths








# === TELEGRAM WEBHOOK (Render) ===
# Neden: Render Free bir web servistir; uyku/restart döngüsüne girer. Yoklama
# (getUpdates) modunda uzun yoklama bağlantısı her restart'ta yeniden kurulur ve
# token'ı dinleyen ikinci bir kopya varsa 409 alınır. Webhook modunda Telegram
# güncellemeyi doğrudan HTTPS ile iter; ayrı port/thread gerekmez, mevcut küçük
# HTTP sunucusu (health_server) kullanılır.
#
# Mod seçimi: TELEGRAM_WEBHOOK_SECRET varsa webhook, yoksa yoklama. İkisi asla
# aynı anda açık olmaz: webhook açıkken getUpdates çağrılmaz (Telegram 409 verir),
# yoklamaya dönülürken de webhook silinir.

# === TELEGRAM (taşıma katmanı — Batch 8 / C2, 8.5) ===
# Sır/adres çözümleme, Bot API çağrısı ve webhook kurulumu artık
# `transport/telegram.py`'de. Buradaki adaptörler eski iç adları ve imzaları
# korur; API fonksiyonları ÇAĞRI ANINDA main globalinden okunur, böylece
# testlerdeki `monkeypatch.setattr(main_mod, "_telegram_api_cagri", ...)`
# davranışı aynen çalışır.
from transport import telegram as _transport_telegram


__all__ = [
    "ACIL_KUYRUK_BOSALTMA_ARALIK_SN",
    "ACTIVE_STOCKS",
    "ALERT_MIN_QUALITY",
    "ALERT_MIN_QUALITY_GLOBAL",
    "ALERT_STATES",
    "ArkaPlanYaniti",
    "BIST_OPEN",
    "DEFERRED_ALERT_DIGEST_LIMIT",
    "DEFERRED_ALERT_DIGEST_TIME",
    "DIGEST_PENDING_DOSYA",
    "DIGEST_PENDING_SUPABASE_KEY",
    "DM_MIN_DEVLAMLILIK",
    "DeferredAlertBuffer",
    "Dict",
    "EVREN_BUYUME_UYARI_ESIGI",
    "FULL_1H_FETCH_PERIOD",
    "HEARTBEAT_MIN_ARALIK_SN",
    "HEARTBEAT_UZAK_ARALIK_SN",
    "ILERI_TEST_GECE_SAAT",
    "IMMEDIATE_ALERT_STATES",
    "INSTANCE_ID",
    "ISTANBUL_TZ",
    "KARNE_UZAK_YAZMA_ARALIK_SN",
    "KOMUT_YARDIM",
    "KarneDefteri",
    "LOCAL_LOG_DIR",
    "LOG_DIR",
    "List",
    "LiveState",
    "MORNING_PRELOAD_HOUR",
    "MORNING_PRELOAD_MINUTE",
    "OFFSESSION_CACHE_MAX_AGE_DAYS",
    "ORNEK_KONTROL_ARALIK_SN",
    "PANEL_DURUM_PUANI",
    "PANEL_IPUCU",
    "PANEL_MESAJ_SINIRI",
    "PANEL_TIMEFRAMES",
    "POST_CLOSE_ANALYSIS_TIME",
    "PROFILE",
    "PROFILE_PARAMS",
    "PUBLIC_MIN_QUALITY",
    "PatternLifecycleManager",
    "RENDER_EXTERNAL_URL",
    "ROUTINE_1H_FETCH_PERIOD",
    "SCAN_BATCH_PAUSE_MAX_SEC",
    "SCAN_BATCH_PAUSE_MIN_SEC",
    "SCAN_DELAY_AFTER_CLOSE_MIN",
    "SCAN_REQUEST_BATCH_SIZE",
    "SCAN_REQUEST_DELAY_MAX_SEC",
    "SCAN_REQUEST_DELAY_MIN_SEC",
    "SCAN_RETRY_BACKOFF_MAX_SEC",
    "SCAN_RETRY_BACKOFF_MIN_SEC",
    "SON_TARAMA_DOSYA",
    "SON_TARAMA_SUPABASE_KEY",
    "STALE_BAR_UYARI_DK",
    "STATE_TR",
    "SUMMARY_HOURS",
    "SUMMARY_MARKERS_SUPABASE_KEY",
    "StockDequeManager",
    "SupabaseStore",
    "TARAMA_SURESI_UYARI_DK",
    "TARAMA_UYARI_ESIK_TUR",
    "TEKRAR_SIFIRLA_STATELER",
    "TELEGRAM_KOMUTLARI",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_WEBHOOK_URL",
    "TERMINAL_TAZE_BAR",
    "TelegramCommandListener",
    "TelegramNotifier",
    "VERI_YOK_MODU_ESIK_DK",
    "WATCH_CONTEXT_HAVUZU",
    "WATCH_STATES",
    "YahooRequestPacer",
    "_CONFIRMED_INVALIDATION_REASONS",
    "_DOMAIN_TIMEFRAMES",
    "_GORELI_MUM",
    "_GRAFIK_GORUNUM",
    "_GRAFIK_HEDEF_SN",
    "_GRAFIK_SEMBOL",
    "_GRAFIK_TF",
    "_KALICI_SAYACLAR",
    "_LIFECYCLE_CONFIRMATION_TYPES",
    "_LIFECYCLE_EVENT_COUNTERS",
    "_MESAJ_GUVENLI_SINIR",
    "_POST_CLOSE_DIFF_LABELS",
    "_UST_TF",
    "_acil_kuyruk_acilista_isle",
    "_acil_kuyruk_gonderim_penceresi_acik",
    "_alarm_izni_var",
    "_alert_break_level",
    "_analiz_hatasi_kaydi",
    "_ardisik_basarisiz_tur",
    "_bekle_veya_tarama",
    "_bos_analiz_mesaji",
    "_break_ok",
    "_build_active_formations_for_summary",
    "_cache_verisi_kullanilabilir",
    "_calistir_istek_taramasi",
    "_capture_digest_lifecycle_baseline",
    "_cift_ornek_durumu",
    "_classified_lifecycle_events",
    "_closed_formation_event_confirmed",
    "_completed_domain_frames",
    "_daily_basarisiz_keys",
    "_daily_basarisiz_tabani",
    "_daily_lifecycle_event_keys",
    "_daily_pattern_keys",
    "_daily_summary_payload",
    "_daily_unannounced_invalidation_keys",
    "_deferred_alert_buffer",
    "_deque_manager_ref",
    "_digest_event_keys_snapshot",
    "_digest_pending_yolu",
    "_digest_son_gonderim_gun",
    "_domain_results_for_notification",
    "_domain_runner_cache",
    "_effective_summary_hours",
    "_endekse_gore_guc",
    "_event_bar_number",
    "_event_field",
    "_event_local_time",
    "_evren_olcek_uyarisi",
    "_filtrele_formasyonlar",
    "_format_deferred_alert_summary",
    "_format_post_close_diff_report",
    "_format_urgent_queue_summary",
    "_formation_history_baslangic_kontrolu",
    "_gece_denetim_son_gun",
    "_gece_denetimi",
    "_gece_onerisi_gonder",
    "_gece_raporu_yaz",
    "_gecen_sure",
    "_goreli_guc_satiri",
    "_grafik_aktif_is",
    "_grafik_is_kilidi",
    "_grafik_isi_calistir",
    "_grafik_isi_yurut",
    "_grafik_ozet_metni",
    "_grafikleri_tur_sonunda",
    "_gun_sayacini_gonderimle_hizala",
    "_gunluk_sayac_kaydet",
    "_gunluk_sayac_yukle",
    "_haftalik_karne_ekle",
    "_haftalik_karne_kisa",
    "_health_server_ref",
    "_heartbeat_icerik_ozeti",
    "_heartbeat_yasi_sn",
    "_heartbeat_yolu",
    "_ileri_test_gece",
    "_ileri_test_kaydet",
    "_ileri_test_son_gece",
    "_invalidation_confirmation_delivered",
    "_invalidation_event_for_snapshot",
    "_is_full_universe_scan",
    "_islem_gunu_loglandi",
    "_istek_tam_evrende_tamamlandi",
    "_kacirilan_digest_ozeti",
    "_kare_altyazisi",
    "_karne_al",
    "_karne_defteri",
    "_karne_dolu",
    "_karne_gonderildi_isaretle",
    "_karne_olay_kaydet",
    "_karne_outcome_bagla",
    "_karne_seri_saglayici",
    "_karne_son_uzak_yazma",
    "_karne_uzak_kaydet",
    "_karneyle_gonder",
    "_kayit_zamani",
    "_kisa_durum",
    "_kismi_kapsam_notu",
    "_komut_backtest",
    "_komut_canli",
    "_komut_durum",
    "_komut_durumu",
    "_komut_evet",
    "_komut_formasyonlar",
    "_komut_grafik",
    "_komut_hayir",
    "_komut_karne",
    "_komut_kirilim",
    "_komut_modu",
    "_komut_olcum",
    "_komut_oneri_cevabi",
    "_komut_ozet",
    "_komut_panel",
    "_komut_retest",
    "_komut_sikisanlar",
    "_komut_tamamlanan",
    "_komut_tara",
    "_komut_yardim",
    "_lifecycle_manager_ref",
    "_live_state",
    "_load_domain_runner",
    "_logging_kuruldu",
    "_manuel_tarama_istegi",
    "_manuel_tarama_tamamla",
    "_ms_hata_kaydet",
    "_ms_hata_satiri",
    "_ms_hata_sayaci",
    "_mum_bilgisi",
    "_note_basarisiz_kirilim",
    "_note_pattern_found",
    "_note_unannounced_invalidation",
    "_notifier_ref",
    "_onceki_sonuc_uyarisi",
    "_ozet_isaret_kaydet",
    "_ozet_isaretlerini_yukle",
    "_ozet_slot_gonderilmeli",
    "_panel_aday_puani",
    "_panel_durum_sayilari",
    "_panel_filtre_coz",
    "_panel_hucre",
    "_panel_kalite",
    "_panel_kritik_anahtar",
    "_panel_kritik_listesi",
    "_panel_raporu",
    "_panel_sembol",
    "_panel_sigdir",
    "_parse_deferred_alert_digest_time",
    "_parse_post_close_analysis_time",
    "_parse_summary_hours",
    "_public_turu_kapat",
    "_record_daily_lifecycle_events",
    "_render_test_sender",
    "_saglik_ozeti",
    "_sayi",
    "_scan_istegi",
    "_scan_job_active",
    "_scan_job_request",
    "_scan_last_result",
    "_scan_request_lock",
    "_shutdown_requested",
    "_son_heartbeat_icerik",
    "_son_heartbeat_uzak_zamani",
    "_son_heartbeat_zamani",
    "_son_tarama_data_dir",
    "_son_tarama_uyari_gun",
    "_son_tarama_yolu",
    "_sonuc_yok_mesaji",
    "_state_paths",
    "_state_persistence",
    "_successful_full_scan_today",
    "_supabase_store_ref",
    "_tarama_saglik_kontrolu",
    "_tekil_ornek_kontrolu",
    "_telegram_api_cagri",
    "_telegram_delete_webhook",
    "_telegram_komut_katmanini_kur",
    "_telegram_listener_ref",
    "_telegram_set_webhook",
    "_telegram_token_al",
    "_telegram_update_processor_ref",
    "_telegram_webhook_isle",
    "_telegram_webhook_kilidi",
    "_telegram_webhook_secret_ayikla",
    "_telegram_webhook_url_olustur",
    "_telegram_yanit_oku",
    "_tf_kisa",
    "_transport_telegram",
    "_veri_durumu_satiri",
    "_webhook_adres_gizle",
    "_yeni_snapshot",
    "ampirik",
    "atr_hesapla",
    "bar_kapandi_mi",
    "config",
    "create_yahoo_pacer",
    "daily_stats",
    "datetime",
    "devamlilik_puani",
    "digest_tamponu_kaydet",
    "digest_tamponu_yukle",
    "domain_bolumleri",
    "dt_time",
    "evening_maintenance",
    "fetch_1h_stocks_paced",
    "fetch_last_bar",
    "fetch_yfinance_1d",
    "fetch_yfinance_1h",
    "format_domain_context",
    "hafta_damgasi",
    "is_bist_open",
    "islem_gunu_mu",
    "json",
    "karne_gunu_mu",
    "karne_uret",
    "karsi_deliller",
    "last_run_stats",
    "logging",
    "main_loop",
    "math",
    "morning_preload",
    "mum_kapanis_ani",
    "os",
    "panel_raporu",
    "pd",
    "random",
    "re",
    "resample_all_timeframes",
    "resample_ohlcv",
    "reset_daily_if_needed",
    "scan_all_stocks",
    "select_yfinance_1h_period",
    "setup_logging",
    "signal",
    "signal_handler",
    "socket",
    "son_bar_yasi_dakika_str",
    "son_kapanan_mum_ani",
    "son_tarama_kaydet",
    "son_tarama_yukle",
    "start_render_health_server",
    "sys",
    "tamamlanmis_mumlar",
    "tarama_animi_mi",
    "tarama_penceresi_acik_mi",
    "threading",
    "time",
    "time_until_next_open",
    "timedelta",
    "write_heartbeat",
]
