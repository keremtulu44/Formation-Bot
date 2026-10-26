"""bot/app.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

# === LOGGING KURULUMU ===
# Batch 8 / C2: bu fonksiyon artık IMPORT anında ÇAĞRILMAZ (yan etki kaldırıldı:
# modül import edildiğinde log dizini oluşturulmuyor/`/var/log` denenmiyordu).
# `main_loop()` ve `python main.py` girişi kurulumu kendisi yapar.
_logging_kuruldu = False


def setup_logging():
    """Log hem console hem dosyaya - Türkçe mesajlar (tek seferlik)."""
    global _logging_kuruldu
    if _pkg._logging_kuruldu:
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
    
    setattr(_pkg, "_logging_kuruldu", True)
    logger = logging.getLogger(__name__)
    _pkg.logger.info(f"Logging kuruldu - dosya: {log_file} - profil: {PROFILE}")
    return _pkg.logger


def signal_handler(signum, frame):
    global _shutdown_requested
    _pkg.logger.info(f"Sinyal alındı: {signum} - güvenli kapanış hazırlanıyor...")
    setattr(_pkg, "_shutdown_requested", True)


def main_loop():
    """
    Ana döngü:
    1. BIST açık mı kontrol et
    2. Açıksa -> mum kapanışından 5dk sonra tara
    3. Kapalıysa -> 5dk uyu, tekrar kontrol et
    Neden 24/7 çalışıp sadece seans saatlerinde CPU harcasın? Oracle Free'de kaynak kısıtlı
    """
    _pkg.setup_logging()   # Batch 8 / C2: handler'lar burada bağlanır (import yan etkisi yok)
    _pkg.logger.info("=== BIST FORMASYON BOTU BAŞLATILIYOR ===")
    _pkg.logger.info(f"Profil: {PROFILE}, Params: {PROFILE_PARAMS}")
    _pkg.logger.info(f"Hisseler: {_pkg.ACTIVE_STOCKS[:5]}... (toplam {len(_pkg.ACTIVE_STOCKS)})")
    evren_uyarisi = _pkg._evren_olcek_uyarisi()
    if evren_uyarisi:
        _pkg.logger.warning(evren_uyarisi)
    
    global _deque_manager_ref, _notifier_ref, _supabase_store_ref, _telegram_update_processor_ref, _lifecycle_manager_ref
    # Digest damgası main_loop içinde birden çok yerde okunur/yazılır; global
    # bildirimi fonksiyon başında olmalı (Python kuralı).
    global _digest_son_gonderim_gun
    supabase_store = SupabaseStore.from_env()
    setattr(_pkg, "_supabase_store_ref", supabase_store)
    if supabase_store is not None:
        # Ortam değişkenleri yanlışsa teşhis loga düşsün; hata halinde bot durmaz.
        supabase_store.ping()
    # Restart/uyku sonrası son başarılı tarama listesi geri yüklenir (Supabase ve
    # yerel dosyanın EN YENİ kopyası). Bu çağrı olmadan /panel, /canli, /durum ve
    # sabah özeti her yeniden başlatmada boş görünür; kalıcılık yazılır ama okunmaz.
    _pkg.son_tarama_yukle(supabase_store)
    # Faz 2.1: çoklu formasyon history defteri. Registry lazy okunur (tarama
    # anında doğum eşleşmesi için diskten yüklenir), bu yüzden bu adım ZORUNLU
    # değildir — yalnızca startup'ta sağlık raporu üretir. Bozuk bir defter
    # botu DURDURMAZ: `yukle()` bozuk dosyada boş defter döner ve tarama
    # Faz 1 yoluyla devam eder.
    _pkg._formation_history_baslangic_kontrolu()
    # Faz 2.6: Local history boşsa ve Supabase store varsa hydrate et
    if supabase_store is not None:
        try:
            from state.formation_mirror import hydrate_all_open
            hydrate_all_open(store=supabase_store)
        except Exception as _hyd_err:
            _pkg.logger.debug("Startup hydration sessizce atlandı: %s", _hyd_err)
    # Çoklu kopya koruması: aynı anahtarlarla başka bir canlı örnek var mı?
    _pkg._tekil_ornek_kontrolu(supabase_store, force=True)
    # Bekleyen gün içi aday tamponu da kalıcıdır (Batch 5): 18:45'ten önce
    # restart olursa adaylar kaybolmaz. Telafi gönderimi notifier kurulduktan
    # hemen sonra yapılır (tampon günü eskiyse).
    _pkg.digest_tamponu_yukle(supabase_store)
    # Analiz snapshot'ı komutların güncel kaynağı değildir. Her /panel ve
    # /tara isteği yeni veriyle yeniden hesaplanır. OHLCV önbelleği Supabase
    # erişilemezse yerel disk/Yahoo üzerinden kurulabilir.
    deque_manager = StockDequeManager(persistent_store=supabase_store)
    setattr(_pkg, "_deque_manager_ref", deque_manager)

    # Başlangıçta tüm cache ve notifier durumlarını tek Supabase isteğiyle al.
    # Supabase boş/erişilemezse mevcut bot_data JSON/pickle fallback'i kullanılır.
    remote_rows = None
    if supabase_store is not None:
        remote_keys = [
            key
            for stock in _pkg.ACTIVE_STOCKS
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
            deque_manager.hydrate_from_supabase(_pkg.ACTIVE_STOCKS, remote_rows)
    lifecycle_manager = PatternLifecycleManager(profile=PROFILE)
    setattr(_pkg, "_lifecycle_manager_ref", lifecycle_manager)
    notifier = TelegramNotifier(
        persistent_store=supabase_store,
        initial_store_data=remote_rows,
    )
    setattr(_pkg, "_notifier_ref", notifier)
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
    _pkg._kacirilan_digest_ozeti(notifier, _pkg.datetime.now(ISTANBUL_TZ))
    # Özet işaretini ilk preload/fetch'ten önce al: seans öncesi kuyruk engeli
    # açılışta hemen çözülsün; kapanış özeti sonrası eski kuyruk ayrı push olmasın.
    _dm_isaretler, _public_isaretler = _pkg._ozet_isaretlerini_yukle()
    _acilis_zamani = _pkg.datetime.now(ISTANBUL_TZ)
    _acilis_digest_saati = _pkg._parse_deferred_alert_digest_time()
    _ozet_slotu = _acilis_digest_saati.strftime("%H:%M")
    _pkg._acil_kuyruk_acilista_isle(
        notifier, _acilis_zamani, _acilis_digest_saati,
        kapanis_ozeti_gonderildi=not _pkg._ozet_slot_gonderilmeli(
            _dm_isaretler, _ozet_slotu, _acilis_zamani.date()),
    )

    _pkg._telegram_komut_katmanini_kur(notifier)
    
    # İlk kurulum/preload de aynı hız sınırını kullanır; boş 1H cache'ler seri çekilir.
    _pkg.logger.info(
        f"İlk yükleme: {len(_pkg.ACTIVE_STOCKS)} hisse evreni; eksik cache'ler "
        f"{SCAN_REQUEST_BATCH_SIZE}'li istek gruplarıyla yavaşça doldurulacak"
    )
    pacer = _pkg.create_yahoo_pacer()
    cache_eksik_hisseler = []
    for stock in _pkg.ACTIVE_STOCKS:
        mevcut = deque_manager.to_dataframe(stock)
        if mevcut is None or len(mevcut) < 50:
            cache_eksik_hisseler.append(stock)

    ilk_veriler, ilk_hatalar, ilk_retry, ilk_kurtarilan = _pkg.fetch_1h_stocks_paced(
        cache_eksik_hisseler, pacer, "İLK YÜKLEME"
    )
    if ilk_retry:
        _pkg.logger.info(
            f"İlk yükleme retry özeti: {ilk_retry} tekrar, {ilk_kurtarilan} başarılı, "
            f"{len(ilk_hatalar)} çözülemeyen"
        )
    for stock in cache_eksik_hisseler:
        taze = ilk_veriler.get(stock)
        if taze is not None:
            deque_manager.append_dataframe(stock, taze)
            deque_manager.save_to_disk(stock)
            _pkg.logger.info(f"{stock}: {len(taze)} mum çekildi ve diske kaydedildi")
        else:
            _pkg.logger.warning(
                f"{stock}: ilk veri çekilemedi ({ilk_hatalar.get(stock, 'veri yok')}); "
                "canlı taramada tekrar denenecek"
            )

    # 1D derin veri de eksikse aynı pacing kuyruğundan geçir.
    for stock in _pkg.ACTIVE_STOCKS:
        if _pkg._shutdown_requested:
            break
        if deque_manager.gunluk_veri_eksik_mi(stock):
            with pacer.request(f"{stock} initial 1D"):
                taze_gunluk = fetch_yfinance_1d(stock)
            deque_manager.gunluk_fetch_denemesi_kaydet(stock)
            if taze_gunluk is not None and len(taze_gunluk) >= 30:
                deque_manager.append_gunluk_dataframe(stock, taze_gunluk)
                deque_manager.save_gunluk_to_disk(stock)
                _pkg.logger.info(f"{stock}: {len(taze_gunluk)} GÜNLÜK mum çekildi ve diske kaydedildi")
            else:
                _pkg.logger.warning(f"{stock}: ilk günlük veri çekilemedi - resample kullanılacak")
    
    # Haftalık karne defteri: açılışta bir kez hazırlanır (uzak yedek varsa
    # Supabase'den birleştirilir). Böylece tarama döngüsü içinde ağ beklemesi
    # olmaz; Supabase yoksa yalnız yerel dosya okunur.
    try:
        kd = _pkg._karne_al()
        kd.buda()
        _pkg._karne_uzak_kaydet(zorla=True)
        _pkg.logger.info("Karne defteri hazır: %d kayıt (%s)", kd.boyut(), kd.dosya)
    except Exception as e:
        _pkg.logger.warning(f"Karne defteri hazırlanamadı (devam ediliyor): {e}")

    # Aynı mum iki kez taranmasın (drift koruması). Restart'ta None -> bir sonraki
    # kapanışta tazelenir, son mum gerekiyorsa bir kez daha taranır (zararsız).
    son_taranan_kapanis = None
    # Özet ve bakım takibi (bedava kalma için)
    summary_hours = _pkg._effective_summary_hours()
    deferred_alert_digest_time = _pkg._parse_deferred_alert_digest_time()
    post_close_analysis_time = _pkg._parse_post_close_analysis_time()
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
            _pkg.datetime.fromisoformat(str(_pc_ham)).date() if _pc_ham else None)
    except (TypeError, ValueError):
        last_post_close_analysis_date = None
    last_maintenance_date = None
    last_preload_date = None
    son_kuyruk_bosaltma = 0.0  # engellenen acil olaylar bu aralıkla yeniden denenir
    # Restart gün sürekliliği: bugün zaten sayaç biriktirilmişse geri yükle
    # (aksi halde 18:45 kanal özeti günün gerçek toplamını eksik gösterir).
    _pkg._gunluk_sayac_yukle()
    
    while not _pkg._shutdown_requested:
        try:
            now = _pkg.datetime.now(ISTANBUL_TZ)
            # Durable delivery is not tied to the next candle or market hours.
            # Media failures must also recover after the closing scan/restart.
            try:
                notifier.teslimleri_dene()
            except Exception as teslim_hata:
                _pkg.logger.warning("Bekleyen bildirim teslimi denenemedi: %s", type(teslim_hata).__name__)

            # Kullanıcı isteği seans saatinden bağımsız olarak ilk fırsatta çalışır.
            if _pkg._scan_istegi.is_set():
                if _pkg._calistir_istek_taramasi(deque_manager, lifecycle_manager, notifier):
                    if _pkg._istek_tam_evrende_tamamlandi(_pkg.last_run_stats):
                        kapanis = son_kapanan_mum_ani(_pkg.datetime.now(ISTANBUL_TZ))
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
                if (_pkg._acil_kuyruk_gonderim_penceresi_acik(now, deferred_alert_digest_time)
                        and notifier.enabled and notifier.kuyruk_durumu().get("bekleyen")
                        and time.time() - son_kuyruk_bosaltma >= ACIL_KUYRUK_BOSALTMA_ARALIK_SN):
                    son_kuyruk_bosaltma = time.time()
                    gonderilen_kuyruk = notifier.kuyrugu_bosalt()
                    if gonderilen_kuyruk:
                        _pkg.logger.info(f"Engellenen acil kuyruğundan {gonderilen_kuyruk} olay gönderildi")
            except Exception as e:
                _pkg.logger.debug(f"Acil kuyruk boşaltma hatası: {e}")

            # --- ÇOKLU ÖRNEK KONTROLÜ (Batch 6 / B10) ---
            # 5 dakikada bir: aynı Supabase anahtarlarını kullanan başka bir canlı
            # kopya var mı? (webhook modunda 409 sinyali yok; bu onun yerini tutar)
            try:
                _pkg._tekil_ornek_kontrolu(supabase_store)
            except Exception as e:
                _pkg.logger.debug(f"Çoklu örnek kontrol hatası: {e}")

            # --- GÜNLÜK ÖZET + ERTELENMİŞ ADAYLAR (akşam 18:45) ---
            # İŞLEM GÜNÜ KAPISI: hafta sonu ve resmî tatilde kanala özet GİTMEZ.
            # Saat hedefleri (09:55/18:45) takvimden bağımsız geldiği için, kapı
            # olmadan cumartesi günü "öne çıkan formasyon olmadı" mesajı gidiyordu;
            # aynı şekilde 20:00 gün sonu analizi boşuna tam evren taraması yapıyordu.
            # DM tarafı da kapanır: sahibe anlamsız "boş gün" özeti gitmez (tam detay
            # istenirse /panel ve /durum komutları her zaman çalışır).
            try:
              if not islem_gunu_mu(now):
                if not _pkg._islem_gunu_loglandi.get("gun") == now.date().isoformat():
                    _pkg.logger.info("İşlem günü değil (%s); günlük özetler ve gün sonu "
                                "analizi atlanıyor.", now.date().isoformat())
                    _pkg._islem_gunu_loglandi["gun"] = now.date().isoformat()
              else:
                for sh in summary_hours:
                    sh_str = sh.strftime("%H:%M")
                    hedef = ISTANBUL_TZ.localize(_pkg.datetime.combine(now.date(), sh))
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
                            and not _pkg._successful_full_scan_today(now)):
                        _pkg.logger.info("18:45 özeti bekletildi: bugün başarılı tam tarama yok")
                        continue
                    # Kapanış özeti kalıcı tampon taşır: restart sonrası aynı DM
                    # özeti ikinci kez gönderilmesin (state:digest_pending).
                    # NOT: bu bayrak yalnız DM yolunu kapatır. Kanala kapanış
                    # gitmeden süreç öldüyse (DM gitti + kanal gitmedi) kanal
                    # kendi KALICI işaretinden (public:18:45) devam eder; yani
                    # eksik kalan mesaj restart sonrası tamamlanır.
                    dm_gonderildi = (sh == deferred_alert_digest_time
                                     and _pkg._digest_son_gonderim_gun == now.date().isoformat())
                    dm_hedefi = (ozet_zamani and not dm_gonderildi
                                 and _pkg._ozet_slot_gonderilmeli(last_summary_sent, sh_str, now.date()))
                    public_hedefi = (ozet_zamani and notifier.public_enabled
                                     and _pkg._ozet_slot_gonderilmeli(
                                         last_summary_public_sent, sh_str, now.date()
                                     ))
                    if not dm_hedefi and not public_hedefi:
                        continue
                    aktif = _pkg._build_active_formations_for_summary(lifecycle_manager)
                    acil_bekleyen = []
                    if sh == deferred_alert_digest_time and dm_hedefi and notifier.enabled:
                        try:
                            kuyruk_ozeti = getattr(notifier, "kuyruk_ozet_kayitlari", None)
                            if callable(kuyruk_ozeti):
                                acil_bekleyen = kuyruk_ozeti(now=now) or []
                        except Exception as kuyruk_hata:  # noqa: BLE001 - özet kuyruk yüzünden düşmesin
                            _pkg.logger.warning("Kapanış kuyruğu özetlenemedi: %s", kuyruk_hata)
                            acil_bekleyen = []
                    summary_payload = _pkg._daily_summary_payload(now)
                    # Kapanış özetinde görünen kuyruk olayları da kullanıcıya bildirildi
                    # sayılır; "Gün: N bildirim" satırı bunları eksik bırakmasın.
                    if acil_bekleyen:
                        summary_payload["alerts_sent"] = int(
                            summary_payload.get("alerts_sent") or 0) + len(acil_bekleyen)
                    ozet = notifier.format_daily_summary(aktif, summary_payload)
                    bekleyen = (
                        _pkg._deferred_alert_buffer.items(now, limit=DEFERRED_ALERT_DIGEST_LIMIT)
                        if sh == deferred_alert_digest_time else []
                    )
                    # Tampondaki gerçek aday sayısı: kesilenler özet metninde
                    # "… N aday daha" satırıyla görünür ve sayaca yazılır.
                    bekleyen_toplam = len(_pkg._deferred_alert_buffer) if bekleyen else 0
                    if bekleyen and bekleyen_toplam > len(bekleyen):
                        _pkg.daily_stats['alerts_digest_overflow'] = bekleyen_toplam - len(bekleyen)
                    watch_summary = _format_deferred_alert_summary(bekleyen, bekleyen_toplam)
                    sessiz_iptal = (
                        _pkg.daily_stats.get("sessiz_gecersizlesme_sayisi", 0)
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
                        karne_metni_eklendi = _pkg._haftalik_karne_ekle(now, deque_manager)
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
                            ana_ok, karne_ok, hata = _pkg._karneyle_gonder(
                                notifier, dm_ozet, karne_metni_eklendi)
                            if ana_ok:
                                if acil_bekleyen:
                                    try:
                                        tuket = getattr(notifier, "kuyruk_ozetleneni_tuket", None)
                                        tuketilen = int(tuket(acil_bekleyen) or 0) if callable(tuket) else 0
                                        if tuketilen:
                                            _pkg.logger.info(
                                                "Kapanış özetinde %d engellenmiş teyitli olay bildirildi; "
                                                "kuyruktan tüketildi.", tuketilen)
                                    except Exception as kuyruk_hata:  # noqa: BLE001 - teslim işareti best effort
                                        _pkg.logger.warning("Özetlenen acil kuyruk tüketilemedi: %s", kuyruk_hata)
                                last_summary_sent[sh_str] = now.date()
                                _pkg._ozet_isaret_kaydet(sh_str, now.date())
                                if bekleyen:
                                    _pkg._deferred_alert_buffer.mark_reported(bekleyen, now)
                                if sh == deferred_alert_digest_time:
                                    setattr(_pkg, "_digest_son_gonderim_gun", now.date().isoformat())
                                    _pkg._capture_digest_lifecycle_baseline()
                                    _pkg.digest_tamponu_kaydet()
                                _pkg.logger.info(f"Günlük DM özeti gönderildi: {sh_str}")
                            else:
                                _pkg.logger.warning(f"Günlük DM özeti gönderilemedi ({sh_str}): {hata}")
                            if karne_metni_eklendi and karne_ok:
                                _pkg._karne_gonderildi_isaretle(now)
                                _pkg.logger.info("Haftalık doğruluk karnesi gönderildi (18:45 özeti altında)")
                        else:
                            # Test/pasif modda döngü boyunca aynı özeti tekrar deneme.
                            last_summary_sent[sh_str] = now.date()
                            if sh == deferred_alert_digest_time:
                                setattr(_pkg, "_digest_son_gonderim_gun", now.date().isoformat())
                                _pkg._capture_digest_lifecycle_baseline()

                    # --- PUBLIC GRUP: sade kapanış özeti (DM'den bağımsız) ---
                    # DM kapalıyken de çalışır; iç izleme notu/dosya yolu taşımaz.
                    if (notifier.public_enabled
                            and _pkg._ozet_slot_gonderilmeli(
                                last_summary_public_sent, sh_str, now.date()
                            )):
                        kisa_karne = ""
                        if sh == deferred_alert_digest_time:
                            kisa_karne = _pkg._haftalik_karne_kisa(now, deque_manager)
                        kapanis_mi = (sh == deferred_alert_digest_time)
                        grup_ozet = notifier.format_public_summary(
                            aktif, summary_payload, izleme=bekleyen, karne_kisa=kisa_karne,
                            tarama_turu=_pkg.daily_stats.get('tarama_sayisi'),
                            kapanis=kapanis_mi,
                        )
                        if notifier.send_to_public(grup_ozet):
                            last_summary_public_sent[sh_str] = now.date()
                            _pkg._ozet_isaret_kaydet(sh_str, now.date(), public=True)
            except Exception as e:
                _pkg.logger.debug(f"Özet gönderim hatası: {e}")

            # --- GÜN SONU TAM EVREN ANALİZİ (varsayılan 20:00 İstanbul) ---
            # İşlem günü değilse (hafta sonu/tatil) gece analizi ÇALIŞMAZ: veri
            # değişmediği için tam evren taraması boşuna kaynak harcar ve panel
            # "değişmeyen gün" raporu üretirdi.
            try:
                if (islem_gunu_mu(now)
                        and now.time() >= post_close_analysis_time
                        and last_post_close_analysis_date != now.date()):
                    _pkg.logger.info("Gün sonu tam evren analizi başlıyor (%s)",
                                post_close_analysis_time.strftime("%H:%M"))
                    digest_sh_str = deferred_alert_digest_time.strftime("%H:%M")
                    kapanis_ozeti_gitti = (
                        _pkg._digest_son_gonderim_gun == now.date().isoformat()
                        or last_summary_sent.get(digest_sh_str) == now.date()
                    )
                    baseline_keys = (
                        set(_pkg._digest_event_keys_snapshot)
                        if _pkg._digest_event_keys_snapshot is not None
                        else set(_pkg._daily_lifecycle_event_keys)
                    )
                    _pkg._scan_job_active.set()
                    try:
                        try:
                            result = _pkg.scan_all_stocks(
                                deque_manager, lifecycle_manager, notifier,
                                manuel=True, stocks=_pkg.ACTIVE_STOCKS, send_alerts=False,
                            )
                        except Exception as exc:
                            _pkg.logger.error("Gün sonu analiz çalıştırması çöktü: %s", exc, exc_info=True)
                            result = _pkg._analiz_hatasi_kaydi(
                                exc, len(_pkg.ACTIVE_STOCKS), "gün sonu analiz",
                            )
                        if result.get("status") == "tamamlandi":
                            from config import post_close_only_on_diff_enabled
                            karne_ek = _pkg._haftalik_karne_ekle(now, deque_manager)
                            if post_close_only_on_diff_enabled() and kapanis_ozeti_gitti:
                                yeni_olaylar = sorted(
                                    set(_pkg._daily_lifecycle_event_keys) - baseline_keys
                                )
                                if yeni_olaylar:
                                    aktif_f = _pkg._build_active_formations_for_summary(lifecycle_manager)
                                    mesaj = _pkg._format_post_close_diff_report(yeni_olaylar, aktif_f)
                                    ana_ok, karne_ok, _hata = _pkg._karneyle_gonder(
                                        notifier, mesaj, karne_ek
                                    )
                                    if ana_ok:
                                        _pkg.logger.info(
                                            "Gün sonu fark raporu gönderildi (%d yeni gelişme)",
                                            len(yeni_olaylar),
                                        )
                                    if karne_ek and karne_ok:
                                        _pkg._karne_gonderildi_isaretle(now)
                                        _pkg.logger.info(
                                            "Haftalık doğruluk karnesi gönderildi (gün sonu farkı altında)"
                                        )
                                elif karne_ek:
                                    karne_ok, _hata = notifier.send_text(karne_ek.strip())
                                    if karne_ok:
                                        _pkg._karne_gonderildi_isaretle(now)
                                        _pkg.logger.info(
                                            "Haftalık doğruluk karnesi gönderildi (20:00 telafisi)"
                                        )
                                else:
                                    _pkg.logger.info(
                                        "Gün sonu analizi tamamlandı; 18:45 sonrası yeni "
                                        "teyit/geçersizleşme yok, 20:00 mesajı atlandı"
                                    )
                            else:
                                rapor = _pkg._panel_raporu("", tamamlandi=True)
                                mesaj = "🌙 GÜN SONU ANALİZİ\n" + rapor
                                # Cuma karnesi 18:45 özetiyle gidemediyse (bot kapalıydı /
                                # gönderim hatası) burada gün sonu analizinin altına eklenir.
                                ana_ok, karne_ok, _hata = _pkg._karneyle_gonder(notifier, mesaj, karne_ek)
                                if ana_ok:
                                    _pkg.logger.info("Gün sonu analizi gönderildi")
                                if karne_ek and karne_ok:
                                    # İşaret KARNE parçası gerçekten gittiyse konur;
                                    # 18:45'te gönderilen karne burada ikinci kez çıkmaz.
                                    _pkg._karne_gonderildi_isaretle(now)
                                    _pkg.logger.info("Haftalık doğruluk karnesi gönderildi (gün sonu analizi altında)")
                        else:
                            notifier.send_text(
                                "⚠️ Gün sonu analizi tamamlanamadı; eski sonuç yeni sonuç gibi "
                                "gösterilmedi. Ayrıntı için bot loglarını kontrol edin."
                            )
                    finally:
                        _pkg._scan_job_active.clear()
                        last_post_close_analysis_date = now.date()
                        # Kalıcı damga: restart olsa bile aynı gün ikinci panel yok.
                        try:
                            _state_persistence.gonderim_durumu_kaydet(
                                {"post_close_analizi_gun": now.date().isoformat()})
                        except Exception as pc_hata:  # noqa: BLE001
                            _pkg.logger.debug("Gün sonu damgası yazılamadı: %s", pc_hata)
                    continue
            except Exception as e:
                _pkg.logger.error("Gün sonu analizi zamanlayıcısı hata verdi: %s", e, exc_info=True)

            # --- SABAH PRE-LOAD (08:30) ---
            try:
                if now.hour == MORNING_PRELOAD_HOUR and now.minute >= MORNING_PRELOAD_MINUTE and now.minute < MORNING_PRELOAD_MINUTE + 10:
                    if last_preload_date != now.date():
                        _pkg.morning_preload(deque_manager, pacer)
                        last_preload_date = now.date()
            except Exception as e:
                _pkg.logger.debug(f"Preload kontrol hatası: {e}")

            # --- AKŞAM BAKIMI (18:10-19:00) ---
            try:
                if now.hour == 18 and now.minute >= 10 and now.minute < 60:
                    if last_maintenance_date != now.date():
                        _pkg.evening_maintenance(deque_manager, lifecycle_manager)
                        last_maintenance_date = now.date()
            except Exception as e:
                _pkg.logger.debug(f"Bakım kontrol hatası: {e}")
            
            
            if _pkg.tarama_penceresi_acik_mi(now):
                if tarama_animi_mi(now, son_taranan_kapanis):
                    # Tarama anı: en son kapanmış mum + 5 dk doldu.
                    kapanis = son_kapanan_mum_ani(now)
                    _pkg.logger.info(f"TARAMA - {now.strftime('%H:%M:%S')} "
                                f"(mum {kapanis.strftime('%H:%M')}'de kapandı, "
                                f"günün {kapanis.hour - 9}. taraması)")
                    _pkg._scan_job_active.set()
                    try:
                        _pkg.scan_all_stocks(
                            deque_manager, lifecycle_manager, notifier,
                            manuel=False, stocks=_pkg.ACTIVE_STOCKS, send_alerts=True,
                        )
                    finally:
                        _pkg._scan_job_active.clear()
                    _pkg._tarama_saglik_kontrolu(notifier)
                    son_taranan_kapanis = kapanis
                    deque_manager.save_all()
                    # Tarama sonunda bekleyen aday tamponu kalıcılaştır (Batch 5 / B3):
                    # restart tamponun tamamını kaybetmesin, tarama başına tek yazma.
                    _pkg.digest_tamponu_kaydet()
                    # Karne defteri yedeği (varsa Supabase; aralıklı, en fazla 5 dk'da bir).
                    _pkg._karne_uzak_kaydet()
                    # Faz 2.6: Formation mirror kuyruğunu Supabase'e flush et
                    if _pkg._supabase_store_ref is not None:
                        try:
                            from state.formation_mirror import get_mirror_queue
                            get_mirror_queue().flush(_pkg._supabase_store_ref)
                        except Exception:  # noqa: BLE001
                            # Mirror kaybı sessiz kalmasın: kuyruk bellekte kalır,
                            # sonraki turda yeniden denenir (2026-10-26 denetimi).
                            _pkg.logger.warning("Formation mirror flush atlandı", exc_info=True)
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
                _pkg.logger.info(f"Sonraki tarama {hedef.strftime('%H:%M')} -> {bekle/60:.1f} dk bekleniyor")
                # Max 5dk uyu; /tara isteği gelirse uyku erken biter.
                if _pkg._bekle_veya_tarama(min(bekle, 300)):
                    _pkg.logger.info("Elle tarama isteği geldi, uyku kesildi")
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
                _pkg.logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                # Boş saatlerin tek gerçek işi: kapanan kayıtların sonucunu yaz.
                _pkg._ileri_test_gece(now)
                # Sonuç yazıldıktan SONRA denetim: aynı günün taze defteri okunur.
                _pkg._gece_denetimi(now)
                if _pkg._bekle_veya_tarama(sleep_time):
                    _pkg.logger.info("Seans dışı analiz isteği geldi; ana döngü uyandırıldı")
                    continue
                
        except KeyboardInterrupt:
            _pkg.logger.info("Bot durduruldu (Ctrl+C)")
            break
        except Exception as e:
            _pkg.daily_stats['errors'] += 1
            _pkg.logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            if _pkg._live_state.status().get('tarama_suruyor'):
                _pkg._analiz_hatasi_kaydi(e, len(_pkg.ACTIVE_STOCKS), "ana döngü")
            _pkg.write_heartbeat(force=True)
            time.sleep(30)
            continue
    
    # Güvenli kapanış (SIGTERM/SIGINT)
    _pkg.logger.info("Bot kapanıyor, son kayıtlar yapılıyor...")
    try:
        if _pkg._telegram_listener_ref is not None:
            _pkg._telegram_listener_ref.stop()
    except Exception as e:
        _pkg.logger.warning(f"Komut dinleyicisi kapatılamadı: {e}")
    # Webhook modunda: kapanışta gelen güncellemeler 503 alsın (Telegram tekrar
    # dener; yarım kalan komut yanıtı üretilmez).
    setattr(_pkg, "_telegram_update_processor_ref", None)
    try:
        if _pkg._deque_manager_ref is not None:
            _pkg._deque_manager_ref.save_all()
        _pkg.son_tarama_kaydet()
        # Bekleyen gün içi adaylar kapanışta da kaybolmasın (Batch 5 / B3).
        _pkg.digest_tamponu_kaydet()
        # Faz 2.6: Kapanışta bekleyen mirror kuyruğunu flush et (SIGTERM/SIGINT)
        if _pkg._supabase_store_ref is not None:
            try:
                from state.formation_mirror import get_mirror_queue
                get_mirror_queue().flush(_pkg._supabase_store_ref)
            except Exception:  # noqa: BLE001
                # Kapanışta mirror kaybı veri kaybı demektir; sessiz geçilmesin.
                _pkg.logger.warning("Kapanışta mirror flush atlandı", exc_info=True)
        _pkg.write_heartbeat(force=True)
    except Exception as e:
        _pkg.logger.error(f"Kapanış kayıt hatası: {e}")
    _pkg.logger.info("Bot durdu")


def _render_test_sender(text):
    """/test ucu icin geri cagirma: notifier hazirsa tek mesaj gonderir.

    Notifier main_loop icinde kurulur; bu yuzden modul seviyesindeki global
    uzerinden okunur (server startup'ta None olabilir, cagri aninda doludur).
    """
    notifier = _pkg._notifier_ref
    if notifier is None:
        return False, "bot henuz baslamadi"
    return notifier.send_text(text)


