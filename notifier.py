# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 + KANAL MODELİ ---
# Tek sistem, gürültü azaltma, public kanal desteği

import os
import logging
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
                    PUBLIC_MIN_QUALITY_TF)
# Telefon satır bütçesi ölçeri (bağımlılıksız, PIL yok). Eski "satır ≤ 70 karakter"
# kuralı Türkçe/rakam genişliklerini hesaba katmadığı için 25 Eyl akışında 120
# satır telefonda sarmalanmıştı; artık piksel bütçesi kullanılıyor.
from telegram_measure import (SATIR_BUTCE, bol as _satir_bol,
                              genislik, genislik as _satir_px, metni_sigdir)
# Watch adaylarının state'ini Türkçe basmak için TEK KAYNAK sözlük (reporting
# katmanı da aynısını kullanır; böylece alarm mesajı ile /panel aynı dili konuşur).
from reporting.format import STATE_TR, sayi as _format_sayi
# Günlük public durumu (bütçe sayaçları + gönderilememiş kuyruk) restart'ta
# korunsun diye kalıcılık katmanı kullanılır (canlı denetim: ikisi de kayboluyordu).
from state import persistence as _state_persistence

from secrets_redaction import redact_sensitive_text

logger = logging.getLogger(__name__)


def _grafik_salteri_acik() -> bool:
    """Grafik kill-switch'ini grafik modülünü içe aktarmadan oku.

    `grafik.grafik_aktif_mi()` ile aynı env sözleşmesi: eksik/boş/`yok` kapalı,
    diğer değerler açık. Bu kontrol, kill-switch kapalıyken grafik katmanını
    gereksiz yere yüklememek için notifier içinde tutulur.
    """
    return (os.environ.get("TELEGRAM_GRAFIK") or "yok").strip().lower() != "yok"


def _kuyruk_verisi(data: Dict) -> Dict:
    """Persist a detached chart snapshot as well as the text context.

    These are plain chart dictionaries, not DataFrames or engine instances.
    The tagged JSON codec preserves their timestamps across restarts.
    """
    from notification_delivery import freeze
    return freeze(data or {})


def _grafik_basligi(olay: Dict, kare: Dict, meta: Dict) -> str:
    """Kare altındaki tek satır kimlik + veri dipnotu (§4, FAZ 1).

    Neden kısa: caption Telegram'da AYRI mesaj gövdesi olur; kartın satırlarını
    buraya koymak „1 olay = 1 mesaj" kuralını deler. Yalnız hangi hisse, hangi
    zaman dilimi ve kaç mum — sayı/px ayrıntısı karenin kendisinde ve `meta`da.
    Kartla aynı dil: TF kısaltması 4s/1s (ham kod değil), sayı virgüllü (`sayi`).

    FAZ 1: kareden ÇIKARILAN geliştirici metinleri (`veri: N bar hacimsiz`,
    `bölge: N kutu kapak dışında`, `eksik: …`) artık karenin altında değil, kartın
    altında tek satır dipnot olarak gider — karede kazanılan dikey alan mumlara
    kalır, bilgi kaybolmaz. Dipnot 200 karakterle sınırlıdır (caption bütçesi).
    """
    sembol = str(olay.get("sembol") or "").strip().upper() or "?"
    # Kartta hangi etiket görünüyorsa karede de o: 4h → 4s (ham TF kodu değil).
    tf = str((kare.get("goruntu") or {}).get("tf_kisa") or kare.get("tf") or "1h")
    parcalar = [sembol, tf]
    if olay.get("state") == "KIRILIM_GECERSIZLESTI" or ((kare.get("goruntu") or {}).get("alarm") or {}).get("tur") == "gecersiz":
        return " · ".join(parcalar)
    mum = meta.get("mum_sayisi")
    if mum:
        parcalar.append(f"{_format_sayi(mum, 0)} mum")
    try:
        lejant_gizli = max(0, int(meta.get("lejant_atlanan") or 0))
    except (TypeError, ValueError, OverflowError):
        lejant_gizli = 0
    if lejant_gizli:
        parcalar.append(f"lejant kısaltıldı (+{lejant_gizli})")
    baslik = " · ".join(parcalar)
    dipnot = _grafik_dipnotu(meta)
    return f"{baslik}\n{dipnot}" if dipnot else baslik


def _grafik_dipnotu(meta: Dict) -> str:
    """Kareden çıkarılan veri dipnotları (FAZ 1): kartın altında tek satır.

    Sıra: veri sorunları (eksik katman/kırmızı uyarı) → gri notlar (kadraj
    budaması, kapak dışı kutular) → kısaltma izleri. Hiçbiri yoksa boş döner ve
    caption tek satır kalır (uydurma metin yazılmaz). En fazla 200 karakter:
    caption bütçesi (Telegram 1024) medya grubunda paylaşılır.
    """
    metin = (meta or {}).get("metin") if isinstance(meta, dict) else None
    if not isinstance(metin, dict):
        return ""
    parcalar: List[str] = []
    for satir in list(metin.get("dipnotlar") or []) + list(metin.get("notlar") or []):
        temiz = " ".join(str(satir).split())
        if temiz and temiz not in parcalar:
            parcalar.append(temiz)
    if not parcalar:
        return ""
    return ("ℹ️ " + " · ".join(parcalar))[:200]


def _istanbul(dt: datetime) -> datetime:
    """Naive datetime'ı İstanbul saatine sabitler.

    Neden: süreç UTC'de çalışsa bile gün/saat sınırları BIST saatine göre
    hesaplanmalı (Render'da TZ verilmezse günlük kota gece 03:00'te sıfırlanıyordu).
    Eski kayıtlarda (telegram_kap.json / Supabase) naive ISO damgalar var; onları
    da buradan geçirerek TypeError riskini ortadan kaldırıyoruz.
    """
    if dt.tzinfo is None:
        return ISTANBUL_TZ.localize(dt)
    return dt.astimezone(ISTANBUL_TZ)

PATTERN_EMOJI = {
    "Yükselen Üçgen": "🔺",
    "Alçalan Üçgen": "🔻",
    "Simetrik Üçgen": "🔷",
    "Yükselen Kama": "📐⬆️",
    "Alçalan Kama": "📐⬇️",
    "Boğa Bayrağı": "🚩🐂",
    "Ayı Bayrağı": "🚩🐻",
    "Boğa Flaması": "🎏🐂",
    "Ayı Flaması": "🎏🐻",
}

CONFIRMED_PUBLIC_STATES = frozenset({
    "KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI",
})

KRITIK_STATELER = tuple(sorted(CONFIRMED_PUBLIC_STATES))

TF_HUMAN = {
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
}
TF_EVENT_HUMAN = {
    "1h": "1 saat",
    "2h": "2 saat",
    "4h": "4 saat",
    "1d": "1 gün",
}

def quality_comment(q: float) -> str:
    if q >= 85:
        return "çok güçlü"
    elif q >= 75:
        return "güçlü"
    elif q >= 65:
        return "orta"
    else:
        return "zayıf"

def _yon_metni(break_dir) -> str:
    """Kırılım yönünü Türkçe tek kelimeye çevirir (özet satırları için)."""
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return "belirsiz"


def _format_price(value) -> str:
    """Fiyat metni (Türkçe ondalık). Boşta hiçbir sayı basılmaz: `""`.

    Biçim tek kaynaktan gelir (`reporting.format.sayi`); G0 öncesi burada
    nokta kalıp kartta virgül çıkıyordu — aynı sayı iki görünümde okunuyordu.
    """
    return _sayı(value)


def quality_emoji(q: float) -> str:
    if q >= 85:
        return "⭐⭐⭐"
    elif q >= 75:
        return "⭐⭐"
    elif q >= 65:
        return "⭐"
    else:
        return "〰️"


def _format_price_tl(value) -> str:
    """BIST fiyatını Türkçe ondalık ayırıcı ve TL ekiyle biçimlendir."""
    formatted = _format_price(value)
    return f"{formatted} TL" if formatted else ""


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


# Günlük engel sayaçları: /durum ve teşhis bu anahtarları gösterir. Yeni engel
# eklendiğinde TEK yerde dursun diye tuple; `_gunu_sifirla_gerekirse` de bunu kullanır.
_ENGEL_SAYACLAR = {
    "cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0, "tekrar": 0,
    # "baglam_degismedi": bağlam bloğu birebir aynıysa kart kısaltıldı (kopya blok basılmadı).
    "baglam_degismedi": 0,
}

# --- TELEFON KARTI (düz metin; parse_mode yok) ----------------------------
# 25 Eyl canlı akışında alarm başına 1358-1559 karakter / 47-54 görsel satır
# oluşuyordu ve 120 satır telefonda sarmalanıyordu. Kart kuralları:
#   1 satır = 1 bilgi grubu · satır ≤ TELEGRAM_SATIR_PX (px) · gruplar boş satırla
#   ayrılır · olay ilk satırda (bildirim önizlemesi okunabilsin) · hizalama için
#   boşluk kullanılmaz (orantılı yazı tipinde bozulur) · bilgi kesilmez, sığmıyorsa
#   devam satırına taşınır.
_KART_YON = {1: "YUKARI", -1: "AŞAĞI"}
_KART_OLAY = {
    # İkinci satırdaki kısa not, ilk satırda söylenmeyeni söyler: RETEST BAŞARILI
    # zaten "seviye korundu" demek olduğu için orada ek not yoktur (yer boşa gitmez).
    "KIRILIM_TEYITLI": ("TEYİTLİ", "kapanışla"),
    "RETEST_BASARILI": ("RETEST BAŞARILI", ""),
    "KIRILIM_GECERSIZLESTI": ("GEÇERSİZLEŞTİ", "bandına dönüş"),
}
# mtf_destek yalnız 1h→4h ve 4h→1g için hesaplanır (main.py); etiket bu yüzden
# alarm TF'sine göre yazılır. Eskiden her durumda "4h destekliyor" deniyordu.
_KART_UST_TF = {"1h": "4s", "2h": "4s", "4h": "1g"}
TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}


def _px_butce():
    """Kart satır bütçesi; 0 = bölme yok."""
    try:
        butce = float(TELEGRAM_SATIR_PX)
    except (TypeError, ValueError):
        return None
    return butce if butce > 0 else None


def _satir(çıktı: List[str], metin: str, girinti: str = "   ") -> None:
    """Satırı bütçeye sığdırıp ekler; sığmıyorsa böler (bilgi düşmez)."""
    for satir in _satir_bol(metin, _px_butce(), girinti=girinti):
        if satir.strip():
            çıktı.append(satir)


def _sayı(value, basamak: int = 2) -> str:
    """Yerel kısayol: biçimi `reporting.format.sayi` verir (boşta `""`)."""
    return _format_sayi(value, basamak, varsayilan="")


def _yuzde(value, basamak: int = 1) -> str:
    metin = _sayı(value, basamak)
    return f"%{metin}" if metin else ""


#: Kart metninde ay adı açık yazılır (`21 Ekim`), sayısal kısa yazım (`21.10`)
#: kullanılmaz. Tek kaynak: `_kart_mum_damgasi` ve `_kart_yas_metni` buradan okur.
_KART_AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


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


def _kart_suzgec_aktif() -> bool:
    """GÖRSEL-7 süzgeci (2026-10-15): kârenin zaten taşıdığı satırlar metinden düşülür.

    Neden: gerçek motor çıktısıyla ölçüldü — teyitli kart 45 satır/980 kr, geçersiz
    kart 31/636; satırların %40'ı girintili DEVAM satırıydı ve 7 satır aynı `▪` ile
    başlıyordu. Kâre aynı bilgiyi (kırılan/kapanış/kalite/daralma/temas/yapı/kutular)
    çiziyor. Kapatmak için `TELEGRAM_KART_SUZGEC=0` → bugünkü tam kart geri döner.
    """
    try:
        return bool(TELEGRAM_KART_SUZGEC)
    except NameError:  # pragma: no cover - import sırası bozulursa süzgeç AÇIK
        return True


def _kart_esik_px() -> float:
    """Satırın güvenle sığdığı piksel eşiği (`telegram_measure` güvenlik payıyla).

    `_satir` bütçeyi %5 güvenlik payıyla uygular; bu eşik o payın ALTINDA kalır,
    böylece kart satırı kendiliğinden bölünmez (bölünme = girintili devam satırı).
    """
    try:
        return float(SATIR_BUTCE) * 0.95 - 6.0
    except (TypeError, ValueError):
        return 260.0


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


#: Sade kartın satır tavanı (CTA ve yasal uyarı dahil). GÖRSEL-8 kullanıcı
#: kararı (2026-10-21): "alarm metni kendi başına okunabilsin" — kart, kârenin
#: taşıdığı her şeyi değil, KARAR İÇİN GEREKEN ölçüleri taşır. Tavan aşılırsa
#: en düşük öncelikli ek satır düşer (bilgi gizlenmez, ölçülerek seçilir).
#: GÖRSEL-9 (2026-10-22): 7 bloklu düzen + blok arası 1 boş satır. Boş satırlar
#: tavan hesabına GİRMEZ (bütçe px ile ölçülür); tavan 16 -> 20 çıktı çünkü
#: `◇` ölçü bloğu 3 satıra ve ölçüm dipnotu karta girdi.
_KART_MAKS_SATIR = 20


def _kart_daralma(data: Dict) -> str:
    """`· daralma %52` — formasyonun olgunluğu (contraction, 0-1)."""
    deger = data.get("contraction")
    try:
        sayi_deger = float(deger) if deger is not None else None
    except (TypeError, ValueError):
        sayi_deger = None
    if sayi_deger is None or sayi_deger < 0:
        return ""
    return f"· daralma %{max(0, min(100, round(sayi_deger * 100)))}"


def _kart_temas(data: Dict) -> str:
    """`· temas üst 2 / alt 3` — bant sınırlarının kaç kez denendiği."""
    ust, alt = data.get("upper_touches"), data.get("lower_touches")
    if ust is None or alt is None:
        return ""
    return f"· temas üst {ust} / alt {alt}"


def _format_lifecycle_alert_kart_sade(data: Dict, *, guncelleme: bool = False) -> str:
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

    bloklar: List[List[str]] = []

    # ── BLOK 1 · OLAY ────────────────────────────────────────────────────────
    blok: List[str] = []
    _satir(blok, f"{ok} {stock} {tf_label} {olay_metni}".strip())
    if kisalt:
        aday = f"{pattern} — {kisalt}"
        if genislik(aday) > _kart_esik_px():
            aday = f"{pattern} - {kisalt}"
        _satir(blok, aday)
    else:
        _satir(blok, pattern)
    damga = _kart_mum_damgasi(data)
    if damga:
        _satir(blok, damga)
    # Olayın tek ölçüsü: teyitlide "kapanış · sınır", geçersizleşmede "dönüş sınırı".
    if gecersiz:
        if esik:
            _satir(blok, f"· dönüş sınırı {_sayı(esik)} {yon_eki}")
        elif kapanis:
            _satir(blok, f"· kapanış {kapanis}")
    elif kapanis and kirilan:
        _satir(blok, f"· kapanış {kapanis} · sınır {kirilan}")
    elif kapanis:
        _satir(blok, f"· kapanış {kapanis}")
    elif kirilan:
        _satir(blok, f"· sınır {kirilan}")
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
    kalite = _sayı(data.get("confidence_score"), 0)
    güç = _sayı(data.get("break_strength"), 0)
    if kalite and güç:
        _satir(blok, f"· kalite {kalite}/100 — güç {güç}")
    elif kalite:
        _satir(blok, f"· kalite {kalite}/100")
    yas_metni = _kart_yas_metni(data)
    if yas_metni:
        if genislik(yas_metni) <= _kart_esik_px():
            _satir(blok, yas_metni)
        else:
            for parca in yas_metni.split(" · "):
                _satir(blok, parca if parca.startswith("·") else "· " + parca)
    if blok:
        bloklar.append(blok)

    # ── BLOK 3 · YAPI ────────────────────────────────────────────────────────
    blok = []
    yapi_ozet = list(bolumler.get("yapi_ozet") or []) if isinstance(bolumler, dict) else []
    if yapi_ozet and not gecersiz:
        _satir(blok, str(yapi_ozet[0]))
    retest = "geri çekilme var" if data.get("retest_seen") else "geri çekilme yok"
    ust_tf = _KART_UST_TF.get(timeframe)
    if ust_tf:
        mtf = f"{ust_tf} de onaylı" if data.get("mtf_destek") else f"{ust_tf} onayı yok"
        _satir(blok, f"{retest} · {mtf}")
    else:
        _satir(blok, retest)
    if blok:
        bloklar.append(blok)

    # ── BLOK 4 · ÖLÇÜ (arşiv; en çok 3 satır) ────────────────────────────────
    olcum = list(bolumler.get("olcum") or []) if isinstance(bolumler, dict) else []
    if olcum:
        blok = []
        for satir in olcum[:3]:
            _satir(blok, str(satir))
        # Ölçüm dipnotu: oran "kazanç" diye okunmasın. `/tara` satırının yerine
        # geldi (2026-10-22 kararı). Ölçüm varsa her zaman basılır.
        _satir(blok, "· geçmiş davranış, kazanç değil")
        bloklar.append(blok)

    # ── BLOK 5 · KATILIM ─────────────────────────────────────────────────────
    hacim = list(bolumler.get("hacim") or []) if isinstance(bolumler, dict) else []
    blok = []
    for satir in hacim[:2]:
        _satir(blok, str(satir))
    if blok:
        bloklar.append(blok)

    # ── BLOK 6 · SINIR ───────────────────────────────────────────────────────
    blok = []
    karsi = [str(x) for x in (data.get("domain_karsi") or []) if str(x).strip()]
    if karsi:
        _satir(blok, "ters işaret: " + " — ".join(karsi[:2]))
    if esik and not gecersiz:
        _satir(blok, f"· bozulur: {_sayı(esik)} {yon_eki} kapanış")

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

    # ── isteğe bağlı ölçüler: yer varsa 2. bloğa girer ──────────────────────
    ekler: List[tuple[int, str]] = []
    for oncelik, metin in ((3, _kart_daralma(data)), (2, _kart_temas(data))):
        if metin:
            ekler.append((oncelik, metin))

    icerik = sum(len(b) for b in bloklar)
    kalan = _KART_MAKS_SATIR - icerik
    secilen: List[str] = []
    for _oncelik, metin in sorted(ekler, reverse=True):
        if kalan <= 0:
            break
        secilen.append(metin)
        kalan -= 1
    if secilen:
        # Ölçü satırları 2. blokta (bant/kalite ile) okunur.
        hedef = bloklar[1] if len(bloklar) > 1 else bloklar[0]
        hedef.extend(secilen)

    # ── BLOK 7 · CTA ─────────────────────────────────────────────────────────
    bloklar.append(["• yatırım tavsiyesi değildir"])

    # Bloklar arası TEK boş satır; boş satır satır tavanına sayılmaz.
    return "\n\n".join("\n".join(b) for b in bloklar if b)


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
    kalite = _sayı(data.get("confidence_score"), 0)
    güç = _sayı(data.get("break_strength"), 0)
    if kalite:
        # "Kalite" eskiden formasyonun o anki kalitesiydi (main.py: snap.effective_quality);
        # alarmı geçiren sayı ile mesajda okunan sayı karışmasın diye etiket açık.
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


# --- DM içerik kapısı ---------------------------------------------------------
# 25 Eyl akışında TOASO'nun 10:40 ve 15:10 mesajlarının 35 satırının 30'u
# birebir aynıydı: piyasa yapısı, bölgeler ve hacim hiç değişmemişti.
# Kural (bilinçli olarak yalnız KISALTMA): mesaj her durumda gider, çünkü
# "aynı olayı ikinci kez gönderme" kararının tek sahibi mühürdür (_son_alert_key).
# Bu kapı mesaj keserse mühürle çift kontrol doğar ve "kuyrukta beklerken bağlamı
# değişen" olayların mührü yenilenmez (test_tekrar_alarm_koruması bu yüzden patladı).
# Kapı yalnızca: imza aynıysa bağlam bloğunun yerine tek satır basar.
def _dm_anahtar(data: Dict) -> str:
    stock = str(data.get("stock_name") or "").strip().upper()
    tf = str(data.get("timeframe") or "").strip().lower()
    # State Anahtarda YOK: bağlam (yapı/bölge/hacim) hisse+TF'nin özelliğidir,
    # state'ten bağımsız. 25 Eyl'de TOASO 1s 10:40 (geçersizleşti) ve 15:10
    # (teyitli) kartlarının 30 satırı birebir aynıydı; state'i ayırınca kapı
    # hiçbir şey yakalamıyordu. Olaya özel veri (seviye, kapanış, state) kartın
    # kendi satırlarında durduğu için kısaltma bilgi kaybettirmiyor.
    return f"{stock}|{tf}"


def _dm_imza(data: Dict) -> str:
    """Bağlamın değişim imzası (hash): kart bölümleri ya da klasik bağlam metni.

    Yalnız bağlam ölçülür; seviye/kapanış/state kartın kendi satırlarında zaten
    yazılıyor. "Aynı olayı ikinci kez basma" kararı mühre (_son_alert_key) aittir,
    bu kapı yalnız DEĞİŞMEYEN BAĞLAMI kısaltır.
    """
    import hashlib
    parcalar: list[str] = []
    bolumler = data.get("domain_bolumleri")
    if isinstance(bolumler, dict) and bolumler:
        # Anahtar adı yazılmıyor (satır içeriği zaten başlık taşıyor); sıralı
        # dolaşılır ki yeni bir bölüm eklendiğinde imza kendiliğinden kapsasın.
        for anahtar in sorted(bolumler):
            parcalar.append("|".join(str(x) for x in (bolumler.get(anahtar) or [])))
    else:
        parcalar.append(str(data.get("domain_context") or ""))
    return hashlib.sha1("\n".join(parcalar).encode("utf-8")).hexdigest()[:16]



def _format_lifecycle_alert(data: Dict, *, guncelleme: bool = False) -> str:
    """Onaylı yaşam döngüsü olaylarının mesajı. Stil: TELEGRAM_ALERT_STYLE."""
    stil = str(TELEGRAM_ALERT_STYLE or "kart").strip().lower()
    if stil == "klasik":
        return _format_lifecycle_alert_klasik(data)
    return _format_lifecycle_alert_kart(data, guncelleme=guncelleme)



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


# Türkçe ay kısaltmaları: strftime('%b') sistem yerelinden İngilizce basıyordu
# ("02 Oct 20:05"); mesajların tamamı Türkçe olduğu için tarih de Türkçe olmalı.
_AY_KISALTMALARI = {
    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara",
}


def _tr_tarih(dt: datetime) -> str:
    """Kısa Türkçe tarih: '02 Eki 20:05'. Gün/ay/saat hizalı kalır (telefonda düzgün görünür)."""
    return f"{dt.day:02d} {_AY_KISALTMALARI.get(dt.month, '')} {dt:%H:%M}"


def _summary_int(gun_ozeti: Dict, key: str) -> int:
    try:
        return max(0, int((gun_ozeti or {}).get(key) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _summary_lifecycle_counts(gun_ozeti: Dict) -> str:
    if not isinstance(gun_ozeti, dict):
        return ""
    confirmed = _summary_int(gun_ozeti, "kirilim_teyitli_olay_sayisi")
    retests = _summary_int(gun_ozeti, "retest_basarili_olay_sayisi")
    invalidated = _summary_int(gun_ozeti, "kirilim_gecersizlesti_olay_sayisi")
    # Uzun hali ("3 teyitli kırılım · 1 başarılı retest · 2 teyit sonrası
    # geçersizleşme") 479 px'idi ve bölüm başlığındaki 🔎 satırı üçe bölünüyordu.
    # Bölüm adları zaten kart/bülten metinlerinde tam yazılı; burada sayım önemli.
    parcalar = [f"{confirmed} teyitli", f"{retests} retest başarılı",
                f"{invalidated} geçersizleşme"]
    # Uzun hali ("3 teyitli kırılım · 1 başarılı retest · 2 teyit sonrası
    # geçersizleşme") 479 px'idi. Sığan kadarı etiketle aynı satıra, kalanı
    # girintili alt satıra çıkar — arada "·" bırakmak yerine satır kırıyoruz ki
    # devam satırı ayrı bir madde gibi okunsun.
    etiket = "🔎 Bugün:"
    satirlar: List[str] = []
    mevcut = etiket
    for tok in parcalar:
        aday = f"{mevcut} {tok}" if mevcut == etiket else f"{mevcut} · {tok}"
        if genislik(aday) > SATIR_BUTCE and mevcut != etiket:
            satirlar.append(mevcut)
            mevcut = f"   {tok}"
        else:
            mevcut = aday
    satirlar.append(mevcut)
    return "\n".join(satirlar)


def _summary_last_full_scan(gun_ozeti: Dict) -> str:
    """Özetin altındaki 'son tam tarama' bloğu.

    Etiket ve değer ayrı satırlarda: "🕒 Son başarılı tam tarama: 11 Eki 18:00 ✓"
    335 px'a çıkıp ortadan ikiye düşüyordu. "başarılı" kelimesi düşürülmedi —
    kısmi/başarısız taramalar bu sayaca girmiyor ve okuyucu bunu bilmeli.
    """
    if not isinstance(gun_ozeti, dict):
        return ""
    etiket = "🕒 Son başarılı tam tarama:"
    raw = gun_ozeti.get("son_basarili_tam_tarama")
    if not raw:
        return f"{etiket}\n   kayıt yok"
    try:
        value = raw if isinstance(raw, datetime) else datetime.fromisoformat(
            str(raw).replace("Z", "+00:00")
        )
        value = _istanbul(value)
        when = _tr_tarih(value)
    except (TypeError, ValueError, OverflowError):
        return f"{etiket}\n   zaman bilgisi okunamadı"
    if gun_ozeti.get("tam_tarama_guncel") is True:
        return f"{etiket}\n   {when} ✓"
    return (f"{etiket}\n   {when}\n"
            "   bugün güncel tam tarama yok;\n"
            "   eski formasyonlar gösterilmedi.")


def _public_izleme_adaylari(aktif: List[Dict], adet: int = 5, haric=None) -> List[Dict]:
    """Sabah notu için izleme listesi: hâlâ WATCH_STATES'te olan adaylar.

    Kaynak DM tarafındaki kuyruk değil, o anki canlı durumdur; kaliteye göre
    sıralanır ve alan adları panel/kuyruk sözlüğüne çevrilir.
    `haric`: aynı mesajda zaten yazılmış hisseler (örn. ⚡ Sıkışan satırı) —
    tek mesajda aynı hisse iki kez görünmesin.
    """
    haric = set(haric or ())
    adaylar = [f for f in aktif or []
               if isinstance(f, dict) and str(f.get('state') or '') in WATCH_STATES
               and f.get('stock_name') not in haric]
    try:
        adaylar.sort(key=lambda f: float(f.get('confidence_score') or 0), reverse=True)
    except (TypeError, ValueError):
        pass
    sonuc = []
    for f in adaylar[:adet]:
        sonuc.append({"stock": f.get("stock_name"), "timeframe": f.get("timeframe"),
                      "pattern_name": f.get("pattern_name"),
                      "quality": f.get("confidence_score")})
    return sonuc

# Zaman dilimi -> bir bar kaç saat? Tek-seferlik mühürün bayatma süresi buna
# göre ölçeklenir (bkz. _muhur_ttl_saat).
_TF_BAR_SAAT = {"1h": 1, "2h": 2, "4h": 4, "1d": 24}
_FORMATION_ALERT_MUHR_TTL_SAAT = 7 * 24


def _muhur_ttl_saat(timeframe: str) -> float:
    """Tek-seferlik mühürün kaç saat geçerli olduğu.

    NEDEN VAR: motor bitmiş (terminal) bir formasyonu TERMINAL_TAZE_BAR bar
    boyunca "taze" sayar ve raporlamaya devam eder (ölü formasyon
    filtresindeki istisna — "az önce tamamlandı" bilgisi kaçmasın diye).
    Mühür gün bazlı bayatıyorsa bu pencereden taşan formasyon sonraki
    gün/taramada TEKRAR bildiriliyordu:
        1 günlük grafikte 3 bar = 3 gün  -> aynı haber 3 gün daha basılıyordu
        4 saatlikte     3 bar = 12 saat -> ertesi sabah yine basılıyordu
    TTL artık bar süresine göre ölçekleniyor: 3 bar + 1 saat pay.
    Böylece mühür her zaman motorun "aynı olay" penceresini kapsar.
    """
    bar_saat = _TF_BAR_SAAT.get(str(timeframe or "").lower())
    if bar_saat is None:
        return 24.0          # bilinmeyen TF: eski gün bazlı davranış
    return TERMINAL_TAZE_BAR * bar_saat + 1


def _env_temizle(deger) -> str:
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()

_PUBLIC_MAX_METIN = 4000     # Telegram sınırı 4096; kanal/grup yolu da kırpmalı


def _kirp(metin: str, sinir: int = _PUBLIC_MAX_METIN) -> str:
    """Public gönderim için Telegram sınırına sığdırır (eskiden kırpma yoktu →
    uzun özet 400 alabiliyordu)."""
    metin = str(metin or "")
    if len(metin) <= sinir:
        return metin
    return metin[: sinir - 40].rstrip() + "\n\n… (mesaj sınırı nedeniyle kesildi)"


# Public grup için SADE durum etiketleri: iç izleme notları ("teyit bekleniyor",
# "retest tutarsa yapı güçlenir") gruba taşınmaz.
PUBLIC_STATE_ETIKET = {
    "KIRILIM_TEYITLI": "kapanışla teyitli kırılım",
    "RETEST_BASARILI": "kapanışla başarılı retest",
    "KIRILIM_GECERSIZLESTI": "önceki teyitli kırılım geçersizleşti",
}


def _yon_kisa(break_dir) -> str:
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return ""


def token_bicimi_uygun_mu(token: str) -> bool:
    t = _env_temizle(token)
    if not t:
        return False
    if ":" not in t:
        return False
    parcalar = t.split(":", 1)
    if len(parcalar) != 2:
        return False
    ilk, ikinci = parcalar
    if not ilk.isdigit():
        return False
    if len(ilk) < 5:
        return False
    if len(ikinci) < 20:
        return False
    if not re.match(r"^[A-Za-z0-9_\-]+$", ikinci):
        return False
    return True

def telegram_hata_ipucu(status_code: int, response_text: str = "") -> str:
    txt = (response_text or "").lower()
    if status_code == 401:
        return (
            "Token geçersiz veya iptal edilmiş (401). "
            "@BotFather'dan token'ı tam kopyala, Render → Environment → TELEGRAM_BOT_TOKEN'ı güncelle. "
            "Sızdıysa /revoke ile iptal edip yeni bot aç."
        )
    if status_code == 404:
        return (
            "Bot bulunamadı veya endpoint yanlış (404). "
            "Token doğru mu? URL https://api.telegram.org/bot<token>/... olmalı. "
            "BotFather'da bot silinmiş olabilir."
        )
    if "chat not found" in txt:
        return (
            "Sohbet bulunamadı (chat not found). "
            "Kendi botuna Telegram'da /start yaz, sonra tekrar dene. "
            "chat_id yanlışsa @userinfobot'tan Id'yi tekrar al."
        )
    if "bot was blocked" in txt or "blocked" in txt:
        return (
            "Bot engellenmiş (bot was blocked): Telegram'da bot sohbetinde Unblock yap, "
            "engellenmiş olabilir, /start ile yeniden başlat."
        )
    if status_code == 400:
        return (
            "İstek hatalı (400). chat_id sayı mı, mesaj boş mu? "
            "@userinfobot'tan Id'yi tekrar al, grup için -100... ile başlayan id kullan. "
            "Sohbet bulunamadı (chat not found) ise kendi botuna /start yaz. "
            "Mesaj çok uzun veya biçim hatalı olabilir."
        )
    if status_code == 403:
        return (
            "Bot bu sohbete mesaj gönderemiyor (403). "
            "Kendi botuna Telegram'da bir kez /start yaz, engeli kaldır, engellenmiş olabilir. "
            "Grup ise botu gruba ekle ve admin yap. chat not found ise botla hiç konuşmamışsındır. "
            "Unblock yapman gerekebilir."
        )
    if status_code == 409:
        return (
            "Aynı token'ı iki yer aynı anda dinliyor (409 Conflict). "
            "Termux/PC'de açık kalan ikinci kopyayı kapat, Render'da tek instance çalışmalı. "
            "getUpdates aynı anda iki süreçten çağrılamaz."
        )
    # Kaynak METNİN TAMAMI kırpılmadan önce maskelenir: 200 karakter sınırında
    # bölünen bir token bire-bir eşleştirmeden kaçabilirdi.
    return f"Telegram hatası HTTP {status_code}: {redact_sensitive_text(response_text)[:200]}"


class TelegramNotifier:
    def __init__(self, persistent_store=None, initial_store_data=None):
        self.persistent_store = persistent_store
        self.initial_store_data = initial_store_data if isinstance(initial_store_data, dict) else {}
        self.token = _env_temizle(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        self.chat_id = _env_temizle(os.environ.get("TELEGRAM_CHAT_ID", ""))
        # Public hedef: grup (tercih) ya da eski kanal ayarı. Grup, DM'den BAĞIMSIZ
        # çalışır; DM kapalıyken de grup yayını sürer.
        self.group_id = _env_temizle(os.environ.get("TELEGRAM_GROUP_ID", ""))
        self.channel_id = _env_temizle(os.environ.get("TELEGRAM_CHANNEL_ID", ""))
        self.public_chat_id = self.group_id or self.channel_id
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}
        self.max_saatlik = TELEGRAM_MAX_MESAJ_SAAT
        self.max_gunluk = TELEGRAM_MAX_MESAJ_GUN
        self._saatlik_zamanlar: List[datetime] = []
        # Gönderilemeyen alarmların SEBEP sayaçları (gün içi, gün değişiminde sıfırlanır).
        # Neden: can_send False döndüğünde olay hiçbir yerde görünmüyordu; kullanıcı
        # "kaç tanesi bastırıldı" sorusunun cevabını /durum'da görebilmeli.
        self.engeller = dict(_ENGEL_SAYACLAR)
        # DM içerik kapısı durumu: anahtar -> {"imza","kapanis","gün"}
        self._dm_imzalar: Dict[str, Dict] = {}
        self._dm_imza_lck = threading.Lock()
        self.gonderim_hatasi = 0
        self.gonderilen_alarm = 0
        # Son can_send çağrısının engel sebebi (None = engel yok). Çağıran taraf
        # "gönderilemedi" durumunu bundan ayırt eder (kuyruk için gerekli).
        self._son_engel = None
        # --- gönderim sağlığı (heartbeat) ---
        # "Yaşıyor ama hiçbir şey gönderemiyor" durumu dışarıdan görünmeli.
        self.son_basarili_gonderim = None   # ISO (İstanbul)
        self.son_gonderme_hatasi = None     # son hata metni
        self.kanal_hatasi = 0               # public kanal gönderim hatası
        self.retry_bekleme_sn = 1.0         # testlerde 0'a çekilir
        self._gunluk_sayac = 0
        # Gün/saat sınırları İstanbul'a göre (naive now() UTC sunucuda 03:00 sıfırlaması yapıyordu).
        self._gunluk_tarih = datetime.now(ISTANBUL_TZ).date()
        self._kap_uyarildi = False
        # C4: dosyalar doğrudan DATA_DIR'e (eskiden DATA_DIR'ın ebeveyni + "bot_data"
        # sabitleniyordu; DATA_DIR repo dışına çıkınca yol tutarsız kalıyordu).
        self._cooldown_dosya = os.path.join(DATA_DIR, "telegram_soguma.json")
        self._kap_dosya = os.path.join(os.path.dirname(self._cooldown_dosya), "telegram_kap.json")
        self._cooldown_yukle()
        self._kap_yukle()
        # --- engellenen acil olay kuyruğu (Batch 5 / B4) ---
        # Neden: cooldown/kap yüzünden gönderilemeyen teyitli olaylar kaybolmasın.
        # Engel digest saatinden önce kalkarsa gönderilir; kapanıştan sonra kalanlar
        # ayrı push yapılmaz, 18:45 DM özetine eklenir (main loop zaman kapısı).
        # Live alerts now use a durable, event-locked text+album FIFO.
        from notification_delivery import DeliveryOutbox
        self._delivery = DeliveryOutbox(self, DATA_DIR)
        self._grafik_kuyruk: List[dict] = []
        self._grafik_gonderim_lck = threading.Lock()
        self._acil_kuyruk: List[dict] = []  # en eski kayıt önce
        self._kuyruk_dosya = os.path.join(os.path.dirname(self._cooldown_dosya),
                                          "telegram_acil_kuyruk.json")
        self.kuyruk_gonderildi = 0
        self.kuyruk_zaman_asimi = 0
        self.kuyruk_tasmasi = 0
        self._kuyruk_yukle()
        # Legacy picture-only adapters remain for explicit command/test callers.
        # They are not the live alert delivery path; that is self._delivery.
        self._grafik_lck = threading.Lock()
        self._son_grafik_ts = None
        self._grafik_supuruldu = False   # bayat dosya süpürmesi süreçte bir kez
        self.grafik_gonderilen = 0
        self.grafik_atlanan_hata = 0
        self.grafik_atlanan_kota = 0
        self.grafik_atlanan_baglam = 0   # „bağlam değişmedi" güncellemesi → kare yok
        self.grafik_olay = 0             # grafik açıkken gönderilmiş alarm kartı
        self.grafik_olay_karesiz = 0     # açıkken köprüden kare alamayan alarm kartı
        self.grafik_kopru_hata = 0
        self.grafik_son_neden = None
        self.grafik_toplam_ms = 0
        self.grafik_kare_sayisi = 0
        # --- tek-seferlik olay hafızası (repeat-guard) ---
        # Neden: motor tam_yeniden=True ile pencereyi her taramada baştan oynatır;
        # terminal/acil state'ler her tur yeniden üretilir ve eski tek koruma
        # (4 saatlik zaman cooldown'ı) dolunca AYNI olay tekrar basılıyordu
        # (örn. 4h TF'de 1 bar = 4 saat = cooldown süresi).
        # Mühür (hisse+TF+state) başına son bildirilen İstanbul GÜNÜNÜ tutar:
        # aynı gün içinde aynı olay bir kez bildirilir; state ilerlemesi
        # (TEYITLI -> RETEST -> TAMAMLANDI) serbest kalır; yeni gün tekrar
        # haberdar. Slot sıfırlama (flicker) mühürü silmez. Kalıcıdır:
        # Supabase "state:telegram_son_alerts" + disk (eski düz-string biçimi
        # açılışta yeni biçime taşınır).
        self._son_alert: Dict[str, dict] = {}
        self._son_alert_dosya = os.path.join(DATA_DIR, "telegram_son_alerts.json")
        self._son_alert_yukle()

        try:
            from config import PUBLIC_MIN_QUALITY, PUBLIC_STATES, PUBLIC_SIKISMA_MIN_CONTRACTION
            self.public_min_quality = PUBLIC_MIN_QUALITY
            # Public anlık bildirim de yalnızca kapanışla doğrulanan olayları
            # alır; eski/env kaynaklı attempt/fail/wait/complete state'leri
            # public kuyruğa yanlışlıkla taşınamaz.
            self.public_states = set(PUBLIC_STATES) & CONFIRMED_PUBLIC_STATES
            self.public_sikisma_min = PUBLIC_SIKISMA_MIN_CONTRACTION
        except Exception:
            self.public_min_quality = 0
            self.public_states = set(CONFIRMED_PUBLIC_STATES)
            self.public_sikisma_min = 0.80
        # TF bazlı public eşik: DM alarm eşikleriyle AYNI (tek kaynak ALERT_MIN_QUALITY);
        # `public_min_quality` sıfırdan büyükse ek taban olarak uygulanır.
        try:
            self.public_min_quality_tf = {str(k).lower(): float(v)
                                          for k, v in dict(PUBLIC_MIN_QUALITY_TF).items()}
        except Exception:
            self.public_min_quality_tf = dict(ALERT_MIN_QUALITY)

        # --- PUBLIC (grup) kuyruğu: olaylar tarama turu boyunca toplanır, tur
        # sonunda TEK bülten olarak gönderilir (mum kapanışında 9 ayrı mesaj
        # yerine 1 mesaj). Bütçe DM'den ayrıdır: grup için saatte/günde sınır.
        self._public_kuyruk: List[dict] = []
        self._public_alert_markers: Dict[str, str] = {}
        self._public_lck = threading.Lock()
        self._public_saatlik: List[datetime] = []
        self._public_gun_sayac = 0
        self._public_gun = datetime.now(ISTANBUL_TZ).date()
        self._son_public_ts = None
        self.public_max_saatlik = PUBLIC_MAX_MESAJ_SAAT
        self.public_max_gunluk = PUBLIC_MAX_MESAJ_GUN
        self.public_min_aralik_sn = PUBLIC_MIN_ARALIK_SN
        self.public_kuyruk_limit = 40
        self.public_gonderilen = 0
        self.public_hatasi = 0
        self.public_engel = 0
        self.public_kuyruk_tasmasi = 0
        self.son_public_gonderim = None

        self.public_enabled = bool(self.token and self.public_chat_id)
        # GÖREV 6 (A10): Telegram sayaç ayrımı — alert/watch/digest/command
        # Mevcut alert/watch/digest/command ayrımını bozmayacak şekilde eklenir.
        # send_text() içeriğine göre kategorize edilir; mevcut çağrı noktaları değişmeden çalışır.
        self.command_sayac = 0        # /durum, /ozet, /karne gibi komut yanıtları
        self.digest_sayac = 0         # 18:45 digest (WATCH_STATES) — not: bu ayrı bir mekanizma,
        # ancak notifier üzerinden gönderilen digest parçaları için sayılır.
        self.alert_sayac = 0          # ALERT_STATES (anlık push) — mevcut _gunluk_sayac ile paralel
        # Kanal hedefi doğrulamasının önbelleği (main açılışta bir kez doldurur;
        # heartbeat ağa çıkmadan bunu okur).
        self.public_hedef_bilgi: Dict = {}
        # Restart gün sürekliliği: bütçe sayaçları ve gönderilememiş kuyruk
        # (canlı denetimde ölçüldü: restart'ta ikisi de sıfırlanıyordu -> günlük
        # tavan aşılabiliyor ve bültendeki olaylar sessizce kayboluyordu).
        self._public_durum_yukle()
        if not self.token:
            logger.warning("Telegram token env'de yok - notifier pasif (test modu)")
            self.enabled = False
        elif not self.chat_id:
            # DM kapalı ama public hedef tanımlı: grup yayını DM olmadan çalışır.
            logger.info("TELEGRAM_CHAT_ID yok: DM kapalı, public hedef (%s) yayında",
                        self.public_chat_id or "-")
            self.enabled = False
        else:
            if self.public_enabled:
                logger.info(f"Telegram public hedef aktif: {self.public_chat_id} (DM + public)")
            if not token_bicimi_uygun_mu(self.token):
                logger.warning("Telegram token biçimi uygun değil (beklenen 123456789:AA...). Kontrol et.")
            self.enabled = True
            logger.info("Telegram notifier aktif - insanlaştırma V2 + kanal")

    def _gonderim_sagligi_kaydet(self, basari: bool, hata: str = "") -> None:
        """Son başarılı/başarısız gönderimi işaretle (heartbeat ve /durum okur).

        Neden: token yanlış/eksikken veya ağ sürekli hata veriyorken bot
        "çalışıyor" görünüyordu; dışarıdan "hiç mesaj gitmiyor" durumu
        görülemiyordu.
        """
        if basari:
            self.son_basarili_gonderim = datetime.now(ISTANBUL_TZ).isoformat()
        else:
            self.gonderim_hatasi += 1
            self.son_gonderme_hatasi = str(hata or "bilinmeyen hata")[:200]

    def send_text(self, text: str, deneme: int = 2):
        """Düz metin gönderir (özet, komut yanıtı, /test).

        - Telegram'ın 4096 karakter sınırına karşı metin `kirp()` ile kısaltılır;
          eskiden uzun bir özet sessizce HTTP 400 alabiliyordu.
        - Geçici hatada (ağ hatası, 5xx, 429) bir kez daha denenir; 4xx kalıcı
          hatalar (403 engel, 400 bozuk istek) tekrar denenmez.
        """
        if not self.enabled:
            return False, "Telegram notifier pasif (token/chat_id env'de yok)"

        from telegram_commands import kirp  # döngüsel import yok: telegram_commands notifier'ı import etmez
        # Satır bütçesi burada, tek noktadan: özetler, sistem uyarıları, /test ve
        # karne aynı yolu kullanıyor ve 300-600 px'lık satırlarla telefonda
        # dağılıyordu. Alarm yolu (``_gonder``) burada DEĞİL: kart satırlarını
        # kendi üretirken bütçeliyor, klasik stil ise eski haliyle kalmalı.
        govde = kirp(metni_sigdir(text, guvenlik=1.0))
        deneme = max(1, int(deneme))
        son_hata = ""
        for i in range(deneme):
            try:
                import requests
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": govde},
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._gonderim_sagligi_kaydet(basari=True)
                    # GÖREV 6 (A10): Telegram sayaç ayrımı — içerik tabanlı kategorize
                    # Mevcut alert/watch/digest/command ayrımını bozmaz; sadece sayaçları ayırır.
                    # Heuristik: mesaj içeriğine göre kategori belirlenir.
                    metin_kucuk = (govde or "").lower()
                    if "📊" in metin_kucuk or "📋" in metin_kucuk or "📈" in metin_kucuk or "haftalık" in metin_kucuk:
                        self.digest_sayac += 1  # Digest / WATCH_STATES (18:45 özet)
                    elif "/durum" in metin_kucuk or "/ozet" in metin_kucuk or "/karne" in metin_kucuk or "/yardim" in metin_kucuk:
                        self.command_sayac += 1  # Komut yanıtı
                    elif any(x in metin_kucuk for x in ["formasyon", "üçgen", "kema", "bayrak", "flama", "kırılım", "retest", "tamamlanma"]):
                        self.alert_sayac += 1  # ALERT_STATES (anlık formasyon bildirimi)
                    else:
                        # Diğer mesajlar (genel duyuru, hata, vb.) mevcut alert sayacına eklenir
                        # (mevcut davranış korunur)
                        pass
                    # Ana günlük/saatlik sayaç (mevcut budget) alert için korunur;
                    # diğer kategoriler ayrı sayaçta takip edilir.
                    return True, "mesaj gonderildi"
                # Önce maskele, sonra kırp: ipucu metni ham yanıtın kesitini taşıyor;
                # token 200. karakterden sonra başlıyorsa kırpma secret'ı korumazdı.
                ipucu = telegram_hata_ipucu(resp.status_code,
                                             redact_sensitive_text(resp.text, self.token))
                son_hata = (f"HTTP {resp.status_code}: "
                            f"{redact_sensitive_text(resp.text, self.token)[:200]} | {ipucu}")
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    break  # kalıcı hata: tekrar denemek anlamsız
                logger.warning(f"Telegram gönderimi başarısız (deneme {i + 1}/{deneme}): HTTP {resp.status_code}")
            except Exception as e:
                son_hata = f"istek hatasi: {e}"[:200]
                logger.warning(f"Telegram gönderim hatası (deneme {i + 1}/{deneme}): {e}")
            if i + 1 < deneme and self.retry_bekleme_sn > 0:
                time.sleep(self.retry_bekleme_sn)
        self._gonderim_sagligi_kaydet(basari=False, hata=son_hata)
        return False, son_hata

    def check_connection(self) -> bool:
        if not self.enabled:
            return False
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{self.token}/getMe", timeout=10
            )
            if resp.status_code == 200:
                username = (resp.json().get("result") or {}).get("username", "?")
                logger.info(f"Telegram bağlantısı OK (bot: @{username}, chat_id: {self.chat_id})")
                return True
            ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
            logger.error("Telegram token/chat_id reddedildi: HTTP %s %s | %s",
                         resp.status_code, redact_sensitive_text(resp.text, self.token)[:200], ipucu)
        except Exception as e:
            logger.error(f"Telegram bağlantı hatası (token yanlış olabilir): {e}")
        return False

    def check_public_connection(self) -> Dict:
        """Public hedefi (kanal/grup) açılışta doğrular ve önbelleğe alır.

        NEDEN: canlıdaki en olası hata "bot kanalda yönetici değil / mesaj
        gönderme izni kapalı". Bu durumda her gönderim 403 döner ve kullanıcı
        sebebi ancak loglara bakınca anlar. Açılışta tek isteklerle kontrol
        edilir, sonuç heartbeat'e yazılır (`public_hedef`).
        Döner: {"hedef","baslik","tip","yonetici","can_post","hata"} (ağ hatası
        botu durdurmaz, hata alanına yazılır).
        """
        bilgi: Dict = {"hedef": self.public_chat_id, "baslik": None, "tip": None,
                       "yonetici": None, "can_post": None, "hata": ""}
        if not self.public_enabled:
            bilgi["hata"] = "public hedef tanımlı değil"
            self.public_hedef_bilgi = bilgi
            return bilgi
        try:
            import requests
            temel = f"https://api.telegram.org/bot{self.token}"

            def _cagri(method, **params):
                yanit = requests.post(f"{temel}/{method}", json=params, timeout=10)
                veri = yanit.json() if yanit.status_code == 200 else {}
                return veri.get("result") if veri.get("ok") else None, yanit

            ben, _ = _cagri("getMe")
            sohbet, yanit = _cagri("getChat", chat_id=self.public_chat_id)
            if sohbet is None:
                ipucu = telegram_hata_ipucu(yanit.status_code,
                                     redact_sensitive_text(getattr(yanit, "text", ""), self.token))
                bilgi["hata"] = f"getChat başarısız ({getattr(yanit, 'status_code', '?')}) {ipucu}"
                logger.error(
                    "❌ Public hedef doğrulanamadı (%s): %s. Kanal/grup kimliğini ve botun "
                    "hedefe eklenmiş olduğunu kontrol et.", self.public_chat_id, bilgi["hata"])
                self.public_hedef_bilgi = bilgi
                return bilgi
            bilgi["baslik"] = sohbet.get("title") or sohbet.get("username")
            bilgi["tip"] = sohbet.get("type")
            uye, _ = _cagri("getChatMember", chat_id=self.public_chat_id,
                            user_id=(ben or {}).get("id"))
            durum = str((uye or {}).get("status") or "")
            bilgi["yonetici"] = durum in ("administrator", "creator")
            # Kanallarda 'can_post_messages' alanı; gruplarda yokluğu "serbest" demek.
            bilgi["can_post"] = bool((uye or {}).get("can_post_messages")) or (
                bilgi["tip"] != "channel" and bilgi["yonetici"])
            if bilgi["tip"] == "channel" and not bilgi["can_post"]:
                logger.error(
                    "❌ Public hedef '%s' bir KANAL ve bot yönetici değil ya da 'Mesaj "
                    "gönderme' izni kapalı. Kanal → Yöneticiler → bot → Mesaj gönderme.",
                    bilgi["baslik"])
            else:
                logger.info("✅ Public hedef doğrulandı: %s (%s) · yönetici=%s · mesaj gönderme=%s",
                            bilgi["baslik"], bilgi["tip"], bilgi["yonetici"], bilgi["can_post"])
        except Exception as exc:  # noqa: BLE001 - ağ hatası botu durdurmaz
            bilgi["hata"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Public hedef doğrulanamadı (ağ): %s", bilgi["hata"])
        self.public_hedef_bilgi = bilgi
        return bilgi

    def should_send_to_public(self, data: Dict) -> bool:
        """Public kanala gönderilsin mi? (DM'den bağımsız filtre)

        Kural bugün iki koşula bakar: state `PUBLIC_STATES` içinde olacak ve
        kalite `PUBLIC_MIN_QUALITY` üstünde olacak.

        NOT: Eskiden burada `SIKISMA_GUCLENIYOR` için "daralma >= eşik ise
        gönderilebilir" gibi görünen bir dal vardı ama iki yolda da `False`
        dönüyordu (ölü kod). Kanal davranışı KİMSENİN onayı olmadan
        değiştirilmesin diye dal kaldırıldı: sıkışma adaylarını kanalda görmek
        istersen `PUBLIC_STATES` env'ine `SIKISMA_GUCLENIYOR` ekle (günlük
        özetteki daralma eşiği `PUBLIC_SIKISMA_MIN_CONTRACTION` ayrıca geçerli).
        """
        state = data.get('state', '')
        quality = data.get('confidence_score', 0)
        if state not in CONFIRMED_PUBLIC_STATES or state not in self.public_states:
            return False
        try:
            q = float(quality or 0)
        except (TypeError, ValueError):
            return False
        tf = str(data.get('timeframe') or '').lower()
        esik = self.public_min_quality_tf.get(tf, ALERT_MIN_QUALITY_GLOBAL)
        try:
            esik = max(float(esik), float(self.public_min_quality or 0))
        except (TypeError, ValueError):
            pass
        return q >= esik

    # --- PUBLIC (grup) gönderim yolu ------------------------------------
    # DM yolundan tamamen bağımsızdır: kendi bütçesi, kendi sayaçları, kendi
    # hata durumu vardır. DM kapalıyken de çalışır.

    @staticmethod
    def _public_event_key(data: Dict) -> str:
        """Kalıcı public tekrar mührü: aynı formation/state ikinci bültene girmez."""
        formation_id = str(data.get("formation_id") or "").strip()
        if not formation_id:
            return ""
        stock = str(data.get("stock_name") or "").strip().upper()
        timeframe = str(data.get("timeframe") or "").strip().lower()
        state = str(data.get("state") or "").strip().upper()
        if not stock or not timeframe or state not in CONFIRMED_PUBLIC_STATES:
            return ""
        return f"{stock}|{timeframe}|{state}|{formation_id}"

    def _public_alert_muhurlerini_temizle(self, now=None) -> bool:
        """7 günden eski public event mühürlerini buda; harita sınırlı kalsın."""
        now = now or datetime.now(ISTANBUL_TZ)
        degisti = False
        for key, raw_time in list(self._public_alert_markers.items()):
            try:
                sent_at = _istanbul(datetime.fromisoformat(str(raw_time)))
            except (TypeError, ValueError):
                del self._public_alert_markers[key]
                degisti = True
                continue
            age_hours = (now - sent_at).total_seconds() / 3600.0
            if age_hours < 0 or age_hours >= _FORMATION_ALERT_MUHR_TTL_SAAT:
                del self._public_alert_markers[key]
                degisti = True
        return degisti

    def _public_durum_yukle(self) -> None:
        """Aynı güne ait public bütçe, kuyruk ve olay mühürlerini geri yükler."""
        try:
            veri = _state_persistence.gunluk_durum_yukle() or {}
        except Exception as hata:  # noqa: BLE001
            logger.debug("Public günlük durum okunamadı: %s", hata)
            return
        public = veri.get("public") or {}
        if not isinstance(public, dict):
            return
        raw_markers = public.get("alert_muhurlari")
        if isinstance(raw_markers, dict):
            self._public_alert_markers = {
                str(key): str(value) for key, value in raw_markers.items()
                if key and value
            }
        markers_changed = self._public_alert_muhurlerini_temizle()
        try:
            self._public_gun_sayac = int(public.get("gun_sayac") or 0)
        except (TypeError, ValueError):
            self._public_gun_sayac = 0
        saatlik = []
        for damga in list(public.get("saatlik_ts") or []):
            try:
                saatlik.append(datetime.fromisoformat(str(damga)))
            except (TypeError, ValueError):
                continue
        self._public_saatlik = saatlik
        kuyruk = public.get("kuyruk")
        if isinstance(kuyruk, list):
            temiz = [k for k in kuyruk if isinstance(k, dict)
                     and k.get("stock_name")
                     and str(k.get("state") or "").strip().upper() in CONFIRMED_PUBLIC_STATES
                     and str(k.get("state") or "").strip().upper() in self.public_states]
            if temiz:
                self._public_kuyruk = temiz[:self.public_kuyruk_limit]
                logger.info("Public kuyruk restart'tan geri yüklendi: %d olay", len(self._public_kuyruk))
            if len(temiz) != len(kuyruk):
                logger.info("Public kuyruktan yeni politikaya kapalı %d eski olay temizlendi",
                            len(kuyruk) - len(temiz))
                self._public_durum_kaydet()
        if markers_changed:
            self._public_durum_kaydet()
        if self._public_gun_sayac or self._public_kuyruk:
            logger.info("Public günlük bütçe geri yüklendi: %d/%d gönderim (kuyruk %d)",
                        self._public_gun_sayac, self.public_max_gunluk,
                        len(self._public_kuyruk))

    def _public_durum_kaydet(self) -> None:
        """Public bütçe + kuyruğu GÜN damgalı yazar (I/O hatası gönderimi bozmaz)."""
        try:
            with self._public_lck:
                self._public_alert_muhurlerini_temizle()
                kuyruk = [dict(k) for k in self._public_kuyruk]
                markers = dict(self._public_alert_markers)
            _state_persistence.gunluk_durum_guncelle({"public": {
                "gun_sayac": self._public_gun_sayac,
                "saatlik_ts": [t.isoformat() for t in self._public_saatlik],
                "kuyruk": kuyruk,
                "alert_muhurlari": markers,
            }})
        except Exception as hata:  # noqa: BLE001
            logger.debug("Public günlük durum yazılamadı: %s", hata)

    def _public_gun_sifirla_gerekirse(self, simdi: datetime) -> None:
        if simdi.date() != self._public_gun:
            self._public_gun = simdi.date()
            self._public_gun_sayac = 0
            self._public_saatlik = []
            self._public_durum_kaydet()

    def _public_kap_gec(self) -> bool:
        """Saatlik/günlük public bütçesi müsait mi? (DM kapılarından AYRI)"""
        simdi = datetime.now(ISTANBUL_TZ)
        self._public_gun_sifirla_gerekirse(simdi)
        self._public_saatlik = [t for t in self._public_saatlik
                                if (simdi - t).total_seconds() < 3600]
        if self._public_gun_sayac >= self.public_max_gunluk:
            return False
        if len(self._public_saatlik) >= self.public_max_saatlik:
            return False
        return True

    def _public_pace(self) -> None:
        """Sohbet başına ~1 mesaj/sn kuralı: aynı flush içinde kısa bekleme."""
        try:
            ara = float(self.public_min_aralik_sn or 0)
        except (TypeError, ValueError):
            ara = 0.0
        if ara <= 0 or self._son_public_ts is None:
            return
        bekle = ara - (time.monotonic() - self._son_public_ts)
        if bekle > 0:
            time.sleep(min(bekle, 5.0))

    def send_to_public(self, text: str, deneme: int = 1) -> bool:
        """Grup/kanal hedefine gönderir: bütçe + pacing + 429 retry + kırpma."""
        if not self.public_enabled:
            logger.info(f"[MOCK PUBLIC] {text[:120]}")
            return True
        if not self._public_kap_gec():
            self.public_engel += 1
            logger.warning("Public bütçe dolu (saatlik %d / günlük %d) - gönderim atlandı",
                           self.public_max_saatlik, self.public_max_gunluk)
            return False
        govde = _kirp(metni_sigdir(text, guvenlik=1.0))
        try:
            import requests
            self._public_pace()
            for deneme_no in range(max(0, int(deneme)) + 1):
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.public_chat_id, "text": govde},
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._son_public_ts = time.monotonic()
                    self._public_saatlik.append(datetime.now(ISTANBUL_TZ))
                    self._public_gun_sayac += 1
                    self.public_gonderilen += 1
                    self.son_public_gonderim = datetime.now(ISTANBUL_TZ).isoformat()
                    self._public_durum_kaydet()
                    logger.info("Telegram public hedefe gönderildi: %s", self.public_chat_id)
                    return True
                if resp.status_code == 429 and deneme_no < max(0, int(deneme)):
                    bekle = 3.0
                    try:
                        bekle = float((resp.json().get("parameters") or {}).get("retry_after") or bekle)
                    except Exception:
                        pass
                    logger.warning("Public 429: %.0f sn sonra tekrar denenecek", bekle)
                    time.sleep(max(0.0, min(bekle, 20.0)))
                    continue
                ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
                logger.error("Telegram public hata: %s | %s",
                             redact_sensitive_text(resp.text, self.token)[:200], ipucu)
                break
            self.public_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata="public: gönderim başarısız")
            return False
        except Exception as e:
            logger.error("Telegram public gönderim hatası: %s", e)
            self.public_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata=f"public: {e}")
            return False

    def send_to_channel(self, text: str) -> bool:
        """Geriye dönük ad: eski kanal çağrıları artık public yola düşer."""
        return self.send_to_public(text)

    def public_kuyruk(self, data: Dict) -> bool:
        """Uygun olayı public kuyruğa alır (gönderim tarama turu sonunda)."""
        if not self.public_enabled:
            return False
        try:
            if not self.should_send_to_public(data):
                return False
        except Exception as exc:  # noqa: BLE001 - kuyruk hatası taramayı durdurmasın
            logger.debug("Public filtre hatası: %s", exc)
            return False
        if self._delivery.public_duplicate(data):
            return False
        kayit = {k: data.get(k) for k in (
            "stock_name", "timeframe", "pattern_name", "state", "confidence_score",
            "critical_price_level", "break_price", "break_dir", "contraction", "bar_metni",
            "candle_close_price", "upper_touches", "lower_touches", "formation_id")}
        anahtar = (str(kayit["stock_name"] or "").upper(),
                   str(kayit["timeframe"] or "").lower(),
                   str(kayit["state"] or "").strip().upper())
        event_key = self._public_event_key(kayit)
        # Kanal/grup: "geçersizleşti" YALNIZCA önceki teyitli mesaj gerçekten bu
        # kanala gittiyse gider. Kanalda görmemiş bir teyidin geri alınması
        # okuyucu için anlamsızdır ve "geçersiz geçersiz" gidip gelmesi üretir.
        # DM tarafı bu kapıdan etkilenmez (oradaki seri kendi içinde okunur).
        if (TELEGRAM_KANAL_GECERSIZ_KAPISI
                and str(kayit.get("state") or "").strip().upper() == "KIRILIM_GECERSIZLESTI"):
            teyit_key = self._public_event_key({**kayit, "state": "KIRILIM_TEYITLI"})
            onek = "%s|%s|KIRILIM_TEYITLI|" % (
                str(kayit.get("stock_name") or "").strip().upper(),
                str(kayit.get("timeframe") or "").strip().lower())
            with self._public_lck:
                gonderilmis = bool(
                    (teyit_key and teyit_key in self._public_alert_markers)
                    or any(str(k).startswith(onek) for k in self._public_alert_markers)
                )
            if not gonderilmis:
                logger.info("Public geçersizleşme atlandı (%s): önceki teyitli mesaj bu "
                            "kanala gönderilmemiş", onek.rstrip("|"))
                return False
        with self._public_lck:
            self._public_alert_muhurlerini_temizle()
            if event_key and event_key in self._public_alert_markers:
                return False
            for queued in self._public_kuyruk:
                if event_key:
                    if self._public_event_key(queued) == event_key:
                        return False
                elif (str(queued.get("stock_name") or "").upper(),
                      str(queued.get("timeframe") or "").lower(),
                      str(queued.get("state") or "").strip().upper()) == anahtar:
                    return False
            if len(self._public_kuyruk) >= self.public_kuyruk_limit:
                self.public_kuyruk_tasmasi += 1
                logger.warning("Public kuyruk dolu (%d) - olay atıldı: %s",
                               self.public_kuyruk_limit, anahtar)
                return False
            self._public_kuyruk.append(kayit)
        self._public_durum_kaydet()
        self._delivery.remember_public(data)
        return True

    def public_bosalt(self, azami: int = 12) -> int:
        """Kuyruğu tek bülten(ler) halinde gönderir; engel varsa kayıtlar bekler."""
        with self._public_lck:
            original_count = len(self._public_kuyruk)
            self._public_kuyruk = [
                kayit for kayit in self._public_kuyruk
                if str(kayit.get("state") or "").strip().upper() in CONFIRMED_PUBLIC_STATES
                and str(kayit.get("state") or "").strip().upper() in self.public_states
            ]
            queue_changed = len(self._public_kuyruk) != original_count
            kuyruk = list(self._public_kuyruk)
        if queue_changed:
            self._public_durum_kaydet()
        if not kuyruk or not self.public_enabled:
            return 0
        gonderilen = 0
        basarili_kayitlar = []
        kalan = list(kuyruk)
        while kalan:
            parca = kalan[:max(1, int(azami))]
            metin = self.format_public_batch(parca)
            if not metin:
                kalan = kalan[len(parca):]
                continue
            if not self.send_to_public(metin):
                # Bütçe/ağ engeli: kayıtlar kuyrukta kalır, sonraki turda denenir.
                break
            gonderilen += len(parca)
            basarili_kayitlar.extend(parca)
            kalan = kalan[len(parca):]
        if gonderilen:
            damga = datetime.now(ISTANBUL_TZ).isoformat()
            with self._public_lck:
                self._public_kuyruk = self._public_kuyruk[gonderilen:]
                for kayit in basarili_kayitlar:
                    event_key = self._public_event_key(kayit)
                    if event_key:
                        self._public_alert_markers[event_key] = damga
                self._public_alert_muhurlerini_temizle()
            self._public_durum_kaydet()
            logger.info("Public bülten gönderildi: %d olay (%d mesaj)",
                        gonderilen, max(1, (gonderilen + azami - 1) // azami))
        return gonderilen

    def format_public_batch(self, kayitlar: List[Dict]) -> str:
        """Grup sürümü bülten: sade satırlar, iç izleme notu ve kuyruk yok."""
        kayitlar = [
            k for k in (kayitlar or [])
            if isinstance(k, dict)
            and str(k.get("state") or "").strip().upper() in CONFIRMED_PUBLIC_STATES
        ]
        if not kayitlar:
            return ""
        # Başlık eskiden "📊 Formasyon bülteni · 25 Eyl 10:40 · 2 gelişme" idi:
        # ~300 px ile satır bütçesini aşıp son kelimeyi kaydırıyordu. Etiket
        # kısaltıldı; tarih ve gelişme sayısı (veri) aynen duruyor.
        # Başlık iki kısa satır: tek satıra tarih + sayıyı dizmek 278-300 px
        # edip son kelimeyi kaydırıyordu. Kelimeler ("gelişme") aynen korunur.
        satirlar = [f"📊 Bülten · {len(kayitlar)} gelişme",
                    f"   {_tr_tarih(datetime.now(ISTANBUL_TZ))}"]
        # Olay BAŞINA kısa satırlar. Eskiden her gelişme tek satıra diziliyordu
        # (1 095-1 160 px → telefonda 3-4 satıra sarıp okunmaz oluyordu) ve fiyat
        # noktalı (407.17) yazılıyordu; DM kartı virgül kullanıyor.
        # Olay etiketleri DM kartıyla AYNI sözlüğü kullanır: kanal okuyucusu da
        # "kapanışla teyitli" der, "önceki teyitli kırılım geçersizleşti" gibi
        # cümle kurmaz (cümle 1 160 px'lik saran satır üretiyordu).
        _bulleten_olay = {
            "KIRILIM_TEYITLI": "kapanışla teyitli",
            "RETEST_BASARILI": "kapanışla retest başarılı",
            "KIRILIM_GECERSIZLESTI": "teyit geçersizleşti",
        }
        for k in kayitlar:
            stock = str(k.get("stock_name") or "?")
            tf = TF_KISA.get(str(k.get("timeframe") or "").lower(),
                             TF_HUMAN.get(k.get("timeframe"), str(k.get("timeframe") or "")))
            pattern = str(k.get("pattern_name") or "Formasyon")
            state = str(k.get("state") or "").strip().upper()
            etiket = _bulleten_olay.get(state) or PUBLIC_STATE_ETIKET.get(
                state, STATE_TR.get(state, state))
            yon = _yon_kisa(k.get("break_dir"))
            _satir(satirlar, f"{PATTERN_EMOJI.get(pattern, '📈')} {stock} {tf} · {pattern}")
            govde = [f"{yon + ' ' if yon else ''}{etiket}"]
            seviye = k.get("critical_price_level") or k.get("break_price")
            govde.append(_sayı(seviye) if seviye else "")
            _satir(satirlar, "   " + " · ".join(p for p in govde if p), girinti="   ")
            kapanis = _sayı(k.get("candle_close_price"))
            ust_t, alt_t = k.get("upper_touches"), k.get("lower_touches")
            temas = f"temas {ust_t}/{alt_t}" if ust_t is not None and alt_t is not None else ""
            kalite = _sayı(float(k.get("confidence_score") or 0), 0)
            satir3 = " · ".join(p for p in ((f"kapanış {kapanis}" if kapanis else ""),
                                            (f"kalite {kalite}" if kalite else ""), temas) if p)
            if satir3:
                _satir(satirlar, "   " + satir3, girinti="   ")
            damga = _kart_mum_damgasi(k)
            if damga:
                satirlar.append(f"   {damga}")
        satirlar.append("")
        satirlar.append("📌 yatırım tavsiyesi değildir")
        return metni_sigdir("\n".join(satirlar), guvenlik=1.0)

    def format_public_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None,
                              izleme: List[Dict] = None, karne_kisa: str = "",
                              tarama_turu=None, kapanis: bool = True) -> str:
        """Grup sürümü kapanış/sabah özeti: sayılar + izleme listesi, teknik döküm yok.

        `kapanis=False` (09:55 sabah notu): başlık ve izleme listesi başlığı değişir;
        dün akşam gönderilen kuyruk yerine o an İZLENEN adaylar listelenir; gün
        sıfırlandığı için "❌ bugün" satırı ve tarama sayısı yazılmaz.
        """
        simdi = datetime.now(ISTANBUL_TZ)
        aktif = [f for f in (aktif_formasyonlar or []) if isinstance(f, dict)]
        freshness_known = isinstance(gun_ozeti, dict) and "tam_tarama_guncel" in gun_ozeti
        scan_current = (bool(gun_ozeti.get("tam_tarama_guncel"))
                        if freshness_known else True)
        if freshness_known and not scan_current:
            aktif = []
            izleme = []
        # Başlık eskiden "📊 13 Eki 19:30 kapanış · BIST formasyon özeti" idi ve
        # 372 px ile sarmalanıyordu. Etiket öne, tarih alta taşınır: aynı kelime.
        # (Grup tarafında "kapanış/sabah notu" ayrımı başlıkta okunmaya devam eder.)
        baslik = (f"📊 BIST kapanış · {_tr_tarih(simdi)}" if kapanis
                  else f"📊 BIST sabah notu · {_tr_tarih(simdi)}")
        satirlar = [baslik]
        retest = [f for f in aktif if f.get('state') == 'RETEST_BASARILI']
        teyitli = [f for f in aktif if f.get('state') == 'KIRILIM_TEYITLI']
        sikisan = [f for f in aktif if f.get('state') == 'SIKISMA_GUCLENIYOR'
                   and (f.get('contraction') or 0) >= self.public_sikisma_min]
        if retest or teyitli:
            # İki sayaç ayrı satırda: birleşik hali 315 px'tı ve ortadan ikiye
            # düşüp "· ✅ Teyitli kırılım 2" satırını üretiyordu.
            satirlar.append(f"🎯 Retest başarılı {len(retest)}")
            satirlar.append(f"✅ Teyitli kırılım {len(teyitli)}")
        if sikisan:
            ilk = " · ".join(f"{f.get('stock_name')} {f.get('timeframe') or ''} "
                             f"(%{(f.get('contraction') or 0) * 100:.0f})" for f in sikisan[:3])
            satirlar.append(f"⚡ Sıkışan {len(sikisan)}: {ilk}")
        if not izleme and not kapanis:
            # Sabah: dün akşamki kuyruk çoktan tüketildi; o an izlenen adaylar
            # (sıkışma/olgunlaşma) kaliteye göre sıralanıp "bugünün listesi" olur.
            izleme = _public_izleme_adaylari(aktif, haric={f.get('stock_name') for f in sikisan})
        if izleme:
            satirlar.append("")
            basliklar = ("Yarının izleme listesi" if kapanis else "Bugünün izleme listesi")
            satirlar.append(f"📡 {basliklar} (ilk {min(5, len(izleme))})")
            for k in list(izleme)[:5]:
                if not isinstance(k, dict):
                    continue
                # Kartla aynı dil: "4s" + "q89". "4 saatlik · kalite 89" ikilisi
                # satırı 330 px'a çıkarıp her maddeyi ikiye bölüyordu.
                try:
                    from reporting.format import tf_kisa as _tf_kisa
                    tf = _tf_kisa(k.get('timeframe'))
                except Exception:
                    tf = TF_HUMAN.get(k.get('timeframe'), str(k.get('timeframe') or ''))
                try:
                    kalite = f" q{float(k.get('quality') or 0):.0f}"
                except (TypeError, ValueError):
                    kalite = ""
                satirlar.append(f"• {k.get('stock')} {tf} {k.get('pattern_name') or 'formasyon'}"
                                f"{kalite}")
        if not (retest or teyitli or sikisan) and not izleme:
            if freshness_known and not scan_current:
                satirlar.append("Bugün güncel tam tarama yok;")
                satirlar.append("   eski formasyonlar gösterilmedi.")
            else:
                # "…formasyon olmadı." 287 px'ti ve satır bütçesini aşınca cümlenin
                # ortasından bölünüyordu; kısa hali tek satıra sığıyor.
                satirlar.append("Bugün öne çıkan formasyon yok." if kapanis
                                else "Şu an izlenen formasyon yok.")
        try:
            tur = int(tarama_turu) if tarama_turu is not None else 0
        except (TypeError, ValueError):
            tur = 0
        satirlar.append("")
        # "…zaman dilimi · 4 tarama · gün yeni başlıyor" 470 px'lık tek satırdı.
        if tur:
            satirlar.append(f"📈 Gün: {tur} tarama")
        satirlar.append(f"   {len(ACTIVE_STOCKS)} hisse × {len(TF_HUMAN)} zaman dilimi")
        if not kapanis:
            satirlar.append("   gün yeni başlıyor")
        if freshness_known and kapanis:
            event_counts = _summary_lifecycle_counts(gun_ozeti)
            if event_counts:
                satirlar.append(event_counts)
        scan_line = _summary_last_full_scan(gun_ozeti)
        if scan_line:
            satirlar.append(scan_line)
        if karne_kisa:
            satirlar += ["", karne_kisa]
        satirlar.append("📌 yatırım tavsiyesi değildir")
        return metni_sigdir("\n".join(satirlar), guvenlik=1.0)

    def format_daily_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None) -> str:
        now = datetime.now(ISTANBUL_TZ)
        # Başlık iki satır: tek satırda 310 px'e çıkıp "· 02 Eki 20:05" kısmını
        # kaydırıyordu. Ayraç 30 çizgi 300 px ediyordu (24 = 240 px, sarmaz).
        baslik = f"📊 BIST Formasyon Özeti\n   {_tr_tarih(now)}\n"
        baslik += "─" * 24 + "\n"
        # Yalnızca doğrulanmış kırılım/retest ve yüksek sıkışma özetlenir.
        # Tamamlandı/başarısız/deneme state'leri scheduled Telegram özetine girmez.
        freshness_known = isinstance(gun_ozeti, dict) and "tam_tarama_guncel" in gun_ozeti
        scan_current = (bool(gun_ozeti.get("tam_tarama_guncel"))
                        if freshness_known else True)
        snapshot = [f for f in (aktif_formasyonlar or []) if isinstance(f, dict)]
        if freshness_known and not scan_current:
            snapshot = []
        retest = [f for f in snapshot if f.get('state') == 'RETEST_BASARILI']
        teyitli = [f for f in snapshot if f.get('state') == 'KIRILIM_TEYITLI']
        sikisan = [f for f in snapshot if f.get('state') == 'SIKISMA_GUCLENIYOR' and (f.get('contraction', 0) or 0) >= self.public_sikisma_min]
        # Madde biçimi /canli ile aynı: "HISSE TF DESEN q<KALİTE> · YÖN". Uzun
        # hali ("… · aşağı yön · kalite 88") 350 px edip her maddeyi ikiye
        # bölüyordu; 10 maddelik liste 20 satır oluyordu. Kelime kısalır,
        # veri (hisse/desen/TF/kalite/yön) aynen durur.
        def _madde(f, ek=""):
            tf = str(f.get("timeframe") or "")
            # Yön oku yalnız gerçek yönde basılır: sıkışanlarda "↔" gürültüydü ve
            # satırı 283 px sınırının üstüne taşıyordu.
            ok = "↑" if f.get("break_dir") == 1 else ("↓" if f.get("break_dir") == -1 else "")
            try:
                q = f"q{float(f.get('confidence_score') or 0):.0f}"
            except (TypeError, ValueError):
                q = ""
            # "·" ayraçları kaldırıldı: "• … · … · …" biçimi 350 px'ı aşıp her
            # maddeyi ikiye bölüyordu (10 madde = 20 satır). "•" kalır — liste
            # maddesi olarak okunması, satır sayısından daha önemli.
            return (f"• {ok} {f.get('stock_name')} {tf} {f.get('pattern_name')} {q} "
                    f"{ek}").replace("  ", " ").strip() + "\n"

        if teyitli:
            baslik += (f"\n✅ TEYİTLİ KIRILIM ({len(teyitli)}"
                       f"{' · ilk 3' if len(teyitli) > 3 else ''}):\n")
            for f in teyitli[:3]:
                baslik += _madde(f)
        if retest:
            baslik += (f"\n🎯 RETEST BAŞARILI ({len(retest)}"
                       f"{' · ilk 3' if len(retest) > 3 else ''}):\n")
            for f in retest[:3]:
                baslik += _madde(f)
        if sikisan:
            baslik += (f"\n⚡ SIKIŞANLAR ({len(sikisan)}"
                       f"{' · ilk 5' if len(sikisan) > 5 else ''}):\n")
            for f in sikisan[:5]:
                try:
                    yuzde = f"%{(float(f.get('contraction') or 0) * 100):.0f}"
                except (TypeError, ValueError):
                    yuzde = ""
                baslik += _madde(f, ek=yuzde + " ")
        if not (teyitli or retest or sikisan):
            if freshness_known and not scan_current:
                baslik += ("Güncel tam tarama yok;\n"
                           "   eski formasyonlar gösterilmedi.\n")
            else:
                baslik += "Şu an öne çıkan teyitli olay ya da sıkışma yok.\n"
        if gun_ozeti:
            # "432 hisse tarandı" = 48 hisse × 9 tarama; yanıltıcıydı.
            # Doğru okuma: kaç tur tarandı + evren büyüklüğü.
            try:
                tur = int(gun_ozeti.get("tarama_sayisi") or 0)
            except (TypeError, ValueError):
                tur = 0
            if tur <= 0:
                baslik += "\n📈 Gün: henüz tarama yapılmadı\n"
            else:
                # İki tasarlanmış satır: tek satır 435 px'a çıkıp ortadan ikiye
                # düşüyordu ("· 6 bildirim" havada kalıyordu).
                _adet = gun_ozeti.get('alerts_sent', 0)
                baslik += ("\n📈 Gün: " + (f"{tur} tarama" if tur else "tarama")
                           + (f" · {_adet} bildirim" if _adet else "") + "\n")
                baslik += (f"   {len(ACTIVE_STOCKS)} hisse × {len(TF_HUMAN)} "
                           f"zaman dilimi\n")
            if freshness_known:
                event_counts = _summary_lifecycle_counts(gun_ozeti)
                if event_counts:
                    baslik += event_counts + "\n"
        scan_line = _summary_last_full_scan(gun_ozeti)
        if scan_line:
            baslik += scan_line + "\n"
        baslik += "\n📌 yatırım tavsiyesi değildir"
        return metni_sigdir(baslik, guvenlik=1.0)

    def _kap_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_caps")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._kap_dosya):
                    return
                with open(self._kap_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            self._gunluk_sayac = int(ham.get("gunluk_sayac", 0))
            self._gunluk_tarih = datetime.fromisoformat(ham["gunluk_tarih"]).date()
            self._saatlik_zamanlar = [_istanbul(datetime.fromisoformat(t))
                                      for t in ham.get("saatlik", [])]
            logger.info(f"Telegram kap hafızası {kaynak} yüklendi: saatlik={len(self._saatlik_zamanlar)}, günlük={self._gunluk_sayac}")
        except Exception as e:
            logger.debug(f"Kap hafızası yüklenemedi (ilk çalışma olabilir): {e}")

    def _gonderim_kaydet(self):
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        self._saatlik_zamanlar.append(datetime.now(ISTANBUL_TZ))
        self._gunluk_sayac += 1
        self._kap_kaydet()

    def _kap_kaydet(self):
        payload = {
            "gunluk_sayac": self._gunluk_sayac,
            "gunluk_tarih": self._gunluk_tarih.isoformat(),
            "saatlik": [t.isoformat() for t in self._saatlik_zamanlar],
        }
        try:
            import json
            os.makedirs(os.path.dirname(self._kap_dosya), exist_ok=True)
            with open(self._kap_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Kap hafızası kaydedilemedi: {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_caps", payload)

    def _gunu_sifirla_gerekirse(self):
        bugun = datetime.now(ISTANBUL_TZ).date()
        if bugun != self._gunluk_tarih:
            self._gunluk_sayac = 0
            self._gunluk_tarih = bugun
            self._kap_uyarildi = False
            # Engel/hata sayaçları da günlüktür; yoksa /durum dünün engelini gösterir.
            self.engeller = dict(_ENGEL_SAYACLAR)
            self.gonderim_hatasi = 0
            self.gonderilen_alarm = 0

    def _dm_degisim_durumu(self, data: Dict) -> str:
        """'yeni' | 'guncelleme' — bağlam önceki kartla birebir aynıysa kısalt.

        Tam susturma YAPILMAZ: kopya olayı zaten mühür keser. Buradaki amaç,
        mührü farklı bir olaya değse bile (25 Eyl TOASO: 10:40 → 15:10, 35 satırın
        30'u aynı) değişmemiş 600-800 kr'luk bağlam bloğunu tekrar basmamak.
        """
        anahtar = _dm_anahtar(data)
        if not anahtar.strip("|"):
            return "yeni"
        if not isinstance(data.get("domain_bolumleri"), dict) or not data.get("domain_bolumleri"):
            return "yeni"        # bağlam zaten yok → kısaltılacak bir şey yok
        imza = _dm_imza(data)
        with self._dm_imza_lck:
            kayit = self._dm_imzalar.get(anahtar) or {}
        return "guncelleme" if str(kayit.get("imza") or "") == imza else "yeni"

    def _dm_imza_kaydet(self, data: Dict) -> None:
        anahtar = _dm_anahtar(data)
        if not anahtar.strip("|"):
            return
        with self._dm_imza_lck:
            self._dm_imzalar[anahtar] = {
                "imza": _dm_imza(data),
                "gun": datetime.now(ISTANBUL_TZ).date().isoformat(),
            }
            # Gün değişince imzalar düşer: ertesi gün aynı bağlam bile olsa yeni
            # bir seans bilgisidir.
            gunler = {v.get("gun") for v in self._dm_imzalar.values()}
            if len(gunler) > 1:
                guncel = datetime.now(ISTANBUL_TZ).date().isoformat()
                self._dm_imzalar = {k: v for k, v in self._dm_imzalar.items()
                                    if v.get("gun") == guncel}

    def _saatligi_temizle(self):
        sinir = datetime.now(ISTANBUL_TZ) - timedelta(hours=1)
        self._saatlik_zamanlar = [t for t in self._saatlik_zamanlar if t > sinir]

    def kap_durumu(self) -> Dict:
        self._saatligi_temizle()
        self._gunu_sifirla_gerekirse()
        return {
            "saatlik": len(self._saatlik_zamanlar),
            "saatlik_limit": self.max_saatlik,
            "gunluk": self._gunluk_sayac,
            "gunluk_limit": self.max_gunluk,
            # GÖREV 6 (A10): Ayrı kategori sayaçları — mevcut alert/watch/digest/command ayrımı korunur
            "alert_sayac": getattr(self, 'alert_sayac', 0),
            "watch_digest_sayac": getattr(self, 'digest_sayac', 0),
            "command_sayac": getattr(self, 'command_sayac', 0),
        }

    def _cooldown_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_cooldowns")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._cooldown_dosya):
                    return
                with open(self._cooldown_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            for k, iso in ham.items():
                # Eski kayıtlar naive olabilir; _istanbul ile normalize edilir.
                self.last_sent[k] = _istanbul(datetime.fromisoformat(iso))
            logger.info(f"Cooldown hafızası {kaynak} yüklendi: {len(ham)} kayıt")
        except Exception as e:
            logger.warning(f"Cooldown yüklenemedi (devam ediliyor): {e}")

    def _cooldown_kaydet(self):
        payload = {k: v.isoformat() for k, v in self.last_sent.items()}
        try:
            import json
            os.makedirs(os.path.dirname(self._cooldown_dosya), exist_ok=True)
            with open(self._cooldown_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=0)
        except Exception as e:
            logger.warning(f"Cooldown kaydedilemedi (devam ediliyor): {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_cooldowns", payload)

    def _cooldown_key(self, stock: str, pattern: str, timeframe: str, state: str) -> str:
        return f"{stock}_{pattern}_{timeframe}_{state}"

    # --- tek-seferlik olay hafızası (repeat-guard) --------------------------
    # Mühür (hisse + TF + state + varsa formation ID) anahtarlıdır. Kimliksiz
    # eski olaylar bar süresine göre TTL ile; yeni stable-ID olaylar 7 gün ile
    # sınırlandırılır. Üç kök neden düzeltildi:
    #   1) pattern anahtardan ÇİKARILDI: motor aynı slotta bazen "Simetrik
    #      Üçgen", bazen "Alçalan Üçgen" etiketi üretebiliyordu; iki farklı
    #      anahtar = iki ayrı mesaj (örn. PETKM 4h iki kez TAMAMLANDI).
    #   2) mühür "slot sıfırlama" ile siliniyordu; canlı geometri (has_pattern)
    #      kayan pencerede bir taramada False olup FORMASYON_YOK'a düştüğünde
    #      (flicker) mühür silinip aynı olay tekrar basılıyordu.
    #   3) bayatlık "İstanbul günü" ölçülüyordu; motor terminal formasyonu
    #      TERMINAL_TAZE_BAR bar taze tuttuğu için gün sınırını aşan formasyon
    #      (1 günlük grafikte 3 gün, 4 saatlikte ertesi sabah) tekrar
    #      bildiriliyordu. Artık TTL bar süresine göre ölçekleniyor.
    # Aynı hisse+TF+state, motorun aynı olay penceresi içinde en fazla BİR kez bildirilir.
    def _son_alert_key(self, stock: str, timeframe: str, state: str,
                       formation_id=None) -> str:
        """Olay anahtarı: hisse + TF + state; varsa formasyon kimliğiyle tekilleştir."""
        base = f"{stock}_{timeframe}_{state}"
        event_id = str(formation_id or "").strip()
        return f"{base}_formation_{event_id}" if event_id else base

    @classmethod
    def _muhr_gecerli_mi(cls, muhur, state: str, timeframe: str = "",
                         formation_id=None) -> bool:
        """Mühür hâlâ geçerliyse True (olay zaten bildirildi, tekrar basma).

        Formation ID varsa aynı teyitli olayı 7 gün boyunca tekilleştir; bu
        süre 1 günlük TF'deki retest tutunma penceresini de kapsar. Kimliksiz
        eski kayıtlar, geriye dönük uyum için bar süresi tabanlı TTL kullanır.
        """
        if not muhur or not isinstance(muhur, dict):
            return False
        if muhur.get("state") != state:
            return False
        incoming_id = str(formation_id or "").strip()
        stored_id = str(muhur.get("formation_id") or "").strip()
        if incoming_id and stored_id and incoming_id != stored_id:
            return False
        zaman = muhur.get("zaman")
        if not isinstance(zaman, str):
            return False
        try:
            basma = datetime.fromisoformat(zaman)
        except (TypeError, ValueError):
            return False
        if basma.tzinfo is None:
            basma = ISTANBUL_TZ.localize(basma)
        yas_saat = (datetime.now(ISTANBUL_TZ) - basma).total_seconds() / 3600.0
        ttl = (_FORMATION_ALERT_MUHR_TTL_SAAT
               if incoming_id and stored_id == incoming_id
               else _muhur_ttl_saat(muhur.get("tf") or timeframe))
        return 0 <= yas_saat < ttl

    @staticmethod
    def _muhur_kaydi(state: str, timeframe: str, gun: str = None,
                     zaman: str = None, formation_id=None) -> Dict:
        """Mühür kaydı üretir; oluşum kimliği varsa olay bazında saklar.

        Yeni mühür ŞU AN ile damgalanır. Yalnız ESKİ (gün bazlı) kayıtlar
        dönüştürülürken o günün 00:00'i kullanılır: böylece deploy öncesi
        basılmış mühürler bayat sayılmaz, upgrade anında kopya dalgası çıkmaz.
        """
        if not isinstance(zaman, str) or not zaman:
            if isinstance(gun, str) and gun:
                # ESKİ BİÇİM (gün bazlı): o günün 00:00'i (İstanbul).
                try:
                    zaman = datetime.fromisoformat(gun).isoformat()
                except (TypeError, ValueError):
                    zaman = datetime.now(ISTANBUL_TZ).isoformat()
            else:
                zaman = datetime.now(ISTANBUL_TZ).isoformat()
        kayit = {"state": state, "zaman": zaman, "tf": timeframe}
        event_id = str(formation_id or "").strip()
        if event_id:
            kayit["formation_id"] = event_id
        return kayit

    @staticmethod
    def _anahtardan_tf(anahtar: str) -> str:
        """"hisse_tf_STATE" anahtarından zaman dilimini çıkar (eski kayıtlar için).

        STATE adları alt çizgi içerir (FORMASYON_TAMAMLANDI), bu yüzden sağdan
        değil bilinen state listesiyle eşleştirilerek ayrıştırılır.
        """
        for state in ALERT_STATES:
            if anahtar.endswith(f"_{state}"):
                _, _, tf = anahtar[:-len(f"_{state}")].rpartition("_")
                return tf
        return ""

    def _son_alert_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_son_alerts")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._son_alert_dosya):
                    return
                with open(self._son_alert_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            if isinstance(ham, dict):
                for k, v in ham.items():
                    if not isinstance(k, str):
                        continue
                    if isinstance(v, str):
                        # ESKİ BİÇİM: anahtar "hisse_pattern_tf", değer state.
                        # Yeni anahtara ("hisse_tf_state") taşınır ve bugüne
                        # mühürlenir — upgrade anında olay tekrar basmaz.
                        stock_pattern, _, tf = k.rpartition("_")
                        if not stock_pattern or not tf or not v:
                            continue
                        stock = stock_pattern.split("_", 1)[0]
                        if not stock:
                            continue
                        self._son_alert[f"{stock}_{tf}_{v}"] = self._muhur_kaydi(v, tf)
                    elif isinstance(v, dict) and isinstance(v.get("state"), str):
                        # Yeni biçim: zaman damgası korunur (bayatsa _muhr_gecerli_mi reddeder).
                        self._son_alert[k] = self._muhur_kaydi(
                            v["state"], v.get("tf") or self._anahtardan_tf(k),
                            gun=v.get("gun"), zaman=v.get("zaman"),
                            formation_id=v.get("formation_id"))
            logger.info(f"Son-alert mühürleri {kaynak} yüklendi: {len(self._son_alert)} kayıt")
        except Exception as e:
            logger.warning(f"Son-alert mühürleri yüklenemedi (devam ediliyor): {e}")

    def _son_alert_kaydet(self):
        # TTL'si dolmuş mühürler diske/Supabase'a taşınmaz; sözlük şişmesin.
        bayat_anahtarlar = [
            key for key, marker in self._son_alert.items()
            if not self._muhr_gecerli_mi(
                marker,
                marker.get("state", ""),
                marker.get("tf", ""),
                marker.get("formation_id"),
            )
        ]
        for key in bayat_anahtarlar:
            del self._son_alert[key]
        payload = {k: dict(v) for k, v in self._son_alert.items()}
        try:
            import json
            os.makedirs(os.path.dirname(self._son_alert_dosya), exist_ok=True)
            with open(self._son_alert_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=0)
        except Exception as e:
            logger.warning(f"Son-alert mühürleri diske kaydedilemedi: {e}")
        if self.persistent_store is not None:
            try:
                self.persistent_store.upsert("state:telegram_son_alerts", payload)
            except Exception as e:
                logger.debug(f"Son-alert mühürleri Supabase'e kaydedilemedi: {e}")

    def _tek_seferlik_isle(self, stock: str, pattern: str, timeframe: str,
                           state: str, formation_id=None) -> None:
        """Başarılı gönderim sonrası teyitli olaya tek-seferlik mühür basar.

        Deneme, bekleme, başarısızlık ve tamamlanma state'leri push politikasında
        değildir. Formation ID varsa aynı state'in aynı oluşumdan tekrar çıkmasını
        engeller; kimlik yoksa geriye dönük slot/TTL mührü kullanılır.
        """
        if state not in ALERT_STATES:
            return
        key = self._son_alert_key(stock, timeframe, state, formation_id)
        self._son_alert[key] = self._muhur_kaydi(
            state, timeframe, formation_id=formation_id
        )
        self._son_alert_kaydet()

    def son_alert_sifirla(self, stock: str, timeframe: str) -> None:
        """Slotun (hisse+TF) ZAMAN cooldown'larını siler; mühürlere DOKUNMAZ.

        NEDEN DEĞİŞTİ: bu fonksiyon önce mühürleri de siliyordu. Motorun canlı
        geometrisi (has_pattern) kayan pencerede bir taramada False olup
        FORMASYON_YOK'a düştüğünde (flicker) main bu fonksiyonu çağırıyordu;
        mühür silinince aynı formasyon bir sonraki taramada yeniden "doğup"
        AYNI TAMAMLANDI/BAŞARISIZ mesajını tekrar basıyordu (ölçüm: kullanıcının
        günlüğünde ~45 mesajın ~13'ü birebir kopya). Mühür artık yalnız gün
        değişiminde bayatlar.

        Cooldown temizliği KORUNUR: slotu tekrar kaplayan yeni formasyonun
        ilerleme mesajları (TEYITLI -> RETEST -> TAMAMLANDI) 4 saat beklemez.
        """
        on_ek = f"{stock}_"
        # Anahtar biçimi hisse_desen_tf_STATE; STATE listesi üzerinden sonek eşle.
        durumler = set(ALERT_STATES) | set(WATCH_STATES)
        for anahtar in list(self.last_sent.keys()):
            if not anahtar.startswith(on_ek):
                continue
            govde = anahtar[len(on_ek):]
            if any(govde.endswith(f"_{timeframe}_{durum}") for durum in durumler):
                del self.last_sent[anahtar]
        self._cooldown_kaydet()

    # --- engellenen acil olay kuyruğu (Batch 5 / B4) ------------------------

    @staticmethod
    def _kuyruk_key(veri: Dict) -> tuple:
        return (
            str(veri.get("stock_name") or "").strip().upper(),
            str(veri.get("pattern_name") or "").strip(),
            str(veri.get("timeframe") or "").strip().lower(),
            str(veri.get("state") or "").strip().upper(),
        )

    def _kuyruk_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_acil_kuyruk")
            kaynak = "Supabase"
            if not isinstance(ham, list):
                kaynak = "disk"
                if not os.path.exists(self._kuyruk_dosya):
                    return
                with open(self._kuyruk_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            if not isinstance(ham, list):
                return
            from notification_delivery import _decode
            ham = json.loads(json.dumps(ham), object_hook=_decode)
            self._acil_kuyruk = [k for k in ham if isinstance(k, dict) and isinstance(k.get("veri"), dict)]
            logger.info(f"Telegram acil kuyruğu {kaynak} yüklendi: {len(self._acil_kuyruk)} olay")
        except Exception as e:
            logger.debug(f"Acil kuyruk yüklenemedi (ilk çalışma olabilir): {e}")

    def _kuyruk_kaydet(self):
        import json
        from notification_delivery import _encode
        kayitlar = json.loads(json.dumps(self._acil_kuyruk, default=_encode))
        try:
            os.makedirs(os.path.dirname(self._kuyruk_dosya), exist_ok=True)
            with open(self._kuyruk_dosya + ".tmp", "w", encoding="utf-8") as f:
                json.dump(kayitlar, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(self._kuyruk_dosya + ".tmp", self._kuyruk_dosya)
        except Exception as e:
            logger.debug(f"Acil kuyruk dosyaya kaydedilemedi: {e}")
        if self.persistent_store is not None:
            try:
                self.persistent_store.upsert("state:telegram_acil_kuyruk", kayitlar)
            except Exception as e:
                logger.debug(f"Acil kuyruk Supabase'e kaydedilemedi: {e}")

    def _kuyruga_ekle(self, data: Dict, engel: str) -> None:
        """Engel nedeniyle gönderilemeyen acil olayı kuyruğa alır (en fazla 1 kopya)."""
        key = self._kuyruk_key(data)
        if not all(key):
            return
        simdi = datetime.now(ISTANBUL_TZ)
        for kayit in self._acil_kuyruk:
            if self._kuyruk_key(kayit.get("veri") or {}) == key:
                # Aynı sinyal zaten kuyrukta: veriyi tazele, kuyrukta bekleme süresi
                # ilk girişten sayılmaya devam etsin (TTL şişmesin).
                kayit["veri"] = _kuyruk_verisi(data)
                kayit["son_deneme"] = simdi.isoformat()
                kayit["son_engel"] = engel
                self._kuyruk_kaydet()
                return
        while len(self._acil_kuyruk) >= ACIL_KUYRUK_LIMIT:
            self._acil_kuyruk.pop(0)
            self.kuyruk_tasmasi += 1
        self._acil_kuyruk.append({
            "kuyruk_zaman": simdi.isoformat(),
            "son_deneme": simdi.isoformat(),
            "son_engel": engel,
            "veri": _kuyruk_verisi(data),
        })
        logger.info(f"📬 Acil olay kuyruğa alındı ({engel}): {key[0]} {key[2]} {key[3]} "
                    f"(kuyruk: {len(self._acil_kuyruk)})")
        self._kuyruk_kaydet()

    def kuyrukta_mi(self, data: Dict) -> bool:
        """Bu olay kuyrukta bekliyor mu? (çağıran taraf sayaç/huni için kullanır)"""
        key = self._kuyruk_key(data)
        return any(self._kuyruk_key(kayit.get("veri") or {}) == key for kayit in self._acil_kuyruk)

    def kuyruk_durumu(self) -> Dict:
        return {
            "bekleyen": len(self._acil_kuyruk),
            "limit": ACIL_KUYRUK_LIMIT,
            "gonderildi": self.kuyruk_gonderildi,
            "zaman_asimi": self.kuyruk_zaman_asimi,
            "tasma": self.kuyruk_tasmasi,
        }

    def kuyruk_ozet_kayitlari(self, now: Optional[datetime] = None) -> List[dict]:
        """Kapanış özetinde gösterilebilecek taze, henüz bildirilmemiş olayları kopyala.

        Bu yöntem hiçbir şeyi tüketmez. Özet Telegram'a başarıyla teslim olduktan
        sonra çağıran `kuyruk_ozetleneni_tuket()` ile yalnızca gösterilenleri alır.
        """
        simdi = _istanbul(now) if now is not None else datetime.now(ISTANBUL_TZ)
        ttl_siniri = simdi - timedelta(minutes=max(1, ACIL_KUYRUK_TTL_DK))
        sonuc = []
        for kayit in self._acil_kuyruk:
            veri = dict(kayit.get("veri") or {})
            state = str(veri.get("state") or "").strip().upper()
            if state not in ALERT_STATES:
                continue
            try:
                kuyruk_zamani = _istanbul(datetime.fromisoformat(kayit.get("kuyruk_zaman")))
            except (TypeError, ValueError):
                kuyruk_zamani = simdi
            if kuyruk_zamani < ttl_siniri or kuyruk_zamani.date() != simdi.date():
                continue
            stock, pattern, timeframe, _state = self._kuyruk_key(veri)
            formation_id = veri.get("formation_id")
            marker = self._son_alert.get(
                self._son_alert_key(stock, timeframe, state, formation_id))
            if (not marker and formation_id):
                marker = self._son_alert.get(self._son_alert_key(stock, timeframe, state))
            if self._muhr_gecerli_mi(marker, state, timeframe, formation_id):
                continue
            sonuc.append({"kuyruk_zaman": kayit.get("kuyruk_zaman"), "veri": veri})
        return sonuc

    def kuyruk_ozetleneni_tuket(self, kayitlar: List[dict]) -> int:
        """Başarıyla iletilen kapanış özetindeki olayları tüket ve tekilleştir.

        Özetin Telegram kabulü, olayın kullanıcıya görünür teslimidir. Böylece
        aynı formation/state ertesi turda ayrı bir acil mesaj olarak yinelenmez.
        """
        imzalar = set()
        for kayit in kayitlar or []:
            if not isinstance(kayit, dict) or not isinstance(kayit.get("veri"), dict):
                continue
            imzalar.add((self._kuyruk_key(kayit["veri"]),
                         str(kayit.get("kuyruk_zaman") or "")))
        if not imzalar:
            return 0
        kalan = []
        tuketilen = []
        for kayit in self._acil_kuyruk:
            imza = (self._kuyruk_key(kayit.get("veri") or {}),
                    str(kayit.get("kuyruk_zaman") or ""))
            (tuketilen if imza in imzalar else kalan).append(kayit)
        if not tuketilen:
            return 0
        self._acil_kuyruk = kalan
        muhur_degisti = False
        for kayit in tuketilen:
            veri = kayit.get("veri") or {}
            state = str(veri.get("state") or "").strip().upper()
            if state not in ALERT_STATES:
                continue
            stock, pattern, timeframe, _state = self._kuyruk_key(veri)
            muhur_anahtari = self._son_alert_key(
                stock, timeframe, state, veri.get("formation_id"))
            self._son_alert[muhur_anahtari] = self._muhur_kaydi(
                state, timeframe, formation_id=veri.get("formation_id"))
            muhur_degisti = True
        if muhur_degisti:
            self._son_alert_kaydet()
        self._kuyruk_kaydet()
        return len(tuketilen)

    def kuyruk_tumunu_temizle(self) -> int:
        """Kapanış özeti daha önce gönderildiyse eski kuyruğu post-digest push'tan al."""
        adet = len(self._acil_kuyruk)
        if adet:
            self._acil_kuyruk.clear()
            self._kuyruk_kaydet()
        return adet

    def kuyrugu_bosalt(self, max_adet: int = 5, now: Optional[datetime] = None) -> int:
        """Çağıran zaman kapısı açıksa, engel kalkınca acil olayları sırayla gönder.

        Main loop bunu kapanış digest saatinden önce çağırır; daha geç saatlerde
        bekleyen kayıtlar DM kapanış özetine katılır.
        - TTL'yi aşan kayıtlar gönderilmez, atılır (bayat sinyal zarar verir).
        - Aynı sinyal sonradan gönderilmişse kuyruk kopyası sessizce düşürülür.
        - Kap/cooldown sürüyorsa sıradaki tura kadar beklenir; ağ hatasında
          kayıt korunur (veri kaybı yok).
        """
        if not self.enabled or not self._acil_kuyruk:
            return 0
        simdi = _istanbul(now) if now is not None else datetime.now(ISTANBUL_TZ)
        ttl_siniri = simdi - timedelta(minutes=max(1, ACIL_KUYRUK_TTL_DK))
        gonderilen = 0
        degisti = False
        for kayit in list(self._acil_kuyruk):
            if gonderilen >= max(1, int(max_adet)):
                break
            veri = dict(kayit.get("veri") or {})
            if str(veri.get("state") or "").strip().upper() not in ALERT_STATES:
                # Eski deploy'lardan kalan deneme/başarısız/tamamlandı kuyrukları
                # yeni bildirim politikasında kesinlikle gönderme.
                self._acil_kuyruk.remove(kayit)
                degisti = True
                continue
            try:
                kuyruk_zamani = _istanbul(datetime.fromisoformat(kayit.get("kuyruk_zaman")))
            except (TypeError, ValueError):
                kuyruk_zamani = simdi
            if kuyruk_zamani.date() != simdi.date():
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_zaman_asimi += 1
                degisti = True
                logger.warning(
                    "📬 Önceki İstanbul gününde kalan acil olay ayrı push yapılmadı: %s %s",
                    self._kuyruk_key(veri)[0], veri.get("state"),
                )
                continue
            if kuyruk_zamani < ttl_siniri:
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_zaman_asimi += 1
                degisti = True
                logger.warning(
                    f"📬 Kuyruktaki acil olay bayatladı ({ACIL_KUYRUK_TTL_DK} dk): "
                    f"{self._kuyruk_key(veri)[0]} {veri.get('state')}"
                )
                continue
            key = self._kuyruk_key(veri)
            if not self.can_send(
                key[0], key[1], key[2], key[3], formation_id=veri.get("formation_id")
            ):
                if self._son_engel == "tekrar":
                    # Mühür bu olayın zaten gönderildiğini söylüyor; kuyruktaki
                    # bayat kopya gereksiz -> sessizce düşür (cooldown dalından önce).
                    self._acil_kuyruk.remove(kayit)
                    degisti = True
                    continue
                if self._son_engel == "cooldown" and key in self.last_sent:
                    if _istanbul(self.last_sent[key]) > kuyruk_zamani:
                        # Aynı sinyal kuyruğa girdikten sonra gönderildi; kopya gereksiz.
                        self._acil_kuyruk.remove(kayit)
                        degisti = True
                        continue
                break  # engel sürüyor: sırayı bozmadan bekle
            # Acil kuyrukta `grafik_verisi` bilerek yoktur; bunu normal bir
            # köprü atlaması gibi sayıp karesiz sayaçlarını şişirmeyelim.
            veri["_kuyruktan"] = True
            if self._gonder(veri):
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_gonderildi += 1
                gonderilen += 1
                degisti = True
                logger.info(f"📬 Kuyruktan gönderildi: {key[0]} {key[2]} {key[3]}")
            else:
                # Ağ/Telegram hatası: kayıt kuyrukta kalır, kaybolmaz.
                break
        if degisti:
            self._kuyruk_kaydet()
        return gonderilen

    def can_send(self, stock: str, pattern: str, timeframe: str, state: str = "",
                 formation_id=None) -> bool:
        """Gönderim yapılabilir mi? Hayırsa SEBEBİ sayaca yazılır (bkz. self.engeller)."""
        # Her çağrı temiz başlar: kritik state'in kapıyı geçmesi bir önceki
        # engelin sebebini taşımaz (yanlış "kuyruğa al" kararı olmasın).
        self._son_engel = None
        # Tek-seferlik mühür (repeat-guard) ZAMAN cooldown'undan ÖNCE gelir:
        # motor aynı terminal state'i her tur yeniden ürettiği için 4 saat dolunca
        # kopya mesaj basılıyordu. Mühür "bu slot bu state'i BUGÜN zaten bildirdi"
        # derse olay NİHAİ reddir (kuyruğa alınmaz, beklenmez). Slot sıfırlama
        # (flicker) mühürü artık silmez; bayatlık yalnız gün değişiminde.
        if state in ALERT_STATES:
            marker_key = self._son_alert_key(stock, timeframe, state, formation_id)
            marker = self._son_alert.get(marker_key)
            # Deploy öncesi mühürler kimliksizdir; kısa legacy TTL süresince
            # yeni anahtara taşınırken yinelenen push'u da engellesin.
            if (not marker and formation_id
                    and self._muhr_gecerli_mi(
                        self._son_alert.get(self._son_alert_key(stock, timeframe, state)),
                        state, timeframe, formation_id)):
                marker = self._son_alert.get(self._son_alert_key(stock, timeframe, state))
            if self._muhr_gecerli_mi(marker, state, timeframe, formation_id):
                self.engeller["tekrar"] += 1
                self._son_engel = "tekrar"
                return False
        key = self._cooldown_key(stock, pattern, timeframe, state)
        if key not in self.last_sent:
            cooldown_tamam = True
        else:
            elapsed = datetime.now(ISTANBUL_TZ) - _istanbul(self.last_sent[key])
            cooldown_tamam = elapsed > timedelta(hours=self.cooldown_hours)
        if not cooldown_tamam:
            self.engeller["cooldown"] += 1
            self._son_engel = "cooldown"
            return False
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        if self._gunluk_sayac >= self.max_gunluk:
            self.engeller["gunluk_kap"] += 1
            self._son_engel = "gunluk_kap"
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.error(f"TELEGRAM GÜNLÜK KAPANI AŞILDI ({self.max_gunluk} mesaj) - bugün başka mesaj gönderilmeyecek.")
            return False
        if len(self._saatlik_zamanlar) >= self.max_saatlik:
            if state in KRITIK_STATELER:
                return True
            self.engeller["saatlik_kap"] += 1
            self._son_engel = "saatlik_kap"
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.warning(f"TELEGRAM SAATLİK KAPANI AŞILDI ({self.max_saatlik} mesaj/saat) - sadece kritik sinyaller.")
            return False
        self._son_engel = None
        return True

    def gonderim_durumu(self) -> Dict:
        """Bugünün gönderim/engel özeti (/durum ve heartbeat için)."""
        return {
            "enabled": self.enabled,
            "gonderilen_alarm": self.gonderilen_alarm,
            "hatalar": self.gonderim_hatasi,
            "kanal_hatasi": self.kanal_hatasi,
            "engeller": dict(self.engeller),
            "gunluk_kap": self.max_gunluk,
            "saatlik_kap": self.max_saatlik,
            "son_basarili_gonderim": self.son_basarili_gonderim,
            "son_gonderme_hatasi": self.son_gonderme_hatasi,
            # Engellenen acil olaylar: kaç tanesi bekliyor / kaçı gönderildi.
            "acil_kuyruk": len(self._acil_kuyruk),
            "teslim_kuyrugu": self._delivery.status(),
            "kuyruk_gonderildi": self.kuyruk_gonderildi,
            "kuyruk_zaman_asimi": self.kuyruk_zaman_asimi,
            "kuyruk_tasmasi": self.kuyruk_tasmasi,
            # Public (grup) hedefi: DM'den bağımsız sayaçlar.
            "public_enabled": self.public_enabled,
            "public_chat_id": self.public_chat_id,
            "public_gonderilen": self.public_gonderilen,
            "public_hatasi": self.public_hatasi,
            "public_engel": self.public_engel,
            # Görsel kuyruğu (§4): metin kotasından bağımsız sayaçlar.
            "grafik_acik": _grafik_salteri_acik(),
            "grafik_olay": self.grafik_olay,
            "grafik_olay_karesiz": self.grafik_olay_karesiz,
            "grafik_kopru_hata": self.grafik_kopru_hata,
            "grafik_son_neden": self.grafik_son_neden,
            "grafik_gonderilen": self.grafik_gonderilen,
            "grafik_kuyruk": len(getattr(self, "_grafik_kuyruk", []) or []),
            "grafik_atlanan_hata": self.grafik_atlanan_hata,
            "grafik_atlanan_kota": self.grafik_atlanan_kota,
            "grafik_atlanan_baglam": self.grafik_atlanan_baglam,
            "grafik_ort_ms": (round(self.grafik_toplam_ms / self.grafik_kare_sayisi, 1)
                              if self.grafik_kare_sayisi else 0.0),
            "public_kuyruk": len(self._public_kuyruk),
            "public_kuyruk_tasmasi": self.public_kuyruk_tasmasi,
            "son_public_gonderim": self.son_public_gonderim,
        }

    def format_message(self, data: Dict) -> str:
        stock = data.get('stock_name', 'Bilinmiyor')
        timeframe = data.get('timeframe', '1h')
        pattern = data.get('pattern_name', 'Formasyon')
        state = data.get('state', 'ADAY_OLUSUYOR')
        # Raw failure/attempt/completed lifecycle states remain suppressed. A
        # separate notification-only alias is created only after a prior
        # confirmed breakout later closes back inside the formation band.
        if state in {"KIRILIM_DENEMESI", "BASARISIZ_KIRILIM", "FORMASYON_TAMAMLANDI"}:
            return ""
        if state in {"KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"}:
            return _format_lifecycle_alert(
                data, guncelleme=bool(data.get("_dm_bağlam_değişmedi"))
            )
        quality = data.get('confidence_score', 0)
        price = data.get('critical_price_level', 0)
        timestamp = data.get('timestamp', datetime.now())
        break_dir = data.get('break_dir', 0)
        upper = data.get('upper_now', price)
        lower = data.get('lower_now', price)
        contraction = data.get('contraction', None)
        retest_seen = data.get('retest_seen', True)
        upper_touches = data.get('upper_touches', None)
        lower_touches = data.get('lower_touches', None)
        age_bars = data.get('age_bars', None)
        mtf_destek = data.get('mtf_destek', False)

        tf_human = TF_HUMAN.get(timeframe, timeframe)
        emoji = PATTERN_EMOJI.get(pattern, "📈")
        q_comment = quality_comment(quality)
        q_emoji = quality_emoji(quality)

        if isinstance(timestamp, str):
            time_str = timestamp
        else:
            try:
                time_str = _tr_tarih(timestamp)
            except (AttributeError, ValueError, TypeError):
                # strftime desteklemeyen/tuhaf timestamp: metne düşür (dar kapsam).
                time_str = str(timestamp)

        # Daralma metni: "baya sıkışmış" gibi günlük konuşma dilinden çıkarıldı;
        # aynı bilgi kısa ve nötr veriliyor.
        contraction_str = ""
        if contraction is not None:
            pct = contraction * 100
            if pct >= 80:
                contraction_str = f"daralma %{pct:.0f} · sıkışma güçlü"
            elif pct >= 60:
                contraction_str = f"daralma %{pct:.0f} · sıkışıyor"
            elif pct >= 40:
                contraction_str = f"daralma %{pct:.0f}"
            else:
                contraction_str = f"daralma %{pct:.0f} · erken"

        temas_str = ""
        if upper_touches is not None and lower_touches is not None:
            temas_str = f"Temas üst/alt {upper_touches}/{lower_touches}"
        yas_str = f"{age_bars} bar" if age_bars else ""

        kalite_str = f"Kalite {quality:.0f} {q_emoji} ({q_comment})"
        # Kalite ve detay AYRI satırlarda: telefon ekranında hiçbir satırın
        # tek satıra sığması gerekiyor (eskiden tek satır ~90 karaktere çıkıp
        # üç satıra bölünüyordu).
        detay_str = " · ".join(p for p in (contraction_str, temas_str, yas_str,
                                           "4h destekliyor" if mtf_destek else "") if p)

        # Her mesaj aynı iskeleti paylaşır: başlık / olay / kalite / detay / seviye.
        # Rastgele şablon seçimi yok: aynı olay her zaman birebir aynı metni üretir.
        # Dil herkese açık kanal dili — kişisel asistan sesi ve tavsiye cümlesi yok.
        if state == "ADAY_OLUSUYOR":
            satirlar = [f"👀 {stock} {tf_human} · {pattern}",
                        "Formasyon oluşuyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)}")

        elif state == "GEOMETRI_ADAYI":
            satirlar = [f"{emoji} {stock} {tf_human} · {pattern}",
                        "Geometri oturuyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)} · olgunlaşma bekleniyor")

        elif state == "FORMASYON_TANIMLANDI":
            satirlar = [f"📋 {stock} {tf_human} · {pattern}",
                        "Formasyon tanımlandı",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Üst: {_sayı(upper)} / Alt: {_sayı(lower)}")

        elif state == "SIKISMA_GUCLENIYOR":
            satirlar = [f"⚡ {stock} {tf_human} · {pattern}",
                        "Sıkışma güçleniyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)} · kırılım yakın")

        elif state == "KIRILIM_HAZIRLIGI":
            satirlar = [f"⚠️ {stock} {tf_human} · {pattern}",
                        "Kırılım hazırlığında",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Kritik seviyeler: {_sayı(lower)} / {_sayı(upper)}")

        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            yon_eki = f"{direction} yönde " if direction else ""
            satirlar = [f"🔥 {stock} {tf_human} · {pattern}",
                        f"Kırılım denemesi · {yon_eki}{_sayı(level)} zorlanıyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Kırılım gücü henüz düşük, teyit bekleniyor")

        elif state == "KIRILIM_ADAYI":
            direction = "YUKARI" if break_dir == 1 else "AŞAĞI" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            power = data.get('break_strength', quality)
            kapanis_yonu = "üstünde" if break_dir == 1 else "altında" if break_dir == -1 else "yakınında"
            baslik_eki = f"{direction} " if direction else ""
            # Eskiden iki şablon rastgele seçiliyordu (🚀 KIRIYOR / 💥 kırılım adayı);
            # aynı olay iki farklı metinle gidiyordu. Artık tek metin.
            satirlar = [f"🚀 {stock} {tf_human} · {pattern}",
                        f"{baslik_eki}kırılım adayı · {_sayı(level)} {kapanis_yonu} kapanış",
                        f"Kırılım gücü {power:.0f} {q_emoji} · teyit mumu bekleniyor"]

        elif state == "KIRILIM_TEYITLI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = _format_price(data.get('break_price', upper if break_dir == 1 else lower))
            yon = f"{direction} " if direction else ""
            event_line = f"Kapanışla teyitli {yon}kırılım"
            if level:
                event_line += f" · seviye {level}"
            satirlar = [f"✅ {stock} {tf_human} · {pattern}", event_line, kalite_str]
            if detay_str:
                satirlar.append(detay_str)

        elif state == "RETEST_BEKLENIYOR":
            level = data.get('break_price', price)
            satirlar = [f"⏳ {stock} {tf_human} · {pattern}",
                        f"Retest bekleniyor · {_sayı(level)}'e dönüş olabilir",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Retest tutarsa yapı güçlenir")

        elif state == "RETEST_EDILIYOR":
            satirlar = [f"🔄 {stock} {tf_human} · {pattern}",
                        "Retest sürüyor · kırılan seviyeye geri dönüldü",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Tutunursa devamı bekleniyor")

        elif state == "RETEST_BASARILI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            yon = f"{direction} kırılım" if direction else "kırılım"
            level = _format_price(data.get('break_price', price))
            event_line = f"Kapanışla başarılı retest · {yon}"
            satirlar = [f"🎯 {stock} {tf_human} · {pattern}", event_line]
            if level:
                satirlar.append(f"Seviye {level} korundu")
            satirlar.append(kalite_str)
            if detay_str:
                satirlar.append(detay_str)

        elif state == "FORMASYON_GECERSIZ":
            # Bu şablon bilerek korunuyor: ölü formasyonlar alarm akışından
            # kapı ile elenir (yalnız manuel/test gönderiminde buraya düşülür).
            reason = data.get('invalid_reason', 'Süre doldu veya bozuldu')
            satirlar = [f"⚪ {stock} {tf_human} · {pattern}",
                        f"Formasyon geçersiz · sebep: {reason}"]

        else:
            satirlar = [f"{emoji} {stock} {tf_human} · {pattern}",
                        f"Durum: {state}",
                        kalite_str,
                        f"Seviye: {_sayı(price)} · {time_str}"]

        # Kapanan mum satırı (P0): anlık olay mesajlarında "hangi mum kapandı?"
        # sorusu mesajın içinde cevaplanır. İzleme/digest akışına eklenmez
        # (orada yer bütçesi farklı ve o adaylar zaten kapanış özetiyle gider).
        mum_str = str(data.get('bar_metni') or "").strip()
        if state in ("KIRILIM_TEYITLI", "RETEST_BASARILI"):
            insert_at = 2
            if mum_str:
                satirlar.insert(insert_at, mum_str)
                insert_at += 1
            close_price = _format_price(
                data.get("candle_close_price", data.get("close_price"))
            )
            if close_price:
                satirlar.insert(insert_at, f"Mum kapanışı: {close_price}")

        msg = "\n".join(satirlar)

        # Domain başlıkları yalnızca formatlayıcının ürettiği gerçek bulgular
        # varsa görünür; boş bir Market Structure/OB/FVG/hacim başlığı eklenmez.
        domain_context = str(data.get("domain_context") or "").strip()
        if domain_context:
            msg += "\n\n" + domain_context

        # Eski kuyruk kayıtları için alanı okumaya devam et; yeni acil mesajlarda
        # izleme adayları bu alana eklenmez ve kapanış digest'inde tutulur.
        # Acil olay mesajına, ayrı alarm olarak henüz gönderilmemiş en fazla üç
        # kısa izleme adayı bağlamı eklenir. Adaylar kendi başlarına gönderilmez.
        watch_context = data.get("watch_context") or []
        context_lines = []
        for candidate in watch_context[:3]:
            if not isinstance(candidate, dict):
                continue
            candidate_stock = str(candidate.get("stock") or "?")
            candidate_tf = TF_HUMAN.get(candidate.get("timeframe"), candidate.get("timeframe", ""))
            candidate_pattern = str(candidate.get("pattern_name") or "formasyon")
            # State adı Türkçe ve tek kaynaktan (STATE_TR): eskiden
            # "SIKISMA_GUCLENIYOR" -> "sikisma gucleniyor" gibi Türkçe
            # karaktersiz/eksik metin basıyordu.
            _ham_state = str(candidate.get("state") or "").strip().upper()
            candidate_state = STATE_TR.get(
                _ham_state, _ham_state.title().replace("_", " ") or "izlemede")
            try:
                candidate_quality = float(candidate.get("quality") or 0)
                quality_suffix = f" · kalite {candidate_quality:.0f}"
            except (TypeError, ValueError):
                quality_suffix = ""
            context_lines.append(
                f"• {candidate_stock} {candidate_tf} {candidate_pattern}: {candidate_state}{quality_suffix}"
            )
        if context_lines:
            msg += "\n\n👀 Diğer izleme adayları\n" + "\n".join(context_lines)

        if state in ("KIRILIM_TEYITLI", "RETEST_BASARILI"):
            msg += "\n\n📌 Formasyon takibi · yatırım tavsiyesi değildir"
        return msg

    def send(self, data: Dict, kuyrukla: bool = True) -> bool:
        """Kapanışta teyitli alarm gönder; diğer lifecycle state'lerini reddet."""
        return self.send_with_prepare(data, before_send=None, kuyrukla=kuyrukla)

    def send_with_prepare(self, data: Dict, before_send=None, kuyrukla: bool = True) -> bool:
        """Gönderim kapısını geçince bağlamı hazırla, sonra tek kez gönder.

        ``before_send`` scanner'ın yalnızca gerçekten gönderilecek/yedeklenecek
        olay için taze domain çıktısı eklemesini sağlar. Repeat mührü olan eski
        olaylarda domain motorları hiç çalıştırılmaz. Cooldown/kap nedeniyle
        kuyruğa girecek yeni olayın bağlamı da kuyruk kaydına alınır.
        """
        stock = data.get("stock_name", "")
        pattern = data.get("pattern_name", "")
        timeframe = data.get("timeframe", "")
        state = str(data.get("state", "") or "").strip().upper()
        if state not in ALERT_STATES:
            self._son_engel = "state_disabled"
            logger.info("%s %s %s %s - state bildirim politikasında kapalı",
                        stock, pattern, timeframe, state)
            return False
        data["state"] = state
        if self.enabled and (self._delivery.already_done(data) or self._delivery.is_cross_duplicate(data)):
            self._son_engel = "tekrar"
            self.engeller["tekrar"] += 1
            return False
        if data.get("formation_id") is not None:
            data["formation_id"] = str(data["formation_id"])

        def prepare_context():
            if not callable(before_send):
                return
            try:
                before_send(data)
            except Exception as exc:  # noqa: BLE001 - domain bağlamı alarmı düşürmesin
                data["domain_context"] = ""
                logger.warning("Bildirim bağlamı hazırlanamadı (%s %s): %s",
                               stock, timeframe, exc)

        if not self.can_send(
            stock, pattern, timeframe, state, formation_id=data.get("formation_id")
        ):
            engel = self._son_engel or "cooldown"
            # "tekrar" nihai reddir: mühürlü olay için ne kuyruk ne de domain işi.
            if kuyrukla and self.enabled and engel != "tekrar":
                prepare_context()
                self._kuyruga_ekle(data, engel)
            logger.info("%s %s %s %s - %s, gönderilmiyor",
                        stock, pattern, timeframe, state, engel)
            return False

        prepare_context()
        # İçerik kapısı: bağlam ve kapanış önceki mesajla birebir aynıysa kopya
        # gitmez; yalnız kapanış/marj değiştiyse kısa güncelleme gider.
        if TELEGRAM_DM_DEGISIM_KAPISI and state in ALERT_STATES:
            durum = self._dm_degisim_durumu(data)
            data["_dm_bağlam_değişmedi"] = (durum == "guncelleme")
            if durum == "guncelleme":
                self.engeller["baglam_degismedi"] = int(self.engeller.get("baglam_degismedi", 0)) + 1
                logger.info("%s %s %s - bağlam önceki kartla aynı: yapı/bölge/hacim bloğu "
                            "kısaltıldı (%d kez bugün)", stock, timeframe, state,
                            self.engeller["baglam_degismedi"])
        ok = self._gonder(data)
        if ok:
            self._dm_imza_kaydet(data)
        return ok

    # --- grafik karesi teslimi (G4 / §4) -----------------------------------

    def grafik_kopru_hatasi(self, neden: str) -> None:
        """Tarayıcı-kare köprüsü hatasını say ve ilkini görünür biçimde logla."""
        neden_kisa = " ".join(
            redact_sensitive_text(str(neden), self.token).split()
        )[:120]
        with self._grafik_lck:
            self.grafik_kopru_hata += 1
            self.grafik_son_neden = neden_kisa
            sayi = self.grafik_kopru_hata
        if sayi == 1:
            # Bir kere WARNING: Render'ın varsayılan INFO loglarında teşhis görünür.
            logger.warning("grafik köprüsü ilk hatası: %s", neden_kisa)
        else:
            # Tekrarlayan tarama hataları sayılır, fakat log akışını doldurmaz.
            logger.debug("grafik köprüsü hatası #%d: %s", sayi, neden_kisa)

    def grafik_kuyruga_ekle(self, data: Dict, *, gonder: bool = False) -> int:
        """`data["grafik_verisi"]`ni gönderim kuyruğuna alır; eklenen kare sayısı.

        `gonder=True` (canlı akış, GÖRSEL-4): kuyruğa ekledikten sonra boşta
        bir gönderim işçisi başlatılır — kareler metnin hemen ardından gider ve
        tur sonu toplu gönderimi tekrar tetiklemez. Test/mock yolları bayrağı
        vermez; eski davranış (tur sonunda boşaltma) korunur.

        Neden burada: kart metni gitmiş oldu — kare ALARMIN devamıdır, ayrı olay
        değildir (§4: 1 olay = 1 metin + kareler). Şalter açıkken köprüden görsel
        alamayan olaylar sayılır; acil kuyruktan gelen kartlar bu sayımlara girmez.
        """
        if not isinstance(data, dict):
            return 0
        grafik_acik = _grafik_salteri_acik()
        kuyruktan = bool(data.get("_kuyruktan"))
        if grafik_acik and not kuyruktan:
            veri_sayac = data.get("grafik_verisi")
            goruntu_sayac = (veri_sayac.get("goruntular")
                             if isinstance(veri_sayac, dict) else None)
            with self._grafik_lck:
                self.grafik_olay += 1
                if not goruntu_sayac:
                    self.grafik_olay_karesiz += 1

        veri = data.get("grafik_verisi")
        if not isinstance(veri, dict):
            return 0
        goruntular = veri.get("goruntular") or []
        if not goruntular:
            return 0
        if data.get("_dm_bağlam_değişmedi"):
            # Kısa güncelleme kartı (§DM içerik kapısı): bağlam birebir aynıysa tek
            # satır gider. Aynı olayın 4 karesini yeniden göndermek „1 olay = 1 mesaj
            # + kareleri" kuralını şişirir ve medyayı yorar → kare eklenmez.
            self.grafik_atlanan_baglam += 1
            logger.debug("grafik: bağlam güncellemesi olduğu için kare eklenmedi (%s %s)",
                         data.get("stock_name"), data.get("timeframe"))
            return 0
        if not grafik_acik:
            return 0
        try:
            import grafik
            if not grafik.grafik_aktif_mi():
                return 0
        except Exception as hata:  # pragma: no cover - bağımlılık yoksa görsel yok
            logger.debug("grafik modülü hazır değil: %s", hata)
            return 0
        with self._grafik_lck:
            self._grafik_kuyruk.append({
                "anahtar": (str(data.get("stock_name") or ""),
                            str(data.get("timeframe") or ""),
                            str(data.get("state") or "")),
                "sembol": veri.get("sembol") or data.get("stock_name") or "",
                "goruntular": list(goruntular),
                "kota": int(veri.get("kota") or 0),
            })
            if veri.get("kota"):
                self.grafik_atlanan_kota += int(veri.get("kota"))
        if gonder:
            self._grafik_gonderim_baslat()
        return len(goruntular)

    def _grafik_gonderim_baslat(self) -> None:
        """Boşta işçi yoksa bir tane başlatır (her çağrı thread AÇMAZ).

        Neden tek işçi: medya gönderimi SIRALI olmalı — kullanıcının istediği
        akış "bir metin, ardından o metnin görselleri". Kuyruk boşalınca işçi
        çıkar; yeni kare geldiğinde yeni bir işçi başlar.
        """
        with self._grafik_gonderim_lck:
            mevcut = getattr(self, "_grafik_gonderim_isi", None)
            if mevcut is not None and mevcut.is_alive():
                return
            is_ = threading.Thread(target=self._grafik_gonderim_dongusu,
                                   name="grafik-gonderim", daemon=True)
            self._grafik_gonderim_isi = is_
            is_.start()

    def _grafik_gonderim_dongusu(self) -> None:
        """İşçi gövdesi: kuyruk boşalana kadar parça parça gönderir; sızdırmaz."""
        try:
            while True:
                ozet = self.grafikleri_gonder()
                if int(ozet.get("kare") or 0) == 0:
                    return
        except Exception as hata:  # noqa: BLE001 - metin/görsel akışını düşürmesin
            logger.warning("grafik arka plan gönderimi durdu: %s: %s",
                           type(hata).__name__, hata)

    def grafik_dosya_gonder(self, yol, caption: str = "") -> tuple:
        """Bir PNG'yi DM'e gönderir ve dosyayı SİLER (§4); `(ok, aciklama)`.

        Neden ayrı metod: `/grafik` komutu kareyi kullanıcının kendisi istediği için
        sıraya bekletmeden gönderir; alarm kuyruğu da aynı gönderimi kullanır. Dosya
        her durumda silinir (kalan tek şey disk çöpü olurdu), geçici yol
        `grafik.kare_yolu`ndan gelir — `DATA_DIR` dışı.
        """
        ok, aciklama = False, "gönderim denenmedi"
        try:
            if not self.enabled:
                return False, "Telegram notifier pasif (token/chat_id env'de yok)"
            # Fotoğraf hedefi gerçekten DM olmalı. CHAT_ID yanlışlıkla public
            # grupla eşlenmişse metin politikasına dokunmadan görseli reddet.
            try:
                dm_kimligi = int(str(self.chat_id).strip()) > 0
            except (ValueError, TypeError):
                dm_kimligi = False
            public_hedef = str(getattr(self, "public_chat_id", "") or "").strip()
            if not dm_kimligi or (public_hedef and public_hedef == str(self.chat_id).strip()):
                self.grafik_atlanan_hata += 1
                return False, "görseller yalnız DM'e gönderilir; hedef private DM değil"
            from transport.telegram import foto_gonder

            self._grafik_pace()
            ok, aciklama = foto_gonder(yol, notifier=self, caption=caption)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += 1
            else:
                self.grafik_atlanan_hata += 1
                logger.warning("grafik karesi gönderilemedi: %s",
                               redact_sensitive_text(str(aciklama), self.token)[:160])
        except Exception as hata:  # noqa: BLE001 - görsel hiçbir akışı düşürmesin
            ok, aciklama = False, f"{type(hata).__name__}"[:120]
            self.grafik_atlanan_hata += 1
        finally:
            try:
                os.remove(yol)
            except (OSError, TypeError):
                pass
        return ok, aciklama

    def _grafik_pace(self) -> None:
        """Kareler arası kısa bekleme: §4 mevcut pacing yardımcısını kullanır.

        `public_min_aralik_sn` yeniden okunur ama kendi zaman damgasımız tutulur:
        grup bülteni ile görseller birbirinin temposunu bozmasın.
        """
        try:
            ara = float(self.public_min_aralik_sn or 0)
        except (TypeError, ValueError):
            ara = 0.0
        if ara <= 0 or self._son_grafik_ts is None:
            return
        bekle = ara - (time.monotonic() - self._son_grafik_ts)
        if bekle > 0:
            time.sleep(min(bekle, 5.0))

    def grafikleri_gonder(self, sinir: Optional[int] = None) -> Dict:
        """Kuyruğu boşaltır: kare → PNG → `sendPhoto` (tarama turu sonunda çağrılır).

        Sıra §4'teki gibi: önce alarm METNİ gitmiştir; kareler onun altında, olay
        sırasında ve tek tek gider (`sendMediaGroup` v2'de, §4). Görsel hiçbir
        koşulda metni/alamı engellemez: her hata sayılır ve sıradaki kareye geçilir.
        Üretilen geçici PNG gönderimden sonra silinir (§4).
        """
        with self._grafik_gonderim_lck:
            kuyruk = list(self._grafik_kuyruk)
            self._grafik_kuyruk.clear()
        ozet = {"gonderilen": 0, "hata": 0, "kare": 0, "sure_ms": 0, "atlanan": 0}
        if not kuyruk or not self.enabled:
            return ozet
        try:
            import grafik  # noqa: F401 - yoksa katman zaten çalışmaz
        except Exception as hata:  # pragma: no cover - matplotlib yoksa görsel yok
            logger.warning("grafik teslimi kapatıldı (%s): %s", type(hata).__name__, hata)
            ozet["atlanan"] = sum(len(k["goruntular"]) for k in kuyruk)
            self.grafik_atlanan_hata += ozet["atlanan"]
            return ozet
        if not grafik.disk_uygun_mu():
            logger.warning("diskte %d MB altında yer var: kareler üretilmedi",
                           grafik.DISK_MIN_BOS_MB)
            ozet["atlanan"] = sum(len(k["goruntular"]) for k in kuyruk)
            self.grafik_atlanan_hata += ozet["atlanan"]
            return ozet
        if not self._grafik_supuruldu:
            self._grafik_supuruldu = True
            silinen = grafik.bayat_kareleri_supur()
            if silinen:
                logger.info("grafik: %d bayat kare dosyası silindi", silinen)
        # `sinir` KARE sayısısıdır, OLAY sayısı değil (bir olay 4 kare taşıyabilir;
        # ilk sürümde `len(kuyruk)` kullanıldığı için ikinci kare kuyrukta kalıyordu).
        limit = -1 if sinir is None else max(0, int(sinir))
        kalan = []
        for olay in kuyruk:
            paketler = []          # (yol, caption, meta) — olay başına TEK albüm
            for kare in olay["goruntular"]:
                if 0 <= limit <= ozet["kare"] + len(paketler):
                    kalan.append({"olay": olay, "kare": kare})
                    continue
                yol, meta = None, {}
                try:
                    yol, meta = grafik.kareyi_yaz(kare.get("goruntu") or {},
                                                   kare.get("tf") or "1h")
                except Exception as hata:  # noqa: BLE001 - görsel alarmı düşürmesin
                    logger.warning("grafik: kare üretilemedi (%s %s): %s",
                                   olay["sembol"], kare.get("tf"), hata)
                    self.grafik_atlanan_hata += 1
                    ozet["hata"] += 1
                    ozet["kare"] += 1
                    continue
                if not yol:
                    # Çizim reddi (kadraj/uyuşmazlık): meta'da nedeni var, sessiz olmasın.
                    logger.info("grafik: kare çizilmedi (%s %s): %s", olay["sembol"],
                                kare.get("tf"), " · ".join(meta.get("uyarilar") or []))
                    self.grafik_atlanan_hata += 1
                    ozet["hata"] += 1
                    ozet["kare"] += 1
                    continue
                paketler.append((yol, _grafik_basligi(olay, kare, meta), meta))
            ozet["kare"] += len(paketler)
            if not paketler:
                continue
            sonuc = self.grafik_toplu_gonder([(y, c) for y, c, _m in paketler])
            for (_y, _c, meta), ok in zip(paketler, sonuc):
                # Sayaçları `grafik_toplu_gonder` tutuyor; burada yalnız tur özeti ve süre.
                if ok:
                    self.grafik_kare_sayisi += 1
                    self.grafik_toplam_ms += float(meta.get("sure_ms") or 0)
                    ozet["gonderilen"] += 1
                    ozet["sure_ms"] += int(meta.get("sure_ms") or 0)
                else:
                    ozet["hata"] += 1
        if kalan:
            with self._grafik_gonderim_lck:
                for parca in reversed(kalan):
                    self._grafik_kuyruk.insert(0, {
                        "anahtar": parca["olay"]["anahtar"], "sembol": parca["olay"]["sembol"],
                        "goruntular": [parca["kare"]], "kota": 0})
            ozet["atlanan"] = len(kalan)
        return ozet

    def grafik_toplu_gonder(self, paketler) -> list:
        """`[(yol, caption)]` → kare başına başarı listesi; geçici dosyaları SİLER.

        Tek kare → `sendPhoto` (`grafik_dosya_gonder`). 2–10 kare → TEK albüm
        (`sendMediaGroup`): kareler arasına metin girmez. Albüm reddedilirse kareler
        tek tek yeniden denenir (kare kaybı olmasın). Her yol, sonuçtan bağımsız
        olarak bu fonksiyonda silinir (§4).
        """
        paketler = [(y, c) for y, c in (paketler or []) if y]
        sonuc = [False] * len(paketler)
        try:
            if not paketler:
                return sonuc
            if not self.enabled:
                self.grafik_atlanan_hata += len(paketler)
                return sonuc
            try:
                dm_kimligi = int(str(self.chat_id).strip()) > 0
            except (ValueError, TypeError):
                dm_kimligi = False
            public_hedef = str(getattr(self, "public_chat_id", "") or "").strip()
            if not dm_kimligi or (public_hedef and public_hedef == str(self.chat_id).strip()):
                self.grafik_atlanan_hata += len(paketler)
                logger.warning("grafik: görseller yalnız DM'e gönderilir; hedef private DM değil")
                return sonuc
            if len(paketler) == 1:
                ok, aciklama = self.grafik_dosya_gonder(paketler[0][0], caption=paketler[0][1])
                sonuc[0] = ok
                return sonuc
            from transport.telegram import medya_grubu_gonder

            self._grafik_pace()
            ok, aciklama = medya_grubu_gonder(
                [y for y, _c in paketler], captions=[c for _y, c in paketler],
                notifier=self)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += len(paketler)
                return [True] * len(paketler)
            logger.warning("grafik albümü gönderilemedi, kare kare deneniyor: %s",
                           redact_sensitive_text(str(aciklama), self.token)[:160])
            # Yedek: albüm reddedildiyse kareleri tek tek dene (kare kaybı olmasın).
            # `grafik_dosya_gonder` dosyayı siler; önce kopya gerekmez, yalnız bir kez denenir.
            for k, (yol, caption) in enumerate(paketler):
                sonuc[k] = self._tekil_gonder_dosyasiz(yol, caption)
            return sonuc
        finally:
            for yol, _c in paketler:
                try:
                    os.remove(yol)
                except (OSError, TypeError):
                    pass

    def _tekil_gonder_dosyasiz(self, yol, caption: str) -> bool:
        """`grafik_dosya_gonder` ile aynı, ama dosyayı silmez (toplu çağıran siler)."""
        try:
            from transport.telegram import foto_gonder

            self._grafik_pace()
            ok, aciklama = foto_gonder(yol, notifier=self, caption=caption)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += 1
            else:
                self.grafik_atlanan_hata += 1
                logger.warning("grafik karesi gönderilemedi: %s",
                               redact_sensitive_text(str(aciklama), self.token)[:160])
            return bool(ok)
        except Exception as hata:  # noqa: BLE001 - görsel hiçbir akışı düşürmesin
            self.grafik_atlanan_hata += 1
            logger.debug("grafik yedek gönderimi: %s", type(hata).__name__)
            return False

    def _gonder(self, data: Dict) -> bool:
        if self.enabled:
            try:
                return self._delivery.submit(data)
            except Exception as exc:
                logger.error("Bildirim kalıcı kuyruğa alınamadı: %s", type(exc).__name__)
                return False
        return self._gonder_metin(data)

    def teslimleri_dene(self) -> int:
        return self._delivery.flush() if self.enabled else 0

    def teyit_teslim_edildi_mi(self, formation_id) -> bool:
        """Aynı formation_id'li KIRILIM_TEYITLI teslim kuyruğunda gerçekten gitti mi?"""
        return bool(self._delivery.confirmation_delivered(formation_id))

    def _gonder_metin(self, data: Dict) -> bool:
        """can_send kapısı geçildikten sonraki gerçek gönderim (kuyruk bunu çağırır)."""
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        state = data.get('state', '')

        message = data.get("_delivery_message") or self.format_message(data)
        # Güvenlik: 4096 kr üzeri istek Telegram'da 400 döner ve mesaj tamamen
        # kaybolurdu. Artık sınırına kırpılır ve logda iz bırakır.
        if len(message) > _PUBLIC_MAX_METIN:
            logger.warning("Alarm mesajı Telegram sınırını aştı (%d kr) → kırpıldı", len(message))
            message = _kirp(message)
        elif TELEGRAM_ALERT_MAX_KARAKTER and len(message) > TELEGRAM_ALERT_MAX_KARAKTER:
            logger.warning("Alarm kartı hedefin üstünde: %s %s %s · %d kr (hedef %d)",
                           stock, timeframe, state, len(message), TELEGRAM_ALERT_MAX_KARAKTER)
        asiyan = [satir for satir in message.splitlines() if _satir_px(satir) > (_px_butce() or 1e9)]
        if asiyan:
            logger.warning("Alarm kartında %d satır telefon bütçesini aşıyor (%s %s)",
                           len(asiyan), stock, timeframe)

        if not self.enabled:
            logger.info(f"[MOCK TELEGRAM {state}]\n{message}\n")
            if self.should_send_to_public(data):
                # Public hedef artık bültenle gider; mock modda yalnız görünürlük.
                logger.info(f"[MOCK PUBLIC {state}] {stock} {timeframe} bültene eklenecek")
            key = self._cooldown_key(stock, pattern, timeframe, state)
            self.last_sent[key] = datetime.now(ISTANBUL_TZ)
            self._gonderim_kaydet()
            self.gonderilen_alarm += 1
            self._gonderim_sagligi_kaydet(basari=True)
            self._tek_seferlik_isle(
                stock, pattern, timeframe, state, formation_id=data.get("formation_id")
            )
            return True

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {'chat_id': self.chat_id, 'text': message}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram gönderildi: {stock} {pattern} {state}")
                key = self._cooldown_key(stock, pattern, timeframe, state)
                self.last_sent[key] = datetime.now(ISTANBUL_TZ)
                self._cooldown_kaydet()
                self._gonderim_kaydet()
                self.gonderilen_alarm += 1
                self._gonderim_sagligi_kaydet(basari=True)
                # Tek-seferlik mühür: DM ve public hedef aynı kapıdan geçtiği
                # için her ikisi de tekilleşir.
                self._tek_seferlik_isle(
                    stock, pattern, timeframe, state, formation_id=data.get("formation_id")
                )
                # NOT: Public (grup) gönderimi burada YAPILMAZ. Olaylar tarama
                # turu boyunca `public_kuyruk()` ile toplanır ve tur sonunda tek
                # bültende gider; DM başarısız olsa bile grup yayını etkilenmez.
                # Prepared media is sent synchronously by the durable FIFO.
                # This method only acknowledges the text component.
                return True
            else:
                ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
                logger.error(f"Telegram hatası: {resp.text} | {ipucu}")
                self._gonderim_sagligi_kaydet(basari=False, hata=ipucu)
                return False
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            self._gonderim_sagligi_kaydet(basari=False, hata=f"istek hatasi: {e}")
            return False


if __name__ == "__main__":
    notifier = TelegramNotifier()
    test_cases = [
        {'stock_name': 'THYAO', 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen', 'state': 'ADAY_OLUSUYOR', 'confidence_score': 83, 'critical_price_level': 302.11, 'upper_now': 302.11, 'lower_now': 294.32, 'contraction': 0.87, 'timestamp': datetime.now(), 'upper_touches': 2, 'lower_touches': 2, 'age_bars': 18},
        {'stock_name': 'GARAN', 'timeframe': '4h', 'pattern_name': 'Simetrik Üçgen', 'state': 'SIKISMA_GUCLENIYOR', 'confidence_score': 88, 'critical_price_level': 120.5, 'upper_now': 122.0, 'lower_now': 119.0, 'contraction': 0.91, 'timestamp': datetime.now(), 'upper_touches': 3, 'lower_touches': 2, 'age_bars': 22},
        {'stock_name': 'AKBNK', 'timeframe': '1h', 'pattern_name': 'Alçalan Kama', 'state': 'KIRILIM_ADAYI', 'confidence_score': 82, 'critical_price_level': 58.3, 'upper_now': 58.3, 'lower_now': 55.1, 'contraction': 0.75, 'break_dir': 1, 'break_strength': 82, 'timestamp': datetime.now()},
    ]
    for tc in test_cases:
        print(notifier.format_message(tc))
        print("---")
