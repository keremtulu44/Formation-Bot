# --- MAIN LOOP ---
# BIST Bot Ana Döngü - İskelet
# Henüz tam değil, adım adım doldurulacak
# Türkçe yorumlar: Neden uyuyor, neden tarıyor?

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


















































# === HAFTALIK DOĞRULUK KARNESİ ============================================
# Tasarım: sinyal defteri verileri tarama sırasında toplanır (scan_all_stocks),
# karne metni Cuma gün sonu mesajının ALTINA eklenir. Defter ve ölçüm TAMAMEN
# YERELDİR (DATA_DIR/karne_defteri.json) - Supabase/uzak store gerekmez.











































































if __name__ == "__main__":
    setup_logging()
    # HTTP sunucusu main_loop'tan ÖNCE başlar: Render'ın health check'i ilk veri
    # yüklemesi sürerken de yanıt verir. Webhook modunda güncellemeler bu sunucudan
    # gelir; bot komutları kurana kadar /webhook 503 döner (Telegram tekrar dener).
    _health_server_ref = start_render_health_server(
        test_sender=_render_test_sender,
        webhook_handler=_telegram_webhook_isle,
        webhook_secret=TELEGRAM_WEBHOOK_SECRET,
        # Denetim B-4: /health botun canlılığını da raporlasın (heartbeat yaşı).
        health_provider=_saglik_ozeti,
    )
    if os.getenv("BOT_HEALTH_SMOKE_ONLY") == "1":
        # CI liveness dumanı (Render parity): yalnız HTTP sunucusu ayakta kalsın.
        # Notifier kurulmaz, Telegram/Supabase'e istek gitmez, Yahoo fetch ve ana
        # tarama döngüsü BAŞLAMAZ — CI'nın dışa bağımlı olmadan gerçek entrypoint'ı
        # denemesi için tek güvenlik kapısı budur.
        logger.info("Health smoke mode: provider and command loops disabled")
        while not _shutdown_requested:
            time.sleep(0.25)
    else:
        main_loop()
