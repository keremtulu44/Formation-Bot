"""bot/scan.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

# Def-anı varsayılan: import anında _pkg.okunamaz (döngü); sabit değer çapraz
# import edilir (monkeypatch yaması yok; değer bot.statestore'da tek sahipli).
from bot.statestore import _GORELI_MUM  # noqa: F401  (aşağıdaki varsayılan için)

def _evren_olcek_uyarisi(evren=None) -> str:
    """Evren eşiğin üzerindeyse pacing/panel/digest limitlerini hatırlatır.

    Davranışı DEĞİŞTİRMEZ: yalnız loga tek satır uyarı düşer (rapor B8: evren
    48'den büyürse önce pacing/digest/panel limitleri ölçülmeli).
    """
    hisseler = list(_pkg.ACTIVE_STOCKS if evren is None else evren)
    if len(hisseler) <= EVREN_BUYUME_UYARI_ESIGI:
        return ""
    return (f"⚠️ Evren {len(hisseler)} hisse (eşik {EVREN_BUYUME_UYARI_ESIGI}): pacing "
            "(SCAN_*), panel mesaj bütçesi ve 18:45 digest limiti yeniden ölçülmeli "
            "(KODLAMA_PLANI → 'Evren büyütme').")


def _tarama_saglik_kontrolu(notifier) -> None:
    """Tur sonucuna göre sessiz arıza bekçisi: üst üste başarısızsa sahibe DM.

    Başarı ölçütü: tur "tamamlandi" VE en az bir hisse işlendi. Üst üste
    TARAMA_UYARI_ESIK_TUR tur bu sağlanmazsa bir kez DM gider (günde en fazla
    bir). Kanal sessizleşmeden sahip haberdar olur; başarılı turda sayaç sıfırlanır.
    """
    global _ardisik_basarisiz_tur, _son_tarama_uyari_gun
    try:
        durum = (_pkg.last_run_stats or {}).get("status")
        islenen = int((_pkg.last_run_stats or {}).get("processed") or 0)
    except Exception:  # noqa: BLE001
        return
    if durum == "tamamlandi" and islenen > 0:
        if _pkg._ardisik_basarisiz_tur:
            _pkg.logger.info("Tarama sağlığı düzeldi (üst üste %d başarısız turdan sonra).",
                        _pkg._ardisik_basarisiz_tur)
        setattr(_pkg, "_ardisik_basarisiz_tur", 0)
        return
    setattr(_pkg, "_ardisik_basarisiz_tur", _pkg._ardisik_basarisiz_tur + (1))
    if _pkg._ardisik_basarisiz_tur < _pkg.TARAMA_UYARI_ESIK_TUR:
        return
    bugun = _pkg.datetime.now(ISTANBUL_TZ).date().isoformat()
    if _pkg._son_tarama_uyari_gun == bugun:
        return
    setattr(_pkg, "_son_tarama_uyari_gun", bugun)
    _pkg.logger.error("Tarama üst üste %d turdur başarısız; sahibe uyarı gönderiliyor.",
                 _pkg._ardisik_basarisiz_tur)
    if notifier is None or not getattr(notifier, "enabled", False):
        return
    try:
        notifier.send_text(
            "⚠️ Tarama üst üste %d turdur sonuç üretemedi.\n"
            "Kanal sessiz kalabilir (veri kaynağı/bağlantı sorunu).\n"
            "Durum: /durum · Panel: /panel\n"
            "Botu yeniden başlatmak gerekirse Render → servis → Restart."
            % _pkg._ardisik_basarisiz_tur)
    except Exception as hata:  # noqa: BLE001
        _pkg.logger.debug("Tarama sağlık uyarısı gönderilemedi: %s", hata)


def create_yahoo_pacer() -> YahooRequestPacer:
    """Her Yahoo isteğine uygulanan seri pacing ayarları."""
    return YahooRequestPacer(
        batch_size=SCAN_REQUEST_BATCH_SIZE,
        request_delay_min=SCAN_REQUEST_DELAY_MIN_SEC,
        request_delay_max=SCAN_REQUEST_DELAY_MAX_SEC,
        batch_pause_min=SCAN_BATCH_PAUSE_MIN_SEC,
        batch_pause_max=SCAN_BATCH_PAUSE_MAX_SEC,
        logger=_pkg.logger,
    )


def fetch_1h_stocks_paced(stocks, pacer: YahooRequestPacer, phase: str, periods=None):
    """1H verilerini seri çeker; geçici hatalı sembolleri bir kez tekrar dener.

    Dönenler: başarılı DataFrame'ler, kalıcı/son hatalar, retry sayısı,
    retry ile kurtarılan sembol sayısı.
    """
    fetched = {}
    failures = {}
    retryable = {}
    periods = periods or {}

    for index, stock in enumerate(stocks, start=1):
        if _pkg._shutdown_requested:
            _pkg.logger.info(f"{phase}: kapanış istendi; veri çekimi durduruluyor")
            break
        period = periods.get(stock, FULL_1H_FETCH_PERIOD)
        try:
            with pacer.request(f"{stock} 1H"):
                frame, can_retry, reason = _pkg.fetch_yfinance_1h(
                    stock, period=period, with_status=True
                )
        except Exception as exc:
            frame, can_retry, reason = None, False, f"{type(exc).__name__}: {exc}"

        if frame is not None:
            fetched[stock] = frame
            _pkg.logger.info(
                f"{phase} [{index}/{len(stocks)}] {stock}: {period} taze 1H veri alındı "
                f"({len(frame)} bar)"
            )
        else:
            failures[stock] = reason or "veri alınamadı"
            if can_retry:
                retryable[stock] = failures.pop(stock)
                _pkg.logger.warning(f"{phase} {stock}: geçici fetch hatası; son turda bir kez denenecek ({retryable[stock]})")
            else:
                _pkg.logger.warning(f"{phase} {stock}: yeniden denenmeyecek fetch hatası ({failures[stock]})")

    retry_count = 0
    recovered_count = 0
    if retryable and _pkg._shutdown_requested:
        failures.update(retryable)
    if retryable and not _pkg._shutdown_requested:
        backoff = random.uniform(SCAN_RETRY_BACKOFF_MIN_SEC, SCAN_RETRY_BACKOFF_MAX_SEC)
        _pkg.logger.warning(
            f"{phase}: {len(retryable)} geçici veri hatası için tek tekrar denemesi; "
            f"{backoff:.1f} sn bekleniyor"
        )
        time.sleep(backoff)
        pacer.reset_batch()

        for stock, first_reason in retryable.items():
            if _pkg._shutdown_requested:
                failures[stock] = first_reason
                continue
            retry_count += 1
            try:
                with pacer.request(f"{stock} 1H retry"):
                    frame, _can_retry_again, reason = _pkg.fetch_yfinance_1h(
                        stock,
                        period=periods.get(stock, FULL_1H_FETCH_PERIOD),
                        with_status=True,
                    )
            except Exception as exc:
                frame, reason = None, f"{type(exc).__name__}: {exc}"

            if frame is not None:
                fetched[stock] = frame
                recovered_count += 1
                _pkg.logger.info(f"{phase} {stock}: tekrar denemesi başarılı ({len(frame)} bar)")
            else:
                failures[stock] = reason or first_reason or "tekrar denemesi başarısız"
                _pkg.logger.warning(f"{phase} {stock}: tekrar denemesi de başarısız ({failures[stock]})")

    return fetched, failures, retry_count, recovered_count


def _tekil_ornek_kontrolu(store=None, force: bool = False) -> dict:
    """Supabase'de başka canlı bot örneği var mı? (uyarı + heartbeat alanı)"""
    global _cift_ornek_durumu
    store = _pkg._supabase_store_ref if store is None else store
    if store is None or not getattr(store, "writable", True):
        return _pkg._cift_ornek_durumu
    simdi = _pkg.datetime.now(ISTANBUL_TZ)
    son = _pkg._cift_ornek_durumu.get("son_kontrol")
    if not force and son is not None and (simdi - son).total_seconds() < _pkg.ORNEK_KONTROL_ARALIK_SN:
        return _pkg._cift_ornek_durumu
    try:
        sonuc = store.ornek_bildir(_pkg.INSTANCE_ID, simdi.isoformat())
    except Exception as exc:
        _pkg.logger.debug(f"Çoklu örnek kontrolü yapılamadı: {exc}")
        return _pkg._cift_ornek_durumu
    if not isinstance(sonuc, dict):
        return _pkg._cift_ornek_durumu
    digerleri = sonuc.get("canli_digerleri") or []
    setattr(_pkg, "_cift_ornek_durumu", {
        "instance_id": _pkg.INSTANCE_ID,
        "son_kontrol": simdi,
        "canli_digerleri": digerleri,
        "uyari": bool(digerleri),
    })
    if digerleri:
        _pkg.logger.error(
            "⚠️ AYNI ANDA ÇALIŞAN BAŞKA BOT ÖRNEĞİ GÖRÜNÜYOR: %s — çift mesaj ve cache "
            "yarışı riski. Fazladan kopyayı kapatın (Render'da tek instance olmalı).",
            ", ".join(str(d.get("id")) for d in digerleri),
        )
    return _pkg._cift_ornek_durumu


def _formation_history_baslangic_kontrolu() -> dict:
    """Faz 2.1: startup'ta çoklu formasyon history defterlerinin sağlık raporu.

    ZORUNLU DEĞİL: registry tarama anında lazy okunur, bu adım olmadan da
    history korunur. Amacı operatöre görünürlük vermek ve BOZUK defterleri
    loga düşürmektir. Bot hiçbir koşulda bu adım yüzünden durmaz.
    """
    try:
        from state import formation_history as fh
        rapor = fh.saglik_raporu()
    except Exception as exc:  # pragma: no cover - savunma amaçlı
        _pkg.logger.warning("Formation history raporu alınamadı (bot çalışmaya devam ediyor): %s", exc)
        return {}
    if rapor.get("dosya"):
        _pkg.logger.info(
            "Formation history: %d defter, %d kayıt (dizin %s)",
            rapor["dosya"], rapor["kayit"], rapor.get("yol"))
    if rapor.get("bozuk"):
        # Bozuk defter: `yukle()` boş defter döner, tarama Faz 1 yoluyla devam
        # eder. Yeni kimlik üretimi olur ama bot ÇALIŞIR.
        _pkg.logger.warning(
            "Formation history: %d bozuk defer atlandı (yeni kimlik üretilir, bot çalışıyor): %s",
            len(rapor["bozuk"]), ", ".join(rapor["bozuk"][:10]))
    return rapor


def _load_domain_runner():
    """Domain runner'ı yalnızca teyitli bir Telegram olayı gerektiğinde yükle.

    Import hatası cache'lenmez; sonraki tarama/olayda yeniden denenebilir.
    Domain kaynaklarına dokunulmaz ve sonuç cache'lerinden eski çıktı okunmaz.
    """
    global _domain_runner_cache
    if _pkg._domain_runner_cache is not None:
        return _pkg._domain_runner_cache
    try:
        from domain_engines.runner import run_domain_engines
    except Exception as exc:  # noqa: BLE001 - opsiyonel bağlam taramayı durdurmaz
        _pkg.logger.warning("Domain runner yüklenemedi; formation alert domain bağlamı boş kalacak: %s", exc)
        return None
    setattr(_pkg, "_domain_runner_cache", run_domain_engines)
    return _pkg._domain_runner_cache


def _completed_domain_frames(all_timeframes, now):
    """Runner'a yalnızca timestamp'li, kapanmış ve yeterli uzunluktaki frame'leri ver."""
    prepared = {}
    if not isinstance(all_timeframes, dict):
        return prepared
    for timeframe in _pkg._DOMAIN_TIMEFRAMES:
        frame = all_timeframes.get(timeframe)
        if frame is None:
            continue
        if not isinstance(frame, pd.DataFrame):
            _pkg.logger.error("Domain frame preparation failed for %s: expected DataFrame", timeframe)
            continue
        if len(frame) == 0:
            continue
        if not isinstance(frame.index, pd.DatetimeIndex):
            _pkg.logger.error(
                "Domain frame preparation failed for %s: %s index must be DatetimeIndex",
                timeframe,
                type(frame.index).__name__,
            )
            continue
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(frame.columns)):
            eksik = sorted(required - set(frame.columns))
            _pkg.logger.error("Domain frame preparation failed for %s: missing columns %s", timeframe, eksik)
            continue
        try:
            closed = _pkg.tamamlanmis_mumlar(frame, timeframe, now=now)
            if closed is None or len(closed) < 30:
                continue
            if not _pkg.bar_kapandi_mi(closed.index[-1], timeframe, now=now):
                continue
            prepared[timeframe] = closed.copy(deep=True)
        except Exception as exc:  # noqa: BLE001 - bozuk domain frame diğer TF'leri engellemesin
            _pkg.logger.error("Domain frame preparation failed for %s: %s", timeframe, exc)
    return prepared


def _domain_results_for_notification(stock, all_timeframes, now, cache):
    """Bu scan turunda sembol başına bir kez taze domain sonucu üret."""
    if stock in cache:
        return cache[stock]
    runner = _pkg._load_domain_runner()
    if runner is None:
        cache[stock] = {}
        return cache[stock]
    frames = _pkg._completed_domain_frames(all_timeframes, now)
    results = {}
    for timeframe, frame in frames.items():
        try:
            output = runner(stock, timeframe, frame, profile=PROFILE)
            if isinstance(output, dict):
                results[timeframe] = output
            else:
                _pkg.logger.warning("Domain runner %s/%s beklenmeyen sonuç döndürdü", stock, timeframe)
        except Exception as exc:  # noqa: BLE001 - domain hatası formation uyarısını bastırmasın
            _pkg.logger.warning("Domain runner hatası %s/%s: %s", stock, timeframe, exc)
    cache[stock] = results
    return results


def _endekse_gore_guc(df_hisse, df_endeks, adet: int = _GORELI_MUM):
    """(fark_puan, adet) — hisse getirisi eksi endeks getirisi; yoksa None."""
    try:
        if df_hisse is None or df_endeks is None:
            return None
        if len(df_hisse) < adet + 1 or len(df_endeks) < adet + 1:
            return None
        hisse = pd.to_numeric(df_hisse["close"], errors="coerce").dropna()
        endeks = pd.to_numeric(df_endeks["close"], errors="coerce").dropna()
        if len(hisse) < adet + 1 or len(endeks) < adet + 1:
            return None
        # Endeks serisi hissenin SON mumuna kadar hizalanır: "aynı pencere"
        # iddiası ancak böyle doğru olur (farklı bitiş tarihleri kıyaslanmaz).
        bitis = hisse.index[-1]
        endeks = endeks[endeks.index <= bitis]
        if len(endeks) < adet + 1:
            return None
        h0, h1 = float(hisse.iloc[-adet - 1]), float(hisse.iloc[-1])
        e0, e1 = float(endeks.iloc[-adet - 1]), float(endeks.iloc[-1])
        if not all(math.isfinite(x) and x > 0 for x in (h0, h1, e0, e1)):
            return None
        return ((h1 / h0 - 1.0) - (e1 / e0 - 1.0)) * 100.0, adet
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def _goreli_guc_satiri(stock: str, tf_name: str, df_tf, deque_manager,
                       endeks: str = "XU100") -> str:
    """Kartın YAPI bloğuna giren tek satır; veri yoksa boş metin."""
    if str(stock or "").upper() == endeks:
        return ""
    try:
        df_endeks_1h = deque_manager.to_dataframe(endeks)
        if df_endeks_1h is None or len(df_endeks_1h) == 0:
            return ""
        if str(tf_name).lower() != "1h":
            df_endeks_1h = resample_ohlcv(df_endeks_1h, str(tf_name))
    except Exception as exc:  # noqa: BLE001 - bağlam satırı alarmı düşürmesin
        _pkg.logger.debug("Endeks serisi okunamadı (%s): %s", endeks, exc)
        return ""
    sonuc = _pkg._endekse_gore_guc(df_tf, df_endeks_1h)
    if sonuc is None:
        return ""
    fark, adet = sonuc
    if abs(fark) < 0.05:
        return f"· {adet} mumda endeksle başabaş"
    # İŞARETLİ değer: "önde/geride" kelimesi satırı 283 px'in üstüne çıkarıyordu
    # (ölçüm: 304,5 px → sarma). "+2,1 puan" aynı bilgiyi 270,5 px'te taşır;
    # birim "puan" kalır çünkü iki yüzdenin farkı yüzde değildir.
    isaret = "+" if fark > 0 else "-"
    # Ölçüm (widen: en kötü hâl iki haneli fark):
    #   `· 20 mumda endeksten +2,1 puan` 270,5 px  → _satir bölüyordu
    #   `· 20 mumda endekse +17,9 puan`  263,5 px  → eşiğin (262,85) üstünde
    #   `· 20 mum endekse +17,9 puan`    243,5 px  → sığar
    # Pencere ("20 mum"), işaret ve birim ("puan") korunur; girintili devam
    # satırı yasak olduğu için kısaltma zorunlu.
    return f"· {adet} mum endekse {isaret}{_sayi(abs(fark), 1)} puan"


def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier, manuel: bool = False, stocks=None, send_alerts: bool = True):
    """
    Aktif tarama evrenini tara; Yahoo verisi seri ve gruplu alınır, analiz ardından yapılır.
    - Deque'den veri al
    - Resample 2H/4H/1D
    - Pattern tespit (üçgen/kama/bayrak)
    - Lifecycle update (kırılım takibi)
    - Telegram (cooldown ile)
    """
    simdiki_zaman = _pkg.datetime.now(ISTANBUL_TZ)
    tarama_baslangici = time.monotonic()
    scan_stocks = list(dict.fromkeys(stocks or _pkg.ACTIVE_STOCKS))
    tur_taranan = 0
    tur_formasyon = 0
    tur_hata = 0
    en_son_bar = None
    en_eski_bar_yasi_dk = None
    # Teyitli bir olay aynı sembolde birden çok TF'de çıkarsa, alan çıktıları
    # bu scan turunda taze biçimde yalnızca bir kez hesaplanır.
    domain_results_by_stock = {}
    _pkg._live_state.begin_scan(
        simdiki_zaman,
        manuel=manuel,
        beklenen_hisse=len(scan_stocks),
        scope=scan_stocks,
        replace_all=(set(scan_stocks) == set(_pkg.ACTIVE_STOCKS)),
    )
    _pkg.logger.info(f"=== TARAMA BAŞLIYOR{' (ELLE)' if manuel else ''} - {len(scan_stocks)} hisse, profil: {PROFILE} "
                f"({simdiki_zaman.strftime('%H:%M')}) ===")
    _pkg.logger.info(
        f"Yahoo pacing: her {SCAN_REQUEST_BATCH_SIZE} istekte "
        f"{SCAN_REQUEST_DELAY_MIN_SEC:.1f}-{SCAN_REQUEST_DELAY_MAX_SEC:.1f} sn aralık, "
        f"grup arası {SCAN_BATCH_PAUSE_MIN_SEC:.0f}-{SCAN_BATCH_PAUSE_MAX_SEC:.0f} sn"
    )

    # Sağlıklı cache'te son 5 günü, boş/5 günden eski cache'te tam 60 günü çek.
    # Böylece rutin saatlik taramada büyük geçmiş penceresi tekrar tekrar inmez.
    fetch_periods = {}
    for stock in scan_stocks:
        cached = deque_manager.to_dataframe(stock)
        fetch_periods[stock] = _pkg.select_yfinance_1h_period(cached)
    full_count = sum(period == FULL_1H_FETCH_PERIOD for period in fetch_periods.values())
    routine_count = len(fetch_periods) - full_count
    _pkg.logger.info(
        f"1H fetch penceresi: tam {FULL_1H_FETCH_PERIOD}={full_count}, "
        f"rutin cache güncellemesi={routine_count} ({ROUTINE_1H_FETCH_PERIOD})"
    )

    # Önce 1H fetch turu ve yalnız geçici hatalar için tek retry; analiz retry
    # tamamlandıktan sonra yapılır ki kurtarılan taze veri aynı turda kullanılsın.
    pacer = _pkg.create_yahoo_pacer()
    taze_1h_verileri, fetch_hatalari, retry_sayisi, retry_kurtarilan = _pkg.fetch_1h_stocks_paced(
        scan_stocks, pacer, "MANUEL ANALİZ" if manuel else "CANLI TARAMA", periods=fetch_periods
    )
    _pkg.daily_stats['fetch_ok'] += len(taze_1h_verileri)
    _pkg.daily_stats['fetch_failures'] += len(fetch_hatalari)
    _pkg.daily_stats['fetch_retries'] += retry_sayisi
    _pkg.daily_stats['fetch_retry_recovered'] += retry_kurtarilan

    for idx, stock in enumerate(scan_stocks):
        if _pkg._shutdown_requested:
            _pkg.logger.info("Kapanış istendi, tarama durduruluyor")
            break
        try:
            _pkg.reset_daily_if_needed()
            simdiki_zaman = _pkg.datetime.now(ISTANBUL_TZ)
            
            _pkg.logger.info(f"[{idx+1}/{len(scan_stocks)}] {stock} taranıyor...")
            
            # Deque'den mevcut pencere; fetch aşaması yukarıda, retry dahil tamamlandı.
            df_1h = deque_manager.to_dataframe(stock)
            taze = taze_1h_verileri.get(stock)
            if taze is not None:
                deque_manager.append_dataframe(stock, taze)
                df_1h = deque_manager.to_dataframe(stock)
            else:
                _pkg.logger.warning(
                    f"{stock}: taze 1H veri yok ({fetch_hatalari.get(stock, 'fetch yapılmadı')}); "
                    "cache varsa yalnız veri tazeliği uygunsa kullanılacak"
                )
            
            if df_1h is None or len(df_1h) < 50:
                _pkg.logger.warning(f"{stock}: veri yok (fetch basarisiz + cache bos) - bu tur atlandi")
                continue
            
            # --- VERİ TAZELİĞİ ÖLÇÜMÜ (FAZ 1) ---
            # En yeni 1H mumun yaşı. Yahoo saatlerce kapalıysa bu değer büyür ve
            # bot eski veriyle (yanlış sinyalle) çalışmaya devam eder. Ölçüp
            # loglayıp heartbeat'e yazıyoruz ki kör çalışma görünür olsun.
            son_bar = df_1h.index[-1]
            son_bar = son_bar.tz_convert(ISTANBUL_TZ) if son_bar.tzinfo else ISTANBUL_TZ.localize(son_bar)
            en_son_bar = max(en_son_bar, son_bar) if en_son_bar is not None else son_bar
            son_bar_yasi_dk = (simdiki_zaman - df_1h.index[-1].tz_convert(ISTANBUL_TZ)
                               if df_1h.index[-1].tzinfo else
                               simdiki_zaman - ISTANBUL_TZ.localize(df_1h.index[-1])).total_seconds() / 60.0
            if _pkg.daily_stats['max_bar_age_min'] is None or son_bar_yasi_dk > _pkg.daily_stats['max_bar_age_min']:
                _pkg.daily_stats['max_bar_age_min'] = round(son_bar_yasi_dk, 1)
            if en_eski_bar_yasi_dk is None or son_bar_yasi_dk > en_eski_bar_yasi_dk:
                en_eski_bar_yasi_dk = round(son_bar_yasi_dk, 1)
            # Seansın ilk saatinde en yeni veri dünkü kapanıştır (ilk mum 10:30'da
            # kapanır) -> o pencereyi uyarı dışında tut.
            erken_seans = simdiki_zaman.time() < dt_time(10, 50)
            # --- SPLIT / VERİ SORUNU KONTROLÜ (FAZ 2) ---
            # Ham seride split/bedelsiz tespit edildiyse bu hisseyi ANALİZ ETME:
            # pivot/sınır/kırılım sahte olur. Log'da net yazar, kullanıcı müdahale
            # edene kadar hisse sessiz kalır (yanlış sinyal vermekten iyidir).
            st_sorunlar = deque_manager.sureklilik_sorunlari.get(stock)
            if st_sorunlar:
                tipler = sorted({x['tip'] for x in st_sorunlar})
                if 'split' in tipler:
                    _pkg.daily_stats['split_atlanan'] += 1
                    _pkg.logger.error(
                        f"{stock}: analiz atlanıyor - veri sorunu {tipler}. "
                        f"Detay yukarıdaki uyarılarda; veri düzeltilince otomatik döner."
                    )
                    continue
                # boşluk/şok: analize devam (tek olay, motor ATR ile absorbe eder)
                _pkg.logger.info(f"{stock}: veri notu {tipler} - analiz devam ediyor")

            # Seans dışında provider'dan yeni mum gelmemesi olağandır; bu durum
            # yalnızca piyasa açıkken VERİ YOK sayılır. Kapalı seanslarda son mum,
            # genel yaş sınırına kadar değerlendirilebilir.
            seans_acik = _pkg.tarama_penceresi_acik_mi(simdiki_zaman)
            if (taze is None and seans_acik and son_bar_yasi_dk is not None
                    and son_bar_yasi_dk > VERI_YOK_MODU_ESIK_DK):
                _pkg.daily_stats['veri_yok_modu'] = True
                _pkg.logger.info(
                    f"{stock}: seans açıkken yeni veri yok (son mum "
                    f"{son_bar_yasi_dakika_str(son_bar_yasi_dk)} önce, fetch başarısız) - analiz atlanıyor"
                )
                continue

            # Seans içinde fetch başarısızsa eski cache ile sinyal üretme. Seans
            # dışında ise en son tamamlanmış mum, yapılandırılmış yaş sınırına
            # (varsayılan 14 gün) kadar açıkça eski veri olarak kullanılabilir.
            if not _pkg._cache_verisi_kullanilabilir(
                    son_bar_yasi_dk, taze is not None, seans_acik):
                _pkg.daily_stats['stale_stocks'] += 1
                _pkg.daily_stats['data_stale'] = True
                _pkg.logger.warning(
                    f"{stock}: son tamamlanmış mum {son_bar_yasi_dakika_str(son_bar_yasi_dk)} yaşında; "
                    "bu hisse analiz dışı bırakıldı"
                )
                continue
            if taze is None and not seans_acik and son_bar_yasi_dk > STALE_BAR_UYARI_DK:
                _pkg.logger.warning(
                    f"{stock}: sağlayıcıya erişilemedi; seans dışı son mevcut cache "
                    f"({son_bar_yasi_dakika_str(son_bar_yasi_dk)}) kullanılıyor"
                )

            if son_bar_yasi_dk > STALE_BAR_UYARI_DK and not erken_seans:
                _pkg.daily_stats['stale_stocks'] += 1
                _pkg.daily_stats['data_stale'] = True
                _pkg.logger.warning(
                    f"{stock}: VERİ ESKİ - en yeni 1H mum {son_bar_yasi_dakika_str(son_bar_yasi_dk)} önce "
                    f"(eşik {STALE_BAR_UYARI_DK} dk). yfinance çekimi "
                    f"{'başarısız' if taze is None else 'veri gelmiyor'}, cache ile devam ediliyor - "
                    f"formasyonlar eski veriyle hesaplanıyor!"
                )
            
            # Tüm timeframe'leri üret
            all_tfs = _pkg.resample_all_timeframes(df_1h)
            
            # --- 1D İÇİN DERİN VERİ (FAZ 2) ---
            # Resample 1D sadece 1H penceresi kadar (~40 bar) derinlikte olur ve 1D
            # formasyon penceresi (20-60 bar) marjinal kalıyordu (ölçüm: 40.0 bar).
            # 1H penceresini büyütmek Pine uyumunu bozabileceği için günlük veriyi
            # AYRI ve DERİN (~2 yıl) çekiyoruz. Veri yoksa resample'e geri dönülür
            # (davranış asla kötüleşmez, sadece iyileşir).
            if deque_manager.gunluk_veri_eksik_mi(stock, simdiki_zaman):
                with pacer.request(f"{stock} 1D"):
                    taze_gunluk = fetch_yfinance_1d(stock)
                deque_manager.gunluk_fetch_denemesi_kaydet(stock, simdiki_zaman)
                if taze_gunluk is not None and len(taze_gunluk) >= 30:
                    deque_manager.append_gunluk_dataframe(stock, taze_gunluk)
                    _pkg.logger.info(f"{stock}: günlük veri tazelendi ({len(taze_gunluk)} bar)")
                else:
                    _pkg.logger.warning(f"{stock}: günlük derin veri çekilemedi - resample kullanılacak")
            df_gunluk = deque_manager.to_gunluk_dataframe(stock)
            if df_gunluk is not None and len(df_gunluk) >= 30:
                all_tfs['1d'] = df_gunluk
            
            # Her TF için: yarım (devam eden) mumu çıkar, TAMAMLANMIŞ mumları besle
            hisse_formasyonlari = []
            for tf_name, df_tf in all_tfs.items():
                if df_tf is None or len(df_tf) < 30:
                    _pkg.logger.debug(f"{stock} {tf_name} için yeterli veri yok")
                    continue
                df_tf = _pkg.tamamlanmis_mumlar(df_tf, tf_name)
                if df_tf is None or len(df_tf) < 30:
                    _pkg.logger.debug(f"{stock} {tf_name}: tamamlanmış mum kalmadı (seans içi erken tarama)")
                    continue
                # P0 güvenlik kapısı: motorun gördüğü SON bar gerçekten kapandı mı?
                # tamamlanmis_mumlar aynı kuralı uygular; burada olay anındaki an ile
                # yeniden doğrulanır (restart/telafi/saat kayması regresyonlarına karşı).
                # Kapı "hayır" derse anlık push yapılmaz, sonraki taramaya bırakılır.
                son_bar_kapanis = mum_kapanis_ani(df_tf.index[-1], tf_name)
                son_bar_kapandi = _pkg.bar_kapandi_mi(df_tf.index[-1], tf_name, now=simdiki_zaman)
                if not son_bar_kapandi:
                    _pkg.logger.warning(
                        f"{stock} {tf_name}: son bar ({df_tf.index[-1]}) henüz kapanmadı "
                        f"(kapanış {son_bar_kapanis}) - bu tur bildirim üretilmeyecek"
                    )
                
                # Motor adayı kendisi bulur ve kırılım anında dondurur (Pine v0.4.6 akışı).
                # tam_yeniden=True: pencere her taramada sıfırdan deterministik oynatılır.
                snap = lifecycle_manager.scan(stock + "_" + tf_name, df_tf, tam_yeniden=True)
                state, break_dir, lifecycle_log = snap.state, snap.break_dir, snap.log
                active = snap.active
                invalidation_event = _pkg._invalidation_event_for_snapshot(snap, active)
                notification_state = (
                    "KIRILIM_GECERSIZLESTI" if invalidation_event is not None else state
                )
                # Yaşam döngüsü yok/geçersiz/zayıflama state'ine düştü: bu slotun
                # "tekrar" mühürleri + 4 saatlik cooldown'ı temizlenir, aynı slotu
                # tekrar kaplayan yeni formasyon anında bildirilebilir.
                if state in _pkg.TEKRAR_SIFIRLA_STATELER:
                    notifier.son_alert_sifirla(stock, tf_name)
                
                if active:
                    q = snap.effective_quality if snap.effective_quality is not None else active.raw_quality
                    try:
                        candle_close_price = float(df_tf["close"].iloc[-1])
                    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
                        candle_close_price = None
                    break_price = _pkg._alert_break_level(active, break_dir, notification_state)
                    _pkg._record_daily_lifecycle_events(
                        stock, tf_name, snap, fallback_bar_time=df_tf.index[-1]
                    )
                    _pkg._note_pattern_found(stock, tf_name)
                    _pkg.logger.info(
                        f"🔍 {stock} {tf_name} - {active.pattern_type} kalite {q:.0f} "
                        f"state {state} / bildirim {notification_state} - {snap.log}"
                    )
                    # --- HAFTALIK KARNE DEFTERİ (yerel; Supabase gerekmez) ---
                    # Kırılım teyidi: performans ölçülecek sinyal (giriş = teyit
                    # barının kapanışı). Diğer state'ler: formasyon sayımı + huni.
                    try:
                        if state == "KIRILIM_TEYITLI" and break_dir in (1, -1):
                            _pkg._karne_olay_kaydet(
                                stock, tf_name, state, active.pattern_type, q,
                                df_tf.index[-1], kirilim=True, dir=int(break_dir),
                                entry=float(df_tf["close"].iloc[-1]), df_tf=df_tf,
                                stable_id=getattr(active, "stable_id", None),
                            )
                        else:
                            _pkg._karne_olay_kaydet(stock, tf_name, state, active.pattern_type, q,
                                               df_tf.index[-1], df_tf=df_tf,
                                               stable_id=getattr(active, "stable_id", None))
                    except Exception as karne_hata:  # noqa: BLE001 - tarama asla durmasın
                        _pkg.logger.debug("Karne kaydı atlandı (%s %s): %s", stock, tf_name, karne_hata)
                    
                    # Çoklu zaman teyidi: 1h kırılımında 4h destekliyor mu?
                    # 2026-10-25: kart "4h de aynı yönde" diyordu ama yön
                    # karşılaştırılmıyordu (yalnız "aktif mi" bakılıyordu).
                    # Artık yön de aranıyor; kartın iddiası ölçümle aynı olsun.
                    # 2026-10-26: bu blok eskiden alarm hazırlık dalının
                    # İÇİNDEYDİ; DM musluğu (aşağıda) `mtf_uyum`/`bant_mesafe_atr`
                    # okuduğu için ilk adayda UnboundLocalError, sonraki
                    # adaylarda önceki TF'nin eskimiş değeriyle yanlış puan
                    # çıkıyordu. Girdiler her aktif formasyonda bir kez, en
                    # başta hesaplanır.
                    mtf_destek = False
                    mtf_uyum = 0
                    try:
                        ust_snap = None
                        if tf_name == "1h":
                            ust_snap = lifecycle_manager.get_snapshot(stock + "_4h")
                        elif tf_name == "4h":
                            ust_snap = lifecycle_manager.get_snapshot(stock + "_1d")
                        if (ust_snap and ust_snap.active
                                and ust_snap.state not in ("FORMASYON_GECERSIZ", "Yok", "ST_NONE")):
                            mtf_destek = True
                            # Yön uyumu: üst TF'nin kırılım yönü aynıysa
                            # ölçümdeki "MTF 4/4" kademesine denk sayılır.
                            ust_yon = int(getattr(ust_snap, "break_dir", 0) or 0)
                            if ust_yon and int(break_dir or 0) and ust_yon == int(break_dir):
                                mtf_uyum = 4
                    except Exception:
                        mtf_destek = False
                        mtf_uyum = 0

                    # Girişin banda uzaklığı (ATR cinsinden). Devamlılık
                    # puanının en sağlam maddesi: kırılımı kovalamak
                    # formasyonun katkısını yiyor (aile içi Q5−Q1 −7,0).
                    bant_mesafe_atr = None
                    try:
                        _atr = atr_hesapla(df_tf)
                        _giris = float(candle_close_price)
                        _bant = float(break_price)
                        if _atr and _atr > 0:
                            bant_mesafe_atr = abs(_giris - _bant) / float(_atr)
                    except Exception:
                        bant_mesafe_atr = None

                    # Alert eşiği kontrolü - timeframe'e göre (effective_quality üzerinden)
                    min_q = ALERT_MIN_QUALITY.get(tf_name, ALERT_MIN_QUALITY_GLOBAL)
                    # Devamlılık puanı DM musluğu (varsayılan 0 = kapalı, davranış
                    # değişmez). >0 verilirse yalnız bu puanın üstü DM'e gider.
                    # 2026-10-26 denetimi: burada eskiden `continue` vardı ve
                    # kayıt (/formasyonlar, canlı durum) + public kuyruk da
                    # kesiliyordu — musluk yalnız DM'i kapatmalı (aşağıdaki
                    # `dm_gecersiz_engel` ile aynı yol; `PUBLIC_MIN_DEVLAMLILIK`
                    # grubu kendi kapısından geçirir).
                    dm_dev_engel = False
                    if DM_MIN_DEVLAMLILIK > 0:
                        _dev_puan = devamlilik_puani({
                            'pattern_name': active.pattern_type,
                            'mtf_uyum': mtf_uyum,
                            'bant_mesafe_atr': bant_mesafe_atr})
                        if _dev_puan is None or _dev_puan < DM_MIN_DEVLAMLILIK:
                            dm_dev_engel = True
                            _pkg.logger.info("DM atlandı (devamlılık %s < %s): %s %s",
                                        _dev_puan, DM_MIN_DEVLAMLILIK, stock, tf_name)
                    try:
                        yas_bar = max(0, int(snap.bar_index - active.start_bar))
                    except Exception:
                        yas_bar = None
                    # Telegram /formasyonlar ve Top-12 sıralaması aynı hesaplanmış
                    # formasyon kaydını kullanır; scoring için temas/daralma da saklanır.
                    tur_formasyon += 1
                    formasyon_kaydi = {
                        'stock': stock,
                        'timeframe': tf_name,
                        'pattern_name': active.pattern_type,
                        'quality': float(q),
                        'state': state,
                        'notification_state': notification_state,
                        'break_dir': break_dir,
                        # Phase 1: kalıcı formation kimliği (doğumdan terminal'e).
                        # Motor-içi `identity`'den ayrıdır; restart sonrası re-attach
                        # ile aynı formation aynı stable_id'yi taşımaya devam eder.
                        'stable_id': getattr(active, 'stable_id', None),
                        'upper': getattr(active, 'upper_now', None),
                        'lower': getattr(active, 'lower_now', None),
                        'critical_price': (active.upper_now if break_dir == 1 else active.lower_now),
                        'break_strength': getattr(active, 'break_strength', None),
                        'contraction': getattr(active, 'contraction', None),
                        'upper_touches': getattr(active, 'upper_touches', None),
                        'lower_touches': getattr(active, 'lower_touches', None),
                        'age_bars': yas_bar,
                        'mtf_destek': False,
                        'bar_time': str(df_tf.index[-1]),
                        # Kapanan mumun damgası + güvenlik kapısı sonucu: mesajda
                        # gösterilir ve push öncesi son kontrol olarak kullanılır.
                        # ISO STRING: bu kayıt LiveState/son_tarama JSON'larına
                        # yazılır; Timestamp nesnesi serileştirmeyi kırardı.
                        'bar_kapanis': (son_bar_kapanis.isoformat()
                                        if son_bar_kapanis is not None else None),
                        'bar_kapandi': bool(son_bar_kapandi),
                        'bar_metni': _mum_bilgisi(tf_name, df_tf.index[-1], son_bar_kapanis),
                        'candle_close_price': candle_close_price,
                        'min_quality': float(min_q),
                        'alert_gonderildi': False,
                    }
                    hisse_formasyonlari.append(formasyon_kaydi)
                    _pkg._live_state.record_formation(formasyon_kaydi)
                    # Her başarılı sembol/TF analizi bekleyen adayın son durumunu yeniler.
                    # Kalite eşiği altı kayıtlar kapanış özetine de taşınmaz.
                    if state in WATCH_STATES and q >= min_q:
                        _pkg._deferred_alert_buffer.observe(stock, tf_name, formasyon_kaydi, simdiki_zaman)
                    else:
                        _pkg._deferred_alert_buffer.observe(stock, tf_name, None, simdiki_zaman)
                    # Public kapanış özeti için: gün içinde kaç kırılım başarısız
                    # oldu? (Gruba her ❌ tek tek gitmez; özet tek satır verir.)
                    if send_alerts and state == "BASARISIZ_KIRILIM":
                        _pkg._note_basarisiz_kirilim(stock, tf_name, df_tf.index[-1])
                    # Aday hunisi: bu kaydın akıbeti sayılır (bkz. daily_stats notu).
                    # Geri alma (geçersizleşti) kalite eşiğine TAKILMAZ: teyit
                    # eşiği geçmiş bir olayın iptali, formasyon kalitesi sonradan
                    # düştü diye bastırılırsa kullanıcıda "geçerli" kalır.
                    if q < min_q and notification_state != "KIRILIM_GECERSIZLESTI":
                        _pkg.daily_stats['alerts_below_threshold'] += 1
                        _pkg.logger.debug(f"{stock} {tf_name} kalite {q:.0f} < {min_q} (alert eşiği) - telegram atlanıyor")
                    elif send_alerts and not _pkg._alarm_izni_var(stock):
                        # Makro sembol: tarama/grafik/bağlam var, push yok.
                        _pkg.daily_stats['alerts_makro_kapali'] = int(
                            _pkg.daily_stats.get('alerts_makro_kapali') or 0) + 1
                        _pkg.logger.debug("%s %s %s: makro sembol, alarm kapalı "
                                     "(MAKRO_ALARM=0); formasyon kaydı tutuldu",
                                     stock, tf_name, notification_state)
                    elif send_alerts and state in WATCH_STATES:
                        _pkg.daily_stats['alerts_deferred'] += 1
                        _pkg.logger.info(f"{stock} {tf_name} {state}: düşük öncelikli bildirim kapanış özetine ertelendi")
                    # Teyitli kırılım, başarılı retest, tamamlanma ve başarısız kırılım acildir.
                    elif send_alerts and notification_state in _pkg.IMMEDIATE_ALERT_STATES and not son_bar_kapandi:
                        # P0 güvenlik kapısı: bar kapanmadan anlık push yok. Bu dal
                        # normalde HİÇ çalışmaz (tamamlanmis_mumlar aynı kuralı
                        # uygular); saat/tarama kayması olursa sinyal yanlış
                        # gönderilmek yerine bir sonraki taramaya bırakılır.
                        _pkg.daily_stats['alerts_bar_kapanmadi'] += 1
                        _pkg.logger.warning(
                            f"⏸️ {stock} {tf_name} {notification_state}: bar henüz kapanmadı "
                            f"({df_tf.index[-1]} → {son_bar_kapanis}); push sonraki taramaya bırakıldı"
                        )
                    elif (send_alerts and notification_state in _pkg.IMMEDIATE_ALERT_STATES
                          and not _pkg._closed_formation_event_confirmed(
                              notification_state, break_dir, candle_close_price, break_price)):
                        _pkg.daily_stats['alerts_break_close_invalid'] += 1
                        _pkg.logger.warning(
                            "⏸️ %s %s %s: kapanış teyit seviyesi dışında; Telegram push atlandı "
                            "(close=%s, level=%s)",
                            stock, tf_name, notification_state, candle_close_price, break_price,
                        )
                    elif send_alerts and notification_state in _pkg.IMMEDIATE_ALERT_STATES:
                        # Tur 2a DM geçersizleşme kapısı. Eskiden AYRI bir `elif`ti:
                        # kapı kapandığında bu blok hiç çalışmıyordu, yani
                        # `public_kuyruk` da çağrılmıyordu → grupta teyit
                        # "geçerli" kalıyordu (DM'e teyit gitmediyse geri alma
                        # sonsuza kadar düşüyordu). Artık kapı yalnız DM push'unu
                        # durdurur; bağlam hazırlanır ve public kendi kapısıyla
                        # (`TELEGRAM_KANAL_GECERSIZ_KAPISI`) karar verir.
                        dm_gecersiz_engel = (
                            notification_state == "KIRILIM_GECERSIZLESTI"
                            and not _pkg._invalidation_confirmation_delivered(
                                notifier, getattr(active, "stable_id", None))
                        )
                        if dm_gecersiz_engel:
                            _pkg._note_unannounced_invalidation(
                                stock, tf_name, getattr(active, "stable_id", None),
                                df_tf.index[-1],
                            )
                            _pkg.logger.info(
                                "⏸️ %s %s %s: önceki KIRILIM_TEYITLI DM'e teslim "
                                "edilmemiş; DM push yok, public kendi kapısıyla gider",
                                stock, tf_name, notification_state,
                            )
                        # Humanized mesaj için ek bilgiler - var olan veriyi kullan, ekstra hesaplama yok
                        upper_touches = getattr(active, 'upper_touches', None)
                        lower_touches = getattr(active, 'lower_touches', None)
                        try:
                            age_bars = snap.bar_index - active.start_bar if hasattr(active, 'start_bar') and snap.bar_index >= 0 else None
                        except Exception:
                            age_bars = None
                        # Bandın izlenme başlangıcı: "96 bar" tek başına kullanıcıya
                        # gün söylemez. Bar indeksi DataFrame indeksinden okunur; okunamazsa
                        # alan hiç yazılmaz (varsayım/gün hesabı uydurulmaz).
                        band_baslangic = None
                        try:
                            _bas_indeks = int(getattr(active, 'start_bar', -1))
                            if _bas_indeks >= 0 and _bas_indeks < len(df_tf.index):
                                band_baslangic = df_tf.index[_bas_indeks]
                        except Exception:
                            band_baslangic = None
                        alert_data = {
                            'stock_name': stock,
                            'timeframe': tf_name,
                            'pattern_name': active.pattern_type,
                            'state': notification_state,
                            'formation_id': getattr(active, 'stable_id', None),
                            'confidence_score': q,
                            'critical_price_level': break_price,
                            'candle_close_price': candle_close_price,
                            'close_price': candle_close_price,
                            'upper_now': active.upper_now,
                            'lower_now': active.lower_now,
                            'contraction': getattr(active, 'contraction', None),
                            'timestamp': df_tf.index[-1],
                            # Kapanan mum bilgisi: mesajda "hangi mum kapandı?" satırı
                            # olarak görünür (bar_kapandi zaten yukarıda doğrulandı).
                            # ISO string: engellenen alarm kuyruğa yazılırken JSON
                            # serileştirmesi bozulmasın.
                            'bar_time': df_tf.index[-1],
                            'bar_kapanis': (son_bar_kapanis.isoformat()
                                            if son_bar_kapanis is not None else None),
                            'bar_kapandi': True,
                            'bar_metni': _mum_bilgisi(tf_name, df_tf.index[-1], son_bar_kapanis),
                            'break_dir': break_dir,
                            'break_strength': getattr(active, 'break_strength', q),
                            'break_price': break_price,
                            'retest_seen': getattr(snap, 'retest_seen', False),
                            'upper_touches': upper_touches,
                            'lower_touches': lower_touches,
                            'age_bars': age_bars,
                            'band_baslangic': band_baslangic,
                            'mtf_destek': mtf_destek,
                            # Devamlılık puanının girdileri (bkz. devamlilik.py).
                            # `confidence_score` kapı için kalır, kartta okunmaz.
                            'mtf_uyum': mtf_uyum,
                            'bant_mesafe_atr': bant_mesafe_atr,
                            # Acil mesaj kısa kalsın; izleme adayları 18:45 digest'inde
                            # gösterilir, bu nedenle burada bağlam eklenmez/tüketilmez.
                            'watch_context': [],
                        }
                        # Public (grup) kuyruğa ekleme `_attach_domain_context`
                        # SONUNDA yapılır (2026-10-22): bülten DM kartıyla aynı
                        # 7 bloğu bastığı için kayıt, ölçüm/bölge/yapı bağlamı
                        # eklendikten sonra kuyruğa girmeli. DM engeli
                        # (cooldown/kap) grubu etkilemez.
                        def _grafik_koprusu(payload, outputs):
                            # G4 KÖPRÜSÜ (§4): kareler kartla BİREBİR aynı veriden.
                            # Motor burada YENİDEN çağrılmaz — `outputs` bu turda
                            # `_domain_results_for_notification`da üretildi; kare
                            # yalnız kopyalar (§14.2). `grafik_verisi` bellek içidir
                            # ve acil kuyruk kaydından arındırılır (notifier).
                            try:
                                import grafik
                                if not grafik.grafik_aktif_mi():
                                    return
                                taze = _pkg._completed_domain_frames(all_tfs, simdiki_zaman)
                                alarm_bar = getattr(snap, 'bar_index', -1)
                                # GÖRSEL-4: geçersizleşmede TEK kare (geçersizleşen TF).
                                # `ek_cerceveler` bu durumda boş geçirilir: diğer TF
                                # karelerinde bant/alarm çizilmiyor, neredeyse boş
                                # görseller gönderiliyordu.
                                tek_kare = (notification_state
                                            == "KIRILIM_GECERSIZLESTI")
                                veri = grafik.kare_listesi(
                                    active, tf_name,
                                    taze.get(tf_name) if taze.get(tf_name) is not None else df_tf,
                                    sonuclar=outputs,
                                    ek_cerceveler=({} if tek_kare else
                                                   {k: v for k, v in taze.items()
                                                    if k != tf_name}),
                                    alarm_turu=grafik.alarm_turu_bul(notification_state),
                                    alarm_bar=(int(alarm_bar) if alarm_bar is not None
                                               and int(alarm_bar) >= 0 else None),
                                    sembol=stock, zaman_damgasi=df_tf.index[-1],
                                    simdi=simdiki_zaman)
                                if veri.get("goruntular"):
                                    payload['grafik_verisi'] = veri
                                # PUBLIC görseli (2026-10-22 kararı): DM 4 kare
                                # alır, grup YALNIZ 1 kare + üst zaman dilimi.
                                # Ayrı liste üretilir; aynı veriden çizilir
                                # (§14.2: kare kopyadır, motor yeniden koşmaz).
                                # 2026-10-28 (kullanıcı: "grup da kanal gibi
                                # olsun, bir ana bir de üst TF"): 1g alarmının
                                # ÜST zaman dilimi yok (bot 1s/2s/4s/1g tarıyor),
                                # grupta tek kare kalıyordu. O durumda ikinci
                                # kare ALT zaman dilimi olur (1g → 4s) ve
                                # etiketi "alt zaman dilimi" yazar; yanlış
                                # "üst" demektense doğru söylemek yeğdir.
                                ana_tf = str(tf_name or '').lower()
                                ust_tf = _pkg._UST_TF.get(ana_tf)
                                ust_rol = "ust"
                                if ust_tf is None:
                                    ust_tf = _pkg._ALT_TF.get(ana_tf)
                                    ust_rol = "alt"
                                ust_cerceve = (taze.get(ust_tf)
                                               if ust_tf and taze.get(ust_tf) is not None
                                               else None)
                                public_veri = grafik.kare_listesi(
                                    active, tf_name,
                                    taze.get(tf_name) if taze.get(tf_name) is not None else df_tf,
                                    sonuclar=outputs,
                                    ek_cerceveler=({ust_tf: ust_cerceve}
                                                   if ust_tf and ust_cerceve is not None else {}),
                                    alarm_turu=grafik.alarm_turu_bul(notification_state),
                                    alarm_bar=(int(alarm_bar) if alarm_bar is not None
                                               and int(alarm_bar) >= 0 else None),
                                    sembol=stock, zaman_damgasi=df_tf.index[-1],
                                    adet=2, simdi=simdiki_zaman)
                                if public_veri.get("goruntular"):
                                    # İkinci karenin "üst/alt" rolü kaynaktan
                                    # yazılır: notifier TF sırasını bilmek
                                    # zorunda kalmaz, caption yanlış olmaz.
                                    if len(public_veri["goruntular"]) > 1:
                                        public_veri["goruntular"][1]["rol"] = ust_rol
                                    payload['grafik_verisi_public'] = public_veri
                            except Exception as grafik_hata:  # noqa: BLE001 - görsel alarmı düşürmesin
                                # Sayaç/diagnostic kodu da alarm akışını durduramaz.
                                try:
                                    notifier.grafik_kopru_hatasi(
                                        f"{type(grafik_hata).__name__}: "
                                        f"{str(grafik_hata)[:90]} ({stock} {tf_name})"
                                    )
                                except Exception as sayac_hata:  # noqa: BLE001
                                    _pkg.logger.debug(
                                        "grafik köprüsü hata sayacı yazılamadı (%s %s): %s",
                                        stock, tf_name, type(sayac_hata).__name__,
                                    )

                        def _attach_domain_context(payload):
                            outputs = None     # köprü hata durumunda da None görsün
                            try:
                                outputs = _pkg._domain_results_for_notification(
                                    stock, all_tfs, simdiki_zaman, domain_results_by_stock
                                )
                                # MS arıza sayacı (yalnız /durum'da görünür).
                                _pkg._ms_hata_kaydet(outputs, stock)
                                # Klasik bağlam metni KENDİ try'ında: bu metin
                                # üretilemese bile kart bölümleri (aşağıda) karta
                                # girmeli. 23 Eki 2026: tek istisna ikisini birden
                                # düşürüyor, canlı kart "sade" kalıyordu.
                                try:
                                    payload['domain_context'] = format_domain_context(
                                        outputs,
                                        reference_price=candle_close_price,
                                        alarm_tf=tf_name,
                                        yalniz_tf=(notification_state
                                                   == "KIRILIM_GECERSIZLESTI"),
                                    )
                                except Exception as ctx_hata:  # noqa: BLE001
                                    payload['domain_context'] = ""
                                    _pkg.logger.warning(
                                        "Domain bağlam metni üretilemedi (%s %s): %s",
                                        stock, tf_name, ctx_hata,
                                    )
                                # Ölçüm kesitleri "normalin x katı" eşiğini ATR'den
                                # okur. 23 Eki 2026: buradaki ad (`atr_alarm`) hiç
                                # tanımlanmamıştı; her alarmda NameError yutuluyor
                                # (aşağıdaki `except kart_hata`) ve karta HİÇBİR
                                # domain bölümü girmiyordu — canlı kart bu yüzden
                                # "sade" görünüyordu. ATR alarm TF'sinden, karne ile
                                # aynı fonksiyonla hesaplanır.
                                atr_alarm = atr_hesapla(df_tf)
                                # Kart biçimleyicisi bölümleri AYRI ister: kendi
                                # bölümünü kendi başlığıyla basabilsin ve imza
                                # (değişmedi kontrolü) yalnız bağlamı görsün.
                                # AYRI try/except: kart hazırlığı patlarsa klasik
                                # bağlam metni de kaybolsun istemeyiz (25 Eyl testinde
                                # tek bloktaki hata domain_context'i boşaltıyordu).
                                if getattr(config, "TELEGRAM_ALERT_STYLE", "kart") != "klasik":
                                    try:
                                        # Yorum kapısı (S01–S32): yalnız canlı
                                        # akış bu anahtarı yazar — harici/test
                                        # çağrıları eski kartla kalır.
                                        payload['kart_yorum_kapisi'] = True
                                        payload['domain_bolumleri'] = domain_bolumleri(
                                            outputs,
                                            reference_price=candle_close_price,
                                            stil="kart",
                                            alarm_tf=tf_name,
                                            # Arşiv ölçümü bölümü: kart, aynı
                                            # kurulumun geçmiş sonucunu da yazar.
                                            olcum=True,
                                            # Ölçüm AİLESİ: formasyon alarmı
                                            # yalnız formasyon ölçümünü basar
                                            # (kırılım tuttu / rol uyumu), MS
                                            # "devam etti" satırı bu karta
                                            # girmez — iki ayrı yüzde yan yana
                                            # okunmuyordu (2026-10-22 kararı).
                                            aile="FRM",
                                            # Kart 3 ölçü satırı taşır
                                            # (GÖRSEL-9 blok düzeni).
                                            azami_olcum=3,
                                            # Beklenti hükmü varsayılan KAPALI
                                            # (TELEGRAM_KART_TAHMIN); açıkken
                                            # ölçüm satırlarının önüne hüküm +
                                            # sayaç girer, kart 3 satırı aşmaz.
                                            beklenti=bool(getattr(config, "TELEGRAM_KART_TAHMIN", False)),
                                            atr=atr_alarm,
                                            yon=break_dir,
                                            retest_seen=payload.get('retest_seen'),
                                            # GÖRSEL-4: geçersizleşme kartı yalnız
                                            # formasyon + geçersizleşen TF'nin bilgisi
                                            # (diğer TF'lerin yapı/bölge/hacim dökümü
                                            # 23 satıra çıkıyordu — kullanıcı kararı).
                                            yalniz_tf=(notification_state
                                                       == "KIRILIM_GECERSIZLESTI"),
                                            # Sembol sınıfı hacim satırını belirler
                                            # (endeks/makro: "hacim yok" yerine neden).
                                            sembol=stock,
                                        )
                                    except Exception as kart_hata:  # noqa: BLE001
                                        _pkg.logger.warning(
                                            "Kart bağlamı hazırlanamadı (%s %s): %s",
                                            stock, tf_name, kart_hata,
                                        )
                                    # Göreli güç yalnız YAPI bloğunda tek satır;
                                    # endeks alarmının kendisinde basılmaz. Kendi
                                    # try'ı: endeks verisi yoksa bölge/hacim/ölçü
                                    # blokları yine basılır.
                                    try:
                                        goreli = _pkg._goreli_guc_satiri(
                                            stock, tf_name, df_tf, deque_manager)
                                        if goreli and isinstance(
                                                payload.get('domain_bolumleri'), dict):
                                            payload['domain_bolumleri']['goreli'] = [goreli]
                                    except Exception as goreli_hata:  # noqa: BLE001
                                        _pkg.logger.debug(
                                            "Göreli güç satırı üretilemedi (%s %s): %s",
                                            stock, tf_name, goreli_hata,
                                        )
                                    try:
                                        payload['domain_karsi'] = karsi_deliller(
                                            outputs,
                                            alarm_tf=tf_name,
                                            break_dir=break_dir,
                                            mtf_destek=payload.get('mtf_destek'),
                                            retest_seen=payload.get('retest_seen'),
                                        )
                                    except Exception as karsi_hata:  # noqa: BLE001
                                        _pkg.logger.debug(
                                            "Karşı delil üretilemedi (%s %s): %s",
                                            stock, tf_name, karsi_hata,
                                        )
                            except Exception as exc:  # noqa: BLE001 - bağlam alarmı düşürmesin
                                payload['domain_context'] = ""
                                _pkg.logger.warning(
                                    "Bildirim domain bağlamı atlandı (%s %s): %s",
                                    stock, tf_name, exc,
                                )
                            _grafik_koprusu(payload, outputs)
                            # Public kuyruk: bülten kartı hazır olduktan SONRA
                            # (kart bağlamı + varsa public karesi kayda girer).
                            try:
                                notifier.public_kuyruk(payload)
                            except Exception as public_hata:  # noqa: BLE001
                                _pkg.logger.debug("Public kuyruğa eklenemedi (%s %s): %s",
                                             stock, tf_name, public_hata)


                        if dm_gecersiz_engel or dm_dev_engel:
                            # Yalnız bağlam + public kuyruğu: DM'e gönderim yok,
                            # hint/kuyruk sayaçları da değişmez. İki bilinçli
                            # DM kapısı aynı yolu kullanır: geçersizleşme
                            # duyurulmadan geri alma yok + devamlılık musluğu.
                            _attach_domain_context(alert_data)
                            alert_sent = False
                        else:
                            _pkg.daily_stats['alerts_attempted'] += 1
                            send_with_prepare = getattr(notifier, "send_with_prepare", None)
                            if callable(send_with_prepare):
                                alert_sent = send_with_prepare(
                                    alert_data, before_send=_attach_domain_context
                                )
                            else:
                                # Test/custom notifier adapters may expose only send().
                                _attach_domain_context(alert_data)
                                alert_sent = notifier.send(alert_data)
                        if alert_sent:
                            _pkg.daily_stats['alerts_sent'] += 1
                            _pkg._gun_sayacini_gonderimle_hizala(
                                stock, tf_name, notification_state)
                            _pkg._live_state.mark_alert_sent(stock, tf_name)
                            # Gölge defter: KULLANICIYA GİDEN uyarılar kaydedilir
                            # (kanala gitmeyen aday değil) — ileri testin evreni.
                            _pkg._ileri_test_kaydet(alert_data)
                            _pkg.logger.info(f"📨 Telegram gönderildi: {stock} {tf_name} {notification_state} kalite {q:.0f} touches={upper_touches}/{lower_touches} age={age_bars} mtf={mtf_destek}")
                        elif not (dm_gecersiz_engel or dm_dev_engel):
                            # Neden gönderilemedi? cooldown/kap ise olay kaybolmasın
                            # (Batch 5'te kuyruğa alınır); şimdilik sayılır.
                            # DM geçersizleşme/devamlılık kapıları buraya DÜŞMEZ
                            # (yukarıda ayrıldı): onlar arıza değil, bilinçli
                            # "DM'e söyleme" kararıdır.
                            _pkg.daily_stats['alerts_failed'] += 1
                            if getattr(notifier, "_son_engel", ""):
                                if notifier._son_engel == "cooldown":
                                    _pkg.daily_stats['alerts_engel_cooldown'] += 1
                                elif notifier._son_engel == "tekrar":
                                    # Nihai red: olay zaten bildirildi, kuyruğa girmez.
                                    _pkg.daily_stats['alerts_engel_tekrar'] += 1
                                else:
                                    _pkg.daily_stats['alerts_engel_kap'] += 1
                                # Olay kaybolmadı: kuyruğa alındı, engel kalkınca gider.
                                if notifier.kuyrukta_mi(alert_data):
                                    _pkg.daily_stats['alerts_kuyruk'] += 1
                                    _pkg.logger.info(
                                        f"📬 {stock} {tf_name} {state} engel nedeniyle kuyruğa alındı "
                                        f"({notifier._son_engel})"
                                    )
                            _pkg.logger.warning(
                                f"⚠️ Telegram gönderilemedi: {stock} {tf_name} {notification_state} "
                                f"(engel: {getattr(notifier, '_son_engel', None) or 'gönderim hatası'})"
                            )
                    elif send_alerts:
                        # Ne acil ne izleme: mevcut state politikasında push yok,
                        # yalnız /panel ve /formasyonlar gösterir. Sessizce düşmesin.
                        _pkg.daily_stats['alerts_state_disabled'] += 1
                else:
                    # Başarılı TF taramasında aday kaybolduysa bekleyen kaydı kaldır.
                    _pkg._deferred_alert_buffer.observe(stock, tf_name, None, simdiki_zaman)
                    # Canlı formasyon yok (terminal state'ler ve kalite kapısı dahil)
                    _pkg.logger.debug(f"{stock} {tf_name} - Canlı formasyon yok: {snap.log}")
            
            for formasyon_kaydi in hisse_formasyonlari:
                tf_kaydi = formasyon_kaydi.get("timeframe")
                teyit_tf = "4h" if tf_kaydi in ("1h", "2h") else "1d" if tf_kaydi == "4h" else None
                if teyit_tf:
                    teyit = lifecycle_manager.get_snapshot(stock + "_" + teyit_tf)
                    formasyon_kaydi["mtf_destek"] = bool(
                        teyit and teyit.active
                        and teyit.state not in ("FORMASYON_GECERSIZ", "Yok", "ST_NONE")
                    )
                    _pkg._live_state.record_formation(formasyon_kaydi)

            _pkg.daily_stats['stocks_scanned'] += 1
            tur_taranan += 1
            
            # Her hisse sonrası diske kaydet (crash durumunda kayıp azalsın) + heartbeat
            try:
                deque_manager.save_to_disk(stock)
            except Exception as e:
                _pkg.logger.warning(f"{stock} save_to_disk hatası: {e}")
            _pkg.write_heartbeat(notifier=notifier)

            # Mirror üretimi tarama sırasında olur. Sadece tur sonunda flush
            # etmek 57 hisselik tur boyunca kuyruğun taşmasına yol açıyordu.
            # Hisse başına sınırlı iş yap; arıza analizi/taramayı durdurmasın.
            if _pkg._supabase_store_ref is not None and getattr(_pkg._supabase_store_ref, "writable", True):
                try:
                    from state.formation_mirror import get_mirror_queue
                    get_mirror_queue().flush(_pkg._supabase_store_ref, max_batches=2)
                except Exception:  # noqa: BLE001 - mirror opsiyoneldir
                    _pkg.logger.warning("Tarama sırasında mirror flush atlandı", exc_info=True)

        except Exception as e:
            _pkg.daily_stats['errors'] += 1
            tur_hata += 1
            _pkg.logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
            continue
    
    for _st in scan_stocks[:3]:
        _df_g = deque_manager.to_gunluk_dataframe(_st)
        if _df_g is not None:
            _pkg.daily_stats['gunluk_bar_sayisi'] = len(_df_g)
            break

    sure_dk = (time.monotonic() - tarama_baslangici) / 60.0
    _pkg.daily_stats['son_tarama_suresi_dk'] = round(sure_dk, 1)
    eksik = max(len(scan_stocks) - tur_taranan, 0)
    global last_run_stats
    run_status = "tamamlandi" if tur_taranan == len(scan_stocks) and tur_hata == 0 else "basarisiz"
    finished_at = _pkg.datetime.now(ISTANBUL_TZ)
    full_universe_success = run_status == "tamamlandi" and _pkg._is_full_universe_scan(scan_stocks)
    setattr(_pkg, "last_run_stats", {
        "status": run_status,
        "requested": len(scan_stocks),
        "processed": tur_taranan,
        "failed": max(tur_hata, eksik),
        "patterns": tur_formasyon,
        "fresh_fetch": len(taze_1h_verileri),
        "fetch_failures": len(fetch_hatalari),
        "duration_minutes": round(sure_dk, 1),
        "data_asof": en_son_bar.isoformat() if en_son_bar is not None else None,
        "oldest_bar_age_minutes": en_eski_bar_yasi_dk,
        "finished_at": finished_at.isoformat(),
    })
    if run_status == "tamamlandi":
        finish_fields = {}
        if full_universe_success:
            finish_fields["son_basarili_tam_tarama"] = finished_at.isoformat()
        _pkg._live_state.finish_scan(
            finished_at,
            son_tarama_durumu="tamamlandi",
            son_tarama_suresi_dk=round(sure_dk, 1),
            son_tarama_hissesi=tur_taranan,
            son_tarama_beklenen_hisse=len(scan_stocks),
            son_tarama_hata_hisse=0,
            son_tarama_taze_veri=len(taze_1h_verileri),
            son_tarama_fetch_hatasi=len(fetch_hatalari),
            son_tarama_formasyonu=tur_formasyon,
            son_tarama_veri_zamani=en_son_bar.isoformat() if en_son_bar is not None else None,
            son_tarama_en_eski_veri_yasi_dk=en_eski_bar_yasi_dk,
            **finish_fields,
        )
        _pkg.son_tarama_kaydet()
    else:
        hata = (f"Eksik tarama: {tur_taranan}/{len(scan_stocks)} hisse başarıyla hesaplandı; "
                f"{max(tur_hata, eksik)} hata/atlanan.")
        _pkg._live_state.fail_scan(
            hata,
            _pkg.datetime.now(ISTANBUL_TZ),
            hata_hisse=max(tur_hata, eksik),
            islenen_hisse=tur_taranan,
            istek_hisse=len(scan_stocks),
            sure_dk=round(sure_dk, 1),
        )
        _pkg.logger.error("Tarama sonucu yayımlanmadı; son başarılı snapshot korundu. %s", hata)
        # Formasyon listesini değiştirmeden başarısızlık/son başarılı tam tarama
        # metadatasını da kaydet; restart sonrası eski veri güncel sanılmasın.
        _pkg.son_tarama_kaydet()

    # --- TARAMA DRİFT KORUMASI (FAZ 2) ---
    if sure_dk > TARAMA_SURESI_UYARI_DK:
        _pkg.logger.warning(
            f"TARAMA ÇOK UZUN SÜRDÜ: {sure_dk:.1f} dk (eşik {TARAMA_SURESI_UYARI_DK} dk, "
            f"mum kapanış aralığı 60 dk). Bir sonraki mum gecikmeli analiz edilecek - "
            f"Yahoo yavaşlığı veya rate-limit birikmesi olabilir."
        )

    _pkg.logger.info(f"=== TARAMA BİTTİ - Günlük: {_pkg.daily_stats} ===")
    if _pkg.daily_stats['split_atlanan']:
        _pkg.logger.error(
            f"SPLIT/VERİ SORUNU: {_pkg.daily_stats['split_atlanan']} hisse analiz edilmedi "
            f"(ham seride fiyat sürekliliği ihlali). Detay: "
            f"{ {k: [x['tip'] for x in v] for k, v in deque_manager.sureklilik_sorunlari.items()} }"
        )
    if _pkg.daily_stats['veri_yok_modu']:
        _pkg.logger.warning(
            f"VERİ YOK MODU: bugün için yeni piyasa verisi alınamadı "
            f"(fetch hatası {_pkg.daily_stats['fetch_failures']}/{len(_pkg.ACTIVE_STOCKS)}, "
            f"en eski mum {_pkg.daily_stats['max_bar_age_min']} dk). Analiz yapılmadı - "
            f"tatil veya veri kaynağı arızası olabilir."
        )
    elif _pkg.daily_stats['fetch_failures'] > 0 or _pkg.daily_stats['data_stale']:
        _pkg.logger.warning(
            f"VERİ SAĞLIĞI: taze veri {_pkg.daily_stats['fetch_ok']}/{len(_pkg.ACTIVE_STOCKS)} hisse, "
            f"fetch hatası {_pkg.daily_stats['fetch_failures']}, eski veri {_pkg.daily_stats['stale_stocks']} hisse, "
            f"en eski mum {_pkg.daily_stats['max_bar_age_min']} dk"
        )
    else:
        _pkg.logger.info(
            f"VERİ SAĞLIĞI: taze veri {_pkg.daily_stats['fetch_ok']}/{len(_pkg.ACTIVE_STOCKS)} hisse, "
            f"en eski mum {_pkg.daily_stats['max_bar_age_min']} dk"
        )
    # Tarama turu bitti: public (grup) kuyruğunda biriken olaylar TEK bültende
    # gider. DM'den bağımsızdır; manuel taramalarda (send_alerts=False) kuyruk
    # zaten boştur.
    _pkg._public_turu_kapat(notifier)
    _pkg._grafikleri_tur_sonunda(notifier)
    # Tarama bitti: heartbeat kesin yazılsın (force), böylece per-hisse
    # throttle'a takılan son durum dışarıdan anında görünür.
    _pkg.write_heartbeat(notifier=notifier, force=True)
    return dict(_pkg.last_run_stats)


def _grafikleri_tur_sonunda(notifier) -> None:
    """Retry the durable alert FIFO, then drain legacy command/test pictures."""
    teslim = getattr(notifier, "teslimleri_dene", None)
    if callable(teslim):
        teslim()
    gonder = getattr(notifier, "grafikleri_gonder", None)
    if not callable(gonder):        # test/özel notifier'lar: sessizce yok say
        return
    try:
        ozet = gonder() or {}
    except Exception as hata:  # noqa: BLE001 - görsel taramayı düşürmesin
        _pkg.logger.warning("Grafik kareleri gönderilemedi: %s: %s", type(hata).__name__, hata)
        return
    if int(ozet.get("kare") or 0) or int(ozet.get("atlanan") or 0):
        _pkg.logger.info("📈 Grafik kareleri: %d/%d gönderildi · hata %d · atlanan %d",
                    int(ozet.get("gonderilen") or 0), int(ozet.get("kare") or 0),
                    int(ozet.get("hata") or 0), int(ozet.get("atlanan") or 0))
        try:
            _pkg.daily_stats['grafik_kare'] = int(_pkg.daily_stats.get('grafik_kare') or 0) + int(
                ozet.get("gonderilen") or 0)
            _pkg.daily_stats['grafik_hata'] = int(_pkg.daily_stats.get('grafik_hata') or 0) + int(
                ozet.get("hata") or 0)
        except Exception:  # noqa: BLE001
            # Sayaç güncellenemese de özet logu basılmıştır; iz kalsın (2026-10-26).
            _pkg.logger.debug("Grafik sayaçları güncellenemedi", exc_info=True)


def _is_full_universe_scan(stocks) -> bool:
    """Whether a scan covers each configured symbol exactly once."""
    try:
        expected = {str(stock).upper() for stock in _pkg.ACTIVE_STOCKS}
        requested = [str(stock).upper() for stock in (stocks or [])]
        return bool(expected) and len(requested) == len(expected) and set(requested) == expected
    except Exception:  # noqa: BLE001 - guard helper should fail closed
        return False


