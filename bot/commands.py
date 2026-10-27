"""bot/commands.py — main.py'den taşındı (modülerleştirme, davranış aynı).
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

def _komut_durumu() -> dict:
    """`/health` için komut katmanı özeti (mod + sayaçlar).

    NEDEN: /health "status: ok" derken DM komutlarının hiç çalışmaması mümkündü;
    bu blok modu (webhook/yoklama/kapali), dinleyicinin canlı olup olmadığını ve
    gelen komut sayaçlarını gösterir. Kişisel sohbet kimliği maskelenir.
    """
    dinleyici = _pkg._telegram_listener_ref or _pkg._telegram_update_processor_ref
    ozet: dict = {
        "mod": _pkg._komut_modu,
        "hedef_tanimli": bool(getattr(_pkg._notifier_ref, "chat_id", "")),
    }
    try:
        if dinleyici is not None and hasattr(dinleyici, "durum"):
            ozet.update(dinleyici.durum() or {})
    except Exception as exc:  # noqa: BLE001 - /health asla düşmesin
        ozet["hata"] = f"{type(exc).__name__}: {exc}"[:120]
    return ozet


def _saglik_ozeti() -> dict:
    """GET /health için canlılık alanları (denetim B-4).

    `/health` DAİMA 200 döner; Render'ın health check davranışı değişmez. Bu özet
    "bot ayakta mı, tarama sürüyor mu, seans açık mı" sorusunu dışarıdan
    cevaplanabilir yapar; `?strict=1` ile çağıran monitör heartbeat bayatken 503 alır.

    Bayatlama eşiği:
      - tarama sürüyorsa  → TARAMA_SURESI_UYARI_DK (uzun tam evren taraması yanlış
        alarm üretmesin),
      - seans açıkken     → 30 dk (tarama aralığı ~5 dk + gecikme payı),
      - seans kapalıyken  → 72 sa (hafta sonu/tatil boşluğunda heartbeat üretilmez).
    """
    simdi = _pkg.datetime.now(ISTANBUL_TZ)
    try:
        seans_acik = bool(_pkg.is_bist_open(simdi))
    except Exception:
        seans_acik = None
    try:
        tarama_suruyor = bool(_pkg._live_state.status().get("tarama_suruyor"))
    except Exception:
        tarama_suruyor = None
    if tarama_suruyor:
        esik_sn = int(TARAMA_SURESI_UYARI_DK * 60)
    elif seans_acik:
        esik_sn = 1800
    else:
        esik_sn = 259200
    yas = _pkg._heartbeat_yasi_sn(simdi)
    return {
        "heartbeat_age_s": None if yas is None else int(yas),
        "heartbeat_stale": None if yas is None else bool(yas > esik_sn),
        "heartbeat_stale_esik_s": esik_sn,
        "tarama_suruyor": tarama_suruyor,
        "seans_acik": seans_acik,
        "evren": len(_pkg.ACTIVE_STOCKS),
        "instance_id": _pkg.INSTANCE_ID,
        "komut": _pkg._komut_durumu(),
    }


# === TELEGRAM KOMUTLARI (iki yönlü) ===
# Bot alarm gönderir; bu bölüm Telegram'dan GELEN komutları yanıtlar. Komutlar
# yalnızca TELEGRAM_CHAT_ID'den kabul edilir (yetki kontrolü telegram_commands.py
# içinde). Yanıtlar getUpdates uzun yoklamasıyla ayrı bir thread'de toplanır.
KOMUT_YARDIM = """🤖 Formation-Bot komutları (DM)

/formasyonlar — günün canlı formasyonları (detaylı)
   diğer adlar: /formasyon · /liste
   filtre: /formasyonlar 1h   ·   /formasyonlar THYAO
/canli veya /c — canlı formasyonlar tek mesajda kompakt (kısayol)
/panel veya /p — 48 hisse x 4 zaman dilimi paneli + puanı en yüksek 12 aday
   diğer adlar: /genel · /tablo
   filtre: /panel 1h  ·  /panel THYAO  ·  /panel 1h THYAO  ·  /panel kirilim
/ozet veya /o — günlük özet tek mesajda (tamamlanan/retest/sıkışan)
   diğer ad: /gunluk
/sikisanlar veya /s — sadece sıkışması güçlenenler
   diğer adlar: /sikisan · /sıkışanlar · /sıkışan
/tamamlanan veya /t — sadece tamamlananlar (diğer ad: /tamam)
/retest veya /r — retest bekleyen/başarılı
/kirilim veya /k — kırılım adayı/teyitli (diğer ad: /kırılım)
/durum — bot, piyasa ve veri sağlığı özeti
/olcum — arşiv ölçümü referansı: karttaki ◇ satırlarının hangi tablodan,
   hangi n ile geldiği (diğer adlar: /ölçüm · /referans)
/karne [gün] — doğruluk karnesi: formasyon/kırılım sayıları + kırılım sonrası
   performans (varsayılan bu hafta; /karne 30 ile son 30 gün). Cuma gün sonu
   mesajının altında otomatik gelir. Veriler yerel dosyada (Supabase gerekmez).
   diğer ad: /karnem
/backtest [gün] [detay] — FAZ 3 tarihsel sonuç analizi (salt-okunur): kayıtlı
   outcome'ların tip/TF/kalite/bileşen kırılımı; /backtest 90 · /bt · "detay"
   bileşen + geometri + vaka bloklarını ekler. Hiçbir şey yazılmaz/değiştirilmez.
/tara [HISSE] — şimdi analiz et (seans dışı da çalışır)
/grafik HISSE [1s|2s|4s|1g] [sade|detay] — mum karesini gönder (diğer ad: /g)
   Örnek: /grafik THYAO 4s sade · mum/bant/kritik fiyatı öne çıkarır.
   TF yazılmazsa o sembolün 4 TF karesi denenir; kabul yanıtı hemen, görsel DM’e gelir.
   Veri mevcut bellek/cache katmanından; eksik/eski cache açık hatadır, canlı fetch yok.
   TELEGRAM_GRAFIK kapalıyken de çalışır; görseller alarm metin kotasını tüketmez.
/evet · /hayır — gece denetiminin önerisini onayla/reddet (diğer adlar:
   /onay · /kabul · /hayir · /red). Karar kayda geçer; bot kendiliğinden eşik,
   kart ya da etiket DEĞİŞTİRMEZ — uygulama elle yapılır. Öneri yalnız sapma
   varsa ya da ölçüm "bayrak kaldırılsın" derse DM'e düşer.
/yardim — bu liste (diğer adlar: /help · /start)

Notlar:
• Komutlar YALNIZCA kayıtlı DM sohbetinden (TELEGRAM_CHAT_ID) kabul edilir.
  Public grup/kanal hedefi (TELEGRAM_GROUP_ID) komut KABUL ETMEZ: orası yalnız
  yayın alır. Kanalda komut istiyorsan TELEGRAM_CHAT_ID'yi kanal/grup kimliği
  yapmalısın — o zaman kendi DM komutların susar (tek sohbet kilidi).
• Bu bir AL/SAT aracı değildir: formasyon durumu ve kalite skoru bildirir.
• /panel tüm evreni yeniden hesaplar; /tara [HISSE] istenen kapsamı yeniden analiz eder.
• Analiz bitince sonucu otomatik gönderir; çalışma sırasında gelen komutlar sessiz kalmaz:
  "⏳ Analiz sürüyor" mesajıyla yanıtlanır (kuyruğa alınmaz, aynı anda tek iş).
• Public hedefe (grup/kanal) giden yayın bu komutları ÇALIŞTIRMAZ; alarm/özet
  otomatik gider. Kanal mesajları Telegram'da `channel_post` türünde gelir ve bot
  yalnız `message` güncellemelerini dinler — yani kanalda komut yolu yoktur.
• Komutlar webhook (Render) ya da yoklama ile gelir; ikisi aynı anda açık olmaz.
  Bot ayrıca 15 dk'dan eski komutları çalıştırmaz ("bot uyanık değildi" mesajı gelir)."""


def _komut_yardim(_arguman: str) -> str:
    return _pkg.KOMUT_YARDIM


def _komut_olcum(_arguman: str) -> str:
    """Arşiv ölçümü referansı (karttaki `◇` satırlarının kaynağı).

    Okuma-yalnız ve durum bağımsız: piyasa kapalıyken de aynı metni verir.
    Hatasında komut sessiz kalmaz; kısa bir açıklama döner.
    """
    try:
        return ampirik.komut_metni()
    except Exception as exc:  # noqa: BLE001 - komut yanıtsız kalmasın
        _pkg.logger.warning("Ölçüm referansı üretilemedi: %s", exc)
        return "◇ Arşiv ölçümü şu an üretilemedi; ayrıntı logda."


def _ms_hata_kaydet(outputs, stock: str = "") -> None:
    """MS motoru bu turda hata verdiyse hisseyi sayaca yaz (istisna sızdırmaz)."""
    try:
        import notification_context as _nc
        if not _nc.market_yapisi_hatali(outputs):
            return
        _pkg._ms_hata_sayaci.setdefault("hisseler", set()).add(str(stock or "?").upper())
        for tf in ("1h", "2h", "4h", "1d"):
            sonuc = (outputs or {}).get(tf, {}).get("market_structure") if isinstance(outputs, dict) else None
            hata = sonuc.get("error") if isinstance(sonuc, dict) else None
            if hata:
                _pkg._ms_hata_sayaci["son"] = str(hata)[:60]
                break
    except Exception as exc:  # noqa: BLE001 - sayaç alarmı düşürmesin
        _pkg.logger.debug("MS hata sayacı yazılamadı: %s", exc)


def _ms_hata_satiri() -> str:
    """`/durum` için MS arıza satırı; hata yoksa boş (sessizlik)."""
    hisseler = _pkg._ms_hata_sayaci.get("hisseler") or set()
    adet = len(hisseler) if isinstance(hisseler, (set, list, tuple)) else int(hisseler or 0)
    if adet <= 0:
        return ""
    satir = f"⚠️ MS (piyasa yapısı) motoru: {adet} hissede hata"
    son = str(_pkg._ms_hata_sayaci.get("son") or "").strip()
    if son:
        satir += f" · son: {son}"
    # Kart etkilenmez: kart yalnız kendi alanlarını basar; bu satır teşhis içindir.
    return satir + " · alarm kartı etkilenmez"


def _komut_durum(_arguman: str) -> str:
    now = _pkg.datetime.now(ISTANBUL_TZ)
    st = _pkg._live_state.status()
    if _pkg.tarama_penceresi_acik_mi(now):
        piyasa = "AÇIK (tarama penceresi içinde)"
    else:
        try:
            kalan = time_until_next_open(now)
            piyasa = f"KAPALI · açılışa {_sayi(kalan / 3600, 1)} saat"
        except Exception:
            piyasa = "KAPALI"
    formations = _pkg._live_state.formations()
    en_iyi = formations[0] if formations else None
    status = st.get("son_tarama_durumu", "yok")
    requested = st.get("son_tarama_beklenen_hisse")
    processed = st.get("son_tarama_hissesi")
    if status == "basarisiz":
        requested = _pkg.last_run_stats.get("requested", st.get("son_is_hisse_istek"))
        processed = _pkg.last_run_stats.get("processed", st.get("son_is_hisse_basarili"))
    else:
        if requested is None:
            requested = _pkg.last_run_stats.get("requested")
        if processed is None:
            processed = _pkg.last_run_stats.get("processed")
    fresh = st.get("son_tarama_taze_veri")
    fetch_failures = st.get("son_tarama_fetch_hatasi")
    if status == "basarisiz":
        # Son başarılı taramanın sayaçlarını başarısız son denemeye mal etme.
        fresh = _pkg.last_run_stats.get("fresh_fetch")
        fetch_failures = _pkg.last_run_stats.get("fetch_failures")
    elif status == "yok":
        fresh = None
        fetch_failures = None
    else:
        if fresh is None:
            fresh = _pkg.last_run_stats.get("fresh_fetch")
        if fetch_failures is None:
            fetch_failures = _pkg.last_run_stats.get("fetch_failures")

    satirlar = [
        "🤖 Formation-Bot durum",
        f"Profil: {PROFILE} · Evren: {config.evren_ozeti(_pkg.ACTIVE_STOCKS)}",
        f"Piyasa: {piyasa}",
    ]
    if _pkg._scan_job_active.is_set() or st.get("tarama_suruyor"):
        satirlar.append("⏳ Analiz sürüyor; gelen komutlar iş bitene kadar kısa bir bilgi mesajıyla yanıtlanır.")
    elif status == "basarisiz":
        satirlar.append("⚠️ Son analiz başarısız; boş sonuç olarak yayımlanmadı.")
    elif status == "yok":
        satirlar.append("ℹ️ Bu oturumda henüz başarılı analiz yok; /panel ile başlat.")

    kapsam = (f"{processed if processed is not None else '—'}/"
              f"{requested if requested is not None else len(_pkg.ACTIVE_STOCKS)} sembol")
    sure = (st.get("son_is_suresi_dk") if status == "basarisiz"
            else st.get("son_tarama_suresi_dk"))
    sure_metni = "—" if sure is None else _sayi(sure, 1)
    satirlar += [
        f"Son başarılı analiz: {_gecen_sure(st.get('son_tarama_bitis'))} "
        f"(durum: {status}, kapsam: {kapsam}, süre: {sure_metni} dk)",
        f"Sonuçtaki formasyon: {len(formations)}" + (
            f" · en yüksek: {en_iyi['stock']} {en_iyi['timeframe']} "
            f"{en_iyi['pattern_name']} q{_sayi(en_iyi.get('quality'), 0)}" if en_iyi else ""),
        _veri_durumu_satiri(
            (_pkg.last_run_stats.get('data_asof') if status == "basarisiz" else
             st.get('son_tarama_veri_zamani') or _pkg.last_run_stats.get('data_asof')),
            fresh, requested, fetch_failures,
            (_pkg.last_run_stats.get("oldest_bar_age_minutes") if status == "basarisiz"
             else st.get("son_tarama_en_eski_veri_yasi_dk")),
        ),
        f"Günlük toplam: {_pkg.daily_stats['patterns_found']} formasyon kaydı, "
        f"{_pkg.daily_stats['alerts_sent']} alarm, {_pkg.daily_stats['errors']} hata",
    ]
    # --- ADAY HUNİSİ: "kaç aday üretildi, kaçı nereye gitti?" ---
    # Kullanıcı sorusu: "18 çıktı alıyoruz ama 3-5'inden bahsediyoruz". Bu satır
    # her adayın akıbetini tek bakışta gösterir; düşen aday sessiz kalmaz.
    huni = (f"🔎 Aday hunisi: {_pkg.daily_stats['patterns_found']} üretildi · "
            f"{_pkg.daily_stats['alerts_sent']} push · {_pkg.daily_stats['alerts_deferred']} digest · "
            f"{_pkg.daily_stats['alerts_state_disabled']} state dışı · "
            f"{_pkg.daily_stats['alerts_below_threshold']} eşik altı")
    if _pkg.daily_stats.get('alerts_digest_overflow'):
        huni += f" · {_pkg.daily_stats['alerts_digest_overflow']} digest taşması"
    if _pkg.daily_stats.get('alerts_kuyruk'):
        huni += f" · {_pkg.daily_stats['alerts_kuyruk']} kuyruğa alındı"
    if _pkg.daily_stats.get('alerts_bar_kapanmadi'):
        # Güvenlik kapısı: kapanmamış bar ile push denenmedi, sonraki tura bırakıldı.
        huni += f" · {_pkg.daily_stats['alerts_bar_kapanmadi']} kapanmamış bar (ertelendi)"
    if _pkg.daily_stats.get('alerts_break_close_invalid'):
        huni += f" · {_pkg.daily_stats['alerts_break_close_invalid']} kapanış teyidi yok"
    satirlar.append(huni)
    # P2 — arşiv sağlığı (gece ölçümünün dayandığı 4 tablo; P0_P1_P2 planı madde 3)
    try:
        arsiv = getattr(_pkg, "_son_arsiv_sagligi", None)
        olcum = getattr(_pkg, "_son_olcum_ozeti", None)
        tut = getattr(_pkg, "_son_tutarlilik_ozeti", None)
        if isinstance(arsiv, dict) and arsiv.get("sayilar"):
            say = arsiv["sayilar"]
            parcalar = []
            for k in ("f2_formations", "f2_events", "f2_outcome_links", "f2_snapshots"):
                v = say.get(k)
                parcalar.append(f"{k} {v if v is not None else '—'}")
            arsiv_satri = "🗄 Arşiv: " + " · ".join(parcalar)
            if arsiv.get("uyarilar"):
                arsiv_satri += " — " + "; ".join(arsiv["uyarilar"])[:120]
            satirlar.append(arsiv_satri)
        if isinstance(olcum, dict) and olcum.get("karar"):
            satirlar.append(f"🌙 Gece ölçümü ({olcum.get('gun','')}): {olcum.get('karar')} — {olcum.get('metin','')[:140]}")
        if isinstance(tut, dict) and tut.get("sapma") is not None:
            satirlar.append(f"🔬 Tutarlılık ({tut.get('gun','')}): {tut.get('sapma')} sapma / {tut.get('kontrol',0)} kontrol")
    except Exception:  # noqa: S110 - opsiyonel gece ölçümü/tutarlılık satırları; hata mesajı düşürmesin
        pass
    gosterim = None
    gosterim_public = None
    gosterim_grafik = None
    gonderim = getattr(_pkg._notifier_ref, "gonderim_durumu", None)
    if callable(gonderim):
        try:
            gd = gonderim()
            engel = gd.get("engeller") or {}
            gosterim = (f"🚧 Gönderim engeli: {engel.get('cooldown', 0)} cooldown · "
                        f"{engel.get('gunluk_kap', 0)} günlük kap · "
                        f"{engel.get('saatlik_kap', 0)} saatlik kap · "
                        f"{engel.get('tekrar', 0)} aynı-olay · "
                        f"{gd.get('hatalar', 0)} hata")
            if gd.get("public_enabled"):
                gosterim_public = (f"📣 Public grup: {gd.get('public_gonderilen', 0)} gönderim · "
                                   f"{gd.get('public_hatasi', 0)} hata · "
                                   f"kuyruk {gd.get('public_kuyruk', 0)} · "
                                   f"engel {gd.get('public_engel', 0)}")
                # Görsel ayrı satır: metin satırı zaten 300 px sınırında; kare
                # sayacı 0/0 olsa da yazılır (\"hiç görüntü gelmiyor\" teşhisi).
                if "public_grafik_gonderilen" in gd:
                    gosterim_public += (f"\n   🖼 public kare: "
                                        f"{gd.get('public_grafik_gonderilen', 0)} gönderildi · "
                                        f"{gd.get('public_grafik_hatasi', 0)} hata")
            # Görsel sayaçları (§4): metin kotasından AYRIDIR. Açık şalterde
            # sıfır sonuç da teşhis için görünür; kapalıyken yalnız eski/bugünkü
            # görsel etkinliği varsa satır kalır ve bunu başında belirtir.
            grafik_acik = bool(gd.get("grafik_acik", False))
            grafik_hareketi = any(gd.get(anahtar) for anahtar in (
                "grafik_olay", "grafik_olay_karesiz", "grafik_kopru_hata",
                "grafik_gonderilen", "grafik_kuyruk", "grafik_atlanan_hata",
                "grafik_atlanan_kota", "grafik_atlanan_baglam", "grafik_ort_ms",
            ))
            if grafik_acik or grafik_hareketi:
                grafik_satiri = (
                    ("🖼 Grafik karesi: " if grafik_acik else
                     "🖼 (şalter kapalı) Grafik karesi: ")
                    + f"{gd.get('grafik_olay', 0)} alarm kartı · "
                    + f"{gd.get('grafik_gonderilen', 0)} kare gönderildi · "
                    + f"{gd.get('grafik_atlanan_hata', 0)} hata · "
                    + f"kuyruk {gd.get('grafik_kuyruk', 0)} · "
                    + f"ort {gd.get('grafik_ort_ms', 0)} ms"
                )
                grafik_ekleri = []
                if gd.get("grafik_atlanan_kota"):
                    grafik_ekleri.append(
                        f"{gd['grafik_atlanan_kota']} adet sınırda kesildi")
                if gd.get("grafik_atlanan_baglam"):
                    grafik_ekleri.append(
                        f"{gd['grafik_atlanan_baglam']} bağlam güncellemesi")
                if gd.get("grafik_olay_karesiz"):
                    grafik_ekleri.append(
                        f"{gd['grafik_olay_karesiz']} karesiz "
                        "(tarama anında şalter kapalı ya da köprü atladı)")
                if gd.get("grafik_kopru_hata"):
                    kopru = f"köprü hatası {gd['grafik_kopru_hata']}"
                    son_neden = str(gd.get("grafik_son_neden") or "").strip()
                    if son_neden:
                        kopru += f" · son neden: {son_neden}"
                    grafik_ekleri.append(kopru)
                if grafik_ekleri:
                    grafik_satiri += " · " + " · ".join(grafik_ekleri)
                gosterim_grafik = grafik_satiri
        except Exception as exc:  # noqa: BLE001 - komut asla çökmesin
            _pkg.logger.debug(f"Gönderim durumu okunamadı: {exc}")
    if gosterim:
        satirlar.append(gosterim)
    if gosterim_public:
        satirlar.append(gosterim_public)
    if gosterim_grafik:
        satirlar.append(gosterim_grafik)
    # Notifier pasifse (token/chat_id yok) komut bunu açıkça söyler: aksi halde
    # kullanıcı "hiç mesaj gelmiyor ama bot çalışıyor" durumunu ayırt edemez.
    if _pkg._cift_ornek_durumu.get("uyari"):
        kimlikler = ", ".join(str(d.get("id")) for d in _pkg._cift_ornek_durumu.get("canli_digerleri") or [])
        satirlar.append(f"🚨 Çoklu örnek uyarısı: başka canlı kopya görünüyor ({kimlikler})")
    if getattr(_pkg._notifier_ref, "enabled", None) is False:
        satirlar.append("⚠️ Telegram PASİF: token/chat_id tanımlı değil, hiçbir bildirim gönderilmiyor.")
    if st.get("son_tarama_hatasi"):
        satirlar.append(f"⚠️ Son hata: {st['son_tarama_hatasi']}")
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    satirlar += ["", "Komutlar: /panel · /tara [HISSE] · /formasyonlar · /grafik [HISSE] · /durum · /yardim"]
    return "\n".join(satirlar)


def _sonuc_yok_mesaji(basarili_bos_mesaji: str, tamamlandi: bool = False) -> str:
    """İstenen filtrede sonuç yokken tarama kalitesini de doğru belirt."""
    st = _pkg._live_state.status()
    if not tamamlandi and (_pkg._scan_job_active.is_set() or st.get("tarama_suruyor")):
        return "⏳ Analiz sürüyor; tamamlanınca güncel sonuç gönderilecek."
    status = st.get("son_tarama_durumu", "yok")
    if status == "basarisiz":
        return ("⚠️ Son analiz başarısız veya eksik; bunu 'sonuç yok' olarak "
                "yorumlama. /durum ile kapsamı kontrol et.")
    if status == "tamamlandi":
        return basarili_bos_mesaji
    return "ℹ️ Henüz başarılı analiz yok. Güncel hesaplama için /panel yaz."


def _bos_analiz_mesaji(tamamlandi: bool = False) -> str:
    st = _pkg._live_state.status()
    beklenen = st.get("son_tarama_beklenen_hisse")
    if (st.get("son_tarama_durumu") == "tamamlandi" and beklenen is not None
            and 0 < int(beklenen) < len(_pkg.ACTIVE_STOCKS)):
        mesaj = f"ℹ️ Son başarılı analiz {beklenen} hisselik kısmi kapsamdaydı; bu kapsamda canlı formasyon bulunmadı."
    else:
        mesaj = "ℹ️ Son başarılı analiz tamamlandı; canlı formasyon bulunmadı."
    return _pkg._sonuc_yok_mesaji(mesaj, tamamlandi=tamamlandi)


def _onceki_sonuc_uyarisi() -> str:
    """Son deneme başarısızsa yayınlanan listeyi önceki başarılı çalışmaya bağla."""
    if _pkg._live_state.status().get("son_tarama_durumu") == "basarisiz":
        return "⚠️ Son analiz başarısız; aşağıdaki kayıtlar önceki başarılı analizdendir."
    return ""


def _kismi_kapsam_notu() -> str:
    """Hisse-özel taramadan sonra korunmuş eski evren kayıtlarını açıkça belirt."""
    st = _pkg._live_state.status()
    istek = st.get("son_tarama_beklenen_hisse")
    if (st.get("son_tarama_durumu") == "tamamlandi" and istek is not None
            and 0 < int(istek) < len(_pkg.ACTIVE_STOCKS)):
        islenen = st.get("son_tarama_hissesi") or istek
        return (f"ℹ️ Son başarılı analiz {islenen}/{istek} hisselik kısmi kapsamdı; "
                "diğer hisselerin kayıtları önceki başarılı analizden korunuyor.")
    return ""


def _komut_formasyonlar(arguman: str, tamamlandi: bool = False) -> str:
    st = _pkg._live_state.status()
    formations = _pkg._live_state.formations()
    filtre = (arguman or "").strip().lower()

    if filtre:
        if filtre in ("1h", "2h", "4h", "1d"):
            formations = [f for f in formations if str(f.get("timeframe")) == filtre]
        else:
            formations = [f for f in formations
                          if filtre in str(f.get("stock", "")).lower()
                          or filtre in str(f.get("pattern_name", "")).lower()]
        if not formations:
            durum_mesaji = _pkg._sonuc_yok_mesaji(
                f"🔍 '{arguman.strip()}' filtresine uyan canlı formasyon yok.",
                tamamlandi=tamamlandi,
            )
            return durum_mesaji + "\nFiltresiz liste için: /formasyonlar"

    baslik = [f"📊 CANLI FORMASYONLAR — {_pkg.datetime.now(ISTANBUL_TZ).strftime('%d.%m.%Y %H:%M')}"]
    if st.get("son_tarama_bitis"):
        baslik.append(f"Son başarılı tarama: {_gecen_sure(st['son_tarama_bitis'])}")
    if st.get("son_tarama_durumu") == "basarisiz":
        baslik.append("⚠️ Son deneme başarısız; gösterilen kayıt varsa önceki başarılı taramadandır.")
    if not formations:
        baslik.append("")
        baslik.append(_pkg._bos_analiz_mesaji(tamamlandi=tamamlandi))
        if st.get("son_tarama_durumu") == "tamamlandi":
            beklenen = st.get("son_tarama_beklenen_hisse")
            if beklenen is not None and 0 < int(beklenen) < len(_pkg.ACTIVE_STOCKS):
                baslik.append(
                    f"Yalnızca {beklenen} hisselik kısmi kapsam analiz edildi; "
                    "tam evrende formasyon olmadığı sonucu çıkarılamaz."
                )
            else:
                baslik.append(f"{config.evren_ozeti()} ve 4 zaman diliminde "
                              "uygun canlı formasyon bulunmadı.")
        else:
            baslik.append("Yeni tam tarama için /panel · tek hisse için /tara THYAO")
        return "\n".join(baslik)

    gosterilecek = formations[:15]
    satirlar = list(baslik)
    satirlar.append("")
    for i, f in enumerate(gosterilecek, 1):
        q = float(f.get("quality") or 0.0)
        yon = "⬆️ yukarı" if f.get("break_dir") == 1 else ("⬇️ aşağı" if f.get("break_dir") == -1 else "↔️ belirsiz")
        durum = STATE_TR.get(str(f.get("state")), str(f.get("state") or "—"))
        esik = f.get("min_quality")
        esik_notu = "" if esik is None else ("" if q >= float(esik) else f" (alarm eşiği {_sayi(esik, 0)} altında)")
        satirlar.append(f"{i}) {f.get('stock')} · {f.get('timeframe')} · {f.get('pattern_name')}")
        satirlar.append(f"   kalite {_sayi(q, 0)}{esik_notu} · {durum} · {yon}")
        satirlar.append(f"   üst {_sayi(f.get('upper'))} / alt {_sayi(f.get('lower'))}"
                        f" · kritik {_sayi(f.get('critical_price'))}")
    if len(formations) > len(gosterilecek):
        satirlar.append("")
        satirlar.append(f"… ve {len(formations) - len(gosterilecek)} tane daha "
                        f"(filtre: /formasyonlar 1h veya /formasyonlar THYAO)")
    satirlar.append("")
    taranan = st.get("son_tarama_hissesi")
    beklenen = st.get("son_tarama_beklenen_hisse")
    taranan_metni = "—" if taranan is None else str(taranan)
    if beklenen is not None:
        taranan_metni += f"/{beklenen}"
    satirlar.append(f"Toplam {len(formations)} canlı formasyon · son başarılı tarama {taranan_metni} hisse")
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    return "\n".join(satirlar)


def _komut_canli(arguman: str) -> str:
    """Kısayol: canlı hisselerde olan formasyonları tek mesajda kompakt at."""
    formations = _pkg._live_state.formations()
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}' filtresi)" if arguman else ""
        return (f"🔍 {_pkg._sonuc_yok_mesaji('Son başarılı analizde canlı formasyon yok.')}{filt}\n"
                "/formasyonlar ile detaylı listeye bak.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:20]
    saat = _pkg.datetime.now(ISTANBUL_TZ).strftime("%H:%M")
    filt_notu = f" [{arguman}]" if arguman else ""
    satirlar = [f"⚡ CANLI ({len(formations)}){filt_notu} - {saat} - tek mesaj"]
    onceki_uyari = _pkg._onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    for f in sirali:
        q = f.get("quality") or 0
        ok = _break_ok(f.get("break_dir"))
        # Yorum "TR map varsa kısa kullan" diyordu ama ham enum basılıyordu:
        # /canli çıktısında SIKISMA_GUCLENIYOR / KIRILIM_TEYITLI okunamıyordu.
        durum = _kisa_durum(f.get("state"))
        tf = _tf_kisa(f.get("timeframe"))
        satirlar.append(
            f"{f.get('stock')} {tf} {f.get('pattern_name')} q{float(q):.0f} {ok} {durum}"
        )
    if len(formations) > 20:
        satirlar.append(f"... ve {len(formations)-20} daha (/formasyonlar ile hepsi)")
    satirlar.append("")
    satirlar.append("💡 /ozet günlük özet, /s sıkışanlar, /r retest, /k kırılım")
    return "\n".join(satirlar)


def _komut_karne(arguman: str) -> str:
    """Haftalık doğruluk karnesi: /karne · /karne 30 (son 30 gün).

    Kaynak: yerel sinyal defteri (DATA_DIR/karne_defteri.json). Supabase gerekmez.
    Cuma gün sonu mesajının altına otomatik eklenir; bu komut istenildiği an verir.
    """
    arguman = (arguman or "").strip()
    gun_sayisi = None
    if arguman:
        try:
            gun_sayisi = max(1, min(365, int(arguman.split()[0])))
        except (TypeError, ValueError):
            return ("Kullanım: /karne · /karne 30\n"
                    "(sayı = kaç günlük karne; boş bırakılırsa bu hafta)")
    defter = _pkg._karne_al()
    if defter.boyut() == 0:
        return ("📊 Doğruluk karnesi boş: henüz kayıtlı sinyal yok.\n"
                "Defter tarama sırasında kendiliğinden dolar (yerel dosya; "
                "Supabase gerekmez). Cuma günü gün sonu mesajının altında otomatik gelir.")
    try:
        metin = karne_uret(defter, _pkg._karne_seri_saglayici(_pkg._deque_manager_ref),
                           gun_sayisi=gun_sayisi)
    except Exception as exc:  # noqa: BLE001 - komut asla çökmesin
        _pkg.logger.error("Karne üretilemedi: %s", exc, exc_info=True)
        return "⚠️ Karne üretilemedi; ayrıntı için bot loglarına bakın."
    # Kayıtlar/tarih bilgisi: kullanıcı karnenin kaynağını ve yaşını görsün.
    # NOT: "📁 Kayıt: /tmp/..." satırı kaldırıldı; dosya yolu iç işletim bilgisidir
    # ve komut çıktısı kopyalanıp paylaşıldığında dışarı sızıyordu.
    return metin


def _komut_backtest(arguman: str) -> str:
    """FAZ 3 Backtest V1 — salt-okunur tarihsel outcome raporu.

    Kullanım: /backtest · /backtest 30 · /backtest 90 detay.
    Yalnızca KAYITLI veriler okunur (Formation History + outcome link + Karne
    defteri); yeniden hesaplama yoktur, hiçbir yere yazılmaz, eşik/scoring/
    matematik değiştirilmez. Ağırlaştırılmış iş yükü istememek için tarama
    kilidiyle etkileşime girmez (yalnız dosya okur).
    """
    try:
        from analytics.backtest import komut as _bt_komut
        return _bt_komut(arguman or "", simdi=_pkg.datetime.now(ISTANBUL_TZ),
                         store=_pkg._supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - komut asla çökmesin
        _pkg.logger.error("Backtest üretilemedi: %s", exc, exc_info=True)
        return "⚠️ Backtest üretilemedi; ayrıntı için bot loglarına bakın."


def _komut_ozet(arguman: str) -> str:
    """Kısayol: günlük özet tek mesajda. Filtre destekler."""
    try:
        formations = _pkg._live_state.formations()
        formations = _filtrele_formasyonlar(formations, arguman)
        summary_payload = _pkg._daily_summary_payload()
        if not formations:
            # Restart'tan kalan snapshotı "bugünkü canlı sonuç" gibi sunma.
            # Güncel tam tarama yoksa mevcut summary formatı eski aday listesini
            # gizler ve son başarılı tam tarama zamanını açıkça gösterir.
            if not summary_payload.get("tam_tarama_guncel"):
                notifier = _pkg._notifier_ref
                if notifier and hasattr(notifier, "format_daily_summary"):
                    bos = notifier.format_daily_summary([], summary_payload)
                    if arguman.strip():
                        bos = (f"Filtre '{arguman.strip()}' için güncel tam tarama yok; "
                               "önceki sonuç kullanılmadı.\n" + bos)
                    return bos
            st = _pkg._live_state.status()
            if not arguman.strip():
                bos = _pkg._bos_analiz_mesaji()
            else:
                bos = _pkg._sonuc_yok_mesaji(
                    f"Son başarılı analizde '{arguman.strip()}' filtresine uyan aktif formasyon bulunmadı."
                )
            if st.get("son_tarama_veri_zamani"):
                bos += f"\nSon mum: {st['son_tarama_veri_zamani']}"
            return f"📊 BIST Formasyon Özeti — {_pkg.datetime.now(ISTANBUL_TZ).strftime('%d.%m %H:%M')}\n{bos}"
        notifier = _pkg._notifier_ref
        if notifier and hasattr(notifier, "format_daily_summary"):
            aktif = []
            for f in formations:
                aktif.append({
                    "stock_name": f.get("stock"),
                    "timeframe": f.get("timeframe"),
                    "pattern_name": f.get("pattern_name"),
                    "state": f.get("state"),
                    "confidence_score": f.get("quality"),
                    "contraction": f.get("contraction"),
                    "break_dir": f.get("break_dir", 0),
                })
            ozet = notifier.format_daily_summary(aktif, summary_payload)
            uyarilar = [x for x in (_pkg._onceki_sonuc_uyarisi(), _pkg._kismi_kapsam_notu()) if x]
            return "\n".join(uyarilar + [ozet]) if uyarilar else ozet
        if not formations:
            return "📊 Özet: " + _pkg._bos_analiz_mesaji()
        tamam = len([f for f in formations if f.get("state") == "FORMASYON_TAMAMLANDI"])
        retest = len([f for f in formations if str(f.get("state", "")).startswith("RETEST")])
        sikis = len([f for f in formations if f.get("state") == "SIKISMA_GUCLENIYOR"])
        kirilim = len([f for f in formations if str(f.get("state", "")).startswith("KIRILIM")])
        filt = f" [{arguman}]" if arguman else ""
        uyarilar = [x for x in (_pkg._onceki_sonuc_uyarisi(), _pkg._kismi_kapsam_notu()) if x]
        return (
            ("\n".join(uyarilar) + "\n" if uyarilar else "")
            + f"📊 Özet {_pkg.datetime.now(ISTANBUL_TZ).strftime('%H:%M')}{filt}\n"
            + f"Canlı: {len(formations)} | Tamamlanan: {tamam} | Retest: {retest} | Sıkışan: {sikis} | Kırılım: {kirilim}\n"
            + "/canli ile tek mesajda hepsi"
        )
    except Exception as e:
        return f"Özet alınamadı: {e}"


def _komut_sikisanlar(arguman: str) -> str:
    formations = [f for f in _pkg._live_state.formations() if f.get("state") == "SIKISMA_GUCLENIYOR"]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _pkg._sonuc_yok_mesaji(f"⚡ Son başarılı analizde yüksek sıkışma yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"⚡ SIKIŞANLAR ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _pkg._onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_tamamlanan(arguman: str) -> str:
    formations = [f for f in _pkg._live_state.formations() if f.get("state") == "FORMASYON_TAMAMLANDI"]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _pkg._sonuc_yok_mesaji(f"🏁 Son başarılı analizde tamamlanan yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🏁 TAMAMLANAN ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _pkg._onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_retest(arguman: str) -> str:
    formations = [
        f for f in _pkg._live_state.formations()
        if str(f.get("state", "")).startswith("RETEST")
    ]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _pkg._sonuc_yok_mesaji(f"🎯 Son başarılı analizde retest bekleyen/başarılı yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🎯 RETEST ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _pkg._onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} {f.get('state')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_kirilim(arguman: str) -> str:
    formations = [
        f for f in _pkg._live_state.formations()
        if str(f.get("state", "")).startswith("KIRILIM")
    ]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _pkg._sonuc_yok_mesaji(f"🚀 Son başarılı analizde kırılım adayı/teyitli yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🚀 KIRILIM ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _pkg._onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _pkg._kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    ms_hatasi = _pkg._ms_hata_satiri()
    if ms_hatasi:
        satirlar.append(ms_hatasi)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} {f.get('state')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _panel_raporu(arguman: str = "", tamamlandi: bool = False) -> str:
    """Panel metni (Batch 8 / 8.3): bağlam burada toplanır, üretim reporting'te.

    Global durumu okuyan tek yer burasıdır; metin üretimi saf fonksiyona taşındı.
    """
    return panel_raporu(
        arguman,
        durum=_pkg._live_state.status(),
        formations=_pkg._live_state.formations(),
        aktif_hisseler=list(_pkg.ACTIVE_STOCKS),
        tarama_suruyor=_pkg._scan_job_active.is_set(),
        last_run_stats=_pkg.last_run_stats,
        tamamlandi=tamamlandi,
        kapsam_notu=_pkg._kismi_kapsam_notu(),
        bos_analiz_mesaji=_pkg._bos_analiz_mesaji(tamamlandi=tamamlandi),
        daily_stats=getattr(_pkg, "daily_stats", None),
    )


def _manuel_tarama_istegi(tip: str, arguman: str = "") -> str:
    """Analizi ana döngüye kuyruğa koy; Telegram işleyicisini bloklama."""
    global _scan_job_request
    with _pkg._scan_request_lock:
        if _pkg._scan_job_active.is_set():
            # Normalde listener busy guard bunu kullanıcıya ulaşmadan yutar.
            return ""
        hisseler = list(_pkg.ACTIVE_STOCKS)
        if tip == "tara" and arguman.strip():
            tokenlar = [t.strip().upper() for t in arguman.replace(",", " ").split()]
            hisse_tokenlari = [t for t in tokenlar if t not in PANEL_TIMEFRAMES]
            if hisse_tokenlari:
                secilen = [s for s in _pkg.ACTIVE_STOCKS
                           if any(t == s or (len(t) >= 3 and t in s) for t in hisse_tokenlari)]
                if not secilen:
                    return (f"🔍 '{arguman.strip()}' için hisse bulunamadı. "
                            "Örnek: /tara THYAO")
                hisseler = list(dict.fromkeys(secilen))
        setattr(_pkg, "_scan_job_request", {
            "tip": tip,
            "arguman": arguman.strip(),
            "hisseler": hisseler,
            "istek_zamani": _pkg.datetime.now(ISTANBUL_TZ).isoformat(),
        })
        _pkg._scan_job_active.set()
        _pkg._scan_istegi.set()
    _pkg.logger.info("Telegram /%s analizi kuyruğa alındı (hisse=%s)",
                tip, ",".join(hisseler))
    kapsam = f"{config.evren_ozeti(hisseler)} × 4 zaman dilimi"
    return f"🔍 Analiz başladı: {kapsam}. Bittiğinde sonucu bu sohbete göndereceğim."


def _komut_panel(arguman: str) -> str:
    """Yeni bir tam evren analizi başlatır; filtreler yalnızca sonuç görünümüne uygulanır."""
    return _pkg._manuel_tarama_istegi("panel", arguman)


def _komut_grafik(arguman: str) -> str:
    """`/grafik [HISSE] [TF] [sade|detay]` — kare(ler) üretir (G4 / §4).

    Neden ayrı komut: alarm kareleri yalnız `TELEGRAM_GRAFIK=alarm` iken gidiyor;
    kullanıcı istediği zaman bakabilsin diye kapıdan bağımsız bir yüzey lazım.
    `sade`, mum/bant/kritik fiyat hiyerarşisini öne çıkarır; `detay` bütün
    domain işaretlerini gösterir. Kabul cevabından sonra sınırlı arka plan işi
    çalışır. Veri mevcut bellek/cache katmanından okunur; canlı çekme yok.
    """
    parcalar = (arguman or "").split()
    if not parcalar:
        return ("Kullanım: /grafik HISSE [1s|2s|4s|1g] [sade|detay] [odak|baglam] [mobil]\n"
                "Örnek: /grafik THYAO 4s sade. TF yazılmazsa 4 TF karesi denenir.")
    if len(parcalar) > 5:
        return "Kullanım: /grafik THYAO [1s|2s|4s|1g] [sade|detay] [odak|baglam] [mobil]"
    hisse = parcalar[0].strip().upper()
    eslesme = _pkg._GRAFIK_SEMBOL.match(hisse)
    if not eslesme:
        return "Geçersiz sembol yazımı. Örnek: /grafik THYAO 4s sade"
    hisse = eslesme.group(1)

    tf = None
    sade = None
    bolge_gorunumu = None
    mobil = False
    for secim in parcalar[1:]:
        secim = secim.strip().lower()
        if secim in {"odak", "baglam", "bağlam"}:
            if bolge_gorunumu is not None:
                return "Bölge görünümü yalnız bir kez seçilebilir: odak veya baglam."
            bolge_gorunumu = "odak" if secim == "odak" else "baglam"
            continue
        if secim == "mobil":
            if mobil:
                return "Mobil görünüm yalnız bir kez seçilebilir."
            mobil = True
            continue
        if secim in _pkg._GRAFIK_GORUNUM:
            if sade is not None:
                return "Görünüm yalnız bir kez seçilebilir: sade veya detay."
            sade = _pkg._GRAFIK_GORUNUM[secim]
            continue
        if secim in _pkg._GRAFIK_TF:
            if tf is not None:
                return "Yalnızca bir zaman dilimi seçin: 1s · 2s · 4s · 1g."
            tf = _pkg._GRAFIK_TF[secim]
            continue
        return f"Zaman dilimi tanınmadı: {secim} (1s · 2s · 4s · 1g; görünüm sade|detay)"
    tfler = (tf,) if tf else ("1h", "2h", "4h", "1d")

    notifier = _pkg._notifier_ref
    if notifier is None or not getattr(notifier, "enabled", False):
        return "Telegram gönderimi kapalı: kare üretilemiyor."
    # Tek aktif manuel grafik işi: çakışan TF'ler ve sınırsız thread/kuyruk yok.
    with _pkg._grafik_is_kilidi:
        if _pkg._grafik_aktif_is:
            cakisma = _pkg._grafik_aktif_is["hisse"] == hisse and bool(
                set(tfler) & set(_pkg._grafik_aktif_is["tfler"]))
            return ("⏳ Aynı sembol/TF grafik isteği zaten hazırlanıyor." if cakisma else
                    "⏳ Başka grafik isteği hazırlanıyor; bitince yeniden deneyin.")
        istek = {"hisse": hisse, "tfler": tfler, "sade": sade,
                 "gorunum": bolge_gorunumu, "mobil": mobil,
                 "asama": "kabul yanıtı bekleniyor"}
        _pkg._grafik_aktif_is.update(istek)

    def baslat():
        try:
            threading.Thread(target=_pkg._grafik_isi_calistir,
                             args=(istek, notifier, _pkg._deque_manager_ref),
                             name="grafik-istegi", daemon=True).start()
        except Exception:
            with _pkg._grafik_is_kilidi:
                _pkg._grafik_aktif_is.clear()
            raise

    gorunum = (f" · {'sade' if sade else 'detay'} görünüm" if sade is not None else "")
    gorunum += (" · " + bolge_gorunumu if bolge_gorunumu else "") + (" · mobil" if mobil else "")
    return ArkaPlanYaniti(
        f"⏳ Grafik isteği alındı, hazırlanıyor: {hisse} · "
        + "/".join(_tf_kisa(tf) for tf in tfler) + gorunum
        + ". Hedef yaklaşık 1 dakika; sonuç ve görsel DM'e gelecek.", baslat)


def _grafik_isi_calistir(istek, notifier, yonetici):
    # Import/bağımlılık/timer kurulumu bile başarısız olsa rezervasyon bırakılmaz.
    try:
        _pkg._grafik_isi_yurut(istek, notifier, yonetici)
    except (Exception, SystemExit) as hata:
        _pkg.logger.warning("/grafik iş kurulumu başarısız: %s", type(hata).__name__)
        try:
            notifier.send_text(f"❌ Grafik isteği tamamlanamadı: {istek['hisse']} · "
                               f"iş kurulumu/bağımlılık: {type(hata).__name__}")
        except Exception:  # noqa: BLE001, S110 - en iyi çaba bildirim; asıl hata yukarıda loglandı
            pass
    finally:
        with _pkg._grafik_is_kilidi:
            _pkg._grafik_aktif_is.clear()


def _grafik_isi_yurut(istek, notifier, yonetici):
    """Yalnız seçilen sembol/TF; mevcut cache, kopya frame, DM teslimi.

    Sağlayıcı fetch'i burada yok: tarama pacer'ı süreç-geneli değil, yeni bir
    pacer eşzamanlı rate-limit güvenliği sağlamaz. Eksik/eski veri açık hatadır.
    """
    import grafik
    import grafik_uret
    from secrets_redaction import redact_sensitive_text

    baslangic = time.monotonic()
    tamam = threading.Event()
    bildirim_kilidi = threading.Lock()
    asama = {"ad": "cache yükleme"}
    ozetler = []
    basarili = 0

    def durum(ad):
        asama["ad"] = ad
        _pkg.logger.info("/grafik %s aşama: %s", istek["hisse"], ad)

    def bildir(metin):
        try:
            ok, neden = notifier.send_text(metin)
            if not ok:
                _pkg.logger.warning("/grafik durum teslimi başarısız: %s",
                               redact_sensitive_text(str(neden), getattr(notifier, "token", ""))[:160])
        except Exception as hata:
            _pkg.logger.warning("/grafik durum teslimi başarısız: %s", type(hata).__name__)

    def gecikme():
        with bildirim_kilidi:
            if not tamam.is_set():
                bildir(f"⏳ {istek['hisse']}: 1 dakika hedefi aşıldı; "
                       f"henüz bitmedi. Aşama: {asama['ad']}. Sonuç ayrıca bildirilecek.")

    zamanlayici = threading.Timer(_pkg._GRAFIK_HEDEF_SN, gecikme)
    zamanlayici.daemon = True
    zamanlayici.start()
    paketler = []        # (tf, yol, caption): kareler TEK albümde gider (metin araya girmez)
    ozetler = []         # üretilemeyen kareler: albüm başlığına eklenir / yalnız hiç kare yoksa metin
    try:
        for tf in istek["tfler"]:
            hedef = grafik.kare_yolu(istek["hisse"], tf)
            yol = None
            try:
                def tazelik(frame, kaynak):
                    now = _pkg.datetime.now(ISTANBUL_TZ)
                    kapanis = mum_kapanis_ani(frame.index[-1], tf)
                    yas = (now - kapanis).total_seconds() / 60.0
                    if not _pkg._cache_verisi_kullanilabilir(
                            yas, False, _pkg.tarama_penceresi_acik_mi(now)):
                        raise grafik_uret.VeriYok(
                            f"cache eski: son kapanmış mum {frame.index[-1].isoformat()} "
                            f"(kapanış yaşı {yas:.0f} dk). Kaynak: {kaynak}. "
                            "Güvenli bağımsız fetch yok; botun veri yüklemesini kontrol edin.")

                sonuc = grafik_uret.kare_uret(
                    istek["hisse"], tf, zone=True, formasyon_tara=True, yonetici=yonetici,
                    veri_dizin=yonetici.data_dir if yonetici is not None else None,
                    sade=istek.get("sade"), gorunum=istek.get("gorunum"),
                    mobil=istek.get("mobil", False),
                    cikti=hedef, asama=lambda ad: durum(f"{_tf_kisa(tf)}: {ad}"),
                    tazelik_kontrol=tazelik)
                yol, meta = sonuc.get("yol"), sonuc.get("meta") or {}
                if not yol:
                    neden = sonuc.get("hata") or " · ".join(meta.get("uyarilar") or []) or "çizim reddi"
                    ozetler.append(f"{_tf_kisa(tf)} ✗ {neden}")
                    continue
                paketler.append((tf, yol, _pkg._kare_altyazisi(istek["hisse"], tf, meta)))
            except (Exception, SystemExit) as hata:
                ozetler.append(f"{_tf_kisa(tf)} ✗ aşama {asama['ad']}: {type(hata).__name__}")
                _pkg.logger.warning("/grafik iş hatası (%s %s): %s", istek["hisse"], tf,
                               type(hata).__name__)
            finally:
                if yol is None:
                    # Yalnız üretilemeyen kare: yazılmış kısmi PNG varsa temizlenir.
                    try:
                        os.remove(hedef)
                    except OSError:
                        pass
        basarili = 0
        if paketler:
            if ozetler:
                # Üretilemeyen TF'ler albümün ilk karesinin altına tek satır olarak yazılır.
                paketler[0] = (paketler[0][0], paketler[0][1],
                               paketler[0][2] + "\n⚠ " + " · ".join(ozetler))
            durum(f"albüm: {len(paketler)} kare")
            # `grafik_toplu_gonder` dosyaları kendisi siler (albüm de tek tek de).
            try:
                sonuc_ok = notifier.grafik_toplu_gonder([(y, c) for _t, y, c in paketler])
            except Exception as hata:  # noqa: BLE001 - görsel süreci düşürmesin
                _pkg.logger.warning("/grafik albüm gönderimi istisna: %s", type(hata).__name__)
                sonuc_ok = [False] * len(paketler)
                for _t, y, _c in paketler:
                    try:
                        os.remove(y)
                    except OSError:
                        pass
            basarili = sum(1 for ok in sonuc_ok if ok)
            if basarili < len(paketler):
                ozetler.extend(f"{_tf_kisa(t)} ✗ sendPhoto" for (t, _y, _c), ok
                               in zip(paketler, sonuc_ok) if not ok)
        with bildirim_kilidi:
            tamam.set()
            if not paketler or basarili == 0:
                bildir(redact_sensitive_text(
                    f"❌ Grafik isteği tamamlanamadı: {istek['hisse']} · "
                    f"{time.monotonic() - baslangic:.1f} sn\n" + "\n".join(ozetler),
                    getattr(notifier, "token", "")))
            elif basarili < len(paketler):
                bildir(redact_sensitive_text(
                    f"⚠️ Grafik isteği kısmen tamamlandı: {istek['hisse']} · "
                    f"{time.monotonic() - baslangic:.1f} sn\n" + "\n".join(ozetler),
                    getattr(notifier, "token", "")))
            else:
                # Albümün kendisi görsel; hangi hisse/TF olduğunu söyleyen tek
                # metin mesajı ayrıca gider (2026-10-23 kullanıcı isteği).
                bildir(redact_sensitive_text(
                    _pkg._grafik_ozet_metni(istek["hisse"], istek["tfler"], basarili,
                                       time.monotonic() - baslangic, istek),
                    getattr(notifier, "token", "")))
            _pkg.logger.info("/grafik %s bitti: %d/%d kare, %.1f sn", istek["hisse"], basarili,
                        len(istek["tfler"]), time.monotonic() - baslangic)
    finally:
        zamanlayici.cancel()
        with bildirim_kilidi:
            tamam.set()


def _grafik_ozet_metni(hisse: str, tfler, adet: int, sure: float,
                       istek: dict) -> str:
    """`/grafik` başarı metni: hisse EN BAŞTA, seçimler arkada (2026-10-23).

    Kullanıcı: "grafik çağırınca hisse metninde gelsin, düzenli şekilde".
    Albüm tek başına yanıttı ve hangi hisseye ait olduğunu söyleyen metin
    yoktu. Metin iki satırdır ve satır başına 283 px bütçesine sığar; sığmayan
    süs (görünüm seçimleri, süre) sırayla düşer — hisse ve TF listesi kalır.
    """
    import telegram_measure as _tm
    modlar = []
    if istek.get("sade") is True:
        modlar.append("sade")
    elif istek.get("sade") is False:
        modlar.append("detay")
    if istek.get("gorunum"):
        modlar.append(str(istek["gorunum"]))
    if istek.get("mobil"):
        modlar.append("mobil")
    tf_listesi = [_tf_kisa(t) for t in tfler]
    sure_metni = f"{sure:.1f} sn".replace(".", ",")
    adaylar = [
        " · ".join(tf_listesi + [f"{adet} kare", sure_metni] + modlar),
        " · ".join(tf_listesi + [f"{adet} kare"] + modlar),
        " · ".join(tf_listesi + modlar),
        " · ".join(tf_listesi),
    ]
    ikinci = adaylar[-1]
    for aday in adaylar:
        if _tm.genislik(aday) <= _tm.SATIR_BUTCE:
            ikinci = aday
            break
    return f"📈 {hisse} · grafik hazır\n{ikinci}"


def _kare_altyazisi(hisse: str, tf: str, meta: dict) -> str:
    """Albüm öğesinin altyazısı: `HİSSE · 1s · 180 mum · formasyon/yok · son kapanan …`."""
    ts = str(meta.get("son_bar_ts") or "")
    try:
        ts = _pkg.datetime.fromisoformat(ts).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        pass
    mum = meta.get("mum_sayisi")
    parcalar = [hisse, _tf_kisa(tf)]
    mod = meta.get("mod")
    if isinstance(mod, dict) and mod.get("sade"):
        parcalar.append("sade")
    try:
        lejant_gizli = max(0, int(meta.get("lejant_atlanan") or 0))
    except (TypeError, ValueError, OverflowError):
        lejant_gizli = 0
    if lejant_gizli:
        parcalar.append(f"lejant kısaltıldı (+{lejant_gizli})")
    if mum:
        parcalar.append(f"{mum} mum")
    if meta.get("formasyon_ad"):
        import grafik as _grafik_etiket
        durum = _grafik_etiket.formasyon_durum_etiketi(meta.get("formasyon_durum"))
        parcalar.append(f"{meta['formasyon_ad']} ({durum})" if durum
                        else str(meta["formasyon_ad"]))
    else:
        parcalar.append("formasyon yok")
    if ts:
        parcalar.append(f"son kapanan {ts}")
    return " · ".join(parcalar)


def _komut_tara(arguman: str) -> str:
    """İstenen hisseyi (yoksa evreni) seans saatinden bağımsız analiz eder."""
    return _pkg._manuel_tarama_istegi("tara", arguman)


def _manuel_tarama_tamamla(request: dict, result: dict, notifier) -> None:
    """Manuel iş tamamlanınca başlatan isteğe tek final mesajı gönder."""
    global _scan_job_request
    try:
        if result.get("status") != "tamamlandi":
            mesaj = (
                "⚠️ Analiz tamamlanamadı; boş sonuç olarak kaydetmedim.\n"
                f"Başarıyla hesaplanan: {result.get('processed', 0)}/"
                f"{result.get('requested', 0)} hisse · hata/atlanan: "
                f"{result.get('failed', 0)}.\n"
                f"{_veri_durumu_satiri(result.get('data_asof'), result.get('fresh_fetch'), result.get('requested'), result.get('fetch_failures'), result.get('oldest_bar_age_minutes'))}\n"
                "Ayrıntı için bot logundaki ilk 'tarama hatası' kaydına bakın."
            )
        elif request.get("tip") == "panel":
            mesaj = _pkg._panel_raporu(request.get("arguman", ""), tamamlandi=True)
        else:
            filt = request.get("arguman", "")
            mesaj = _pkg._komut_formasyonlar(filt, tamamlandi=True)
            mesaj = (f"✅ Tarama tamamlandı: {result.get('processed', 0)}/"
                     f"{result.get('requested', 0)} hisse.\n"
                     f"{_veri_durumu_satiri(result.get('data_asof'), result.get('fresh_fetch'), result.get('requested'), result.get('fetch_failures'), result.get('oldest_bar_age_minutes'))}\n"
                     + mesaj)
        if notifier is not None:
            notifier.send_text(mesaj)
    except Exception as exc:
        _pkg.logger.error("Manuel analiz sonucu Telegram'a gönderilemedi: %s", exc, exc_info=True)
    finally:
        with _pkg._scan_request_lock:
            setattr(_pkg, "_scan_job_request", None)
            _pkg._scan_job_active.clear()


def _komut_oneri_cevabi(cevap: str) -> str:
    """`/evet` · `/hayır`: gece önerisinin kararını yazar (eşik DEĞİŞMEZ)."""
    try:
        import oneri
        return oneri.cevapla(cevap, store=_pkg._supabase_store_ref)
    except Exception as exc:  # noqa: BLE001 - komut sessiz kalmamalı
        _pkg.logger.warning("Gece önerisi yanıtlanamadı: %s", exc)
        return "Gece önerisi kaydı okunamadı; karar yazılmadı. Birkaç dakika sonra yeniden deneyin."


def _komut_evet(_arguman: str) -> str:
    """Gece önerisini kabul et — kayda geçer, kod kendiliğinden değişmez."""
    return _pkg._komut_oneri_cevabi("evet")


def _komut_hayir(_arguman: str) -> str:
    """Gece önerisini reddet — ölçüm sürer, aynı öneri bir süre tekrar sorulmaz."""
    return _pkg._komut_oneri_cevabi("hayır")


TELEGRAM_KOMUTLARI = {
    "start": _komut_yardim,
    "yardim": _komut_yardim,
    "help": _komut_yardim,
    "durum": _komut_durum,
    "formasyonlar": _komut_formasyonlar,
    "formasyon": _komut_formasyonlar,
    "liste": _komut_formasyonlar,
    "tara": _komut_tara,
    "canli": _komut_canli,
    "c": _komut_canli,
    "ozet": _komut_ozet,
    "o": _komut_ozet,
    "gunluk": _komut_ozet,
    "sikisanlar": _komut_sikisanlar,
    "sikisan": _komut_sikisanlar,
    "sıkışanlar": _komut_sikisanlar,
    "sıkışan": _komut_sikisanlar,
    "s": _komut_sikisanlar,
    "tamamlanan": _komut_tamamlanan,
    "tamam": _komut_tamamlanan,
    "t": _komut_tamamlanan,
    "retest": _komut_retest,
    "r": _komut_retest,
    "kirilim": _komut_kirilim,
    "kırılım": _komut_kirilim,
    "k": _komut_kirilim,
    "olcum": _komut_olcum,
    "ölçüm": _komut_olcum,
    "referans": _komut_olcum,
    "karne": _komut_karne,
    "karnem": _komut_karne,
    "backtest": _komut_backtest,
    "bt": _komut_backtest,
    "panel": _komut_panel,
    "p": _komut_panel,
    "grafik": _komut_grafik,
    "g": _komut_grafik,
    "genel": _komut_panel,
    "tablo": _komut_panel,
    # Gece önerisi kararı (§15): onay/red KAYDA geçer, eşik değişmez.
    "evet": _komut_evet,
    "onay": _komut_evet,
    "kabul": _komut_evet,
    "hayir": _komut_hayir,
    "hayır": _komut_hayir,
    "red": _komut_hayir,
}


def _telegram_webhook_secret_ayikla(secret=None) -> str:
    # config değeri ÇAĞRI ANINDA okunur: testlerdeki monkeypatch(main, ...) etkili olur.
    return _transport_telegram.webhook_secret_ayikla(secret, varsayilan=_pkg.TELEGRAM_WEBHOOK_SECRET)


def _telegram_token_al(token=None) -> str:
    return _transport_telegram.token_al(token, notifier=_pkg._notifier_ref)


def _telegram_webhook_url_olustur(secret=None, webhook_url=None, render_url=None) -> str:
    return _transport_telegram.webhook_url_olustur(
        secret=secret, webhook_url=webhook_url, render_url=render_url,
        varsayilan_secret=_pkg.TELEGRAM_WEBHOOK_SECRET,
        varsayilan_url=TELEGRAM_WEBHOOK_URL,
        varsayilan_render=_pkg.RENDER_EXTERNAL_URL)


def _telegram_set_webhook(url=None, secret=None, token=None) -> bool:
    return _transport_telegram.set_webhook(
        url=url, secret=secret, token=token,
        api=_pkg._telegram_api_cagri, yanit_oku_fn=_pkg._telegram_yanit_oku,
        secret_ayikla_fn=_pkg._telegram_webhook_secret_ayikla, token_al_fn=_pkg._telegram_token_al,
        adres_olustur_fn=_pkg._telegram_webhook_url_olustur, gizle_fn=_pkg._webhook_adres_gizle,
    )


def _telegram_delete_webhook(token=None) -> bool:
    return _transport_telegram.delete_webhook(
        token=token, api=_pkg._telegram_api_cagri, yanit_oku_fn=_pkg._telegram_yanit_oku,
        token_al_fn=_pkg._telegram_token_al,
    )


def _telegram_komut_katmanini_kur(notifier, isleyici=None) -> str:
    """Komut katmanını AYNI ANDA TEK modda kurar: 'webhook', 'yoklama' veya 'kapali'.

    - **webhook**: secret + taban adres var, HTTP sunucusu ayakta ve setWebhook
      başarılı. Güncellemeler `/webhook/<secret>` ucundan gelir; yoklama thread'i
      AÇILMAZ (aynı token'da getUpdates 409 alır).
    - **yoklama**: eski davranış (getUpdates daemon thread). Webhook kapalıyken ya da
      setWebhook başarısız olduğunda komutlar tamamen susmasın diye buraya düşülür;
      önce eski webhook kaydı silinir (yoksa 409).
    - **kapali**: token/chat_id yok - bot yalnızca alarm gönderir.

    `isleyici` yalnızca testler için verilir (ağa çıkmayan sahte dinleyici).
    """
    global _telegram_listener_ref, _telegram_update_processor_ref, _komut_modu
    sonuc = _transport_telegram.komut_katmanini_kur(
        notifier, isleyici,
        komutlar=_pkg.TELEGRAM_KOMUTLARI, yardim_metni=_pkg.KOMUT_YARDIM,
        tarama_suruyor=lambda: _pkg._scan_job_active.is_set(),
        health_server_var=_pkg._health_server_ref is not None,
        listener_factory=TelegramCommandListener,
        adres_olustur=_pkg._telegram_webhook_url_olustur,
        gizle=_pkg._webhook_adres_gizle,
        secret_ayikla=_pkg._telegram_webhook_secret_ayikla,
        set_webhook_fn=_pkg._telegram_set_webhook,
        delete_webhook_fn=_pkg._telegram_delete_webhook,
    )
    setattr(_pkg, "_komut_modu", sonuc["mod"])
    if sonuc["mod"] == "webhook":
        setattr(_pkg, "_telegram_update_processor_ref", sonuc["processor"])
    elif sonuc["mod"] == "yoklama":
        setattr(_pkg, "_telegram_listener_ref", sonuc["listener"])
    return sonuc["mod"]


def _telegram_webhook_isle(guncelleme):
    """health_server'ın /webhook ucundan gelen güncellemeyi işler (thread-safe).

    Dönen değer HTTP kodudur:
      200 → işlendi (cevap sendMessage ile gitti),
      503 → bot henüz komutları kurmadı (Telegram tekrar dener),
      500 → işleyici hatası (Telegram tekrar dener, güncelleme kaybolmaz).
    """
    isleyici = _pkg._telegram_update_processor_ref
    if isleyici is None:
        return 503
    with _pkg._telegram_webhook_kilidi:
        try:
            isleyici.handle_update(guncelleme)
        except Exception as exc:  # noqa: BLE001 - tek güncelleme sunucuyu düşürmesin
            _pkg.logger.error(f"Webhook guncellemesi islenemedi: {exc}", exc_info=True)
            return 500
    return 200


def _istek_tam_evrende_tamamlandi(result: dict, evren_boyutu: int = None) -> bool:
    """Başarılı tam manuel analiz, aynı kapanış için otomatik taramayı karşılar."""
    toplam = len(_pkg.ACTIVE_STOCKS) if evren_boyutu is None else int(evren_boyutu)
    return bool(
        (result or {}).get("status") == "tamamlandi"
        and (result or {}).get("requested") == toplam
    )


def _calistir_istek_taramasi(deque_manager, lifecycle_manager, notifier) -> bool:
    """Kuyruktaki kullanıcı isteğini seans saatinden bağımsız çalıştır."""
    with _pkg._scan_request_lock:
        request = _pkg._scan_job_request
        _pkg._scan_istegi.clear()
    if not request:
        _pkg._scan_job_active.clear()
        return False
    try:
        result = _pkg.scan_all_stocks(
            deque_manager,
            lifecycle_manager,
            notifier,
            manuel=True,
            stocks=request.get("hisseler"),
            send_alerts=False,
        )
    except Exception as exc:
        _pkg.logger.error("İstenen analiz çalışırken hata verdi: %s", exc, exc_info=True)
        result = _pkg._analiz_hatasi_kaydi(exc, len(request.get("hisseler") or []), "istenen analiz")
    _pkg._manuel_tarama_tamamla(request, result or {}, notifier)
    return True


def _bekle_veya_tarama(seconds: float) -> bool:
    """Belirtilen süre bekler; /tara isteği gelirse erken döner (True).

    Neden: ana döngü 5 dakikaya kadar uyuyor. Elle tarama isteği geldiğinde
    uykuyu beklemek yerine hemen taramaya geçilir (komut 5 dk askıda kalmasın).
    """
    bitis = time.monotonic() + seconds
    while not _pkg._shutdown_requested:
        kalan = bitis - time.monotonic()
        if kalan <= 0:
            return False
        if _pkg._scan_istegi.wait(min(kalan, 1.0)):
            return True
    return False


