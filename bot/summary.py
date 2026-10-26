"""bot/summary.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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
                gun = _pkg.datetime.fromisoformat(str(deger)).date()
            except (TypeError, ValueError):
                continue
            ad = str(anahtar)
            if ad.startswith("public:"):
                public[ad.split(":", 1)[1]] = gun
            else:
                dm[ad] = gun
        # Ephemeral instance restart/replace durumlarında da slot mühürü kalsın.
        store = _pkg._supabase_store_ref
        if store is not None and hasattr(store, "get_many"):
            remote = store.get_many([_pkg.SUMMARY_MARKERS_SUPABASE_KEY])
            remote_markers = (remote or {}).get(_pkg.SUMMARY_MARKERS_SUPABASE_KEY)
            if isinstance(remote_markers, dict):
                for anahtar, deger in remote_markers.items():
                    try:
                        gun = _pkg.datetime.fromisoformat(str(deger)).date()
                    except (TypeError, ValueError):
                        continue
                    ad = str(anahtar)
                    if ad.startswith("public:"):
                        slot = ad.split(":", 1)[1]
                        public[slot] = max(public.get(slot, gun), gun)
                    else:
                        dm[ad] = max(dm.get(ad, gun), gun)
        if dm or public:
            _pkg.logger.info("Günlük özet işaretleri geri yüklendi: DM=%s public=%s",
                        sorted(dm), sorted(public))
    except Exception as hata:  # noqa: BLE001 - kalıcılık hatası botu durdurmaz
        _pkg.logger.warning("Özet işaretleri okunamadı: %s", hata)
    return dm, public


def _ozet_slot_gonderilmeli(isaretler: dict, slot: str, gun) -> bool:
    """Aynı DM/public özet slotunu aynı İstanbul gününde ikinci kez gönderme."""
    gun_tarihi = gun.date() if isinstance(gun, _pkg.datetime) else gun
    isaret = (isaretler or {}).get(str(slot))
    if isinstance(isaret, str):
        try:
            isaret = _pkg.datetime.fromisoformat(isaret).date()
        except (TypeError, ValueError):
            isaret = None
    elif isinstance(isaret, _pkg.datetime):
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
        store = _pkg._supabase_store_ref
        if store is not None and hasattr(store, "upsert"):
            remote_markers = dict(isaretler)
            try:
                remote = store.get_many([_pkg.SUMMARY_MARKERS_SUPABASE_KEY]) if hasattr(store, "get_many") else None
                existing = (remote or {}).get(_pkg.SUMMARY_MARKERS_SUPABASE_KEY)
                if isinstance(existing, dict):
                    for remote_key, remote_value in existing.items():
                        remote_key = str(remote_key)
                        try:
                            remote_date = _pkg.datetime.fromisoformat(str(remote_value)).date()
                            local_date = _pkg.datetime.fromisoformat(
                                str(remote_markers.get(remote_key) or remote_value)
                            ).date()
                        except (TypeError, ValueError):
                            remote_markers.setdefault(remote_key, remote_value)
                            continue
                        remote_markers[remote_key] = max(local_date, remote_date).isoformat()
            except Exception as remote_error:  # noqa: BLE001 - yerel işaret korunur
                _pkg.logger.debug("Supabase özet işareti okunamadı: %s", remote_error)
            remote_markers[anahtar] = deger
            if not store.upsert(_pkg.SUMMARY_MARKERS_SUPABASE_KEY, remote_markers):
                _pkg.logger.debug("Supabase özet işareti yazılamadı (%s)", slot)
    except Exception as hata:  # noqa: BLE001
        _pkg.logger.debug("Özet işareti yazılamadı (%s): %s", slot, hata)


def _public_turu_kapat(notifier) -> None:
    """Tarama turu sonu: tur sayacını artır + public kuyruğunu bültende boşalt.

    Bülten gönderimi taramayı ASLA durdurmaz (dış servis hatası tarama sonucunu
    geçersiz kılmamalı); hata yalnız loglanır, kayıtlar kuyrukta kalır.
    """
    _pkg.daily_stats['tarama_sayisi'] = int(_pkg.daily_stats.get('tarama_sayisi') or 0) + 1
    _pkg._gunluk_sayac_kaydet()
    try:
        if notifier is not None:
            notifier.public_bosalt()
    except Exception as public_hata:  # noqa: BLE001 - bülten hatası taramayı durdurmasın
        _pkg.logger.warning("Public bülten gönderilemedi: %s", public_hata)


def _parse_summary_hours() -> List[dt_time]:
    """SUMMARY_HOURS env'ini İstanbul saatine çevir (09:55,18:45)."""
    try:
        saatler = []
        for ham in _pkg.SUMMARY_HOURS.split(","):
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
        h, m = _pkg.DEFERRED_ALERT_DIGEST_TIME.split(":")
        saat = dt_time(int(h), int(m))
        if saat < dt_time(18, 45):
            _pkg.logger.warning("DEFERRED_ALERT_DIGEST_TIME son taramadan önce; 18:45'e alındı")
            return dt_time(18, 45)
        return saat
    except Exception:
        _pkg.logger.warning("DEFERRED_ALERT_DIGEST_TIME geçersiz; 18:45 kullanılacak")
        return dt_time(18, 45)


def _karne_uzak_kaydet(zorla: bool = False) -> bool:
    """Defteri (varsa) uzak yedeğe yazar. Sık yazmamak için aralık uygulanır.

    Yerel dosya her kayıtta zaten yazılır; bu yalnız dayanıklılık içindir.
    """
    global _karne_son_uzak_yazma
    if _pkg._supabase_store_ref is None or _pkg._karne_defteri is None:
        return False
    simdi = time.monotonic()
    if not zorla and (simdi - _pkg._karne_son_uzak_yazma) < _pkg.KARNE_UZAK_YAZMA_ARALIK_SN:
        return False
    sonuc = _state_persistence.karne_defteri_kaydet(_pkg._karne_defteri, _pkg._supabase_store_ref)
    if sonuc:
        setattr(_pkg, "_karne_son_uzak_yazma", simdi)
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
            _pkg.logger.debug("Karne serisi alınamadı (%s %s): %s", stock, tf, exc)
            return None
    return saglayici


def _karne_olay_kaydet(stock: str, tf: str, state: str, pattern: str, quality: float,
                       bar_zamani, *, kirilim: bool = False, dir: int = 0,
                       entry=None, df_tf=None, mtf_destek: bool = False,
                       stable_id=None) -> None:
    """Tarama sırasında karne defterine kayıt düşer (hatalar taramayı durdurmaz)."""
    try:
        defter = _pkg._karne_al()
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
        _pkg._karne_outcome_bagla(stock, tf, stable_id, df_tf)
    except Exception as exc:  # noqa: BLE001
        _pkg.logger.debug("Karne kaydı yazılamadı (%s %s %s): %s", stock, tf, state, exc)


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
        defter = _pkg._karne_al()
        return outcome_link.bagla(defter, stock, tf, stable_id,
                                  saglayici=lambda s, t: df_tf)
    except Exception as exc:  # noqa: BLE001 - linkage taramayi asla durdurmaz
        _pkg.logger.debug("Outcome bağlantısı kurulamadı (%s %s): %s", stock, tf, exc)
        return None


def _karne_dolu(defter: KarneDefteri, now: _pkg.datetime) -> bool:
    """Bu hafta için karnede gösterilecek en az bir kayıt var mı?"""
    try:
        from karne import hafta_baslangici
        return bool(defter.aralikta(hafta_baslangici(now), now))
    except Exception:  # noqa: BLE001
        return False


def _haftalik_karne_ekle(now: _pkg.datetime, deque_manager, zorla: bool = False) -> str:
    """Karne günüyse ve bu hafta gönderilmediyse karne metnini döner; yoksa ''.

    `zorla=True` -> gün/hafta kapıları atlanır (yalnız açıkça isteyen çağrı için).
    Karne, gün sonu mesajının ALTINA eklenir; burada gönderim YAPILMAZ.
    """
    try:
        hafta = hafta_damgasi(now)
        defter = _pkg._karne_al()
        if not zorla:
            if not karne_gunu_mu(now):
                return ""
            if defter.karne_gonderildi_mi(hafta):
                return ""
        if not _pkg._karne_dolu(defter, now):
            # Hiç kayıt yoksa boş karne gönderme (hafta başı / yeni kurulum).
            return ""
        return karne_uret(defter, _pkg._karne_seri_saglayici(deque_manager), now=now)
    except Exception as exc:  # noqa: BLE001 - karne hatası özeti engellemesin
        _pkg.logger.warning("Haftalık karne üretilemedi: %s", exc)
        return ""


def _haftalik_karne_kisa(now: _pkg.datetime, deque_manager) -> str:
    """Karne metninin PUBLIC (grup) sürümü: 4-5 satır.

    Tam metin teknik döküm (defter satırı, hedef/nötr/stop, dosya yolu) taşır ve
    gruba uygun değildir; kısa sürüm aynı ölçümü sade dille verir.
    """
    try:
        defter = _pkg._karne_al()
        if not _pkg._karne_dolu(defter, now):
            return ""
        from karne import hafta_baslangici, karne_hesapla, karne_kisa_metni, pencere
        baslangic = hafta_baslangici(now)
        kayitlar = defter.aralikta(baslangic, now)
        metrik = karne_hesapla(kayitlar, _pkg._karne_seri_saglayici(deque_manager), now=now)
        return karne_kisa_metni(metrik, pencere(baslangic, now))
    except Exception as exc:  # noqa: BLE001 - kısa karne özeti engellemesin
        _pkg.logger.debug("Kısa karne üretilemedi: %s", exc)
        return ""


def _karne_gonderildi_isaretle(now: _pkg.datetime) -> None:
    """Karne başarıyla gönderildi -> bu hafta tekrar eklenmez (kalıcı)."""
    try:
        _pkg._karne_al().karne_gonderildi_isaretle(hafta_damgasi(now))
        # Haftalık işaret + kayıtlar restart'ta kaybolmasın: yedeği hemen tazele.
        _pkg._karne_uzak_kaydet(zorla=True)
    except Exception as exc:  # noqa: BLE001
        _pkg.logger.debug("Karne gönderim işareti yazılamadı: %s", exc)


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
    if karne_ek and len(ana_mesaj) + len(karne_ek) + 2 <= _pkg._MESAJ_GUVENLI_SINIR:
        parcalar = [(ana_mesaj + "\n\n" + karne_ek, "ikisi")]
    elif karne_ek:
        _pkg.logger.info("Karne mesaj sınırını aştı; ayrı mesaj olarak gönderiliyor (%d + %d kr)",
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
    if anahtar in _pkg._daily_lifecycle_event_keys:
        return
    counter = _pkg._LIFECYCLE_EVENT_COUNTERS.get(str(state or "").strip().upper())
    if not counter:
        return
    # Olay yolunun yazdığı anahtar: STOCK|tf|kimlik|state|tür|zaman
    for kayit in _pkg._daily_lifecycle_event_keys:
        parcalar = str(kayit).split("|")
        if len(parcalar) < 4 or parcalar[0] == "GONDERIM":
            continue
        if (parcalar[0] == str(stock).upper() and parcalar[1] == str(timeframe).lower()
                and parcalar[3] == str(state or "").strip().upper()):
            return
    _pkg._daily_lifecycle_event_keys.add(anahtar)
    _pkg.daily_stats[counter] = int(_pkg.daily_stats.get(counter) or 0) + 1
    _pkg._gunluk_sayac_kaydet()


def _daily_summary_payload(now=None) -> dict:
    """Daily counters plus freshness metadata for Telegram summaries."""
    now = now or _pkg.datetime.now(ISTANBUL_TZ)
    payload = dict(_pkg.daily_stats)
    try:
        status = _pkg._live_state.status() or {}
    except Exception:  # noqa: BLE001 - summary still works without live status
        status = {}
    full_at = status.get("son_basarili_tam_tarama")
    # Backward compatibility with snapshots created before the dedicated stamp.
    if not full_at:
        try:
            expected = int(status.get("son_tarama_beklenen_hisse") or 0)
            processed = int(status.get("son_tarama_hissesi") or 0)
            if (status.get("son_tarama_durumu") == "tamamlandi"
                    and expected >= len(_pkg.ACTIVE_STOCKS)
                    and processed >= len(_pkg.ACTIVE_STOCKS)):
                full_at = status.get("son_tarama_bitis")
        except (TypeError, ValueError, OverflowError):
            full_at = None
    payload["son_basarili_tam_tarama"] = full_at
    payload["tam_tarama_guncel"] = _pkg._successful_full_scan_today(now)
    payload["son_tarama_durumu"] = status.get("son_tarama_durumu")
    # "N bildirim" satırı yalnız tarama turunda gidenleri sayıyordu; cooldown/kap
    # yüzünden kuyruğa giren ve sonra gönderilen alarm sayılmıyordu (25 Eyl:
    # 6 mesaj gönderildi, özet "5 bildirim" dedi). Kuyruk sayacı da eklenir.
    # payload kopya olduğu için /durum ve kalıcı sayaç davranışı değişmez.
    try:
        _nref = _pkg._notifier_ref
        kuyruk_giden = int(getattr(_nref, "kuyruk_gonderildi", 0) or 0) if _nref else 0
    except Exception:  # noqa: BLE001 - özet, sayaç yüzünden düşmez
        kuyruk_giden = 0
    if kuyruk_giden:
        payload["alerts_sent"] = int(payload.get("alerts_sent") or 0) + kuyruk_giden
    return payload


def _successful_full_scan_today(now: _pkg.datetime) -> bool:
    """True only when the latest full-universe scan completed today."""
    try:
        status = _pkg._live_state.status()
        if status.get("son_tarama_durumu") != "tamamlandi":
            return False
        expected = int(status.get("son_tarama_beklenen_hisse") or
                      status.get("son_is_hisse_istek") or 0)
        processed = int(status.get("son_tarama_hissesi") or
                        status.get("son_is_hisse_basarili") or 0)
        if expected < len(_pkg.ACTIVE_STOCKS) or processed < len(_pkg.ACTIVE_STOCKS):
            return False
        raw_finished = status.get("son_tarama_bitis") or status.get("son_is_bitis")
        if not raw_finished:
            return False
        finished = _pkg.datetime.fromisoformat(str(raw_finished).replace("Z", "+00:00"))
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
    digest_time = _pkg._parse_deferred_alert_digest_time()
    morning_and_day = [hour for hour in _pkg._parse_summary_hours() if hour.hour < 18]
    return sorted(set(morning_and_day + [digest_time]))


def _acil_kuyruk_gonderim_penceresi_acik(simdi: _pkg.datetime, digest_saati: dt_time) -> bool:
    """Acil kuyruğu digest'ten 2 dk önce kapat; ağ kuyruğu özeti geciktirmesin."""
    try:
        yerel = (ISTANBUL_TZ.localize(simdi) if simdi.tzinfo is None
                 else simdi.astimezone(ISTANBUL_TZ))
        kesim = _pkg.datetime.combine(yerel.date(), digest_saati) - timedelta(minutes=2)
        return yerel.replace(tzinfo=None) < kesim
    except (AttributeError, TypeError, ValueError):
        return False


def _acil_kuyruk_acilista_isle(notifier, simdi: _pkg.datetime, digest_saati: dt_time,
                                kapanis_ozeti_gonderildi: bool = False) -> int:
    """Açılışta kuyruğu aç; digest sonrası eski push'ı bireysel gönderme."""
    try:
        if (notifier is None or not getattr(notifier, "enabled", False)
                or not notifier.kuyruk_durumu().get("bekleyen")):
            return 0
        if _pkg._acil_kuyruk_gonderim_penceresi_acik(simdi, digest_saati):
            return int(notifier.kuyrugu_bosalt() or 0)
        if kapanis_ozeti_gonderildi:
            temizle = getattr(notifier, "kuyruk_tumunu_temizle", None)
            atlanan = int(temizle() or 0) if callable(temizle) else 0
            if atlanan:
                _pkg.logger.warning(
                    "Kapanış özeti zaten gönderilmiş; %d bekleyen acil bildirim "
                    "geç saatte ayrı push olmasın diye kuyruktan çıkarıldı.", atlanan)
        # Kapanış özeti henüz gönderilmediyse olaylar özete eklenmek üzere tutulur.
        return 0
    except Exception as hata:  # noqa: BLE001 - kuyruk hatası açılışı düşürmesin
        _pkg.logger.debug("Açılış kuyruk politikası uygulanamadı: %s", hata)
        return 0


def _kacirilan_digest_ozeti(notifier, simdiki_zaman) -> str:
    """Geçmiş günden kalan bekleyen adaylar için kaçırılan 18:45 telafisi.

    Bot akşam 18:45'te kapalıysa tampon bir sonraki açılışa kadar bekler;
    burada tek seferde gönderilir (aksi halde _ensure_day ilk taramada temizler).
    """
    global _digest_son_gonderim_gun
    gun = _pkg._deferred_alert_buffer.gun()
    if not _pkg._deferred_alert_buffer or gun is None or gun >= simdiki_zaman.date():
        return ""
    bekleyen = _pkg._deferred_alert_buffer.items(
        ISTANBUL_TZ.localize(_pkg.datetime.combine(gun, dt_time(23, 59))),
        limit=DEFERRED_ALERT_DIGEST_LIMIT,
    )
    if not bekleyen:
        return ""
    watch_summary = _format_deferred_alert_summary(bekleyen, len(_pkg._deferred_alert_buffer))
    metin = f"⏰ Kaçırılan kapanış özeti ({gun.strftime('%d.%m')} 18:45)\n{watch_summary}"
    if notifier is None or not notifier.enabled:
        # Pasif modda sessizce düşmesin: bir sonraki açılışta tekrar denenmeyecek,
        # bu yüzden kayıt yine de temizlenir ve durum loglanır.
        _pkg.logger.warning("Kaçırılan kapanış özeti gönderilemedi (Telegram pasif): %d aday", len(bekleyen))
    else:
        gonderildi, hata = notifier.send_text(metin)
        if gonderildi:
            _pkg._deferred_alert_buffer.mark_reported(bekleyen, simdiki_zaman)
            # Telafi edilen gün "gönderildi" sayılır; bugünün 18:45'i hâlâ bekliyor.
            setattr(_pkg, "_digest_son_gonderim_gun", gun.isoformat())
            _pkg.logger.info("Kaçırılan kapanış özeti gönderildi: %d aday (%s)", len(bekleyen), gun)
        else:
            _pkg.logger.warning("Kaçırılan kapanış özeti gönderilemedi: %s", hata)
    _pkg._deferred_alert_buffer.clear(simdiki_zaman)
    _pkg.digest_tamponu_kaydet()
    return metin


def _parse_post_close_analysis_time() -> dt_time:
    """Gün sonu tam tarama saatini İstanbul yerel saati olarak çöz."""
    try:
        hour, minute = _pkg.POST_CLOSE_ANALYSIS_TIME.strip().split(":", 1)
        return dt_time(int(hour), int(minute))
    except (AttributeError, TypeError, ValueError):
        _pkg.logger.warning("POST_CLOSE_ANALYSIS_TIME geçersiz; 20:00 kullanılacak")
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
        etiket = _pkg._POST_CLOSE_DIFF_LABELS.get(state_key, state_key)
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
        formations = _pkg._live_state.formations()
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
        _pkg.logger.debug(f"Özet için formasyon toplanamadı: {e}")
    return aktif


def evening_maintenance(deque_manager, lifecycle_manager):
    """18:10-19:00 kapanış bakımı - 3 problem için tek seferlik hafif iş."""
    _pkg.logger.info("=== AKŞAM BAKIMI BAŞLIYOR (veri hijyeni + state temizliği + rapor) ===")
    try:
        # 1. Veri hijyeni: hacmi 0 veya zaman damgası hatalı son barları temizle
        temizlenen = 0
        for stock in _pkg.ACTIVE_STOCKS:
            try:
                df = deque_manager.to_dataframe(stock)
                if df is not None and len(df) > 0:
                    # Son bar hacmi 0 ise ve gün içinde eksik kalmışsa
                    son = df.iloc[-1]
                    if son.get('volume', 1) == 0:
                        # Sadece logla, silme değil - data.py zaten filtreliyor
                        _pkg.logger.debug(f"{stock}: son bar hacim 0 - hijyen logu")
                        temizlenen += 1
            except Exception as e:
                _pkg.logger.debug(f"{stock} hijyen hatası: {e}")
        _pkg.logger.info(f"Veri hijyeni: {temizlenen} hisse kontrol edildi")

        # 2. State temizliği: 48 saatten uzun süredir kırılım yapmamış dosyalar
        # lifecycle_manager zaten terminal tazelik kontrolü yapıyor, burada disk temizliği
        try:
            import glob
            from config import DATA_DIR
            import os
            json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if len(json_files) > 100:
                _pkg.logger.warning(f"bot_data'da {len(json_files)} dosya var, şişme riski - Supabase kullanılıyor mu kontrol et")
        except Exception as e:
            _pkg.logger.debug(f"State temizliği atlandı: {e}")

        # 3. Gün sonu raporu
        try:
            rapor = _pkg._live_state.status() if hasattr(_pkg._live_state, 'status') else {}
            _pkg.logger.info(f"GÜN SONU RAPORU: {rapor}")
            # Telegram özeti burada GÖNDERİLMEZ: 18:45 scheduler aynı günün
            # tek DM/public özetini başarıyla tamamlanmış tarama sonrasında yollar.
            # Bakım sonucu log'da kalır; aksi halde 18:10-18:59 aralığında ikinci
            # ve tarama öncesi bir "Gün Sonu Bakım Raporu" oluşuyordu.
        except Exception as e:
            _pkg.logger.warning(f"Gün sonu raporu hatası: {e}")

        _pkg.logger.info("=== AKŞAM BAKIMI BİTTİ ===")
    except Exception as e:
        _pkg.logger.error(f"Akşam bakımı hatası: {e}", exc_info=True)


def morning_preload(deque_manager, pacer):
    """08:30 pre-load - açılışta 0-latency için son barları yavaşça çek."""
    _pkg.logger.info("=== SABAH ÖN-YÜKLEME BAŞLIYOR (08:30) ===")
    try:
        for stock in _pkg.ACTIVE_STOCKS[:10]:  # ilk 10 hisse, yavaşça
            if _pkg._shutdown_requested:
                break
            try:
                with pacer.request(f"{stock} preload"):
                    taze = fetch_last_bar(stock)
                if taze is not None and len(taze) > 0:
                    deque_manager.append_dataframe(stock, taze)
                    _pkg.logger.debug(f"{stock}: preload {len(taze)} bar")
                time.sleep(1)
            except Exception as e:
                _pkg.logger.debug(f"{stock} preload hatası: {e}")
        _pkg.logger.info("=== SABAH ÖN-YÜKLEME BİTTİ ===")
    except Exception as e:
        _pkg.logger.error(f"Sabah preload hatası: {e}", exc_info=True)


def _ileri_test_kaydet(alert_data) -> None:
    """Gönderilen uyarıyı gölge deftere yazar. Hata botu DURDURMAZ."""
    try:
        import ileri_test
        ileri_test.kaydet(alert_data, store=_pkg._supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - ölçüm kaydı botu düşürmemeli
        _pkg.logger.debug("İleri test kaydı atlandı: %s", exc)


def _ileri_test_gece(now: _pkg.datetime) -> None:
    """Günde bir kez, kapanıştan sonra olgunlaşan kayıtların sonucunu hesaplar."""
    global _ileri_test_son_gece
    if now.hour < _pkg.ILERI_TEST_GECE_SAAT:
        return
    gun = now.date().isoformat()
    if _pkg._ileri_test_son_gece == gun:
        return
    try:
        import ileri_test
        cikti = ileri_test.gece(store=_pkg._supabase_store_ref,
                                rapor_yolu=os.path.join(config.DATA_DIR,
                                                        "ileri_test_ozet.md"))
        setattr(_pkg, "_ileri_test_son_gece", gun)
        _pkg.logger.info("İleri test gece işi tamam: %s", cikti["istatistik"])
        _pkg.logger.info("İleri test özeti:\n%s", cikti["ozet"])
    except Exception as exc:  # noqa: BLE001 - gece işi ana döngüyü düşürmemeli
        _pkg.logger.warning("İleri test gece işi başarısız: %s", exc)


def _gece_raporu_yaz(gun: str, tutarlilik: dict, olcum: dict) -> bool:
    """`gece_raporu` tablosuna gün anahtarıyla tek satır yazar. Hata işi düşürmez."""
    store = _pkg._supabase_store_ref
    if store is None:
        return False
    try:
        cevap = store.request_table(
            "gece_raporu", "POST",
            json={"gun": gun, "tutarlilik": tutarlilik, "olcum": olcum},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    except Exception as exc:  # noqa: BLE001 - rapor yazımı denetimi engellememeli
        _pkg.logger.debug("Gece raporu yazılamadı: %s", exc)
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
    notifier = _pkg._notifier_ref
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
        if oneri.tekrar_mi(metin, store=_pkg._supabase_store_ref):
            _pkg.logger.info("Gece önerisi aynı metinle yanıtlanmış; DM tekrarlanmadı")
            return False
    except Exception as exc:  # noqa: BLE001 - öneri defteri yoksa DM yine gitsin
        _pkg.logger.debug("Gece önerisi defteri okunamadı: %s", exc)
    try:
        gonderildi, durum = notifier.send_text(metin)
    except Exception as exc:  # noqa: BLE001 - DM hatası gece işini düşürmemeli
        _pkg.logger.debug("Gece önerisi gönderilemedi: %s", exc)
        return False
    if not gonderildi:
        _pkg.logger.info("Gece önerisi gönderilemedi: %s", durum)
        return False
    try:
        import oneri
        oneri.kaydet({
            "gun": gun or _pkg.datetime.now().date().isoformat(),
            "metin": metin,
            "karar": (olcum_sonuc or {}).get("karar") or "",
            "ozet": " · ".join(s for s in satirlar if s),
            "sapma": sapma,
            "durum": "bekliyor",
        }, store=_pkg._supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - kayıt yazılamazsa DM gitti, iş sürer
        _pkg.logger.debug("Gece önerisi kaydedilemedi: %s", exc)
    _pkg.logger.info("Gece önerisi DM'e gitti (%d satır)", len(satirlar))
    return True


def _gece_denetimi(now: _pkg.datetime) -> None:
    """Günde bir kez: canlı–replay tutarlılığı + ölçüm tazeleme. Değişiklik YOK."""
    global _gece_denetim_son_gun
    if now.hour < _pkg.ILERI_TEST_GECE_SAAT:
        return
    gun = now.date().isoformat()
    if _pkg._gece_denetim_son_gun == gun:
        return
    try:
        import ileri_test
        import olcum_tazele
        import tutarlilik

        try:
            defter = ileri_test.defter_yukle(store=_pkg._supabase_store_ref)
            kayitlar = defter.get("kayitlar") or []
        except Exception as exc:  # noqa: BLE001 - defter yoksa denetim yine koşar
            _pkg.logger.debug("Gece denetimi defteri okuyamadı: %s", exc)
            kayitlar = []

        tutarlilik_sonuc = tutarlilik.gunluk(kayitlar, simdi=now)
        _pkg.logger.info(tutarlilik.ozet(tutarlilik_sonuc))
        olcum_sonuc = olcum_tazele.tazele(store=_pkg._supabase_store_ref, kayitlar=kayitlar)
        _pkg.logger.info(olcum_sonuc.get("metin"))

        _pkg._gece_raporu_yaz(gun,
                         {k: v for k, v in tutarlilik_sonuc.items() if k != "detay"},
                         {"karar": olcum_sonuc.get("karar"),
                          "metin": olcum_sonuc.get("metin"),
                          "veri": olcum_sonuc.get("veri")})
        _pkg._gece_onerisi_gonder(tutarlilik_sonuc, olcum_sonuc, gun=gun)
        setattr(_pkg, "_gece_denetim_son_gun", gun)
    except Exception as exc:  # noqa: BLE001 - gece işi ana döngüyü düşürmemeli
        _pkg.logger.warning("Gece denetimi başarısız: %s", exc)


