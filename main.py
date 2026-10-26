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

# === LOGGING KURULUMU ===
# Batch 8 / C2: bu fonksiyon artık IMPORT anında ÇAĞRILMAZ (yan etki kaldırıldı:
# modül import edildiğinde log dizini oluşturulmuyor/`/var/log` denenmiyordu).
# `main_loop()` ve `python main.py` girişi kurulumu kendisi yapar.
_logging_kuruldu = False


def setup_logging():
    """Log hem console hem dosyaya - Türkçe mesajlar (tek seferlik)."""
    global _logging_kuruldu
    if _logging_kuruldu:
        return logging.getLogger(__name__)
    # Local mi prod mu? LOG_DIR (/var/log/bist-bot) GERÇEKTEN yazılabilir mi?
    # Not: /var/log'un kendisine bakmak yetmez (root dışında yazılamaz) -
    # LOG_DIR'e yazma testi yapılmalı, yoksa sunucuda loglar ./logs'a düşer.
    log_dir = LOG_DIR
    try:
        os.makedirs(log_dir, exist_ok=True)
        test_path = os.path.join(log_dir, ".write_test")
        with open(test_path, "w") as f:
            f.write("test")
        os.remove(test_path)
    except Exception:
        log_dir = LOCAL_LOG_DIR
        os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "bot.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    _logging_kuruldu = True
    logger = logging.getLogger(__name__)
    logger.info(f"Logging kuruldu - dosya: {log_file} - profil: {PROFILE}")
    return logger

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





def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Sinyal alındı: {signum} - güvenli kapanış hazırlanıyor...")
    _shutdown_requested = True

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










































def _ozet_isaretlerini_yukle() -> tuple:
    """Kalıcı özet işaretlerini okur: (dm_isaretleri, public_isaretleri).

    Anahtarlar `{"09:55": date}` biçimindedir; public işaretleri dosyada
    "public:" önekiyle ayrılır (aynı slot adı iki yayın yolunda da var).
    Bozuk kayıtlar sessizce atlanır; hiçbir okuma hatası botu durdurmaz.
    """
    dm: Dict[str, object] = {}
    public: Dict[str, object] = {}
    try:
        ham = (_state_persistence.gunluk_durum_yukle() or {}).get("ozet_gunleri") or {}
        for anahtar, deger in ham.items():
            try:
                gun = datetime.fromisoformat(str(deger)).date()
            except (TypeError, ValueError):
                continue
            ad = str(anahtar)
            if ad.startswith("public:"):
                public[ad.split(":", 1)[1]] = gun
            else:
                dm[ad] = gun
        # Ephemeral instance restart/replace durumlarında da slot mühürü kalsın.
        store = _supabase_store_ref
        if store is not None and hasattr(store, "get_many"):
            remote = store.get_many([SUMMARY_MARKERS_SUPABASE_KEY])
            remote_markers = (remote or {}).get(SUMMARY_MARKERS_SUPABASE_KEY)
            if isinstance(remote_markers, dict):
                for anahtar, deger in remote_markers.items():
                    try:
                        gun = datetime.fromisoformat(str(deger)).date()
                    except (TypeError, ValueError):
                        continue
                    ad = str(anahtar)
                    if ad.startswith("public:"):
                        slot = ad.split(":", 1)[1]
                        public[slot] = max(public.get(slot, gun), gun)
                    else:
                        dm[ad] = max(dm.get(ad, gun), gun)
        if dm or public:
            logger.info("Günlük özet işaretleri geri yüklendi: DM=%s public=%s",
                        sorted(dm), sorted(public))
    except Exception as hata:  # noqa: BLE001 - kalıcılık hatası botu durdurmaz
        logger.warning("Özet işaretleri okunamadı: %s", hata)
    return dm, public


def _ozet_slot_gonderilmeli(isaretler: dict, slot: str, gun) -> bool:
    """Aynı DM/public özet slotunu aynı İstanbul gününde ikinci kez gönderme."""
    gun_tarihi = gun.date() if isinstance(gun, datetime) else gun
    isaret = (isaretler or {}).get(str(slot))
    if isinstance(isaret, str):
        try:
            isaret = datetime.fromisoformat(isaret).date()
        except (TypeError, ValueError):
            isaret = None
    elif isinstance(isaret, datetime):
        isaret = isaret.date()
    return isaret != gun_tarihi


def _ozet_isaret_kaydet(slot: str, gun, public: bool = False) -> None:
    """'Şu özet gönderildi' işaretini diske ve varsa Supabase'a yazar.

    Restart/instance replacement sonrası aynı slot özetinin ikinci kez gitmesini
    önlemek için yerel ve uzak işaret birlikte tutulur.
    """
    try:
        anahtar = f"public:{slot}" if public else str(slot)
        veri = _state_persistence.gunluk_durum_yukle() or {}
        isaretler = dict(veri.get("ozet_gunleri") or {})
        deger = str(getattr(gun, "isoformat", lambda: gun)())
        isaretler[anahtar] = deger
        _state_persistence.gunluk_durum_guncelle({"ozet_gunleri": isaretler})
        store = _supabase_store_ref
        if store is not None and hasattr(store, "upsert"):
            remote_markers = dict(isaretler)
            try:
                remote = store.get_many([SUMMARY_MARKERS_SUPABASE_KEY]) if hasattr(store, "get_many") else None
                existing = (remote or {}).get(SUMMARY_MARKERS_SUPABASE_KEY)
                if isinstance(existing, dict):
                    for remote_key, remote_value in existing.items():
                        remote_key = str(remote_key)
                        try:
                            remote_date = datetime.fromisoformat(str(remote_value)).date()
                            local_date = datetime.fromisoformat(
                                str(remote_markers.get(remote_key) or remote_value)
                            ).date()
                        except (TypeError, ValueError):
                            remote_markers.setdefault(remote_key, remote_value)
                            continue
                        remote_markers[remote_key] = max(local_date, remote_date).isoformat()
            except Exception as remote_error:  # noqa: BLE001 - yerel işaret korunur
                logger.debug("Supabase özet işareti okunamadı: %s", remote_error)
            remote_markers[anahtar] = deger
            if not store.upsert(SUMMARY_MARKERS_SUPABASE_KEY, remote_markers):
                logger.debug("Supabase özet işareti yazılamadı (%s)", slot)
    except Exception as hata:  # noqa: BLE001
        logger.debug("Özet işareti yazılamadı (%s): %s", slot, hata)


def _public_turu_kapat(notifier) -> None:
    """Tarama turu sonu: tur sayacını artır + public kuyruğunu bültende boşalt.

    Bülten gönderimi taramayı ASLA durdurmaz (dış servis hatası tarama sonucunu
    geçersiz kılmamalı); hata yalnız loglanır, kayıtlar kuyrukta kalır.
    """
    daily_stats['tarama_sayisi'] = int(daily_stats.get('tarama_sayisi') or 0) + 1
    _gunluk_sayac_kaydet()
    try:
        if notifier is not None:
            notifier.public_bosalt()
    except Exception as public_hata:  # noqa: BLE001 - bülten hatası taramayı durdurmasın
        logger.warning("Public bülten gönderilemedi: %s", public_hata)
































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














































def _parse_summary_hours() -> List[dt_time]:
    """SUMMARY_HOURS env'ini İstanbul saatine çevir (09:55,18:45)."""
    try:
        saatler = []
        for ham in SUMMARY_HOURS.split(","):
            ham = ham.strip()
            if not ham:
                continue
            h, m = ham.split(":")
            saatler.append(dt_time(int(h), int(m)))
        return saatler
    except Exception:
        return [dt_time(9, 55), dt_time(18, 45)]


def _parse_deferred_alert_digest_time() -> dt_time:
    """Kapanış özeti en erken son otomatik tarama sonrasına (18:45) ayarlanır."""
    try:
        h, m = DEFERRED_ALERT_DIGEST_TIME.split(":")
        saat = dt_time(int(h), int(m))
        if saat < dt_time(18, 45):
            logger.warning("DEFERRED_ALERT_DIGEST_TIME son taramadan önce; 18:45'e alındı")
            return dt_time(18, 45)
        return saat
    except Exception:
        logger.warning("DEFERRED_ALERT_DIGEST_TIME geçersiz; 18:45 kullanılacak")
        return dt_time(18, 45)


# === HAFTALIK DOĞRULUK KARNESİ ============================================
# Tasarım: sinyal defteri verileri tarama sırasında toplanır (scan_all_stocks),
# karne metni Cuma gün sonu mesajının ALTINA eklenir. Defter ve ölçüm TAMAMEN
# YERELDİR (DATA_DIR/karne_defteri.json) - Supabase/uzak store gerekmez.



def _karne_uzak_kaydet(zorla: bool = False) -> bool:
    """Defteri (varsa) uzak yedeğe yazar. Sık yazmamak için aralık uygulanır.

    Yerel dosya her kayıtta zaten yazılır; bu yalnız dayanıklılık içindir.
    """
    global _karne_son_uzak_yazma
    if _supabase_store_ref is None or _karne_defteri is None:
        return False
    simdi = time.monotonic()
    if not zorla and (simdi - _karne_son_uzak_yazma) < KARNE_UZAK_YAZMA_ARALIK_SN:
        return False
    sonuc = _state_persistence.karne_defteri_kaydet(_karne_defteri, _supabase_store_ref)
    if sonuc:
        _karne_son_uzak_yazma = simdi
    return sonuc


def _karne_seri_saglayici(deque_manager):
    """Karne ölçümü için seri sağlayıcı: yeni veri indirmez, cache'i okur.

    Kırılım kaydı hangi TF'de alındıysa o TF'in serisi kullanılır (1d için derin
    günlük deque, diğerleri için 1H deque).
    """
    def saglayici(stock: str, tf: str):
        if deque_manager is None:
            return None
        try:
            if str(tf).lower() == "1d":
                return deque_manager.to_gunluk_dataframe(stock)
            return deque_manager.to_dataframe(stock)
        except Exception as exc:  # noqa: BLE001 - ölçüm hatası karneyi düşürmesin
            logger.debug("Karne serisi alınamadı (%s %s): %s", stock, tf, exc)
            return None
    return saglayici


def _karne_olay_kaydet(stock: str, tf: str, state: str, pattern: str, quality: float,
                       bar_zamani, *, kirilim: bool = False, dir: int = 0,
                       entry=None, df_tf=None, mtf_destek: bool = False,
                       stable_id=None) -> None:
    """Tarama sırasında karne defterine kayıt düşer (hatalar taramayı durdurmaz)."""
    try:
        defter = _karne_al()
        if kirilim:
            defter.kirilim_kaydet(
                stock=stock, tf=tf, pattern=pattern, state=state, dir=dir,
                entry=entry, atr=atr_hesapla(df_tf), quality=quality,
                bar_zamani=bar_zamani, mtf_destek=mtf_destek, stable_id=stable_id,
            )
        elif state == "FORMASYON_TANIMLANDI" or state in ("SIKISMA_GUCLENIYOR", "KIRILIM_HAZIRLIGI"):
            # Yalnız anlamlı olgunluk eşiği: her aday state'i sayılmaz.
            defter.formasyon_kaydet(stock=stock, tf=tf, pattern=pattern, state=state,
                                    quality=quality, bar_zamani=bar_zamani,
                                    stable_id=stable_id)
        elif state in ("RETEST_BASARILI", "FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM"):
            defter.olay_kaydet(stock=stock, tf=tf, state=state, bar_zamani=bar_zamani,
                               stable_id=stable_id)
        # --- Faz 2.5: outcome linkage (okuma tarafı) ---
        # Karne matematiği DEĞİŞMEZ: burada yalnızca mevcut `sinyal_sonucu()`
        # çağrılır ve sonucu `stable_id` üzerinden formation history'ye bağlanır.
        # Yeni kırılım yoksa da çağrılır: ufuk dolduğunda `bekliyor` -> çözümlenmiş
        # geçişini yakalamak için (yazma yalnızca sonuç değiştiğinde olur).
        _karne_outcome_bagla(stock, tf, stable_id, df_tf)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Karne kaydı yazılamadı (%s %s %s): %s", stock, tf, state, exc)


def _karne_outcome_bagla(stock: str, tf: str, stable_id, df_tf=None):
    """Faz 2.5: outcome'ı formation history'ye bağlar (mevcut motoru kullanır).

    stable_id yoksa (eski kayıt) hiçbir şey yapmaz — geriye dönük uyumluluk.
    Seri sağlayıcı olarak bu slotun kendi df_tf'i verilir; `sinyal_sonucu`
    tam olarak `karne_hesapla`'nın yaptığı gibi çağrılır.
    """
    if not stable_id:
        return None
    try:
        from state import outcome_link
        defter = _karne_al()
        return outcome_link.bagla(defter, stock, tf, stable_id,
                                  saglayici=lambda s, t: df_tf)
    except Exception as exc:  # noqa: BLE001 - linkage taramayi asla durdurmaz
        logger.debug("Outcome bağlantısı kurulamadı (%s %s): %s", stock, tf, exc)
        return None


def _karne_dolu(defter: KarneDefteri, now: datetime) -> bool:
    """Bu hafta için karnede gösterilecek en az bir kayıt var mı?"""
    try:
        from karne import hafta_baslangici
        return bool(defter.aralikta(hafta_baslangici(now), now))
    except Exception:  # noqa: BLE001
        return False


def _haftalik_karne_ekle(now: datetime, deque_manager, zorla: bool = False) -> str:
    """Karne günüyse ve bu hafta gönderilmediyse karne metnini döner; yoksa ''.

    `zorla=True` -> gün/hafta kapıları atlanır (yalnız açıkça isteyen çağrı için).
    Karne, gün sonu mesajının ALTINA eklenir; burada gönderim YAPILMAZ.
    """
    try:
        hafta = hafta_damgasi(now)
        defter = _karne_al()
        if not zorla:
            if not karne_gunu_mu(now):
                return ""
            if defter.karne_gonderildi_mi(hafta):
                return ""
        if not _karne_dolu(defter, now):
            # Hiç kayıt yoksa boş karne gönderme (hafta başı / yeni kurulum).
            return ""
        return karne_uret(defter, _karne_seri_saglayici(deque_manager), now=now)
    except Exception as exc:  # noqa: BLE001 - karne hatası özeti engellemesin
        logger.warning("Haftalık karne üretilemedi: %s", exc)
        return ""


def _haftalik_karne_kisa(now: datetime, deque_manager) -> str:
    """Karne metninin PUBLIC (grup) sürümü: 4-5 satır.

    Tam metin teknik döküm (defter satırı, hedef/nötr/stop, dosya yolu) taşır ve
    gruba uygun değildir; kısa sürüm aynı ölçümü sade dille verir.
    """
    try:
        defter = _karne_al()
        if not _karne_dolu(defter, now):
            return ""
        from karne import hafta_baslangici, karne_hesapla, karne_kisa_metni, pencere
        baslangic = hafta_baslangici(now)
        kayitlar = defter.aralikta(baslangic, now)
        metrik = karne_hesapla(kayitlar, _karne_seri_saglayici(deque_manager), now=now)
        return karne_kisa_metni(metrik, pencere(baslangic, now))
    except Exception as exc:  # noqa: BLE001 - kısa karne özeti engellemesin
        logger.debug("Kısa karne üretilemedi: %s", exc)
        return ""


def _karne_gonderildi_isaretle(now: datetime) -> None:
    """Karne başarıyla gönderildi -> bu hafta tekrar eklenmez (kalıcı)."""
    try:
        _karne_al().karne_gonderildi_isaretle(hafta_damgasi(now))
        # Haftalık işaret + kayıtlar restart'ta kaybolmasın: yedeği hemen tazele.
        _karne_uzak_kaydet(zorla=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Karne gönderim işareti yazılamadı: %s", exc)




def _karneyle_gonder(notifier, ana_mesaj: str, karne_ek: str = ""):
    """Ana mesajı (ve varsa karneyi) Telegram sınırına takılmadan gönderir.

    Karne normalde ana mesajın ALTINA eklenir; sığmıyorsa kesilmek yerine ayrı
    mesaj olarak gönderilir.

    Döner: (ana_gitti, karne_gitti, son_hata).
    NEDEN parça bazlı: "karne iki kez gitti" hatasının kökü, gönderim sonucunun
    tek bayrak olmasıydı. Karne ayrı mesajken başarısız olursa işaret konmuyor,
    ana özet de "gitmedi" sayıldığı için döngü onu tekrar yolluyordu. Artık ana
    özet ve karne AYRI izlenir; karne tekrarı imkânsız hale gelir.
    """
    if karne_ek and len(ana_mesaj) + len(karne_ek) + 2 <= _MESAJ_GUVENLI_SINIR:
        parcalar = [(ana_mesaj + "\n\n" + karne_ek, "ikisi")]
    elif karne_ek:
        logger.info("Karne mesaj sınırını aştı; ayrı mesaj olarak gönderiliyor (%d + %d kr)",
                    len(ana_mesaj), len(karne_ek))
        parcalar = [(ana_mesaj, "ana"), (karne_ek, "karne")]
    else:
        parcalar = [(ana_mesaj, "ana")]
    ana_ok, karne_ok, hata = False, False, ""
    for parca, tur in parcalar:
        # Satır bütçesi `notifier.send_text` içinde uygulanır (tek nokta).
        ok, parca_hata = notifier.send_text(parca)
        if ok:
            if tur in ("ana", "ikisi"):
                ana_ok = True
            if tur in ("karne", "ikisi"):
                karne_ok = True
        else:
            hata = parca_hata or hata
            # Ana mesaj gitmediyse karneyi denemenin anlamı yok; parça sırası
            # gereği burada zaten karne denenmemiş olur.
            break
    return ana_ok, karne_ok, hata




def _gun_sayacini_gonderimle_hizala(stock, timeframe, state):
    """Gönderilen alarmın state'ini gün sayacına yansıt (yalnız eksikse).

    Neden: sayaçlar yalnız o günkü lifecycle OLAY listesinden doldurulur
    (`_record_daily_lifecycle_events`). Önceki güne ait bir teyidin retesti
    bugün gönderildiğinde (25 Eyl: HALKB 4s RETEST BAŞARILI) olay listesinde
    karşılığı yoktur ve özet "0 başarılı retest" yazıp aynı gün alarm göndermiş
    olurdu. Burada yalnız "bugün için hiç sayılmamışsa" tek artış yapılır;
    aynı (hisse, TF, state) için ikinci gönderim sayacı şişirmez.
    """
    anahtar = f"GONDERIM|{stock}|{timeframe}|{state}"
    if anahtar in _daily_lifecycle_event_keys:
        return
    counter = _LIFECYCLE_EVENT_COUNTERS.get(str(state or "").strip().upper())
    if not counter:
        return
    # Olay yolunun yazdığı anahtar: STOCK|tf|kimlik|state|tür|zaman
    for kayit in _daily_lifecycle_event_keys:
        parcalar = str(kayit).split("|")
        if len(parcalar) < 4 or parcalar[0] == "GONDERIM":
            continue
        if (parcalar[0] == str(stock).upper() and parcalar[1] == str(timeframe).lower()
                and parcalar[3] == str(state or "").strip().upper()):
            return
    _daily_lifecycle_event_keys.add(anahtar)
    daily_stats[counter] = int(daily_stats.get(counter) or 0) + 1
    _gunluk_sayac_kaydet()


def _daily_summary_payload(now=None) -> dict:
    """Daily counters plus freshness metadata for Telegram summaries."""
    now = now or datetime.now(ISTANBUL_TZ)
    payload = dict(daily_stats)
    try:
        status = _live_state.status() or {}
    except Exception:  # noqa: BLE001 - summary still works without live status
        status = {}
    full_at = status.get("son_basarili_tam_tarama")
    # Backward compatibility with snapshots created before the dedicated stamp.
    if not full_at:
        try:
            expected = int(status.get("son_tarama_beklenen_hisse") or 0)
            processed = int(status.get("son_tarama_hissesi") or 0)
            if (status.get("son_tarama_durumu") == "tamamlandi"
                    and expected >= len(ACTIVE_STOCKS)
                    and processed >= len(ACTIVE_STOCKS)):
                full_at = status.get("son_tarama_bitis")
        except (TypeError, ValueError, OverflowError):
            full_at = None
    payload["son_basarili_tam_tarama"] = full_at
    payload["tam_tarama_guncel"] = _successful_full_scan_today(now)
    payload["son_tarama_durumu"] = status.get("son_tarama_durumu")
    # "N bildirim" satırı yalnız tarama turunda gidenleri sayıyordu; cooldown/kap
    # yüzünden kuyruğa giren ve sonra gönderilen alarm sayılmıyordu (25 Eyl:
    # 6 mesaj gönderildi, özet "5 bildirim" dedi). Kuyruk sayacı da eklenir.
    # payload kopya olduğu için /durum ve kalıcı sayaç davranışı değişmez.
    try:
        _nref = _notifier_ref
        kuyruk_giden = int(getattr(_nref, "kuyruk_gonderildi", 0) or 0) if _nref else 0
    except Exception:  # noqa: BLE001 - özet, sayaç yüzünden düşmez
        kuyruk_giden = 0
    if kuyruk_giden:
        payload["alerts_sent"] = int(payload.get("alerts_sent") or 0) + kuyruk_giden
    return payload


def _successful_full_scan_today(now: datetime) -> bool:
    """True only when the latest full-universe scan completed today."""
    try:
        status = _live_state.status()
        if status.get("son_tarama_durumu") != "tamamlandi":
            return False
        expected = int(status.get("son_tarama_beklenen_hisse") or
                      status.get("son_is_hisse_istek") or 0)
        processed = int(status.get("son_tarama_hissesi") or
                        status.get("son_is_hisse_basarili") or 0)
        if expected < len(ACTIVE_STOCKS) or processed < len(ACTIVE_STOCKS):
            return False
        raw_finished = status.get("son_tarama_bitis") or status.get("son_is_bitis")
        if not raw_finished:
            return False
        finished = datetime.fromisoformat(str(raw_finished).replace("Z", "+00:00"))
        if finished.tzinfo is None:
            finished = ISTANBUL_TZ.localize(finished)
        else:
            finished = finished.astimezone(ISTANBUL_TZ)
        local_now = (ISTANBUL_TZ.localize(now) if now.tzinfo is None
                     else now.astimezone(ISTANBUL_TZ))
        return finished.date() == local_now.date()
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def _effective_summary_hours() -> List[dt_time]:
    """Akşam özetini son tarama sonrasına al; eski 18:15 saatiyle çakıştırma."""
    digest_time = _parse_deferred_alert_digest_time()
    morning_and_day = [hour for hour in _parse_summary_hours() if hour.hour < 18]
    return sorted(set(morning_and_day + [digest_time]))


def _acil_kuyruk_gonderim_penceresi_acik(simdi: datetime, digest_saati: dt_time) -> bool:
    """Acil kuyruğu digest'ten 2 dk önce kapat; ağ kuyruğu özeti geciktirmesin."""
    try:
        yerel = (ISTANBUL_TZ.localize(simdi) if simdi.tzinfo is None
                 else simdi.astimezone(ISTANBUL_TZ))
        kesim = datetime.combine(yerel.date(), digest_saati) - timedelta(minutes=2)
        return yerel.replace(tzinfo=None) < kesim
    except (AttributeError, TypeError, ValueError):
        return False


def _acil_kuyruk_acilista_isle(notifier, simdi: datetime, digest_saati: dt_time,
                                kapanis_ozeti_gonderildi: bool = False) -> int:
    """Açılışta kuyruğu aç; digest sonrası eski push'ı bireysel gönderme."""
    try:
        if (notifier is None or not getattr(notifier, "enabled", False)
                or not notifier.kuyruk_durumu().get("bekleyen")):
            return 0
        if _acil_kuyruk_gonderim_penceresi_acik(simdi, digest_saati):
            return int(notifier.kuyrugu_bosalt() or 0)
        if kapanis_ozeti_gonderildi:
            temizle = getattr(notifier, "kuyruk_tumunu_temizle", None)
            atlanan = int(temizle() or 0) if callable(temizle) else 0
            if atlanan:
                logger.warning(
                    "Kapanış özeti zaten gönderilmiş; %d bekleyen acil bildirim "
                    "geç saatte ayrı push olmasın diye kuyruktan çıkarıldı.", atlanan)
        # Kapanış özeti henüz gönderilmediyse olaylar özete eklenmek üzere tutulur.
        return 0
    except Exception as hata:  # noqa: BLE001 - kuyruk hatası açılışı düşürmesin
        logger.debug("Açılış kuyruk politikası uygulanamadı: %s", hata)
        return 0







def _kacirilan_digest_ozeti(notifier, simdiki_zaman) -> str:
    """Geçmiş günden kalan bekleyen adaylar için kaçırılan 18:45 telafisi.

    Bot akşam 18:45'te kapalıysa tampon bir sonraki açılışa kadar bekler;
    burada tek seferde gönderilir (aksi halde _ensure_day ilk taramada temizler).
    """
    global _digest_son_gonderim_gun
    gun = _deferred_alert_buffer.gun()
    if not _deferred_alert_buffer or gun is None or gun >= simdiki_zaman.date():
        return ""
    bekleyen = _deferred_alert_buffer.items(
        ISTANBUL_TZ.localize(datetime.combine(gun, dt_time(23, 59))),
        limit=DEFERRED_ALERT_DIGEST_LIMIT,
    )
    if not bekleyen:
        return ""
    watch_summary = _format_deferred_alert_summary(bekleyen, len(_deferred_alert_buffer))
    metin = f"⏰ Kaçırılan kapanış özeti ({gun.strftime('%d.%m')} 18:45)\n{watch_summary}"
    if notifier is None or not notifier.enabled:
        # Pasif modda sessizce düşmesin: bir sonraki açılışta tekrar denenmeyecek,
        # bu yüzden kayıt yine de temizlenir ve durum loglanır.
        logger.warning("Kaçırılan kapanış özeti gönderilemedi (Telegram pasif): %d aday", len(bekleyen))
    else:
        gonderildi, hata = notifier.send_text(metin)
        if gonderildi:
            _deferred_alert_buffer.mark_reported(bekleyen, simdiki_zaman)
            # Telafi edilen gün "gönderildi" sayılır; bugünün 18:45'i hâlâ bekliyor.
            _digest_son_gonderim_gun = gun.isoformat()
            logger.info("Kaçırılan kapanış özeti gönderildi: %d aday (%s)", len(bekleyen), gun)
        else:
            logger.warning("Kaçırılan kapanış özeti gönderilemedi: %s", hata)
    _deferred_alert_buffer.clear(simdiki_zaman)
    digest_tamponu_kaydet()
    return metin


def _parse_post_close_analysis_time() -> dt_time:
    """Gün sonu tam tarama saatini İstanbul yerel saati olarak çöz."""
    try:
        hour, minute = POST_CLOSE_ANALYSIS_TIME.strip().split(":", 1)
        return dt_time(int(hour), int(minute))
    except (AttributeError, TypeError, ValueError):
        logger.warning("POST_CLOSE_ANALYSIS_TIME geçersiz; 20:00 kullanılacak")
        return dt_time(20, 0)






def _format_post_close_diff_report(new_event_keys, active_formations=None) -> str:
    """V2: 18:45 özeti sonrasında oluşan yeni teyit/geçersizleşmeler için kısa fark raporu."""
    keys = [str(k) for k in (new_event_keys or []) if k]
    if not keys:
        return ""
    pattern_lookup = {}
    for item in (active_formations or []):
        if not isinstance(item, dict):
            continue
        st = str(item.get("stock_name") or item.get("stock") or "").strip().upper()
        tf = str(item.get("timeframe") or "").strip().lower()
        pat = str(item.get("pattern_name") or "").strip()
        if st and tf and pat:
            pattern_lookup[(st, tf)] = pat
    satirlar = []
    gorulen = set()
    for raw_key in sorted(keys):
        parcalar = raw_key.split("|")
        if len(parcalar) < 4:
            continue
        stock, tf, ident, state_key = parcalar[0], parcalar[1], parcalar[2], parcalar[3]
        dedup_k = (stock, tf, ident, state_key)
        if dedup_k in gorulen:
            continue
        gorulen.add(dedup_k)
        etiket = _POST_CLOSE_DIFF_LABELS.get(state_key, state_key)
        pat = pattern_lookup.get((stock, tf))
        orta = f" · {pat}" if pat else ""
        satirlar.append(f"• {stock} {tf}{orta} · {etiket}")
    if not satirlar:
        return ""
    return (
        f"🌙 GÜN SONU ANALİZİ · 18:45 Sonrası Fark ({len(satirlar)} gelişme)\n"
        + "\n".join(satirlar)
    )


def _build_active_formations_for_summary(lifecycle_manager, min_quality: float = None) -> List[Dict]:
    """Özet için aktif formasyonları topla (canlı + taze terminal)."""
    if min_quality is None:
        min_quality = PUBLIC_MIN_QUALITY
    aktif = []
    try:
        # Özet ile /panel AYNI kaynaktan beslenir: son başarılı taramanın canlı
        # listesi. (Eski kod olmayan bir metodu -get_formations- hasattr ile
        # yoklayıp her zaman lifecycle snapshots yoluna düşüyordu; sonuç: özet ile
        # panel farklı listeler gösterebiliyordu.)
        formations = _live_state.formations()
        # LiveState boşsa (ilk tarama öncesi) lifecycle_manager snapshots'a düş.
        if not formations:
            for key, snap in getattr(lifecycle_manager, 'last_snapshots', {}).items():
                if snap.active and snap.effective_quality and snap.effective_quality >= min_quality:
                    # stock_timeframe key'ini ayır
                    parts = key.rsplit("_", 1)
                    stock = parts[0] if len(parts) == 2 else key
                    tf = parts[1] if len(parts) == 2 else "1h"
                    aktif.append({
                        'stock_name': stock,
                        'timeframe': tf,
                        'pattern_name': snap.active.pattern_type,
                        'state': snap.state,
                        'confidence_score': snap.effective_quality,
                        'contraction': getattr(snap.active, 'contraction', None),
                        'break_dir': snap.break_dir,
                    })
        else:
            for f in formations:
                if f.get('quality', 0) >= min_quality:
                    aktif.append({
                        'stock_name': f.get('stock'),
                        'timeframe': f.get('timeframe'),
                        'pattern_name': f.get('pattern_name'),
                        'state': f.get('state'),
                        'confidence_score': f.get('quality'),
                        # Daralma gerçek kayıttan gelir; eskiden sabit None
                        # yazılıyordu ve özetin "⚡ SIKIŞANLAR" bölümü sessizce
                        # boşalıyordu (karşılaştırma: contraction >= eşik).
                        'contraction': f.get('contraction'),
                        'break_dir': f.get('break_dir', 0),
                    })
    except Exception as e:
        logger.debug(f"Özet için formasyon toplanamadı: {e}")
    return aktif


def evening_maintenance(deque_manager, lifecycle_manager):
    """18:10-19:00 kapanış bakımı - 3 problem için tek seferlik hafif iş."""
    logger.info("=== AKŞAM BAKIMI BAŞLIYOR (veri hijyeni + state temizliği + rapor) ===")
    try:
        # 1. Veri hijyeni: hacmi 0 veya zaman damgası hatalı son barları temizle
        temizlenen = 0
        for stock in ACTIVE_STOCKS:
            try:
                df = deque_manager.to_dataframe(stock)
                if df is not None and len(df) > 0:
                    # Son bar hacmi 0 ise ve gün içinde eksik kalmışsa
                    son = df.iloc[-1]
                    if son.get('volume', 1) == 0:
                        # Sadece logla, silme değil - data.py zaten filtreliyor
                        logger.debug(f"{stock}: son bar hacim 0 - hijyen logu")
                        temizlenen += 1
            except Exception as e:
                logger.debug(f"{stock} hijyen hatası: {e}")
        logger.info(f"Veri hijyeni: {temizlenen} hisse kontrol edildi")

        # 2. State temizliği: 48 saatten uzun süredir kırılım yapmamış dosyalar
        # lifecycle_manager zaten terminal tazelik kontrolü yapıyor, burada disk temizliği
        try:
            import glob
            from config import DATA_DIR
            import os
            json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if len(json_files) > 100:
                logger.warning(f"bot_data'da {len(json_files)} dosya var, şişme riski - Supabase kullanılıyor mu kontrol et")
        except Exception as e:
            logger.debug(f"State temizliği atlandı: {e}")

        # 3. Gün sonu raporu
        try:
            rapor = _live_state.status() if hasattr(_live_state, 'status') else {}
            logger.info(f"GÜN SONU RAPORU: {rapor}")
            # Telegram özeti burada GÖNDERİLMEZ: 18:45 scheduler aynı günün
            # tek DM/public özetini başarıyla tamamlanmış tarama sonrasında yollar.
            # Bakım sonucu log'da kalır; aksi halde 18:10-18:59 aralığında ikinci
            # ve tarama öncesi bir "Gün Sonu Bakım Raporu" oluşuyordu.
        except Exception as e:
            logger.warning(f"Gün sonu raporu hatası: {e}")

        logger.info("=== AKŞAM BAKIMI BİTTİ ===")
    except Exception as e:
        logger.error(f"Akşam bakımı hatası: {e}", exc_info=True)


def morning_preload(deque_manager, pacer):
    """08:30 pre-load - açılışta 0-latency için son barları yavaşça çek."""
    logger.info("=== SABAH ÖN-YÜKLEME BAŞLIYOR (08:30) ===")
    try:
        for stock in ACTIVE_STOCKS[:10]:  # ilk 10 hisse, yavaşça
            if _shutdown_requested:
                break
            try:
                with pacer.request(f"{stock} preload"):
                    taze = fetch_last_bar(stock)
                if taze is not None and len(taze) > 0:
                    deque_manager.append_dataframe(stock, taze)
                    logger.debug(f"{stock}: preload {len(taze)} bar")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"{stock} preload hatası: {e}")
        logger.info("=== SABAH ÖN-YÜKLEME BİTTİ ===")
    except Exception as e:
        logger.error(f"Sabah preload hatası: {e}", exc_info=True)




def _ileri_test_kaydet(alert_data) -> None:
    """Gönderilen uyarıyı gölge deftere yazar. Hata botu DURDURMAZ."""
    try:
        import ileri_test
        ileri_test.kaydet(alert_data, store=_supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - ölçüm kaydı botu düşürmemeli
        logger.debug("İleri test kaydı atlandı: %s", exc)


def _ileri_test_gece(now: datetime) -> None:
    """Günde bir kez, kapanıştan sonra olgunlaşan kayıtların sonucunu hesaplar."""
    global _ileri_test_son_gece
    if now.hour < ILERI_TEST_GECE_SAAT:
        return
    gun = now.date().isoformat()
    if _ileri_test_son_gece == gun:
        return
    try:
        import ileri_test
        cikti = ileri_test.gece(store=_supabase_store_ref,
                                rapor_yolu=os.path.join(config.DATA_DIR,
                                                        "ileri_test_ozet.md"))
        _ileri_test_son_gece = gun
        logger.info("İleri test gece işi tamam: %s", cikti["istatistik"])
        logger.info("İleri test özeti:\n%s", cikti["ozet"])
    except Exception as exc:  # noqa: BLE001 - gece işi ana döngüyü düşürmemeli
        logger.warning("İleri test gece işi başarısız: %s", exc)




def _gece_raporu_yaz(gun: str, tutarlilik: dict, olcum: dict) -> bool:
    """`gece_raporu` tablosuna gün anahtarıyla tek satır yazar. Hata işi düşürmez."""
    store = _supabase_store_ref
    if store is None:
        return False
    try:
        cevap = store.request_table(
            "gece_raporu", "POST",
            json={"gun": gun, "tutarlilik": tutarlilik, "olcum": olcum},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    except Exception as exc:  # noqa: BLE001 - rapor yazımı denetimi engellememeli
        logger.debug("Gece raporu yazılamadı: %s", exc)
        return False
    return cevap is not None


def _gece_onerisi_gonder(tutarlilik_sonuc: dict, olcum_sonuc: dict,
                        gun: str = "") -> bool:
    """Yalnız eylem gerektiren sonucu DM'e öneri olarak yollar.

    Sessiz gece: sapma yoksa ve ölçüm "kalsın/yetersiz" diyorsa mesaj GİTMEZ
    (her gece boş bildirim atmak, öneriyi okunmaz hale getirir). Gönderilen
    öneri `oneri.py` defterine "bekliyor" olarak yazılır: /evet · /hayır bu
    kaydı yanıtlar. Aynı metin yakın zamanda yanıtlandıysa tekrar gönderilmez.
    """
    notifier = _notifier_ref
    if notifier is None or not getattr(notifier, "enabled", False):
        return False
    satirlar = []
    sapma = (tutarlilik_sonuc or {}).get("sapma") or 0
    if sapma:
        satirlar.append(f"Tutarlılık: {sapma} sapma / "
                        f"{(tutarlilik_sonuc or {}).get('kontrol', 0)} denetim")
        for d in ((tutarlilik_sonuc or {}).get("sapmalar") or [])[:2]:
            satirlar.append(f"· {d.get('sembol')} {d.get('tf')} — {d.get('neden')}")
    if (olcum_sonuc or {}).get("karar") == "bayrak_kaldirilsin":
        satirlar.append(str(olcum_sonuc.get("metin") or "").split(" Arşiv:")[0].strip())
    if not satirlar:
        return False
    metin = ("🌙 Gece denetimi\n" + "\n".join(s for s in satirlar if s)
             + "\n/evet ile onayla ya da /hayır ile reddet. Bot kendiliğinden "
               "eşik değiştirmez.")
    try:
        import oneri
        # Yanıtlanmış öneri aynı metinle 7 gün içinde tekrar sorulmaz.
        if oneri.tekrar_mi(metin, store=_supabase_store_ref):
            logger.info("Gece önerisi aynı metinle yanıtlanmış; DM tekrarlanmadı")
            return False
    except Exception as exc:  # noqa: BLE001 - öneri defteri yoksa DM yine gitsin
        logger.debug("Gece önerisi defteri okunamadı: %s", exc)
    try:
        gonderildi, durum = notifier.send_text(metin)
    except Exception as exc:  # noqa: BLE001 - DM hatası gece işini düşürmemeli
        logger.debug("Gece önerisi gönderilemedi: %s", exc)
        return False
    if not gonderildi:
        logger.info("Gece önerisi gönderilemedi: %s", durum)
        return False
    try:
        import oneri
        oneri.kaydet({
            "gun": gun or datetime.now().date().isoformat(),
            "metin": metin,
            "karar": (olcum_sonuc or {}).get("karar") or "",
            "ozet": " · ".join(s for s in satirlar if s),
            "sapma": sapma,
            "durum": "bekliyor",
        }, store=_supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - kayıt yazılamazsa DM gitti, iş sürer
        logger.debug("Gece önerisi kaydedilemedi: %s", exc)
    logger.info("Gece önerisi DM'e gitti (%d satır)", len(satirlar))
    return True


def _gece_denetimi(now: datetime) -> None:
    """Günde bir kez: canlı–replay tutarlılığı + ölçüm tazeleme. Değişiklik YOK."""
    global _gece_denetim_son_gun
    if now.hour < ILERI_TEST_GECE_SAAT:
        return
    gun = now.date().isoformat()
    if _gece_denetim_son_gun == gun:
        return
    try:
        import ileri_test
        import olcum_tazele
        import tutarlilik

        try:
            defter = ileri_test.defter_yukle(store=_supabase_store_ref)
            kayitlar = defter.get("kayitlar") or []
        except Exception as exc:  # noqa: BLE001 - defter yoksa denetim yine koşar
            logger.debug("Gece denetimi defteri okuyamadı: %s", exc)
            kayitlar = []

        tutarlilik_sonuc = tutarlilik.gunluk(kayitlar, simdi=now)
        logger.info(tutarlilik.ozet(tutarlilik_sonuc))
        olcum_sonuc = olcum_tazele.tazele(store=_supabase_store_ref, kayitlar=kayitlar)
        logger.info(olcum_sonuc.get("metin"))

        _gece_raporu_yaz(gun,
                         {k: v for k, v in tutarlilik_sonuc.items() if k != "detay"},
                         {"karar": olcum_sonuc.get("karar"),
                          "metin": olcum_sonuc.get("metin"),
                          "veri": olcum_sonuc.get("veri")})
        _gece_onerisi_gonder(tutarlilik_sonuc, olcum_sonuc, gun=gun)
        _gece_denetim_son_gun = gun
    except Exception as exc:  # noqa: BLE001 - gece işi ana döngüyü düşürmemeli
        logger.warning("Gece denetimi başarısız: %s", exc)


def main_loop():
    """
    Ana döngü:
    1. BIST açık mı kontrol et
    2. Açıksa -> mum kapanışından 5dk sonra tara
    3. Kapalıysa -> 5dk uyu, tekrar kontrol et
    Neden 24/7 çalışıp sadece seans saatlerinde CPU harcasın? Oracle Free'de kaynak kısıtlı
    """
    setup_logging()   # Batch 8 / C2: handler'lar burada bağlanır (import yan etkisi yok)
    logger.info("=== BIST FORMASYON BOTU BAŞLATILIYOR ===")
    logger.info(f"Profil: {PROFILE}, Params: {PROFILE_PARAMS}")
    logger.info(f"Hisseler: {ACTIVE_STOCKS[:5]}... (toplam {len(ACTIVE_STOCKS)})")
    evren_uyarisi = _evren_olcek_uyarisi()
    if evren_uyarisi:
        logger.warning(evren_uyarisi)
    
    global _deque_manager_ref, _notifier_ref, _supabase_store_ref, _telegram_update_processor_ref, _lifecycle_manager_ref
    # Digest damgası main_loop içinde birden çok yerde okunur/yazılır; global
    # bildirimi fonksiyon başında olmalı (Python kuralı).
    global _digest_son_gonderim_gun
    supabase_store = SupabaseStore.from_env()
    _supabase_store_ref = supabase_store
    if supabase_store is not None:
        # Ortam değişkenleri yanlışsa teşhis loga düşsün; hata halinde bot durmaz.
        supabase_store.ping()
    # Restart/uyku sonrası son başarılı tarama listesi geri yüklenir (Supabase ve
    # yerel dosyanın EN YENİ kopyası). Bu çağrı olmadan /panel, /canli, /durum ve
    # sabah özeti her yeniden başlatmada boş görünür; kalıcılık yazılır ama okunmaz.
    son_tarama_yukle(supabase_store)
    # Faz 2.1: çoklu formasyon history defteri. Registry lazy okunur (tarama
    # anında doğum eşleşmesi için diskten yüklenir), bu yüzden bu adım ZORUNLU
    # değildir — yalnızca startup'ta sağlık raporu üretir. Bozuk bir defter
    # botu DURDURMAZ: `yukle()` bozuk dosyada boş defter döner ve tarama
    # Faz 1 yoluyla devam eder.
    _formation_history_baslangic_kontrolu()
    # Faz 2.6: Local history boşsa ve Supabase store varsa hydrate et
    if supabase_store is not None:
        try:
            from state.formation_mirror import hydrate_all_open
            hydrate_all_open(store=supabase_store)
        except Exception as _hyd_err:
            logger.debug("Startup hydration sessizce atlandı: %s", _hyd_err)
    # Çoklu kopya koruması: aynı anahtarlarla başka bir canlı örnek var mı?
    _tekil_ornek_kontrolu(supabase_store, force=True)
    # Bekleyen gün içi aday tamponu da kalıcıdır (Batch 5): 18:45'ten önce
    # restart olursa adaylar kaybolmaz. Telafi gönderimi notifier kurulduktan
    # hemen sonra yapılır (tampon günü eskiyse).
    digest_tamponu_yukle(supabase_store)
    # Analiz snapshot'ı komutların güncel kaynağı değildir. Her /panel ve
    # /tara isteği yeni veriyle yeniden hesaplanır. OHLCV önbelleği Supabase
    # erişilemezse yerel disk/Yahoo üzerinden kurulabilir.
    deque_manager = StockDequeManager(persistent_store=supabase_store)
    _deque_manager_ref = deque_manager

    # Başlangıçta tüm cache ve notifier durumlarını tek Supabase isteğiyle al.
    # Supabase boş/erişilemezse mevcut bot_data JSON/pickle fallback'i kullanılır.
    remote_rows = None
    if supabase_store is not None:
        remote_keys = [
            key
            for stock in ACTIVE_STOCKS
            for key in (f"cache:1h:{stock}", f"cache:1d:{stock}")
        ] + [
            "state:daily_fetch_attempts",
            "state:telegram_cooldowns",
            "state:telegram_caps",
            # Depolanan durumlara ait kuyruk/mühür anahtarları: redploy'da
            # acil kuyruk ve tek-seferlik mühürler kaybolmasın (kayıp çift
            # mesaj / tekrar alarm kök nedenlerinden biri buydu).
            "state:notification_delivery",
            "state:telegram_acil_kuyruk",
            "state:telegram_son_alerts",
        ]
        remote_rows = supabase_store.get_many(remote_keys)
        if remote_rows is not None:
            deque_manager.hydrate_from_supabase(ACTIVE_STOCKS, remote_rows)
    lifecycle_manager = PatternLifecycleManager(profile=PROFILE)
    _lifecycle_manager_ref = lifecycle_manager
    notifier = TelegramNotifier(
        persistent_store=supabase_store,
        initial_store_data=remote_rows,
    )
    _notifier_ref = notifier
    # Telegram token/chat_id teşhisi: mesaj göndermeden getMe ile doğrular.
    notifier.check_connection()
    # Public hedef (kanal/grup) doğrulaması: bot yönetici değilse/izin yoksa
    # ilk gönderimde 403 almak yerine AÇILIŞTA net uyarı verilir.
    if notifier.public_enabled:
        notifier.check_public_connection()

    # İki yönlü Telegram: komutları (panel/canli/formasyonlar/durum/tara/yardim)
    # dinleyen katman. İki mod var, AYNI ANDA YALNIZCA BİRİ açılır:
    #   - webhook  : TELEGRAM_WEBHOOK_SECRET varsa ve HTTP sunucusu ayaktaysa
    #                (Telegram → POST /webhook/<secret>, health_server taşır)
    #   - yoklama  : aksi halde getUpdates uzun yoklaması (daemon thread)
    # Token/chat_id yoksa hiçbiri başlatılmaz; bot eskisi gibi yalnızca alarm gönderir.
    # 18:45 kapanış özeti kaçırıldıysa (bot akşam kapalıydı) ilk fırsatta telafi et.
    _kacirilan_digest_ozeti(notifier, datetime.now(ISTANBUL_TZ))
    # Özet işaretini ilk preload/fetch'ten önce al: seans öncesi kuyruk engeli
    # açılışta hemen çözülsün; kapanış özeti sonrası eski kuyruk ayrı push olmasın.
    _dm_isaretler, _public_isaretler = _ozet_isaretlerini_yukle()
    _acilis_zamani = datetime.now(ISTANBUL_TZ)
    _acilis_digest_saati = _parse_deferred_alert_digest_time()
    _ozet_slotu = _acilis_digest_saati.strftime("%H:%M")
    _acil_kuyruk_acilista_isle(
        notifier, _acilis_zamani, _acilis_digest_saati,
        kapanis_ozeti_gonderildi=not _ozet_slot_gonderilmeli(
            _dm_isaretler, _ozet_slotu, _acilis_zamani.date()),
    )

    _telegram_komut_katmanini_kur(notifier)
    
    # İlk kurulum/preload de aynı hız sınırını kullanır; boş 1H cache'ler seri çekilir.
    logger.info(
        f"İlk yükleme: {len(ACTIVE_STOCKS)} hisse evreni; eksik cache'ler "
        f"{SCAN_REQUEST_BATCH_SIZE}'li istek gruplarıyla yavaşça doldurulacak"
    )
    pacer = create_yahoo_pacer()
    cache_eksik_hisseler = []
    for stock in ACTIVE_STOCKS:
        mevcut = deque_manager.to_dataframe(stock)
        if mevcut is None or len(mevcut) < 50:
            cache_eksik_hisseler.append(stock)

    ilk_veriler, ilk_hatalar, ilk_retry, ilk_kurtarilan = fetch_1h_stocks_paced(
        cache_eksik_hisseler, pacer, "İLK YÜKLEME"
    )
    if ilk_retry:
        logger.info(
            f"İlk yükleme retry özeti: {ilk_retry} tekrar, {ilk_kurtarilan} başarılı, "
            f"{len(ilk_hatalar)} çözülemeyen"
        )
    for stock in cache_eksik_hisseler:
        taze = ilk_veriler.get(stock)
        if taze is not None:
            deque_manager.append_dataframe(stock, taze)
            deque_manager.save_to_disk(stock)
            logger.info(f"{stock}: {len(taze)} mum çekildi ve diske kaydedildi")
        else:
            logger.warning(
                f"{stock}: ilk veri çekilemedi ({ilk_hatalar.get(stock, 'veri yok')}); "
                "canlı taramada tekrar denenecek"
            )

    # 1D derin veri de eksikse aynı pacing kuyruğundan geçir.
    for stock in ACTIVE_STOCKS:
        if _shutdown_requested:
            break
        if deque_manager.gunluk_veri_eksik_mi(stock):
            with pacer.request(f"{stock} initial 1D"):
                taze_gunluk = fetch_yfinance_1d(stock)
            deque_manager.gunluk_fetch_denemesi_kaydet(stock)
            if taze_gunluk is not None and len(taze_gunluk) >= 30:
                deque_manager.append_gunluk_dataframe(stock, taze_gunluk)
                deque_manager.save_gunluk_to_disk(stock)
                logger.info(f"{stock}: {len(taze_gunluk)} GÜNLÜK mum çekildi ve diske kaydedildi")
            else:
                logger.warning(f"{stock}: ilk günlük veri çekilemedi - resample kullanılacak")
    
    # Haftalık karne defteri: açılışta bir kez hazırlanır (uzak yedek varsa
    # Supabase'den birleştirilir). Böylece tarama döngüsü içinde ağ beklemesi
    # olmaz; Supabase yoksa yalnız yerel dosya okunur.
    try:
        kd = _karne_al()
        kd.buda()
        _karne_uzak_kaydet(zorla=True)
        logger.info("Karne defteri hazır: %d kayıt (%s)", kd.boyut(), kd.dosya)
    except Exception as e:
        logger.warning(f"Karne defteri hazırlanamadı (devam ediliyor): {e}")

    # Aynı mum iki kez taranmasın (drift koruması). Restart'ta None -> bir sonraki
    # kapanışta tazelenir, son mum gerekiyorsa bir kez daha taranır (zararsız).
    son_taranan_kapanis = None
    # Özet ve bakım takibi (bedava kalma için)
    summary_hours = _effective_summary_hours()
    deferred_alert_digest_time = _parse_deferred_alert_digest_time()
    post_close_analysis_time = _parse_post_close_analysis_time()
    last_summary_sent = {}  # DM özeti: "09:55" -> date
    last_summary_public_sent = {}  # public (grup) özeti ayrı izlenir; DM retry gruba kopya üretmesin
    # Özet işaretleri ilk preload'dan önce yüklenmişti; aynı gün restartında aynı
    # slot tekrarlanmaz ve açılış kuyruğu politikası da bu kaydı kullanır.
    last_summary_sent.update(_dm_isaretler)
    last_summary_public_sent.update(_public_isaretler)
    # Gün sonu analizi damgası KALICI okunur: yalnız bellekte tutulunca süreç
    # yeniden başlayınca aynı gün ikinci kez çalışıyor ve panel mesajı
    # tekrarlanıyordu (02.10: 20:05 ve 21:49 iki panel).
    try:
        _pc_ham = (_state_persistence.gonderim_durumu_yukle() or {}).get("post_close_analizi_gun")
        last_post_close_analysis_date = (
            datetime.fromisoformat(str(_pc_ham)).date() if _pc_ham else None)
    except (TypeError, ValueError):
        last_post_close_analysis_date = None
    last_maintenance_date = None
    last_preload_date = None
    son_kuyruk_bosaltma = 0.0  # engellenen acil olaylar bu aralıkla yeniden denenir
    # Restart gün sürekliliği: bugün zaten sayaç biriktirilmişse geri yükle
    # (aksi halde 18:45 kanal özeti günün gerçek toplamını eksik gösterir).
    _gunluk_sayac_yukle()
    
    while not _shutdown_requested:
        try:
            now = datetime.now(ISTANBUL_TZ)
            # Durable delivery is not tied to the next candle or market hours.
            # Media failures must also recover after the closing scan/restart.
            try:
                notifier.teslimleri_dene()
            except Exception as teslim_hata:
                logger.warning("Bekleyen bildirim teslimi denenemedi: %s", type(teslim_hata).__name__)

            # Kullanıcı isteği seans saatinden bağımsız olarak ilk fırsatta çalışır.
            if _scan_istegi.is_set():
                if _calistir_istek_taramasi(deque_manager, lifecycle_manager, notifier):
                    if _istek_tam_evrende_tamamlandi(last_run_stats):
                        kapanis = son_kapanan_mum_ani(datetime.now(ISTANBUL_TZ))
                        if kapanis is not None:
                            # Manuel /panel aynı kapanış mumunu başarıyla hesapladı;
                            # otomatik döngüde aynı tam evreni hemen tekrar tarama.
                            son_taranan_kapanis = kapanis
                    deque_manager.save_all()
                    continue
            # --- ENGELLENEN ACİL OLAYLAR (Batch 5 / B4) ---
            # Teyitli olaylar engel kalkınca birkaç dakikada gönderilir; ancak
            # kapanış digest saatinden sonra bireysel push yapılmaz. Bekleyenler
            # 18:45 özetine katılır, böylece özetin arkasından geç alarm gelmez.
            try:
                if (_acil_kuyruk_gonderim_penceresi_acik(now, deferred_alert_digest_time)
                        and notifier.enabled and notifier.kuyruk_durumu().get("bekleyen")
                        and time.time() - son_kuyruk_bosaltma >= ACIL_KUYRUK_BOSALTMA_ARALIK_SN):
                    son_kuyruk_bosaltma = time.time()
                    gonderilen_kuyruk = notifier.kuyrugu_bosalt()
                    if gonderilen_kuyruk:
                        logger.info(f"Engellenen acil kuyruğundan {gonderilen_kuyruk} olay gönderildi")
            except Exception as e:
                logger.debug(f"Acil kuyruk boşaltma hatası: {e}")

            # --- ÇOKLU ÖRNEK KONTROLÜ (Batch 6 / B10) ---
            # 5 dakikada bir: aynı Supabase anahtarlarını kullanan başka bir canlı
            # kopya var mı? (webhook modunda 409 sinyali yok; bu onun yerini tutar)
            try:
                _tekil_ornek_kontrolu(supabase_store)
            except Exception as e:
                logger.debug(f"Çoklu örnek kontrol hatası: {e}")

            # --- GÜNLÜK ÖZET + ERTELENMİŞ ADAYLAR (akşam 18:45) ---
            # İŞLEM GÜNÜ KAPISI: hafta sonu ve resmî tatilde kanala özet GİTMEZ.
            # Saat hedefleri (09:55/18:45) takvimden bağımsız geldiği için, kapı
            # olmadan cumartesi günü "öne çıkan formasyon olmadı" mesajı gidiyordu;
            # aynı şekilde 20:00 gün sonu analizi boşuna tam evren taraması yapıyordu.
            # DM tarafı da kapanır: sahibe anlamsız "boş gün" özeti gitmez (tam detay
            # istenirse /panel ve /durum komutları her zaman çalışır).
            try:
              if not islem_gunu_mu(now):
                if not _islem_gunu_loglandi.get("gun") == now.date().isoformat():
                    logger.info("İşlem günü değil (%s); günlük özetler ve gün sonu "
                                "analizi atlanıyor.", now.date().isoformat())
                    _islem_gunu_loglandi["gun"] = now.date().isoformat()
              else:
                for sh in summary_hours:
                    sh_str = sh.strftime("%H:%M")
                    hedef = ISTANBUL_TZ.localize(datetime.combine(now.date(), sh))
                    gecikme_sn = (now - hedef).total_seconds()
                    # Normal özetler 10 dakikalık pencerede; kapanış özeti ise
                    # tarama uzasa bile aynı gün ilk fırsatta gönderilir.
                    ozet_zamani = now >= hedef and (
                        sh == deferred_alert_digest_time or gecikme_sn < 600
                    )
                    # Akşam DM/public özeti aynı gün tam evren taraması başarıyla
                    # bitmeden gönderilmez; tarama uzarsa aynı gün ilk uygun döngüde
                    # yeniden denenir. Sabah slotu bu kapıdan bağımsızdır.
                    if (sh == deferred_alert_digest_time and ozet_zamani
                            and not _successful_full_scan_today(now)):
                        logger.info("18:45 özeti bekletildi: bugün başarılı tam tarama yok")
                        continue
                    # Kapanış özeti kalıcı tampon taşır: restart sonrası aynı DM
                    # özeti ikinci kez gönderilmesin (state:digest_pending).
                    # NOT: bu bayrak yalnız DM yolunu kapatır. Kanala kapanış
                    # gitmeden süreç öldüyse (DM gitti + kanal gitmedi) kanal
                    # kendi KALICI işaretinden (public:18:45) devam eder; yani
                    # eksik kalan mesaj restart sonrası tamamlanır.
                    dm_gonderildi = (sh == deferred_alert_digest_time
                                     and _digest_son_gonderim_gun == now.date().isoformat())
                    dm_hedefi = (ozet_zamani and not dm_gonderildi
                                 and _ozet_slot_gonderilmeli(last_summary_sent, sh_str, now.date()))
                    public_hedefi = (ozet_zamani and notifier.public_enabled
                                     and _ozet_slot_gonderilmeli(
                                         last_summary_public_sent, sh_str, now.date()
                                     ))
                    if not dm_hedefi and not public_hedefi:
                        continue
                    aktif = _build_active_formations_for_summary(lifecycle_manager)
                    acil_bekleyen = []
                    if sh == deferred_alert_digest_time and dm_hedefi and notifier.enabled:
                        try:
                            kuyruk_ozeti = getattr(notifier, "kuyruk_ozet_kayitlari", None)
                            if callable(kuyruk_ozeti):
                                acil_bekleyen = kuyruk_ozeti(now=now) or []
                        except Exception as kuyruk_hata:  # noqa: BLE001 - özet kuyruk yüzünden düşmesin
                            logger.warning("Kapanış kuyruğu özetlenemedi: %s", kuyruk_hata)
                            acil_bekleyen = []
                    summary_payload = _daily_summary_payload(now)
                    # Kapanış özetinde görünen kuyruk olayları da kullanıcıya bildirildi
                    # sayılır; "Gün: N bildirim" satırı bunları eksik bırakmasın.
                    if acil_bekleyen:
                        summary_payload["alerts_sent"] = int(
                            summary_payload.get("alerts_sent") or 0) + len(acil_bekleyen)
                    ozet = notifier.format_daily_summary(aktif, summary_payload)
                    bekleyen = (
                        _deferred_alert_buffer.items(now, limit=DEFERRED_ALERT_DIGEST_LIMIT)
                        if sh == deferred_alert_digest_time else []
                    )
                    # Tampondaki gerçek aday sayısı: kesilenler özet metninde
                    # "… N aday daha" satırıyla görünür ve sayaca yazılır.
                    bekleyen_toplam = len(_deferred_alert_buffer) if bekleyen else 0
                    if bekleyen and bekleyen_toplam > len(bekleyen):
                        daily_stats['alerts_digest_overflow'] = bekleyen_toplam - len(bekleyen)
                    watch_summary = _format_deferred_alert_summary(bekleyen, bekleyen_toplam)
                    sessiz_iptal = (
                        daily_stats.get("sessiz_gecersizlesme_sayisi", 0)
                        if sh == deferred_alert_digest_time else 0
                    )
                    acil_kuyruk_ozeti = _format_urgent_queue_summary(
                        acil_bekleyen, sessiz_gecersizlesme=sessiz_iptal
                    )
                    dm_ozet = f"📋 Günlük Özet\n{ozet}"
                    if watch_summary:
                        dm_ozet += "\n\n" + watch_summary
                    if acil_kuyruk_ozeti:
                        dm_ozet += "\n\n" + acil_kuyruk_ozeti

                    # --- HAFTALIK DOĞRULUK KARNESİ (gün sonu mesajının ALTINA) ---
                    # Cuma günü 18:45 kapanış özetinin altına eklenir; haftada bir
                    # kez gönderilir. Defter/ölçüm tamamen yereldir (Supabase yok).
                    karne_metni_eklendi = ""
                    if sh == deferred_alert_digest_time:
                        karne_metni_eklendi = _haftalik_karne_ekle(now, deque_manager)
                        # KARNE buraya DİZİLMEZ: _karneyle_gonder() karneyi ya ana
                        # mesajın sonuna ekler ya da sığmıyorsa ayrı mesaj yapar.
                        # Eskiden hem buraya eklenip hem parametre olarak geçtiği
                        # için blok İKİ KEZ gidiyordu (25 Eyl: 798 kr × 2, özetin
                        # %58'i kopya metindi).
                        

                    if dm_hedefi:
                        if notifier.enabled:
                            # Parça bazlı sonuç: ana özet ve karne AYRI izlenir.
                            # Böylece (a) karne parçası gitmezse yalnız karne, 20:00
                            # yolunda yeniden denenir; (b) ana özet gittiği halde
                            # sayaç artmadığı için özet İKİ KEZ gönderilmez.
                            ana_ok, karne_ok, hata = _karneyle_gonder(
                                notifier, dm_ozet, karne_metni_eklendi)
                            if ana_ok:
                                if acil_bekleyen:
                                    try:
                                        tuket = getattr(notifier, "kuyruk_ozetleneni_tuket", None)
                                        tuketilen = int(tuket(acil_bekleyen) or 0) if callable(tuket) else 0
                                        if tuketilen:
                                            logger.info(
                                                "Kapanış özetinde %d engellenmiş teyitli olay bildirildi; "
                                                "kuyruktan tüketildi.", tuketilen)
                                    except Exception as kuyruk_hata:  # noqa: BLE001 - teslim işareti best effort
                                        logger.warning("Özetlenen acil kuyruk tüketilemedi: %s", kuyruk_hata)
                                last_summary_sent[sh_str] = now.date()
                                _ozet_isaret_kaydet(sh_str, now.date())
                                if bekleyen:
                                    _deferred_alert_buffer.mark_reported(bekleyen, now)
                                if sh == deferred_alert_digest_time:
                                    _digest_son_gonderim_gun = now.date().isoformat()
                                    _capture_digest_lifecycle_baseline()
                                    digest_tamponu_kaydet()
                                logger.info(f"Günlük DM özeti gönderildi: {sh_str}")
                            else:
                                logger.warning(f"Günlük DM özeti gönderilemedi ({sh_str}): {hata}")
                            if karne_metni_eklendi and karne_ok:
                                _karne_gonderildi_isaretle(now)
                                logger.info("Haftalık doğruluk karnesi gönderildi (18:45 özeti altında)")
                        else:
                            # Test/pasif modda döngü boyunca aynı özeti tekrar deneme.
                            last_summary_sent[sh_str] = now.date()
                            if sh == deferred_alert_digest_time:
                                _digest_son_gonderim_gun = now.date().isoformat()
                                _capture_digest_lifecycle_baseline()

                    # --- PUBLIC GRUP: sade kapanış özeti (DM'den bağımsız) ---
                    # DM kapalıyken de çalışır; iç izleme notu/dosya yolu taşımaz.
                    if (notifier.public_enabled
                            and _ozet_slot_gonderilmeli(
                                last_summary_public_sent, sh_str, now.date()
                            )):
                        kisa_karne = ""
                        if sh == deferred_alert_digest_time:
                            kisa_karne = _haftalik_karne_kisa(now, deque_manager)
                        kapanis_mi = (sh == deferred_alert_digest_time)
                        grup_ozet = notifier.format_public_summary(
                            aktif, summary_payload, izleme=bekleyen, karne_kisa=kisa_karne,
                            tarama_turu=daily_stats.get('tarama_sayisi'),
                            kapanis=kapanis_mi,
                        )
                        if notifier.send_to_public(grup_ozet):
                            last_summary_public_sent[sh_str] = now.date()
                            _ozet_isaret_kaydet(sh_str, now.date(), public=True)
            except Exception as e:
                logger.debug(f"Özet gönderim hatası: {e}")

            # --- GÜN SONU TAM EVREN ANALİZİ (varsayılan 20:00 İstanbul) ---
            # İşlem günü değilse (hafta sonu/tatil) gece analizi ÇALIŞMAZ: veri
            # değişmediği için tam evren taraması boşuna kaynak harcar ve panel
            # "değişmeyen gün" raporu üretirdi.
            try:
                if (islem_gunu_mu(now)
                        and now.time() >= post_close_analysis_time
                        and last_post_close_analysis_date != now.date()):
                    logger.info("Gün sonu tam evren analizi başlıyor (%s)",
                                post_close_analysis_time.strftime("%H:%M"))
                    digest_sh_str = deferred_alert_digest_time.strftime("%H:%M")
                    kapanis_ozeti_gitti = (
                        _digest_son_gonderim_gun == now.date().isoformat()
                        or last_summary_sent.get(digest_sh_str) == now.date()
                    )
                    baseline_keys = (
                        set(_digest_event_keys_snapshot)
                        if _digest_event_keys_snapshot is not None
                        else set(_daily_lifecycle_event_keys)
                    )
                    _scan_job_active.set()
                    try:
                        try:
                            result = scan_all_stocks(
                                deque_manager, lifecycle_manager, notifier,
                                manuel=True, stocks=ACTIVE_STOCKS, send_alerts=False,
                            )
                        except Exception as exc:
                            logger.error("Gün sonu analiz çalıştırması çöktü: %s", exc, exc_info=True)
                            result = _analiz_hatasi_kaydi(
                                exc, len(ACTIVE_STOCKS), "gün sonu analiz",
                            )
                        if result.get("status") == "tamamlandi":
                            from config import post_close_only_on_diff_enabled
                            karne_ek = _haftalik_karne_ekle(now, deque_manager)
                            if post_close_only_on_diff_enabled() and kapanis_ozeti_gitti:
                                yeni_olaylar = sorted(
                                    set(_daily_lifecycle_event_keys) - baseline_keys
                                )
                                if yeni_olaylar:
                                    aktif_f = _build_active_formations_for_summary(lifecycle_manager)
                                    mesaj = _format_post_close_diff_report(yeni_olaylar, aktif_f)
                                    ana_ok, karne_ok, _hata = _karneyle_gonder(
                                        notifier, mesaj, karne_ek
                                    )
                                    if ana_ok:
                                        logger.info(
                                            "Gün sonu fark raporu gönderildi (%d yeni gelişme)",
                                            len(yeni_olaylar),
                                        )
                                    if karne_ek and karne_ok:
                                        _karne_gonderildi_isaretle(now)
                                        logger.info(
                                            "Haftalık doğruluk karnesi gönderildi (gün sonu farkı altında)"
                                        )
                                elif karne_ek:
                                    karne_ok, _hata = notifier.send_text(karne_ek.strip())
                                    if karne_ok:
                                        _karne_gonderildi_isaretle(now)
                                        logger.info(
                                            "Haftalık doğruluk karnesi gönderildi (20:00 telafisi)"
                                        )
                                else:
                                    logger.info(
                                        "Gün sonu analizi tamamlandı; 18:45 sonrası yeni "
                                        "teyit/geçersizleşme yok, 20:00 mesajı atlandı"
                                    )
                            else:
                                rapor = _panel_raporu("", tamamlandi=True)
                                mesaj = "🌙 GÜN SONU ANALİZİ\n" + rapor
                                # Cuma karnesi 18:45 özetiyle gidemediyse (bot kapalıydı /
                                # gönderim hatası) burada gün sonu analizinin altına eklenir.
                                ana_ok, karne_ok, _hata = _karneyle_gonder(notifier, mesaj, karne_ek)
                                if ana_ok:
                                    logger.info("Gün sonu analizi gönderildi")
                                if karne_ek and karne_ok:
                                    # İşaret KARNE parçası gerçekten gittiyse konur;
                                    # 18:45'te gönderilen karne burada ikinci kez çıkmaz.
                                    _karne_gonderildi_isaretle(now)
                                    logger.info("Haftalık doğruluk karnesi gönderildi (gün sonu analizi altında)")
                        else:
                            notifier.send_text(
                                "⚠️ Gün sonu analizi tamamlanamadı; eski sonuç yeni sonuç gibi "
                                "gösterilmedi. Ayrıntı için bot loglarını kontrol edin."
                            )
                    finally:
                        _scan_job_active.clear()
                        last_post_close_analysis_date = now.date()
                        # Kalıcı damga: restart olsa bile aynı gün ikinci panel yok.
                        try:
                            _state_persistence.gonderim_durumu_kaydet(
                                {"post_close_analizi_gun": now.date().isoformat()})
                        except Exception as pc_hata:  # noqa: BLE001
                            logger.debug("Gün sonu damgası yazılamadı: %s", pc_hata)
                    continue
            except Exception as e:
                logger.error("Gün sonu analizi zamanlayıcısı hata verdi: %s", e, exc_info=True)

            # --- SABAH PRE-LOAD (08:30) ---
            try:
                if now.hour == MORNING_PRELOAD_HOUR and now.minute >= MORNING_PRELOAD_MINUTE and now.minute < MORNING_PRELOAD_MINUTE + 10:
                    if last_preload_date != now.date():
                        morning_preload(deque_manager, pacer)
                        last_preload_date = now.date()
            except Exception as e:
                logger.debug(f"Preload kontrol hatası: {e}")

            # --- AKŞAM BAKIMI (18:10-19:00) ---
            try:
                if now.hour == 18 and now.minute >= 10 and now.minute < 60:
                    if last_maintenance_date != now.date():
                        evening_maintenance(deque_manager, lifecycle_manager)
                        last_maintenance_date = now.date()
            except Exception as e:
                logger.debug(f"Bakım kontrol hatası: {e}")
            
            
            if tarama_penceresi_acik_mi(now):
                if tarama_animi_mi(now, son_taranan_kapanis):
                    # Tarama anı: en son kapanmış mum + 5 dk doldu.
                    kapanis = son_kapanan_mum_ani(now)
                    logger.info(f"TARAMA - {now.strftime('%H:%M:%S')} "
                                f"(mum {kapanis.strftime('%H:%M')}'de kapandı, "
                                f"günün {kapanis.hour - 9}. taraması)")
                    _scan_job_active.set()
                    try:
                        scan_all_stocks(
                            deque_manager, lifecycle_manager, notifier,
                            manuel=False, stocks=ACTIVE_STOCKS, send_alerts=True,
                        )
                    finally:
                        _scan_job_active.clear()
                    _tarama_saglik_kontrolu(notifier)
                    son_taranan_kapanis = kapanis
                    deque_manager.save_all()
                    # Tarama sonunda bekleyen aday tamponu kalıcılaştır (Batch 5 / B3):
                    # restart tamponun tamamını kaybetmesin, tarama başına tek yazma.
                    digest_tamponu_kaydet()
                    # Karne defteri yedeği (varsa Supabase; aralıklı, en fazla 5 dk'da bir).
                    _karne_uzak_kaydet()
                    # Faz 2.6: Formation mirror kuyruğunu Supabase'e flush et
                    if _supabase_store_ref is not None:
                        try:
                            from state.formation_mirror import get_mirror_queue
                            get_mirror_queue().flush(_supabase_store_ref)
                        except Exception:  # noqa: BLE001
                            # Mirror kaybı sessiz kalmasın: kuyruk bellekte kalır,
                            # sonraki turda yeniden denenir (2026-10-26 denetimi).
                            logger.warning("Formation mirror flush atlandı", exc_info=True)
                    time.sleep(5)  # aynı saniyede tekrar girmesin
                    continue
                
                # Henüz tarama anı değil: ne kadar bekleyeceğiz?
                kapanis = son_kapanan_mum_ani(now)
                if kapanis is None or kapanis.date() != now.date():
                    # Bugün henüz mum kapanmadı (ilk kapanış 10:30) -> ilk tarama anını bekle
                    hedef = (now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute,
                                         second=0, microsecond=0)
                             + timedelta(minutes=40 + SCAN_DELAY_AFTER_CLOSE_MIN))
                else:
                    hedef = kapanis + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)
                bekle = max((hedef - now).total_seconds(), 30)
                logger.info(f"Sonraki tarama {hedef.strftime('%H:%M')} -> {bekle/60:.1f} dk bekleniyor")
                # Max 5dk uyu; /tara isteği gelirse uyku erken biter.
                if _bekle_veya_tarama(min(bekle, 300)):
                    logger.info("Elle tarama isteği geldi, uyku kesildi")
                    continue
                
            else:
                # BIST kapalı
                wait_open = time_until_next_open(now)
                # 5dk'da bir kontrol et, ama açılışa kadar uyu
                sleep_time = min(wait_open, 300)  # Max 5dk
                if now.time() < post_close_analysis_time:
                    rapor_anina = now.replace(
                        hour=post_close_analysis_time.hour,
                        minute=post_close_analysis_time.minute,
                        second=0, microsecond=0,
                    )
                    sleep_time = min(sleep_time, max(1.0, (rapor_anina - now).total_seconds()))
                # TABAN UYKU (regresyon koruması): tatil/yarım gün gibi "pencere
                # kapalı ama is_bist_open True" durumlarında sleep_time 0'a düşüp
                # ana döngü boş dönüyordu (ölçüm: ~21.500 log satırı/sn; tatil
                # günü ~600 milyon satır). time_until_next_open artık tatili
                # atlıyor; bu taban ikinci güvenlik ağı, hiçbir koşulda 0 sn uyku
                # ile dönülmez (60 sn'de bir uyanıp durumu yeniden değerlendirir).
                sleep_time = max(sleep_time, 60.0)
                logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                # Boş saatlerin tek gerçek işi: kapanan kayıtların sonucunu yaz.
                _ileri_test_gece(now)
                # Sonuç yazıldıktan SONRA denetim: aynı günün taze defteri okunur.
                _gece_denetimi(now)
                if _bekle_veya_tarama(sleep_time):
                    logger.info("Seans dışı analiz isteği geldi; ana döngü uyandırıldı")
                    continue
                
        except KeyboardInterrupt:
            logger.info("Bot durduruldu (Ctrl+C)")
            break
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            if _live_state.status().get('tarama_suruyor'):
                _analiz_hatasi_kaydi(e, len(ACTIVE_STOCKS), "ana döngü")
            write_heartbeat(force=True)
            time.sleep(30)
            continue
    
    # Güvenli kapanış (SIGTERM/SIGINT)
    logger.info("Bot kapanıyor, son kayıtlar yapılıyor...")
    try:
        if _telegram_listener_ref is not None:
            _telegram_listener_ref.stop()
    except Exception as e:
        logger.warning(f"Komut dinleyicisi kapatılamadı: {e}")
    # Webhook modunda: kapanışta gelen güncellemeler 503 alsın (Telegram tekrar
    # dener; yarım kalan komut yanıtı üretilmez).
    _telegram_update_processor_ref = None
    try:
        if _deque_manager_ref is not None:
            _deque_manager_ref.save_all()
        son_tarama_kaydet()
        # Bekleyen gün içi adaylar kapanışta da kaybolmasın (Batch 5 / B3).
        digest_tamponu_kaydet()
        # Faz 2.6: Kapanışta bekleyen mirror kuyruğunu flush et (SIGTERM/SIGINT)
        if _supabase_store_ref is not None:
            try:
                from state.formation_mirror import get_mirror_queue
                get_mirror_queue().flush(_supabase_store_ref)
            except Exception:  # noqa: BLE001
                # Kapanışta mirror kaybı veri kaybı demektir; sessiz geçilmesin.
                logger.warning("Kapanışta mirror flush atlandı", exc_info=True)
        write_heartbeat(force=True)
    except Exception as e:
        logger.error(f"Kapanış kayıt hatası: {e}")
    logger.info("Bot durdu")

def _render_test_sender(text):
    """/test ucu icin geri cagirma: notifier hazirsa tek mesaj gonderir.

    Notifier main_loop icinde kurulur; bu yuzden modul seviyesindeki global
    uzerinden okunur (server startup'ta None olabilir, cagri aninda doludur).
    """
    notifier = _notifier_ref
    if notifier is None:
        return False, "bot henuz baslamadi"
    return notifier.send_text(text)


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
