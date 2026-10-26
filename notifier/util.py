# notifier/util.py — saf biçim yardımcıları + kart/sözlük sabitleri (Faz 1).
# Taşıma: notifier.py → notifier/ paketi; davranış aynı, yalnız yapı değişti.
# Yama yüzeyi: bu modül DEĞİL, notifier/__init__.py (plan §3, test_patch_yuzeyi).

import logging
import notifier as _pkg  # yamalı adlar için geç bağlama (plan §3)

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

CONFIRMED_PUBLIC_STATES = frozenset({
    "KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI",
})

KRITIK_STATELER = tuple(sorted(CONFIRMED_PUBLIC_STATES))

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

# Public grup için SADE durum etiketleri: iç izleme notları ("teyit bekleniyor",
# "retest tutarsa yapı güçlenir") gruba taşınmaz.
PUBLIC_STATE_ETIKET = {
    "KIRILIM_TEYITLI": "kapanışla teyitli kırılım",
    "RETEST_BASARILI": "kapanışla başarılı retest",
    "KIRILIM_GECERSIZLESTI": "önceki teyitli kırılım geçersizleşti",
}

TF_EVENT_HUMAN = {
    "1h": "1 saat",
    "2h": "2 saat",
    "4h": "4 saat",
    "1d": "1 gün",
}

TF_HUMAN = {
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
}

TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}

# Türkçe ay kısaltmaları: strftime('%b') sistem yerelinden İngilizce basıyordu
# ("02 Oct 20:05"); mesajların tamamı Türkçe olduğu için tarih de Türkçe olmalı.
_AY_KISALTMALARI = {
    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara",
}

# Günlük engel sayaçları: /durum ve teşhis bu anahtarları gösterir. Yeni engel
# eklendiğinde TEK yerde dursun diye tuple; `_gunu_sifirla_gerekirse` de bunu kullanır.
_ENGEL_SAYACLAR = {
    "cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0, "tekrar": 0,
    # "baglam_degismedi": bağlam bloğu birebir aynıysa kart kısaltıldı (kopya blok basılmadı).
    "baglam_degismedi": 0,
}

_FORMATION_ALERT_MUHR_TTL_SAAT = 7 * 24

#: Kart metninde ay adı açık yazılır (`21 Ekim`), sayısal kısa yazım (`21.10`)
#: kullanılmaz. Tek kaynak: `_kart_mum_damgasi` ve `_kart_yas_metni` buradan okur.
_KART_AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")

#: Sade kartın satır tavanı (CTA ve yasal uyarı dahil). GÖRSEL-8 kullanıcı
#: kararı (2026-10-21): "alarm metni kendi başına okunabilsin" — kart, kârenin
#: taşıdığı her şeyi değil, KARAR İÇİN GEREKEN ölçüleri taşır. Tavan aşılırsa
#: en düşük öncelikli ek satır düşer (bilgi gizlenmez, ölçülerek seçilir).
#: GÖRSEL-9 (2026-10-22): 7 bloklu düzen + blok arası 1 boş satır. Boş satırlar
#: tavan hesabına GİRMEZ (bütçe px ile ölçülür); tavan 16 -> 20 çıktı çünkü
#: `◇` ölçü bloğu 3 satıra ve ölçüm dipnotu karta girdi.
# 2026-10-23: sade dil iki satırı böldü (kalite/güç, dönüş/üst TF, ölçüm
# dipnotu) ve `engel`/`goreli` satırları aynı kartta basılabiliyor → tavan 22.
# Ölçülen en dolu kart 22 satır / 620 kr; sınır 1100 kr.
_KART_MAKS_SATIR = 22

_KART_OLAY = {
    # İkinci satırdaki kısa not, ilk satırda söylenmeyeni söyler (kullanıcı kararı
    # 2026-10-23): "TEYİTLİ" neyin teyidi olduğunu söylemiyordu — artık olay
    # KIRILIM, teyidin türü ikinci satırda ("kapanış onaylı").
    "KIRILIM_TEYITLI": ("KIRILIM", "kapanış onaylı"),
    # RETEST BAŞARILI teknik ad; sade karşılığı kırılan seviyenin korunması.
    "RETEST_BASARILI": ("SEVİYE KORUNDU", "kırılan seviye tuttu"),
    "KIRILIM_GECERSIZLESTI": ("KIRILIM İPTAL", "banda döndü"),
}

#: Uzun formasyon adı + uzun not bütçeyi aşınca kullanılan kısa not. Başlık
#: zaten olayı söylüyor (`SEVİYE KORUNDU`), not yalnız ayrıntıyı ekler.
_KART_OLAY_KISA = {"RETEST_BASARILI": "seviye tuttu"}

# mtf_destek yalnız 1h→4h ve 4h→1g için hesaplanır (main.py); etiket bu yüzden
# alarm TF'sine göre yazılır. Eskiden her durumda "4h destekliyor" deniyordu.
# Kart ızgarası kısa kodu (`4s`) kullanır; ÜST TF satırı sözcükle yazılır çünkü
# tek başına "4s de onaylı" neyin onaylandığını söylemiyordu.
_KART_UST_TF = {"1h": "4s", "2h": "4s", "4h": "1g"}

_KART_UST_TF_SOZ = {"1h": "4 saatlik", "2h": "4 saatlik", "4h": "günlük"}

# --- TELEFON KARTI (düz metin; parse_mode yok) ----------------------------
# 25 Eyl canlı akışında alarm başına 1358-1559 karakter / 47-54 görsel satır
# oluşuyordu ve 120 satır telefonda sarmalanıyordu. Kart kuralları:
#   1 satır = 1 bilgi grubu · satır ≤ TELEGRAM_SATIR_PX (px) · gruplar boş satırla
#   ayrılır · olay ilk satırda (bildirim önizlemesi okunabilsin) · hizalama için
#   boşluk kullanılmaz (orantılı yazı tipinde bozulur) · bilgi kesilmez, sığmıyorsa
#   devam satırına taşınır.
_KART_YON = {1: "YUKARI", -1: "AŞAĞI"}

_PUBLIC_MAX_METIN = 4000     # Telegram sınırı 4096; kanal/grup yolu da kırpmalı

# Zaman dilimi -> bir bar kaç saat? Tek-seferlik mühürün bayatma süresi buna
# göre ölçeklenir (bkz. _muhur_ttl_saat).
_TF_BAR_SAAT = {"1h": 1, "2h": 2, "4h": 4, "1d": 24}

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


def _env_temizle(deger) -> str:
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()


def _evren_ozeti(ayrinti: bool = True) -> str:
    """Evren etiketi; tek kaynak `config.evren_ozeti`.

    Varsayılan `ayrinti=False`: özet/panel satırları 283 px bütçesinde; uzun
    parantez satırı bölüyordu ("… + 5 endeks +\n   4 makro) × 4 zaman dilimi").
    Ayrıntılı hâli `/durum`da (main) kullanılır.
    """
    import config as _config
    return _config.evren_ozeti(ACTIVE_STOCKS, ayrinti=ayrinti)


def _format_price(value) -> str:
    """Fiyat metni (Türkçe ondalık). Boşta hiçbir sayı basılmaz: `""`.

    Biçim tek kaynaktan gelir (`reporting.format.sayi`); G0 öncesi burada
    nokta kalıp kartta virgül çıkıyordu — aynı sayı iki görünümde okunuyordu.
    """
    return _sayı(value)


def _format_price_tl(value) -> str:
    """BIST fiyatını Türkçe ondalık ayırıcı ve TL ekiyle biçimlendir."""
    formatted = _format_price(value)
    return f"{formatted} TL" if formatted else ""


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


def _grafik_salteri_acik() -> bool:
    """Grafik kill-switch'ini grafik modülünü içe aktarmadan oku.

    `grafik.grafik_aktif_mi()` ile aynı env sözleşmesi: eksik/boş/`yok` kapalı,
    diğer değerler açık. Bu kontrol, kill-switch kapalıyken grafik katmanını
    gereksiz yere yüklememek için notifier içinde tutulur.
    """
    return (os.environ.get("TELEGRAM_GRAFIK") or "yok").strip().lower() != "yok"


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


def _kirp(metin: str, sinir: int = _PUBLIC_MAX_METIN) -> str:
    """Public gönderim için Telegram sınırına sığdırır (eskiden kırpma yoktu →
    uzun özet 400 alabiliyordu)."""
    metin = str(metin or "")
    if len(metin) <= sinir:
        return metin
    return metin[: sinir - 40].rstrip() + "\n\n… (mesaj sınırı nedeniyle kesildi)"


def _kuyruk_verisi(data: Dict) -> Dict:
    """Persist a detached chart snapshot as well as the text context.

    These are plain chart dictionaries, not DataFrames or engine instances.
    The tagged JSON codec preserves their timestamps across restarts.
    """
    from notification_delivery import freeze
    return freeze(data or {})


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


def _summary_int(gun_ozeti: Dict, key: str) -> int:
    try:
        return max(0, int((gun_ozeti or {}).get(key) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _tr_tarih(dt: datetime) -> str:
    """Kısa Türkçe tarih: '02 Eki 20:05'. Gün/ay/saat hizalı kalır (telefonda düzgün görünür)."""
    return f"{dt.day:02d} {_AY_KISALTMALARI.get(dt.month, '')} {dt:%H:%M}"


def _yon_kisa(break_dir) -> str:
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return ""


def _yon_metni(break_dir) -> str:
    """Kırılım yönünü Türkçe tek kelimeye çevirir (özet satırları için)."""
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return "belirsiz"


def _yuzde(value, basamak: int = 1) -> str:
    metin = _sayı(value, basamak)
    return f"%{metin}" if metin else ""


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


