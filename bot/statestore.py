"""bot/statestore.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

#: Üst zaman dilimi: public görselinde alarm karesinin yanına eklenen kare
#: (2026-10-22 kararı: public = 1 kare + üst TF; DM 4 kare alır).
#: `mtf_destek` hesabındaki teyit TF'siyle aynı mantık, karttan bağımsız sabit.
_UST_TF = {"1h": "4h", "2h": "4h", "4h": "1d"}

#: Üst TF'si OLMAYAN alarmlarda public görseline eklenen ikinci kare.
#: Tarama 1s/2s/4s/1g yapıyor; 1g'nin üstü (haftalık) yok. 2026-10-28 kullanıcı
#: kararı: "tek kare kalmasın, 4s alt zaman dilimi olarak gelsin". Etiket de
#: doğru okunsun diye kareye `rol="alt"` yazılır (yanlış "üst" demek yerine).
_ALT_TF = {"1d": "4h"}


# main_loop icinde olusturulan nesnelerin global referanslari (heartbeat icin)
_deque_manager_ref = None


_notifier_ref = None


# İşlem günü değilken her döngüde aynı log satırını basmamak için gün damgası.
_islem_gunu_loglandi = {"gun": None}


# SESSİZ ARIZA BEKÇİSİ: üst üste başarısız tarama turu sayacı + son uyarı günü.
# Neden: Yahoo/veri kaynağı bozulduğunda süreç ayakta kalır, kanal sessizleşir ve
# sahibin bundan haberi olmaz (kullanıcı "bot öldü" sanır). En fazla günde 1 DM.
_ardisik_basarisiz_tur = 0


_son_tarama_uyari_gun = None


TARAMA_UYARI_ESIK_TUR = 3


_supabase_store_ref = None


_deferred_alert_buffer = DeferredAlertBuffer()


# Haftalık doğruluk karnesi defteri (yerel JSON; Supabase GEREKTİRMEZ).
# Tembel kurulur: dosya yolu DATA_DIR'e bağlı, import anında I/O yapılmaz.
_karne_defteri: "KarneDefteri | None" = None


# Uzak yedeğe yazma aralığı (saniye): defter her tarama turunda birkaç kayıt alır;
# her kayıtta tüm JSON'u Supabase'e yazmak gereksiz trafik olurdu.
_karne_son_uzak_yazma = 0.0


KARNE_UZAK_YAZMA_ARALIK_SN = 300


# Bugüne ait 18:45 kapanış özetinin gönderilip gönderilmediği (ISO gün). Kalıcı
# tamponla birlikte Supabase/diske yazılır; restart sonrası aynı özet iki kez gitmez.
_digest_son_gonderim_gun = None


# Politika tek kaynak: `config.ALERT_STATES` (anlık) / `config.WATCH_STATES`
# (digest). Bu frozenset yalnız okuma kolaylığı içindir (B7 kararı config'te).
IMMEDIATE_ALERT_STATES = frozenset(ALERT_STATES)


# Yaşam döngüsü "slotu sıfırlayan" state'ler: motor bu state'lerden birine
# düştüğünde ilgili hisse/TF slotunun tek-seferlik mühürleri (notifier
# son_alert) ve 4 saatlik zaman cooldown'ları temizlenir. Böylece aynı slotu
# tekrar kaplayan yeni formasyon eski mühürle sessiz kalmadan, 4 saat
# beklemeksizin anında bildirilebilir (tekrar alarm koruması, bkz. SORUN_RAPORU).
TEKRAR_SIFIRLA_STATELER = frozenset({
    "FORMASYON_YOK",
    "FORMASYON_GECERSIZ",
    "FORMASYON_ZAYIFLADI",
    "KIRILIM_TEYIT_ALAMADI",
})


def _cache_verisi_kullanilabilir(yas_dk: float, taze_veri_var: bool, seans_acik: bool) -> bool:
    """Fetch başarısızsa seans dışı son mumları yaş sınırına kadar kullan."""
    if yas_dk > _pkg.OFFSESSION_CACHE_MAX_AGE_DAYS * 24 * 60:
        return False
    if taze_veri_var:
        return True
    return not seans_acik or yas_dk <= STALE_BAR_UYARI_DK


# === SİNYAL YÖNETİMİ (systemctl stop -> SIGTERM) ===
# Neden? systemd durdururken Python anında ölürse o taramada biriken deque'ler kaybolur.
_shutdown_requested = False

# Startup tamamlanana ve shutdown baslayana kadar hazirlik sinyali kapali.
_startup_ready = False


_deque_manager_ref = None


# Telegram komutları için paylaşılan durum (tarama thread'i yazar, listener okur)
_live_state = LiveState()


_scan_istegi = threading.Event()


_scan_job_active = threading.Event()


_scan_request_lock = threading.Lock()


_scan_job_request = None


_scan_last_result = {}


_lifecycle_manager_ref = None


_telegram_listener_ref = None


# PUBLIC komut hedefinin Telegram'daki GERÇEK tipi (getChat ile bir kez okunur).
# Neden gerekli: `TELEGRAM_GROUP_ID` bir KANAL gösteriyorsa komut imkânsızdır
# (üyeler kanala yazamaz; admin gönderilerinde `from` yoktur). Bu teşhis
# olmadan "public'te komutlar çalışmıyor" sessiz bir bilmeceye dönüşür.
_public_hedef_bilgisi = None


# Webhook modunda: Telegram güncellemelerini işleyen nesne (yoklama thread'i YOK).
# health_server'ın /webhook ucu bu referans üzerinden çalışır; bot hazır değilse
# (açılıştaki ilk veri yüklemesi) uç 503 döner ve Telegram tekrar dener.
_telegram_update_processor_ref = None


# Aynı anda birden çok webhook isteği gelirse (Telegram sıralı gönderir ama ağ
# tekrarı olabilir) komut işleme serileştirilir: dinleyicinin hız sınırı/tekrar
# kümesi kilitli bir bölgede kullanılır.
_telegram_webhook_kilidi = threading.Lock()


# Komut katmanı modu: "webhook" / "yoklama" / "kapali" (ya da başlangıçta None).
# /health bunu raporlar: "komutlar neden gelmiyor?" sorusunun ilk cevabı budur.
_komut_modu = None


# Render PORT'unda çalışan küçük HTTP sunucusu (webhook + /health + /test).
_health_server_ref = None


# === GÜNLÜK ÖZET ===
last_run_stats = {}


def _analiz_hatasi_kaydi(exc, istek_hisse: int, kaynak: str = "analiz") -> dict:
    """scan_all_stocks dışında fırlayan hataları da tutarlı başarısız durum yap."""
    global last_run_stats
    bitis = _pkg.datetime.now(ISTANBUL_TZ).isoformat()
    hata = f"{kaynak} hatası: {type(exc).__name__}: {exc}"
    _pkg._live_state.fail_scan(
        hata,
        _pkg.datetime.now(ISTANBUL_TZ),
        hata_hisse=max(0, int(istek_hisse)),
        islenen_hisse=0,
        istek_hisse=max(0, int(istek_hisse)),
    )
    setattr(_pkg, "last_run_stats", {
        "status": "basarisiz",
        "requested": max(0, int(istek_hisse)),
        "processed": 0,
        "failed": max(0, int(istek_hisse)),
        "fresh_fetch": None,
        "fetch_failures": None,
        "data_asof": None,
        "oldest_bar_age_minutes": None,
        "finished_at": bitis,
    })
    _pkg.son_tarama_kaydet()
    return dict(_pkg.last_run_stats)


# Aynı hisse/TF slotu gün içinde her taramada yeniden bulunur; "bugün kaç formasyon
# buldun?" sorusunun doğru cevabı BENZERSİZ slot sayısıdır. Eskiden sayaç her
# taramada yeniden artıyordu (9 tarama x 21 slot = 189) ve metrik şişiyordu.
# Set, daily_stats içinde tutulmaz (JSON'a serileşmez/heartbeat'e sığmaz).
_daily_pattern_keys: set = set()


daily_stats = {
    'stocks_scanned': 0,
    'patterns_found': 0,
    'alerts_sent': 0,
    'errors': 0,
    # --- ADAY HUNİSİ (kullanıcı isteği) ---
    # "18 üretiliyor ama 3-5'inden bahsediliyor" sorusunun cevabı: her adayın
    # akıbeti sayılır ve /durum'da tek satırda gösterilir. Hiçbir kayıt sessizce
    # düşmez: ya gönderilir, ya ertelenir, ya da NEDENİ sayılır.
    'alerts_attempted': 0,        # acil gönderim denemesi
    'alerts_failed': 0,           # deneme başarısız (HTTP/ağ)
    'alerts_deferred': 0,         # WATCH state: 18:45 digest'ine ertelendi
    'alerts_below_threshold': 0,  # kalite eşiği altı (push üretmez)
    'alerts_state_disabled': 0,   # state hiçbir push akışında değil (yalnız panel)
    'alerts_bar_kapanmadi': 0,    # kapanmamış bar nedeniyle push ertelendi (P0 güvenlik kapısı)
    'alerts_break_close_invalid': 0,  # confirmation/retest close sınırı doğrulamadı
    'alerts_digest_overflow': 0,  # digest limiti nedeniyle gösterilmeyen aday
    'alerts_kuyruk': 0,           # acil alarm engel yüzünden kuyruğa alındı (Batch 5 / B4)
    'alerts_engel_cooldown': 0,   # cooldown nedeniyle gönderilemedi (B4 kuyruğuna girer)
    'alerts_engel_kap': 0,        # saatlik/günlük kap nedeniyle gönderilemedi
    'alerts_engel_tekrar': 0,     # aynı olay tekrar bastırıldı (tekrar mühürü; nihai red, kuyruğa girmez)
    # Veri sağlığı (FAZ 1): fetch başarısızlıkları artık SAYILIYOR ve görünür.
    # Önceden fetch başarısız olunca cache dolu olduğu için hiç log satırı yoktu
    # -> Yahoo saatlerce kapalıysa bot "sağlıklı" görünürken kör çalışıyordu.
    'fetch_ok': 0,
    'fetch_failures': 0,
    'fetch_retries': 0,
    'fetch_retry_recovered': 0,
    'stale_stocks': 0,
    'max_bar_age_min': None,
    'data_stale': False,
    'veri_yok_modu': False,
    'split_atlanan': 0,
    'son_tarama_suresi_dk': None,
    'gunluk_bar_sayisi': None,
    # Lifecycle olayları günlük tekilleştirilmiş olarak tutulur; başarısız
    # teyitsiz denemeler, teyitli kırılım geçersizleşmesi sayacına girmez.
    'basarisiz_kirilim': 0,
    'kirilim_teyitli_olay_sayisi': 0,
    'retest_basarili_olay_sayisi': 0,
    'kirilim_gecersizlesti_olay_sayisi': 0,
    'sessiz_gecersizlesme_sayisi': 0,
    # Tarama turu sayısı; 48 hisse × 9 tur = 432 hisse tarandı şeklinde yazılmaz.
    'tarama_sayisi': 0,
    'last_reset': _pkg.datetime.now(ISTANBUL_TZ).date()
}


# Gün içinde BENZERSİZ başarısız kırılım sayacı (hisse|TF|bar): aynı slot her
# taramada yeniden üretildiği için ham sayım olayı şişirirdi.
_daily_basarisiz_keys: set = set()


_daily_unannounced_invalidation_keys: set = set()


_daily_lifecycle_event_keys: set[str] = set()


_digest_event_keys_snapshot: set[str] | None = None


_LIFECYCLE_CONFIRMATION_TYPES = frozenset({"BREAK_CONFIRMED", "COUNTER_BREAK"})


_CONFIRMED_INVALIDATION_REASONS = frozenset({
    "Kırılım sonrası formasyon alanına dönüldü",
    "Başarılı retest sonrası yapı içine dönüldü",
})


_LIFECYCLE_EVENT_COUNTERS = {
    "KIRILIM_TEYITLI": "kirilim_teyitli_olay_sayisi",
    "RETEST_BASARILI": "retest_basarili_olay_sayisi",
    "KIRILIM_GECERSIZLESTI": "kirilim_gecersizlesti_olay_sayisi",
}


# --- GÜNLÜK SAYAÇ KALICILIĞI (restart gün sürekliliği) ---------------------
# Canlı denetimde ölçüldü: gün ortasında restart olunca 18:45 kanal özeti
# "❌ 8 başarısız / 8 tarama" diyordu; gerçek gün "❌ 9 / 10 tarama" idi.
# Sayaçlar artık GÜN damgalı olarak diske yazılır, aynı gün restart'ta geri yüklenir.
_KALICI_SAYACLAR = ('basarisiz_kirilim', 'kirilim_teyitli_olay_sayisi', 'retest_basarili_olay_sayisi', 'kirilim_gecersizlesti_olay_sayisi', 'sessiz_gecersizlesme_sayisi', 'tarama_sayisi', 'alerts_sent', 'stocks_scanned')


# Restart anında devralınan "başarısız kırılım" sayısı: olay detayı saklanmadığı
# için yalnız SAYI taşınır, yeni olaylar bu tabanın üstüne eklenir.
_daily_basarisiz_tabani = 0


# === ÇOKLU ÖRNEK KORUMASI (Batch 6 / B10) ===
# Aynı token + aynı Supabase anahtarıyla iki kopya çalışırsa: çift mesaj + cache
# yarışı. Yoklama modunda Telegram 409 verir; webhook modunda hiçbir sinyal yoktu.
# Sert kilit kurulmaz (kısa ağ kesintisinde botu durdurmak daha kötü olurdu):
# durum loglanır, heartbeat ve /durum'a taşınır.
INSTANCE_ID = (os.environ.get("BOT_INSTANCE_ID") or "").strip() or f"{socket.gethostname()}:{os.getpid()}"


ORNEK_KONTROL_ARALIK_SN = 300


_cift_ornek_durumu = {
    "instance_id": INSTANCE_ID,
    "son_kontrol": None,
    "canli_digerleri": [],
    "uyari": False,
}


# === HEARTBEAT ===
# Yazma amplifikasyonu koruması (Batch 6 / B5): heartbeat her hisse sonrası
# çağrılıyordu (48 hisse × tarama = 48 Supabase UPSERT + 48 dosya yazımı).
# Yeni kural:
#   - yerel dosya: HEARTBEAT_MIN_ARALIK_SN'den sık yazılmaz (canlılık göstergesi
#     olduğu için tamamen atlanmaz; force=True ile hemen yazılır),
#   - Supabase: içerik değişmediyse veya HEARTBEAT_UZAK_ARALIK_SN dolmadıysa yazılmaz.
_son_heartbeat_zamani = 0.0


_son_heartbeat_icerik = None


_son_heartbeat_uzak_zamani = 0.0


#: MS (piyasa yapısı) motoru hata sayacı. Kart bu uyarıyı BASMAZ (karar D:
#: "⚠ MS domain devre dışı yalnız /durum'da"); alarm kartı karar belgesidir,
#: altyapı arızası oraya girmez. Sayaç `/durum`da görünür ki hata sessiz kalmasın.
#:
#: HİSSE BAZINDA sayılır, olay bazında değil: aynı hissenin iki TF'si alarm
#: ürettiğinde bağlam iki kez hazırlanır (çıktı önbellekten gelir) ve olay bazlı
#: sayaç aynı arızayı iki kez yazardı. Set, tekrarı yutar.
_ms_hata_sayaci: Dict = {"hisseler": set(), "son": ""}


# === /panel — 48 hisse x 4 zaman dilimi slot tablosu ===
# Neden ayrı komut: /canli ve /formasyonlar yalnızca DOLU slotları listeler; hangi
# hissede hiç formasyon yok, hangi TF boş, toplam kaç slot dolu -> görünmez.
# /panel evrenin tamamını (ACTIVE_STOCKS x 4 TF) tek bakışta gösterir: doluluk
# sayıları + kompozit puana göre en anlamlı 12 aday.
WATCH_CONTEXT_HAVUZU = 12    # geçmiş uyumluluğu; acil bildirimlere aday eklenmez


SUMMARY_MARKERS_SUPABASE_KEY = "state:daily_summary_markers"


# /grafik argümanı: sembol + isteğe bağlı zaman dilimi + isteğe bağlı görünüm.
# Desen bilinçli dar — bozuk girdi (path, uzun metin) Telegram'a hiç gitmemeli.
_GRAFIK_SEMBOL = re.compile(r"^([A-Z][A-Z0-9]{1,9})(?:\.IS)?$")


_GRAFIK_TF = {"1s": "1h", "1h": "1h", "2s": "2h", "2h": "2h",
              "4s": "4h", "4h": "4h", "1g": "1d", "1d": "1d"}


_GRAFIK_GORUNUM = {"sade": True, "detay": False}


_grafik_is_kilidi = threading.Lock()


_grafik_aktif_is = {}


_GRAFIK_HEDEF_SN = 60


# Eski iç adlar (testler ve main gövdesi) korunuyor: yol/snapshot yardımcıları
# artık `state/paths.py`'de yaşıyor.
_son_tarama_data_dir = _state_paths.son_tarama_data_dir


_son_tarama_yolu = _state_paths.son_tarama_yolu


_digest_pending_yolu = _state_paths.digest_pending_yolu


_kayit_zamani = _state_paths.kayit_zamani


_yeni_snapshot = _state_paths.yeni_snapshot


SON_TARAMA_DOSYA = _state_paths.SON_TARAMA_DOSYA


SON_TARAMA_SUPABASE_KEY = _state_paths.SON_TARAMA_SUPABASE_KEY


def son_tarama_kaydet(store=None, data_dir=None) -> bool:
    """Son listeyi Supabase + diske kaydeder (bkz. state.persistence)."""
    return _state_persistence.son_tarama_kaydet(
        _pkg._live_state,
        store=_pkg._supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )


def son_tarama_yukle(store=None, data_dir=None) -> int:
    """Kayıtlı son taramayı yükler (bkz. state.persistence)."""
    return _state_persistence.son_tarama_yukle(
        _pkg._live_state,
        store=_pkg._supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )


_webhook_adres_gizle = _transport_telegram.webhook_adres_gizle


_telegram_api_cagri = _transport_telegram.api_cagri


_telegram_yanit_oku = _transport_telegram.yanit_oku


_domain_runner_cache = None


_DOMAIN_TIMEFRAMES = ("1h", "2h", "4h", "1d")


# --- endekse göre göreli güç (2026-10-22) ----------------------------------
# Kullanıcı kararı: "XU100'e göre göreli güç" karta girsin. Taban kuralı: iki
# yüzde AYNI pencerede ve AYNI zaman diliminde hesaplanır; fark "puan" olarak
# yazılır ("%2,1" değil, "2,1 puan") çünkü iki yüzdenin farkı yüzde değildir.
# Endeks yoksa/veri kısaysa satır basılmaz (uydurma yok).
_GORELI_MUM = 20


def _karne_al() -> KarneDefteri:
    """Karne defterini (tembel) oluşturur; dosya okunamazsa da çalışır.

    Opsiyonel uzak yedek (Supabase): kuruluysa yerel defterle BİRLEŞTİRİLİR
    (Render'da DATA_DIR=/tmp olduğu için restart/redeploy yereli siler; yedek
    haftalık karnenin boşalmasını engeller). Supabase yoksa hiçbir şey değişmez.
    """
    global _karne_defteri
    if _pkg._karne_defteri is None:
        setattr(_pkg, "_karne_defteri", KarneDefteri())
        try:
            _state_persistence.karne_defteri_yukle(_pkg._karne_defteri, _pkg._supabase_store_ref)
        except Exception as exc:  # noqa: BLE001 - yedek sorunu karneyi engellemesin
            _pkg.logger.debug("Karne uzak yedeği yüklenemedi: %s", exc)
    return _pkg._karne_defteri


# Telegram tek mesaj sınırı 4096; `kirp()` sondan kestiği için karne (mesajın
# ALTINDA) kaybolabilirdi. Bu sınırın üstünde karne ikinci mesaj olarak gider.
_MESAJ_GUVENLI_SINIR = 3900


# Batch 8 / C2 (8.4): digest tamponu kalıcılığı da `state/persistence.py`'de.
DIGEST_PENDING_SUPABASE_KEY = _state_persistence.DIGEST_PENDING_SUPABASE_KEY


DIGEST_PENDING_DOSYA = _state_paths.DIGEST_PENDING_DOSYA


def digest_tamponu_kaydet(store=None, data_dir=None) -> bool:
    """Bekleyen gün içi adayları Supabase + diske yazar."""
    return _state_persistence.digest_tamponu_kaydet(
        _pkg._deferred_alert_buffer,
        store=_pkg._supabase_store_ref if store is None else store,
        data_dir=data_dir,
        son_digest_gun=_pkg._digest_son_gonderim_gun,
    )


def digest_tamponu_yukle(store=None, data_dir=None) -> int:
    """En yeni digest tamponunu yükler; yüklenen aday sayısını döner."""
    global _digest_son_gonderim_gun
    sayi, son_digest_gun = _state_persistence.digest_tamponu_yukle(
        _pkg._deferred_alert_buffer,
        store=_pkg._supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )
    if son_digest_gun is not None:
        setattr(_pkg, "_digest_son_gonderim_gun", son_digest_gun)
    return sayi


_POST_CLOSE_DIFF_LABELS = {
    "KIRILIM_TEYITLI": "🏁 Kırılım teyitli",
    "RETEST_BASARILI": "🔁 Retest başarılı",
    "KIRILIM_GECERSIZLESTI": "❌ Kırılım geçersizleşti",
}


# --- İLERİ TEST (gölge defter) ----------------------------------------------
# 2026-10-25: Ölçümün açık kalan tek sorusu "kama + üst TF aynı yönde" bayrağı
# örneklem DIŞINDA işe yarıyor mu? Cevap, gönderilen her uyarının 24 bar sonraki
# sonucunu kaydetmekle verilir (docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md
# §11.4). Bu iş mesaj GÖNDERMEZ, eşik DEĞİŞTİRMEZ; yalnız kayıt tutar.
ILERI_TEST_GECE_SAAT = 19          # BIST kapanışından sonra, gece mesaisi yok


_ileri_test_son_gece = ""          # bu süreçte işin koştuğu gün (YYYY-MM-DD)


# --- GECE DENETİMİ (#2 tutarlılık · #3 ölçüm tazeleme) -----------------------
# 2026-10-25: Gece işi iki soruyu yeniden sorar ama hiçbir şeyi DEĞİŞTİRMEZ:
#   1. Canlıda gönderilen uyarı, aynı barlarla yeniden oynatıldığında motor
#      tarafından yine üretiliyor mu? (`tutarlilik.py`)
#   2. "kama + üst TF aynı yönde" bayrağı bayraksız uyarılardan ölçülebilir
#      biçimde fazla veriyor mu? (`olcum_tazele.py`)
# Sonuç loga + `gece_raporu` tablosuna yazılır. DM yalnız EYLEM gerektiren
# sonuçta gider (sapma ya da "bayrak kaldırılsın"); gece 03:00 mesajı yok ve
# öneri kendiliğinden uygulanmaz. Toplam iş süre sınırlıdır (en fazla 10 replay)
# ve yalnız seans kapalıyken koşar; canlı taramayı bekletmez.
_gece_denetim_son_gun = ""        # bu süreçte denetimin koştuğu gün (YYYY-MM-DD)


