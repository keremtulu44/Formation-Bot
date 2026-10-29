# notifier/format_kart.py — alarm kartı biçimlendirme (Faz 1).
# `DEVLAMLILIK_AKTIF` / `TELEGRAM_ALERT_STYLE` / `TELEGRAM_KART_SUZGEC`
# yamalanabilir yüzey olduğu için `_pkg` üzerinden ÇAĞRI ANINDA okunur
# (plan §3 geç bağlama kuralı); testler `notifier.X`'i yamalamaya devam eder.

import logging
import notifier as _pkg  # yamalı adlar için geç bağlama (plan §3)

import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import (ACTIVE_STOCKS, DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT,
                    TELEGRAM_MAX_MESAJ_GUN,
                    TELEGRAM_ALERT_STYLE, TELEGRAM_ALERT_MAX_KARAKTER, TELEGRAM_SATIR_PX,
                    TELEGRAM_KART_SUZGEC,
                    TELEGRAM_DM_DEGISIM_KAPISI, TELEGRAM_KANAL_GECERSIZ_KAPISI,
                    ACIL_KUYRUK_LIMIT, ACIL_KUYRUK_TTL_DK, ALERT_STATES, WATCH_STATES,
                    TERMINAL_TAZE_BAR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL,
                    PUBLIC_MAX_MESAJ_SAAT, PUBLIC_MAX_MESAJ_GUN, PUBLIC_MIN_ARALIK_SN,
                    PUBLIC_MIN_QUALITY_TF, PUBLIC_MIN_DEVLAMLILIK, DM_MIN_DEVLAMLILIK,
                    DEVLAMLILIK_AKTIF)
# Telefon satır bütçesi ölçeri (bağımlılıksız, PIL yok). Eski "satır ≤ 70 karakter"
# kuralı Türkçe/rakam genişliklerini hesaba katmadığı için 25 Eyl akışında 120
# satır telefonda sarmalanmıştı; artık piksel bütçesi kullanılıyor.
from telegram_measure import (SATIR_BUTCE, bol as _satir_bol,
                              genislik, genislik as _satir_px, metni_sigdir)
# Watch adaylarının state'ini Türkçe basmak için TEK KAYNAK sözlük (reporting
# katmanı da aynısını kullanır; böylece alarm mesajı ile /panel aynı dili konuşur).
from reporting.format import STATE_TR, sayi as _format_sayi
# Devamlılık puanı ARTIK KARTTA YOK (§11–§12): 0–100 puan tek bayraktan iyi
# çıkmadı, ondan türeyen "yüksek/normal/zayıf" etiketi de ölçümün taşımadığı bir
# hükümdü. Puan yalnız log/sıralama/gölge kayıt içinde yaşıyor. Geometri
# (confidence_score) artık yalnız bildirim eşiğini besler, kartta okunmaz.
# Ölçüm: docs/arastirma/FAZLA_ANALIZI_2026-10-25.md, PUANLAMA_MIMARISI_2026-10-25.md
import devamlilik as _dev
# Günlük public durumu (bütçe sayaçları + gönderilememiş kuyruk) restart'ta
# korunsun diye kalıcılık katmanı kullanılır (canlı denetim: ikisi de kayboluyordu).
from state import persistence as _state_persistence

from secrets_redaction import redact_sensitive_text


logger = logging.getLogger("notifier")  # eski kayıt adıyla aynı

from notifier.util import (
    CONFIRMED_PUBLIC_STATES,
    KRITIK_STATELER,
    PATTERN_EMOJI,
    PUBLIC_STATE_ETIKET,
    TF_EVENT_HUMAN,
    TF_HUMAN,
    TF_KISA,
    _AY_KISALTMALARI,
    _ENGEL_SAYACLAR,
    _FORMATION_ALERT_MUHR_TTL_SAAT,
    _KART_AYLAR,
    _KART_MAKS_SATIR,
    _KART_OLAY,
    _KART_OLAY_KISA,
    _KART_UST_TF,
    _KART_UST_TF_SOZ,
    _KART_YON,
    _PUBLIC_MAX_METIN,
    _TF_BAR_SAAT,
    _dm_anahtar,
    _dm_imza,
    _env_temizle,
    _evren_ozeti,
    _format_price,
    _format_price_tl,
    _grafik_basligi,
    _grafik_dipnotu,
    _grafik_salteri_acik,
    _istanbul,
    _kirp,
    _kuyruk_verisi,
    _muhur_ttl_saat,
    _px_butce,
    _satir,
    _sayı,
    _summary_int,
    _tr_tarih,
    _yon_kisa,
    _yon_metni,
    _yuzde,
    telegram_hata_ipucu,
    token_bicimi_uygun_mu,
)
def _format_lifecycle_alert(data: Dict, *, guncelleme: bool = False) -> str:
    """Onaylı yaşam döngüsü olaylarının mesajı. Stil: _pkg.TELEGRAM_ALERT_STYLE."""
    stil = str(_pkg.TELEGRAM_ALERT_STYLE or "kart").strip().lower()
    if stil == "klasik":
        return _format_lifecycle_alert_klasik(data)
    return _format_lifecycle_alert_kart(data, guncelleme=guncelleme)


def _format_lifecycle_alert_kart(data: Dict, *, guncelleme: bool = False) -> str:
    # GÖRSEL-7: süzgeç açıkken sade kart döner (kârenin taşıdığı satırlar düşer).
    # Kapatmak için `TELEGRAM_KART_SUZGEC=0` → aşağıdaki 25 Eyl biçimi aynen çalışır.
    if _kart_suzgec_aktif():
        return _format_lifecycle_alert_kart_sade(data, guncelleme=guncelleme)
    stock = str(data.get("stock_name") or "Bilinmiyor").upper()
    timeframe = str(data.get("timeframe") or "1h").lower()
    state = str(data.get("state") or "").strip().upper()
    # Desen adı geldiği gibi yazılır: Python'un str.upper()'i Türkçe "i"yi "I"ya
    # çeviriyor (Simetrik → SIMETRIK). Vurgu zaten ◆ sembolüyle kuruluyor.
    pattern = str(data.get("pattern_name") or "Formasyon")
    tf_label = TF_KISA.get(timeframe, TF_EVENT_HUMAN.get(timeframe, TF_HUMAN.get(timeframe, timeframe)))
    try:
        yon = int(data.get("break_dir") or 0)
    except (TypeError, ValueError):
        yon = 0
    ok = "▲" if yon > 0 else ("▼" if yon < 0 else "◆")
    olay, kisalt = _KART_OLAY.get(state, ("OLAY", ""))
    yon_etiketi = _KART_YON.get(yon, "")
    olay_metni = f"{yon_etiketi} {olay}".strip() if state == "KIRILIM_TEYITLI" else olay

    level = data.get("break_price")
    if level is None:
        level = data.get("critical_price_level")
    kirilan = _sayı(level)
    close = data.get("candle_close_price")
    if close is None:
        close = data.get("close_price")
    kapanis = _sayı(close)

    satirlar = [f"{ok} {stock} {tf_label} · {olay_metni}"]
    _satir(satirlar, f"◆ {pattern}" + (f" · {kisalt}" if kisalt else ""))
    damga = _kart_mum_damgasi(data)
    if damga:
        _satir(satirlar, damga)

    # --- olay künyesi: yalnız payload'da olan veri, uydurma yok ---
    künye: List[str] = []
    if kirilan:
        _satir(künye, f"▪ kırılan {kirilan}")
    if kapanis:
        marj = ""
        try:
            kirilan_say = float(data.get("break_price") or data.get("critical_price_level") or 0)
            kapanis_say = float(data.get("candle_close_price") or data.get("close_price") or 0)
            if kirilan_say > 0 and kapanis_say > 0:
                oran = (kapanis_say - kirilan_say) / kirilan_say * 100.0
                if oran == oran:
                    # Yönu "aştı/kaldı" kelimesi zaten söylüyor; +/− işareti yer
                    # çalmasın (25 Eyl biçimindeki "%1,3" gösterimi de buydu).
                    marj = f" · %{abs(oran):.1f}".replace(".", ",")
                    marj += " aştı" if oran >= 0 else " kaldı"
        except (TypeError, ValueError):
            marj = ""
        _satir(künye, f"▪ kapanış {kapanis}{marj}")
    güç = _sayı(data.get("break_strength"), 0)
    # 2026-10-25: "kalite" (geometri) künyeden kalktı. Eşiği geçen sayı ile
    # mesajda okunan sayı aynı şey değildi; artık mesajda ölçülmüş devamlılık var.
    if _pkg.DEVLAMLILIK_AKTIF:
        # Puan/etiket künyeden de kalktı (§11–§12); ölçülmüş kırılma gücü kalır.
        if güç:
            _satir(künye, f"▪ kırılma gücü {güç}")
    else:
        kalite = _sayı(data.get("confidence_score"), 0)
        if kalite:
            _satir(künye, f"▪ kalite {kalite}/100 (formasyon)"
                          + (f" · kırılma gücü {güç}" if güç else ""))
    temas = []
    if data.get("upper_touches") is not None and data.get("lower_touches") is not None:
        temas.append(f"temas üst {data.get('upper_touches')} / alt {data.get('lower_touches')}")
    temas.append("retest var" if data.get("retest_seen") else "retest yok")
    _satir(künye, "▪ " + " · ".join(t for t in temas if t))
    ust_tf = _KART_UST_TF.get(timeframe)
    if ust_tf:
        _satir(künye, f"▪ MTF: {ust_tf} onayı "
                      + ("var" if data.get("mtf_destek") else "yok"))
    yas = data.get("age_bars")
    dogum = data.get("band_baslangic")
    yas_metni = ""
    try:
        if yas is not None and int(yas) >= 0:
            yas_metni = f"▪ bant {int(yas)} mum"
            if dogum:
                zaman = (dogum if isinstance(dogum, datetime)
                         else datetime.fromisoformat(str(dogum)))
                yas_metni += f" · izlenme {zaman.day:02d}.{zaman.month:02d} {zaman:%H:%M}"
    except (TypeError, ValueError, OverflowError):
        yas_metni = ""
    if yas_metni:
        _satir(künye, yas_metni)
    daralma = _yuzde((float(data.get("contraction")) * 100) if data.get("contraction") is not None else None, 0)
    if daralma:
        _satir(künye, f"▪ daralma {daralma}")
    if künye:
        satirlar.append("")
        satirlar.extend(künye)

    # --- geçersizleşme eşiği: kural güncel bandı okur, dondurulmuş seviyeyi değil ---
    esik = None
    try:
        if yon > 0:
            esik = float(data.get("upper_now") or 0) or None
        elif yon < 0:
            esik = float(data.get("lower_now") or 0) or None
    except (TypeError, ValueError):
        esik = None
    if esik:
        # Kural güncel bandı okur; mesaj da bandı yazar (dondurulmuş kırılım
        # seviyesini değil) — aksi halde "ne olursa teyit düşer" bilgisi yanlış olur.
        esik_metin = f"{esik:.2f}".replace(".", ",")
        _satir(satirlar, f"× geçersiz: {esik_metin} "
                        + ("altı" if yon > 0 else "üstü") + " kapanış")

    if guncelleme:
        # Bağlam (piyasa yapısı/bölge/hacim) önceki mesajla birebir aynı: kopya
        # 1400 karakter yerine tek satırlık güncelleme gider.
        # "(önceki kartta)" eklenince satır 370 px'e çıkıp sarıyordu; altına
        # zaten "› /tara {stock}" satırı geliyor, yani nereye bakılacağı yazılı.
        _satir(satirlar, "▪ yapı/bölge/hacim değişmedi")
        satirlar.append(f"› /tara {stock}")
        satirlar.append("• yatırım tavsiyesi değildir")
        return "\n".join(satirlar)

    bolumler = data.get("domain_bolumleri")
    if isinstance(bolumler, dict) and bolumler:
        bolge = [*(bolumler.get("ust") or []), *(bolumler.get("alt") or [])]
        gruplar = [
            list(bolumler.get("yapi") or []),
            bolge,
            list(bolumler.get("hacim") or []),
        ]
        for grup in gruplar:
            if not grup:
                continue
            satirlar.append("")
            for satir in grup:
                _satir(satirlar, str(satir))
    else:
        baglam = str(data.get("domain_context") or "").strip()
        if baglam:
            satirlar.extend(["", baglam])
    adaylik = []
    for aday in (data.get("watch_context") or [])[:3]:
        if not isinstance(aday, dict):
            continue
        aday_satir = (f"▸ {aday.get('stock') or '?'} "
                      f"{TF_KISA.get(str(aday.get('timeframe') or '').lower(), str(aday.get('timeframe') or ''))}"
                      f" · {STATE_TR.get(str(aday.get('state') or '').strip().upper(), 'izlemede')}")
        adaylik.append(aday_satir)
    if adaylik:
        satirlar.append("")
        satirlar.append("▪ izleme adayları")
        satirlar.extend(adaylik)

    karsi = data.get("domain_karsi") or []
    if karsi:
        _satir(satirlar, "! karşı delil: " + " · ".join(str(x) for x in karsi[:3]))
    # CTA + yasal satır: tek satırda birleştirince 323 px'a çıkıyordu (sarar),
    # bu yüzden iki kısa satır. "yatırım tavsiyesi değildir" ifadesi korunur.
    satirlar.append(f"› /tara {stock}")
    satirlar.append("• yatırım tavsiyesi değildir")
    return "\n".join(satirlar)


def _format_lifecycle_alert_kart_sade(data: Dict, *,
                                      guncelleme: bool = False) -> str:
    """Sade kart (GÖRSEL-9): 7 blok, blok arası bir boş satır, girinti yok.

    Tarihçe:
      * GÖRSEL-7 (15 Eki) kartı 40-45 satırdan 8-11 satıra indirdi, fazla kırptı.
      * GÖRSEL-8 (21 Eki) üç bilgiyi geri getirdi: `🕒 … mumu`, `▲/▼ … önündeki
        bölge`, `◈ … yapı`.
      * GÖRSEL-9 (22 Eki) kartı BLOKLARA ayırdı. Kullanıcı: "okurken nerede ne
        var belli değil". Blok sırası sabittir ve karar sırasını izler:

          1 OLAY     — ne oldu (kimlik, formasyon, mum, kapanış/sınır)
          2 ÖNÜNDE   — kırılımın önündeki canlı bölge, kalite, bant yaşı
          3 YAPI     — kısa vadeli yön ve geri çekilme; yapı uyuyor mu
          4 ÖLÇÜ     — arşivde bu kurulum nasıl bitti (`◇`, en çok 3 satır)
          5 KATILIM  — hacim
          6 SINIR    — karşı işaret ve `· bozulur` eşiği
          7 CTA      — yasal uyarı

    `/tara` satırı karttan ÇIKTI (kullanıcı kararı 2026-10-22): komut çalışmaya
    devam eder, ama her alarmın altında tekrar etmez. Boşalan yer ölçüm dipnotuna
    gitti (`· geçmiş davranış, kazanç değil`) — kartın en yanlış anlaşılacak
    satırı `◇` oranlarıdır ("%76 kazanç" diye okunuyordu).

    Tavan `_KART_MAKS_SATIR` (20, boş satırlar hariç); aşılırsa isteğe bağlı
    ekler en düşük öncelikten düşer, çekirdek satır düşmez.

    TEK ÇIKTI (2026-10-22, akşam): grup mesajı DM kartının **birebir aynısıdır**
    (kullanıcı: *"gelişme olmamalı, DM ile aynı olmalı"*). Bu yüzden ayrı bir
    `public` varyantı yok: aynı fonksiyon, aynı satırlar, aynı ölçü sayısı (3).
    Grup toplu bülten basmaz; her olay kendi mesajında gider.
    """
    stock = str(data.get("stock_name") or "Bilinmiyor").upper()
    timeframe = str(data.get("timeframe") or "1h").lower()
    state = str(data.get("state") or "").strip().upper()
    pattern = str(data.get("pattern_name") or "Formasyon")
    tf_label = TF_KISA.get(timeframe, TF_EVENT_HUMAN.get(timeframe, TF_HUMAN.get(timeframe, timeframe)))
    gecersiz = state == "KIRILIM_GECERSIZLESTI"
    try:
        yon = int(data.get("break_dir") or 0)
    except (TypeError, ValueError):
        yon = 0
    ok = "▲" if yon > 0 else ("▼" if yon < 0 else "◆")
    olay, kisalt = _KART_OLAY.get(state, ("OLAY", ""))
    yon_etiketi = _KART_YON.get(yon, "")
    olay_metni = f"{yon_etiketi} {olay}".strip() if state == "KIRILIM_TEYITLI" else olay

    level = data.get("break_price")
    if level is None:
        level = data.get("critical_price_level")
    kirilan = _sayı(level)
    close = data.get("candle_close_price")
    if close is None:
        close = data.get("close_price")
    kapanis = _sayı(close)
    esik, yon_eki = _kart_esik(data, yon)
    bolumler = data.get("domain_bolumleri")

    # ── YORUM KATMANI (S01–S32 araştırma kapısı) ─────────────────────────────
    # Kapı koşulu açılırsa ◇ satırı gelir; kapı yoksa hiçbir şey yazılmaz ve
    # eski kart birebir sürer. `notifier/kart_yorum` içinde yalnız yorum
    # YAZILIR (yeni ölçüm yok, sayı uydurulmaz); kod/n logdadır.
    yorum: Dict = {}
    try:
        from notifier.kart_yorum import sec as _kart_yorum_sec
        yorum = _kart_yorum_sec(data, bolumler)
    except Exception:  # noqa: BLE001 — yorum katmanı kartı düşürmez
        import logging as _logging
        _logging.getLogger(__name__).exception("kart yorumu hesaplanamadı")

    bloklar: List[List[str]] = []

    # ── BLOK 1 · OLAY ────────────────────────────────────────────────────────
    blok: List[str] = []
    _satir(blok, f"{ok} {stock} {tf_label} {olay_metni}".strip())
    if kisalt:
        # Uzun ad + uzun not (ör. "Yükselen Üçgen — kırılan seviye tuttu")
        # bütçeyi aşıp `tuttu`yu girintili devam satırına düşürüyordu. Sığan
        # en açık biçim seçilir; bilgi başlıkta zaten var.
        kisa_not = _KART_OLAY_KISA.get(state, kisalt)
        _satir(blok, _kart_sigan([
            f"{pattern} — {kisalt}",
            f"{pattern} - {kisalt}",
            f"{pattern} — {kisa_not}",
            f"{pattern} — {kisa_not.split()[-1]}",
        ]))
    else:
        _satir(blok, pattern)
    damga = _kart_mum_damgasi(data)
    if damga:
        _satir(blok, damga)
    # Olayın tek ölçüsü: teyitlide kırılan seviye, geçersizleşmede dönüş
    # sınırı. Kullanıcı isteği (2026-10-26): kapanış bilgisi kaldırıldı,
    # kırılan seviye net şekilde vurgulanır.
    if gecersiz:
        if esik:
            _satir(blok, f"· dönüş sınırı {_sayı(esik)} {yon_eki}")
        elif kirilan:
            _satir(blok, f"· kırılan seviye {kirilan}")
        elif kapanis:
            _satir(blok, f"· kapanış {kapanis}")
    elif kirilan and kapanis:
        # 2026-10-26: kullanıcı isteği kapanış gereksizse düşsün, ama
        # değerler farklıysa (XBANK 13482 vs 13380) İKİSİ de ayrı satırda
        # gösterilir — birleşik satır bütçeyi aşıp girintili devam üretiyordu.
        try:
            _kapi = float(str(kapanis).replace(",", "."))
            _kiri = float(str(kirilan).replace(",", "."))
            esit = abs(_kapi - _kiri) < 0.005
        except Exception:
            esit = str(kapanis).strip() == str(kirilan).strip()
        if esit:
            _satir(blok, f"· kırılan seviye {kirilan}")
        else:
            _satir(blok, f"· kapanış {kapanis}")
            _satir(blok, f"· kırılan {kirilan}")
    elif kirilan:
        _satir(blok, f"· kırılan seviye {kirilan}")
    elif kapanis:
        _satir(blok, f"· kapanış {kapanis}")
    bloklar.append(blok)

    if guncelleme:
        # Güncelleme yolu: olay künyesi + "değişiklik yok" + CTA. Bağlam
        # (yapı/bölge/hacim) önceki mesajla birebir aynı olduğu için ölçüm
        # blokları yeniden basılmaz — kullanıcı zaten görmüştü.
        bloklar.append(["değişiklik yok · yapı/bölge aynı"])
        bloklar.append(["• yatırım tavsiyesi değildir"])
        return "\n\n".join("\n".join(b) for b in bloklar if b)

    # ── BLOK 2 · ÖNÜNDE ──────────────────────────────────────────────────────
    blok = []
    engel = list(bolumler.get("engel") or []) if isinstance(bolumler, dict) else []
    if engel and not gecersiz:
        _satir(blok, str(engel[0]))
    # İki 100'lük sayı yan yana etiketsiz duruyordu ("kalite 80 — güç 99"):
    # hangisi neyin ölçüsü? (kullanıcı 2026-10-23). Ayrı satır + tam ad.
    # 2026-10-25: formasyon kalitesi karttan KALKTI (ölçülen sonucu öngörmüyor:
    # kovalar arası fark <2 puan, bileşenleri zıt yönde). Yerine ölçülmüş
    # devamlılık puanı gelir; geometri yalnız bildirim eşiğini besler.
    güç = _sayı(data.get("break_strength"), 0)
    # 2026-10-25 gece (§11–§12): "Devamlılık: yüksek/normal/zayıf" satırı
    # kaldırıldı. Puan tek bayrağa indirgeniyordu, etiket ise ölçümün taşımadığı
    # bir "kalite hükmü" veriyordu. Aynı bilgi (üst TF aynı yönde mi) kartın
    # kendi üst-zaman-dilimi satırında yazılı; çift satır açmıyoruz.
    # Yalnız rollback yolu (`DEVLAMLILIK_AKTIF=0`) eski kalite satırını basar.
    if not _pkg.DEVLAMLILIK_AKTIF:
        kalite = _sayı(data.get("confidence_score"), 0)
        if kalite:
            _satir(blok, f"· formasyon kalitesi {kalite}/100")
    if güç:
        _satir(blok, f"· kırılım gücü {güç}/100")
    # Kullanıcı isteği (2026-10-26): bant ve temas bilgileri kaldırıldı
    # (bant 114 mum, %57 daralma / üste 3 alta 2 kez değdi) karar için
    # kritik değil ve kartı şişiriyordu.
    if blok:
        bloklar.append(blok)

    # ── BLOK 3 · YAPI ────────────────────────────────────────────────────────
    blok = []
    yapi_ozet = list(bolumler.get("yapi_ozet") or []) if isinstance(bolumler, dict) else []
    if yapi_ozet and not gecersiz:
        _satir(blok, str(yapi_ozet[0]))
    # 2026-10-26: göreli güç (20 mum endekse +puan) kaldırıldı - çok açık değil.
    # Kırılan seviyeye dönüş ve üst TF onayı daha net gösterilmeli (kullanıcı isteği).
    if not gecersiz:
        # Net vurgu: ikon + net ifade, substring korunuyor (test uyumu için)
        if data.get("retest_seen"):
            _satir(blok, "↻ kırılan seviyeye dönüş var ✓")
        else:
            _satir(blok, "↻ kırılan seviyeye dönüş yok ✗")
    ust_kisa = _KART_UST_TF.get(timeframe)
    if ust_kisa:
        if int(_sayı(data.get("mtf_uyum"), 0) or 0) > 0:
            _satir(blok, f"◆ {ust_kisa} onayı var ✓ — uyumlu")
        elif data.get("mtf_destek"):
            _satir(blok, f"◆ {ust_kisa} onayı var — uyumsuz")
        else:
            _satir(blok, f"◆ {ust_kisa} onayı yok ✗")
    if blok:
        bloklar.append(blok)

    # ── BLOK 4 · ÖLÇÜ (arşiv; en çok 3 satır) ────────────────────────────────
    # Yorum ◇'ları ÖLÇÜ'nün yerine geçer (yeni soru seti = yeni kaynak);
    # kapı yoksa (`yorum` boş) arşiv ölçüm satırları aynen sürer.
    yorum_satirlari = list(yorum.get("yorum") or [])
    olcum = yorum_satirlari if yorum_satirlari else (
        list(bolumler.get("olcum") or []) if isinstance(bolumler, dict) else [])
    if olcum:
        blok = []
        # Kart 3 ölçü satırı taşır — grup mesajı da AYNI (DM ile birebir).
        # Beklenti hükmü açıksa (TELEGRAM_KART_TAHMIN) hüküm + sayaç satırları
        # ölçüm satırlarının önüne gelir; `olcum` listesi zaten o sırayla üretilir.
        for satir in olcum[:3]:
            _satir(blok, str(satir))
        # Ölçüm dipnotu: oran "kazanç" diye okunmasın. Kullanıcı (2026-10-23):
        # "geçmiş davranış, kazanç değil" geçmişte bir ÖNERİ olduğu gibi
        # okunuyordu; iki satır açık yazılır (tek satır 330 px, bütçe 283).
        # Kullanıcı (2026-10-23): iki satır bölünmesin, tek satır olsun. Tam
        # hâli (`· oran geçmiş davranıştır, kazanç değildir`) 330 px; bütçe
        # 262,8. Kırpma yok, sözcük ekonomisi: iki yargı da korunur.
        _satir(blok, "geçmiş davranıştır, kazanç değil")
        bloklar.append(blok)

    # ── BLOK 5 · KATILIM ─────────────────────────────────────────────────────
    hacim = list(bolumler.get("hacim") or []) if isinstance(bolumler, dict) else []
    blok = []
    for satir in hacim[:2]:
        _satir(blok, str(satir))
    if blok:
        bloklar.append(blok)

    # ── DİKKAT (yorum katmanı; her kartta en fazla 1) ────────────────────────
    # ÖNÜNDE/SINIR arası; kapı yoksa blok hiç oluşmaz. Tavan döngüsü tek
    # satırlık blokları düşürmez (yalnız ◇ ölçüm satırları düşer).
    dikkat_satiri = str(yorum.get("dikkat") or "")
    if dikkat_satiri:
        bloklar.append([dikkat_satiri])

    # ── BLOK 6 · SINIR ───────────────────────────────────────────────────────
    blok = []
    karsi = [str(x) for x in (data.get("domain_karsi") or []) if str(x).strip()]
    if karsi:
        # 2026-10-26: daha net — uyarı ikonu ve net ifade
        _satir(blok, "⚠ olumsuz: " + " — ".join(karsi[:2]))
    if esik and not gecersiz:
        # "bozulur" neyin bozulduğunu söylemiyordu → teyidin düşme eşiği.
        # 5 haneli fiyatta (XBANK 13510,00) tam satır 278 px ve `_satir` onu
        # GİRİNTİLİ devam satırına bölüyordu (kart sözleşmesi yasak). Bu yüzden
        # sığan en açık biçim seçilir; kırpma yok, kısaltma var.
        fiyat = _sayı(esik)
        # Eşik motorun kuralıdır: kapanış BANTIN içine dönerse teyit düşer.
        # Bant kırılımdan sonra daraldığında eşik kırılan seviyenin öbür
        # tarafına düşebiliyor (DOHOL: kırılan 16,87 ama bant tabanı 16,83).
        # İki sayı yan yana okununca çelişki gibi görünüyordu; eşik kırılana
        # eşit değilse "bant" sözcüğüyle etiketlenir (kullanıcı 2026-10-23).
        kirilan_sayi = None
        try:
            kirilan_sayi = float(str(kirilan).replace(",", ".")) if kirilan else None
        except (TypeError, ValueError):
            kirilan_sayi = None
        try:
            esik_sayi = float(esik)
        except (TypeError, ValueError):
            esik_sayi = None
        bant_farki = (kirilan_sayi is not None and esik_sayi is not None
                      and abs(esik_sayi - kirilan_sayi) > 1e-9)
        adaylar = [
            f"· teyit düşer: {fiyat} {yon_eki} kapanış",
            f"· teyit düşer: {fiyat} {yon_eki}",
        ]
        if bant_farki:
            adaylar = [
                f"· teyit düşer: bant {fiyat} {yon_eki} kapanış",
                f"· teyit düşer: bant {fiyat} {yon_eki}",
            ] + adaylar
        adaylar.append(f"· teyit düşer {fiyat} {yon_eki}")
        _satir(blok, _kart_sigan(adaylar))

    # İzleme adayları (adaptör doldurur; canlı tarayıcı boş bırakır): sınır
    # bloğunun altında, kendi başlığıyla. Bilgi düşürülmez.
    adaylar: List[str] = []
    for aday in list(data.get("watch_context") or [])[:3]:
        if not isinstance(aday, dict):
            continue
        aday_tf = TF_KISA.get(str(aday.get("timeframe") or "").lower(),
                              str(aday.get("timeframe") or ""))
        adaylar.append(f"▸ {aday.get('stock') or '?'} {aday_tf} — "
                       + STATE_TR.get(str(aday.get("state") or "").strip().upper(), "izlemede"))
    if adaylar:
        _satir(blok, "izleme adayları")
        for aday_satir in adaylar:
            _satir(blok, aday_satir)
    if blok:
        bloklar.append(blok)

    # ── satır tavanı ────────────────────────────────────────────────────────
    # Daralma/temas 2026-10-23'te çekirdek satır oldu (bant satırına katıldı),
    # bu yüzden "yer varsa ekle" havuzu kalmadı. Tavan artık ölçü bloğunun
    # altından düşürür: sıra → en son ölçü satırı, sonra göreli güç.
    icerik = sum(len(b) for b in bloklar)
    while icerik > _KART_MAKS_SATIR:
        for blok_ in reversed(bloklar):
            if len(blok_) > 1 and str(blok_[0]).startswith("◇"):
                blok_.pop()
                icerik -= 1
                break
        else:
            break

    # ── BLOK 7 · CTA ─────────────────────────────────────────────────────────
    bloklar.append(["• yatırım tavsiyesi değildir"])

    # Bloklar arası TEK boş satır; boş satır satır tavanına sayılmaz.
    return "\n\n".join("\n".join(b) for b in bloklar if b)


def _format_lifecycle_alert_klasik(data: Dict) -> str:
    """Legacy (verbose) body for confirmed lifecycle push events."""
    state = str(data.get("state") or "").strip().upper()
    stock = str(data.get("stock_name") or "Bilinmiyor")
    timeframe = str(data.get("timeframe") or "1h").lower()
    pattern = str(data.get("pattern_name") or "Formasyon")
    direction = _yon_metni(data.get("break_dir"))
    direction_text = direction if direction != "belirsiz" else ""
    tf_label = TF_EVENT_HUMAN.get(timeframe, TF_HUMAN.get(timeframe, timeframe))
    emoji = PATTERN_EMOJI.get(pattern, "📈")

    if state == "KIRILIM_TEYITLI":
        direction_part = f"{direction_text} kırılım" if direction_text else "kırılım"
        event_line = f"KIRILIM TEYİTLİ: {direction_part} (kapanışla teyit)"
    elif state == "RETEST_BASARILI":
        event_line = (
            f"RETEST BAŞARILI: {direction_text + ' ' if direction_text else ''}"
            "kırılım seviyesi kapanışta korundu"
        )
    else:
        event_line = (
            f"KIRILIM GEÇERSİZLEŞTİ: önceki teyitli {direction_text + ' ' if direction_text else ''}"
            "kırılım sonrası kapanış formasyon bandına döndü"
        )

    lines = [f"{emoji} {stock} · {tf_label} · {pattern}", event_line]
    level = data.get("break_price")
    if level is None:
        level = data.get("critical_price_level")
    level_text = _format_price_tl(level)
    if level_text:
        lines.append(f"Kırılım seviyesi: {level_text}")

    close = data.get("candle_close_price")
    if close is None:
        close = data.get("close_price")
    close_text = _format_price_tl(close)
    if close_text:
        lines.append(f"Son kapanmış mum kapanışı: {close_text}")

    bar_text = str(data.get("bar_metni") or "").strip()
    if bar_text:
        lines.append(bar_text)

    if not _pkg.DEVLAMLILIK_AKTIF:
        # Rollback yolu (`DEVLAMLILIK_AKTIF=0`): 25 Eyl klasik metni birebir,
        # kalite satırı dahil. Aktifken bu satır yok: puan ve kalite hükmü
        # karttan kalktı (§11–§12).
        try:
            quality = float(data.get("confidence_score"))
            if quality == quality and abs(quality) != float("inf"):
                grade = _quality_grade(quality)
                lines.append(f"Kalite: {quality:.0f}/100" + (f" · {grade}" if grade else ""))
        except (TypeError, ValueError, OverflowError):
            pass

    upper_touches = data.get("upper_touches")
    lower_touches = data.get("lower_touches")
    if upper_touches is not None and lower_touches is not None:
        lines.append(f"Temas: üst {upper_touches} / alt {lower_touches}")

    domain_context = str(data.get("domain_context") or "").strip()
    if domain_context:
        lines.extend(["", domain_context])

    # Preserve the legacy optional watch list only when an adapter explicitly
    # supplies it; the live scanner leaves it empty for concise push alerts.
    watch_context = data.get("watch_context") or []
    context_lines = []
    for candidate in watch_context[:3]:
        if not isinstance(candidate, dict):
            continue
        candidate_stock = str(candidate.get("stock") or "?")
        candidate_tf = TF_HUMAN.get(candidate.get("timeframe"), candidate.get("timeframe", ""))
        candidate_pattern = str(candidate.get("pattern_name") or "formasyon")
        candidate_state = STATE_TR.get(
            str(candidate.get("state") or "").strip().upper(), "izlemede"
        )
        context_lines.append(f"• {candidate_stock} {candidate_tf} {candidate_pattern}: {candidate_state}")
    if context_lines:
        lines.extend(["", "👀 Diğer izleme adayları", *context_lines])

    lines.extend(["", "📌 Formasyon takibi · yatırım tavsiyesi değildir"])
    return "\n".join(lines)


def _kart_bant(data: Dict) -> str:
    """`· bant 49 mum, %52 daralma` — süre ve olgunluk TEK satırda.

    Kullanıcı (2026-10-23): "bant 49 mum (30 Eylül'den)" tarihiyle birlikte
    daralma yüzdesiyle aynı satıra sığmıyordu (301 px) ve iki ayrı satır
    ("bant", "daralma") neyin ne olduğunu söylemiyordu. Tarih düştü, iki ölçü
    tek satıra geldi: 233 px. Tarih `/tara` ve kârede duruyor.
    """
    yas = data.get("age_bars")
    try:
        yas_say = int(yas) if yas is not None and int(yas) >= 0 else None
    except (TypeError, ValueError, OverflowError):
        yas_say = None
    daralma = _kart_daralma(data)
    if yas_say is None and not daralma:
        return ""
    if yas_say is None:
        return f"· bant {daralma}"
    if not daralma:
        return f"· bant {yas_say} mum"
    return f"· bant {yas_say} mum, {daralma}"


def _kart_daralma(data: Dict) -> str:
    """`%52` — formasyonun olgunluğu (contraction, 0-1); bant satırına eklenir."""
    deger = data.get("contraction")
    try:
        sayi_deger = float(deger) if deger is not None else None
    except (TypeError, ValueError):
        sayi_deger = None
    if sayi_deger is None or sayi_deger < 0:
        return ""
    return f"%{max(0, min(100, round(sayi_deger * 100)))} daralma"


def _kart_esik(data: Dict, yon: int) -> tuple:
    """(eşik fiyatı, yön eki) — kural GÜNCEL bandı okur, dondurulmuş seviyeyi değil."""
    esik = None
    try:
        if yon > 0:
            esik = float(data.get("upper_now") or 0) or None
        elif yon < 0:
            esik = float(data.get("lower_now") or 0) or None
    except (TypeError, ValueError):
        esik = None
    return esik, ("altı" if yon > 0 else "üstü")


def _kart_esik_px() -> float:
    """Satırın güvenle sığdığı piksel eşiği (`telegram_measure` güvenlik payıyla).

    `_satir` bütçeyi %5 güvenlik payıyla uygular; bu eşik o payın ALTINDA kalır,
    böylece kart satırı kendiliğinden bölünmez (bölünme = girintili devam satırı).
    """
    try:
        return float(SATIR_BUTCE) * 0.95 - 6.0
    except (TypeError, ValueError):
        return 260.0


def _kart_mum_damgasi(data: Dict) -> str:
    """Kapanan mumun damgası: hangi mumun kapandığı mesajın ilk üç satırında."""
    for alan in ("bar_time", "bar_kapanis"):
        deger = data.get(alan)
        if not deger:
            continue
        try:
            zaman = deger if isinstance(deger, datetime) else datetime.fromisoformat(str(deger))
        except (TypeError, ValueError):
            continue
        bitis = data.get("bar_kapanis")
        try:
            bitis_zaman = (bitis if isinstance(bitis, datetime)
                           else datetime.fromisoformat(str(bitis))) if bitis else None
        except (TypeError, ValueError):
            bitis_zaman = None
        # Ay adı açık yazılır: "21 Ekim" herkesin okuduğu biçim, "21.10" değil
        # (kullanıcı kararı 2026-10-21: "teknik bilen biri bile anlamayabilir").
        bas = f"{zaman.day} {_KART_AYLAR[zaman.month - 1]} {zaman:%H:%M}"
        if bitis_zaman is not None and bitis_zaman != zaman:
            bas += f"→{bitis_zaman:%H:%M}"
        return f"🕒 {bas} mumu"
    metin = str(data.get("bar_metni") or "").strip()
    if not metin:
        return ""
    # bar_metni eski biçimde uzun bir cümle: "🕒 4 saatlik mum 25.09 13:30 → 17:30
    # kapandı". Kart için aynı verinin kısa yazımı yeterli (satır bütçesi 283 px).
    eslesme = re.search(r"(\d{2})\.(\d{2})\s+(\d{2}:\d{2})\s*→\s*(\d{2}:\d{2})", metin)
    if eslesme:
        ay = int(eslesme.group(2))
        ay_adi = _KART_AYLAR[ay - 1] if 1 <= ay <= 12 else eslesme.group(2)
        return (f"🕒 {int(eslesme.group(1))} {ay_adi} "
                f"{eslesme.group(3)}→{eslesme.group(4)} mumu")
    # ISO damga ("Mum: 2026-10-12 15:30 kapandı") de normalize edilir; ham metin
    # ASLA kopyalanmaz — aksi halde biçim iki yerden üretilmiş olur.
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})", metin)
    if iso:
        ay = int(iso.group(2))
        ay_adi = _KART_AYLAR[ay - 1] if 1 <= ay <= 12 else iso.group(2)
        return f"🕒 {int(iso.group(3))} {ay_adi} {iso.group(4)} mumu"
    return ""


def _kart_sigan(adaylar: List[str]) -> str:
    """Bütçeye sığan İLK adayı döndürür (hepsi sığmazsa en kısası).

    `_satir` sığmayan satırı bölüp girintili devam satırı üretiyor; kart
    sözleşmesi bunu yasaklar. Bu yüzden uzun biçimler sırayla kısalır —
    bilgi düşmez, sözcük ekonomisi devreye girer.
    """
    esik = _kart_esik_px()
    for aday in adaylar:
        if _satir_px(aday) <= esik:
            return aday
    return min(adaylar, key=_satir_px)


def _kart_suzgec_aktif() -> bool:
    """GÖRSEL-7 süzgeci (2026-10-15): kârenin zaten taşıdığı satırlar metinden düşülür.

    Neden: gerçek motor çıktısıyla ölçüldü — teyitli kart 45 satır/980 kr, geçersiz
    kart 31/636; satırların %40'ı girintili DEVAM satırıydı ve 7 satır aynı `▪` ile
    başlıyordu. Kâre aynı bilgiyi (kırılan/kapanış/kalite/daralma/temas/yapı/kutular)
    çiziyor. Kapatmak için `_pkg.TELEGRAM_KART_SUZGEC=0` → bugünkü tam kart geri döner.
    """
    try:
        return bool(_pkg.TELEGRAM_KART_SUZGEC)
    except NameError:  # pragma: no cover - import sırası bozulursa süzgeç AÇIK
        return True


def _kart_temas(data: Dict) -> str:
    """`· üste 2, alta 2 kez değdi` — bant sınırlarının kaç kez denendiği."""
    ust, alt = data.get("upper_touches"), data.get("lower_touches")
    if ust is None or alt is None:
        return ""
    return f"· üste {ust}, alta {alt} kez değdi"


def _kart_yas_metni(data: Dict) -> str:
    """`bant 94 bar — 30.09'dan beri`: yaş ve izlenme başlangıcı tek satırda.

    Kârede bant çizili ama yaşı yok; bu yüzden satır metinde kalır (§GÖRSEL-7 iş
    bölümü). Başlangıç damgası yoksa yalnız yaş yazılır (uydurma tarih yok).
    """
    yas = data.get("age_bars")
    try:
        yas_say = int(yas) if yas is not None and int(yas) >= 0 else None
    except (TypeError, ValueError, OverflowError):
        yas_say = None
    if yas_say is None:
        return ""
    metin = f"· bant {yas_say} mum"
    dogum = data.get("band_baslangic")
    if dogum:
        try:
            zaman = dogum if isinstance(dogum, datetime) else datetime.fromisoformat(str(dogum))
            aylar = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
            ekler = ("tan", "tan", "tan", "dan", "tan", "dan", "dan", "tan", "den", "den", "dan", "tan")
            # GÖRSEL-8: yaş ve izlenme başlangıcı TEK satırda (`· bant 94 bar ·
            # 30 Eylül'den beri`, 258 px). İki ayrı satır, zenginleşen kartta
            # bütçeyi yiyordu; ayırıcı `—` değil `·` çünkü cümle değil iki künye.
            # Sade dil (2026-10-22): "bar" → "mum". Tarih ek tamlamasıyla
            # (`30 Eylül'den beri`) 271 px'e çıkıyordu; "(30 Eylül'den)" aynı
            # bilgiyi 237 px'te taşır.
            metin += f" ({zaman.day} {aylar[zaman.month - 1]}'{ekler[zaman.month - 1]})"
        except (TypeError, ValueError):
            pass
    return metin


def _quality_grade(value) -> str:
    try:
        quality = float(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not (quality == quality and abs(quality) != float("inf")):
        return ""
    if quality >= 85:
        return "Çok güçlü"
    if quality >= 75:
        return "Güçlü"
    if quality >= 65:
        return "Orta"
    return "Zayıf"


def devamlilik_puani(data: Dict) -> Optional[int]:
    """Kart verisinden devamlılık puanı (5–95). Kapsam dışı ailede None.

    Girdiler: `pattern_name` (aile), `mtf_uyum` (yön uyumlu üst TF teyidi),
    `bant_mesafe_atr` (girişin banda uzaklığı). Eksik alan nötr sayılır.
    """
    return _dev.devamlilik_puani(data.get("pattern_name"),
                                 data.get("mtf_uyum"),
                                 data.get("bant_mesafe_atr"))


def quality_comment(q: float) -> str:
    if q >= 85:
        return "çok güçlü"
    elif q >= 75:
        return "güçlü"
    elif q >= 65:
        return "orta"
    else:
        return "zayıf"


def quality_emoji(q: float) -> str:
    if q >= 85:
        return "⭐⭐⭐"
    elif q >= 75:
        return "⭐⭐"
    elif q >= 65:
        return "⭐"
    else:
        return "〰️"


