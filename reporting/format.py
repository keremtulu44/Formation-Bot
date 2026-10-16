"""Batch 8 / C2 — Raporlama katmanı: main.py'den ayrılan SAF metin/sayı üretimi.

Bu modüldeki fonksiyonlar canlı durumu (LiveState, global sayaçlar) OKUMAZ; kayıt
listelerini/damgaları parametre olarak alır. Böylece Telegram mesajlarının biçimi
main döngüsünden bağımsız test edilebilir hale gelir; `main.py` ince
orkestratöre doğru küçülür.

Davranış değişmedi: metinler birebir aynı (yalnız taşıma).

G0 (2026-10-13): `sayi()` kullanıcıya dönük tüm metinler için tek sayı
standardıdır — ondalık ayıracı Türkçe virgül. Bkz. GRAFIK_TASARIM.md §15/§19.
"""

import logging
from datetime import datetime
from math import isfinite
from typing import List

from config import ISTANBUL_TZ, ACTIVE_STOCKS

logger = logging.getLogger(__name__)


def son_bar_yasi_dakika_str(dk: float) -> str:
    """Dakikayı insan okunur yapar: 95 -> '1sa 35dk', 1500 -> '1g 1sa'."""
    dk = max(0, int(round(dk)))
    if dk >= 24 * 60:
        gun, kalan = divmod(dk, 24 * 60)
        return f"{gun}g {kalan // 60}sa"
    if dk < 60:
        return f"{dk} dk"
    return f"{dk // 60}sa {dk % 60}dk"


STATE_TR = {
    "ADAY_OLUSUYOR": "Aday oluşuyor",
    "GEOMETRI_ADAYI": "Geometri adayı",
    "FORMASYON_TANIMLANDI": "Formasyon tanımlandı",
    "OLGUNLASIYOR": "Olgunlaşıyor",
    "SIKISMA_GUCLENIYOR": "Sıkışma güçleniyor",
    "KIRILIM_HAZIRLIGI": "Kırılım hazırlığı",
    "KIRILIM_DENEMESI": "Kırılım denemesi",
    "KIRILIM_ADAYI": "Kırılım adayı",
    "KIRILIM_TEYITLI": "Kırılım teyitli",
    # Bildirim katmanı alias'ı; patterns/lifecycle state'ini değiştirmez.
    "KIRILIM_GECERSIZLESTI": "Kırılım geçersizleşti",
    "RETEST_BEKLENIYOR": "Retest bekleniyor",
    "RETEST_EDILIYOR": "Retest ediliyor",
    "RETEST_BASARILI": "Retest başarılı",
    "FORMASYON_TAMAMLANDI": "Formasyon tamamlandı",
    # Kapanış durumları: eskiden ham enum ("BASARISIZ_KIRILIM") görünüyordu.
    "BASARISIZ_KIRILIM": "Kırılım başarısız",
    "BASARISIZ_RETEST": "Retest başarısız",
    "FORMASYON_GECERSIZ": "Formasyon geçersiz",
    "GECERSIZ": "Geçersiz",
    # /canli çıktısında ham enum olarak görünen üç state (bkz. patterns/constants):
    "FORMASYON_YOK": "Formasyon yok",
    "KIRILIM_TEYIT_ALAMADI": "Kırılım teyit alamadı",
    "FORMASYON_ZAYIFLADI": "Formasyon zayıfladı",
}

# Kompakt listeler (/canli) için kısa durum. Uzun hali okumak zor, ham enum ise
# hiç okunamaz; satır bütçesi de kısa adı zorunlu kılıyor.
KISA_DURUM = {
    "FORMASYON_YOK": "—",
    "ADAY_OLUSUYOR": "aday",
    "GEOMETRI_ADAYI": "geometri",
    "FORMASYON_TANIMLANDI": "tanımlandı",
    "OLGUNLASIYOR": "olgunlaşıyor",
    "SIKISMA_GUCLENIYOR": "sıkışma",
    "KIRILIM_HAZIRLIGI": "hazırlık",
    "KIRILIM_DENEMESI": "deneme",
    "KIRILIM_ADAYI": "kırılım adayı",
    "KIRILIM_TEYITLI": "teyitli",
    "KIRILIM_GECERSIZLESTI": "geçersizleşti",
    "KIRILIM_TEYIT_ALAMADI": "teyitsiz",
    "RETEST_BEKLENIYOR": "retest bekliyor",
    "RETEST_EDILIYOR": "retestte",
    "RETEST_BASARILI": "retest başarılı",
    "BASARISIZ_KIRILIM": "kırılım başarısız",
    "BASARISIZ_RETEST": "retest başarısız",
    "FORMASYON_TAMAMLANDI": "tamamlandı",
    "FORMASYON_ZAYIFLADI": "zayıfladı",
    "FORMASYON_GECERSIZ": "geçersiz",
    "GECERSIZ": "geçersiz",
}


def kisa_durum(state) -> str:
    """State'i Türkçe ve kısa yazar; bilinmiyorsa STATE_TR, o da yoksa ham değeri."""
    anahtar = str(state or "").strip().upper()
    return KISA_DURUM.get(anahtar) or STATE_TR.get(anahtar) or (str(state or "—") or "—")

def gecen_sure(iso_zaman):
    """'12 dk önce' gibi kısa yaş metni."""
    if not iso_zaman:
        return "—"
    try:
        an = datetime.fromisoformat(iso_zaman)
    except (TypeError, ValueError):
        return "—"
    if an.tzinfo is None:
        an = ISTANBUL_TZ.localize(an)
    fark = (datetime.now(ISTANBUL_TZ) - an).total_seconds()
    if fark < 90:
        return f"{int(fark)} sn önce"
    if fark < 5400:
        return f"{int(fark // 60)} dk önce"
    return f"{sayi(fark / 3600, 1)} sa önce"

# Zaman dilimi adları (Telegram metinleri): notifier'daki TF_HUMAN ile aynı dil.
# reporting katmanı notifier'ı import ETMEZ (ters yön: notifier -> reporting), bu
# yüzden küçük eşleme burada tutulur.
TF_TR = {"1h": "1 saatlik", "2h": "2 saatlik", "4h": "4 saatlik", "1d": "günlük"}


def mum_kapanis_metni(tf_name: str, bar_zamani=None, bar_kapanis=None) -> str:
    """Mesaj satırı: bildirime kaynak olan KAPANMIŞ mumun aralığı.

    "Bu mesaj hangi mumun kapanışıyla geldi?" sorusu mesajın içinde cevaplanır
    (P0 doğrulaması sonrası eklenen güven satırı). Örnekler:
      1h  -> "🕒 1 saatlik mum 25.09 17:30 → 18:00 kapandı"
      4h  -> "🕒 4 saatlik mum 25.09 13:30 → 17:30 kapandı"
      1d  -> "🕒 Günlük mum 25.09 kapanışı · 18:30"
    Boş/geçersiz damgada "" döner (mesaj üretimi asla bozulmaz).
    """
    if bar_zamani is None:
        return ""
    try:
        if str(tf_name) == "1d":
            gun = bar_zamani.strftime("%d.%m")
            if bar_kapanis is not None and callable(getattr(bar_kapanis, "strftime", None)):
                return f"🕒 Günlük mum {gun} kapanışı · {bar_kapanis.strftime('%H:%M')}"
            return f"🕒 Günlük mum {gun} kapanışı"
        ad = TF_TR.get(str(tf_name), str(tf_name))
        baslangic = bar_zamani.strftime("%d.%m %H:%M")
        if bar_kapanis is not None and callable(getattr(bar_kapanis, "strftime", None)):
            return f"🕒 {ad} mum {baslangic} → {bar_kapanis.strftime('%H:%M')} kapandı"
        return f"🕒 {ad} mum {baslangic} kapandı"
    except (AttributeError, ValueError, TypeError):
        return ""


_TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}


def tf_kisa(tf) -> str:
    """Alarm kartındaki kısaltma (1s/2s/4s/1g): aynı bilgi, liste satırında yer açar."""
    return _TF_KISA.get(str(tf or "").strip().lower(), str(tf or ""))


def sayi(deger, basamak=2, varsayilan="—"):
    """Kullanıcıya dönük sayı metni: ondalık ayıracı Türkçe virgül (`46,37`).

    Neden tek nokta: kart, günlük özet, /panel, /formasyonlar ve backtest aynı
    kuralı kullanmalı; ayraç yüzeyler arasında farklı olunca aynı fiyat iki
    görünümde çıkıyordu (G0).
    Binlik ayracı bilinçli olarak YOK: sayaçlar (`360 bar`) ve telefon satır
    bütçesi (≤283 px testi) bundan etkilenmemeli; ayrıca `50,00` ondalığı
    kırpılmaz (bilgi kaybı olmaz).
    NaN/sonsuza da `varsayilan` döner: kullanıcı metninde `nan` görünmez.
    """
    try:
        deger_sayi = float(deger)
    except (TypeError, ValueError, OverflowError):
        return varsayilan
    if not isfinite(deger_sayi):
        return varsayilan
    return f"{deger_sayi:.{basamak}f}".replace(".", ",")


def filtrele_formasyonlar(formations, filtre: str):
    """Filtre: '1h', 'THYAO', '1h THYAO' gibi çoklu token destekler."""
    filtre = (filtre or "").strip().lower()
    if not filtre:
        return formations
    tokens = filtre.split()
    result = formations
    for tok in tokens:
        if tok in ("1h", "2h", "4h", "1d"):
            result = [f for f in result if str(f.get("timeframe", "")).lower() == tok]
        else:
            result = [f for f in result
                      if tok in str(f.get("stock", "")).lower()
                      or tok in str(f.get("pattern_name", "")).lower()
                      or tok in str(f.get("state", "")).lower()]
    return result


def break_ok(bd) -> str:
    try:
        bd = int(bd)
    except Exception:
        return "↔️"
    if bd == 1:
        return "⬆️"
    if bd == -1:
        return "⬇️"
    return "↔️"


PANEL_TIMEFRAMES = ("1h", "2h", "4h", "1d")
PANEL_TOP_KRITIK = 12        # analiz puanına göre en anlamlı 12 canlı aday
PANEL_MESAJ_SINIRI = 3800    # Telegram 4096; kirp() kesmesin diye kendimiz sığdırırız

# Ham bileşenler: kalite ağırlığı 65; formasyonun teyit/durum aşaması en çok 24 puan;
# iki taraflı temas en çok 9 puan; daralma en çok 5 puan; MTF teyidi en çok 5.
# Bu bir AL/SAT skoru değil, tespit edilen adayları şeffaf biçimde sıralama kuralıdır.
PANEL_DURUM_PUANI = {
    "KIRILIM_TEYITLI": 24,
    "RETEST_BASARILI": 22,
    "KIRILIM_ADAYI": 21,
    "RETEST_EDILIYOR": 19,
    "RETEST_BEKLENIYOR": 18,
    "KIRILIM_DENEMESI": 16,
    "KIRILIM_HAZIRLIGI": 15,
    "FORMASYON_TAMAMLANDI": 14,
    "SIKISMA_GUCLENIYOR": 13,
    "OLGUNLASIYOR": 10,
    "FORMASYON_TANIMLANDI": 8,
    "GEOMETRI_ADAYI": 5,
    "ADAY_OLUSUYOR": 3,
}

PANEL_IPUCU = "💡 sıralama kalite + durum + temas + daralma + MTF teyidine dayanır · yatırım tavsiyesi değildir"

def panel_kalite(kayit) -> float:
    """Kalite alanı bozuk/eksik gelse de panel çökmesin."""
    try:
        return float((kayit or {}).get("quality") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def panel_sembol(state) -> str:
    """State -> tek işaret (slot hücresinde yer kazanmak için)."""
    s = str(state or "").upper()
    if s.startswith("KIRILIM"):
        return "🚀"
    if s.startswith("RETEST"):
        return "🎯"
    if s == "FORMASYON_TAMAMLANDI":
        return "🏁"
    if s == "SIKISMA_GUCLENIYOR":
        return "⚡"
    if s.startswith("BASARISIZ") or s.endswith("GECERSIZ"):
        return "⛔"
    return "•"


# Slot tablosundaki tek harflik işaretlerin anlamı. Panelde yalnızca GÖRÜNEN
# işaretler açıklanır: "87⛔" satırının anlamı artık okuyucuya sorulmuyor.
PANEL_SEMBOL_ANLAMI = {
    "🚀": "kırılım",
    "🎯": "retest",
    "🏁": "tamamlandı",
    "⚡": "sıkışma",
    "⛔": "başarısız/geçersiz",
}


def panel_sembol_anahtari(kayitlar) -> str:
    """Panelde görünen işaretlerin tek satırlık açıklaması (yoksa boş)."""
    kayitlar = list(kayitlar or [])
    gorunen = [f"{s} {PANEL_SEMBOL_ANLAMI[s]}"
               for s in PANEL_SEMBOL_ANLAMI
               if any(panel_sembol((k or {}).get("state")) == s for k in kayitlar)]
    if not gorunen:
        return ""
    return "🔑 " + " · ".join(gorunen)


def panel_hucre(kayit, tf: str) -> str:
    """Tek slot hücresi: '1h 87🚀' ya da boşsa '1h —'."""
    if not kayit:
        return f"{tf} —"
    return f"{tf} {panel_kalite(kayit):.0f}{panel_sembol(kayit.get('state'))}"


def panel_aday_puani(kayit) -> float:
    """Kalite, lifecycle teyidi ve geometrik destekten normalize 0-100 puan."""
    kayit = kayit or {}
    kalite = max(0.0, min(100.0, panel_kalite(kayit)))
    state = str(kayit.get("state") or "").upper()
    durum = float(PANEL_DURUM_PUANI.get(state, 0))
    try:
        ust_temas = max(0.0, min(3.0, float(kayit.get("upper_touches") or 0)))
    except (TypeError, ValueError):
        ust_temas = 0.0
    try:
        alt_temas = max(0.0, min(3.0, float(kayit.get("lower_touches") or 0)))
    except (TypeError, ValueError):
        alt_temas = 0.0
    try:
        daralma = max(0.0, min(1.0, float(kayit.get("contraction") or 0)))
    except (TypeError, ValueError):
        daralma = 0.0
    try:
        mtf = 5.0 if kayit.get("mtf_destek") else 0.0
    except Exception:
        mtf = 0.0
    toplam = 0.65 * kalite + durum + 1.5 * (ust_temas + alt_temas) + 5.0 * daralma + mtf
    return round(min(100.0, toplam * 100.0 / 108.0), 1)


def panel_kritik_anahtar(kayit):
    """En yüksek kompozit puan önce; kalite ve sembol deterministik tie-break."""
    return (-panel_aday_puani(kayit), -panel_kalite(kayit),
            str((kayit or {}).get("stock") or ""),
            str((kayit or {}).get("timeframe") or ""))


def panel_filtre_coz(arguman: str, evren=None):
    """Argümanı (kolonlar, hisse_tokenlari) olarak ayırır.

    - Zaman dilimi token'ları (1h/2h/4h/1d) gösterilecek SLOT sütunlarını seçer.
    - Evrendeki bir hisseye (en az 3 karakter) uyan token'lar satırları daraltır.
    - Kalan token'lar (kirilim, üçgen, KIRILIM_TEYITLI ...) sayıları ve top-12
      listesini süzer (filtrele_formasyonlar ile aynı sözdizimi).

    `evren` verilmezse config'teki ACTIVE_STOCKS kullanılır; main kendi
    (monkeypatch edilebilir) evrenini açıkça geçirir.
    """
    tokens = [t for t in (arguman or "").replace(",", " ").split() if t]
    kolonlar = tuple(t.lower() for t in tokens if t.lower() in PANEL_TIMEFRAMES)
    hisse_tokenlari = []
    for t in tokens:
        tl = t.lower()
        if tl in PANEL_TIMEFRAMES or len(tl) < 3:
            continue
        if any(tl in s.lower() for s in (evren if evren is not None else ACTIVE_STOCKS)):
            hisse_tokenlari.append(tl)
    return (kolonlar or PANEL_TIMEFRAMES), hisse_tokenlari


def panel_durum_sayilari(kayitlar) -> str:
    """State gruplarına göre sayılar: kırılım/retest/tamamlanan/sıkışma/diğer."""
    kirilim = retest = tamam = sikis = diger = 0
    for f in kayitlar:
        s = str(f.get("state") or "").upper()
        if s.startswith("KIRILIM"):
            kirilim += 1
        elif s.startswith("RETEST"):
            retest += 1
        elif s == "FORMASYON_TAMAMLANDI":
            tamam += 1
        elif s == "SIKISMA_GUCLENIYOR":
            sikis += 1
        else:
            diger += 1
    return (f"🚀 kırılım {kirilim} · 🎯 retest {retest} · 🏁 tamamlanan {tamam} · "
            f"⚡ sıkışma {sikis} · • diğer {diger} · toplam {len(kayitlar)}")


def panel_kritik_listesi(kayitlar, adet: int = PANEL_TOP_KRITIK):
    """Kompozit puana göre ilk `adet` kayıt (fiyat seviyesiyle)."""
    sirali = sorted(kayitlar, key=panel_kritik_anahtar)[:adet]
    baslik = f"🔥 TOP {adet} ANLAMLI ADAY (puan)"
    if len(kayitlar) > adet:
        baslik += f" ({len(kayitlar)} kayıt içinden)"
    satirlar = [baslik]
    if not sirali:
        satirlar.append("— (filtreye uyan formasyon yok)")
        return satirlar
    for i, f in enumerate(sirali, 1):
        durum = STATE_TR.get(str(f.get("state")), str(f.get("state") or "—"))
        satirlar.append(
            f"{i:>2}) {f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} "
            f"puan {sayi(panel_aday_puani(f), 1)} · q{sayi(f.get('quality'), 0)} "
            f"{panel_sembol(f.get('state'))} {durum}"
            f" · kritik {sayi(f.get('critical_price'))}"
        )
    return satirlar


def panel_sigdir(grid_satirlari, butce: int):
    """Slotsatırlarını mesaj bütçesine sığdırır; sığmayan kuyruk tek satırda özetlenir."""
    secilen = []
    kullanilan = 0
    for i, satir in enumerate(grid_satirlari):
        uzunluk = len(satir) + 1
        if kullanilan + uzunluk <= butce:
            secilen.append(satir)
            kullanilan += uzunluk
            continue
        kalan = len(grid_satirlari) - i
        secilen.append(f"… ve {kalan} satır daha (filtre: /panel THYAO)")
        break
    return secilen


def veri_durumu_satiri(data_asof, fresh_fetch=None, requested=None, fetch_failures=None,
                        oldest_age_minutes=None) -> str:
    """Son tamamlanmış mum zamanı/yaşı ve fetch durumunu tutarlı biçimde göster."""
    if not data_asof:
        return "📡 Son tamamlanmış mum: bu analizde veri zamanı yok"
    try:
        bar = datetime.fromisoformat(str(data_asof))
        if bar.tzinfo is None:
            bar = ISTANBUL_TZ.localize(bar)
        else:
            bar = bar.astimezone(ISTANBUL_TZ)
        yas = max(0.0, (datetime.now(ISTANBUL_TZ) - bar).total_seconds() / 60.0)
        zaman = bar.strftime("%d.%m.%Y %H:%M %Z")
        yas_metni = son_bar_yasi_dakika_str(yas)
    except (TypeError, ValueError, OverflowError):
        zaman, yas_metni = str(data_asof), "hesaplanamadı"
    fetch = ""
    if fresh_fetch is not None:
        kapsam = requested if requested is not None else "?"
        hata = f" · fetch hatası {fetch_failures}" if fetch_failures is not None else ""
        fetch = f" · başarılı fetch {fresh_fetch}/{kapsam}{hata}"
    eski = (f" · en eski taranan veri yaşı {son_bar_yasi_dakika_str(oldest_age_minutes)}"
            if oldest_age_minutes is not None else "")
    # Tek satıra dizilince 900+ px ediyordu (telefonda 3-4 satıra sarıyordu);
    # veri yaşı/fetch bilgisi ayrı satıra iner, içerik aynı kalır.
    govde = f"📡 Son tamamlanmış mum: {zaman} · veri yaşı {yas_metni}"
    ayrinti = " · ".join(p for p in (eski.strip(" ·"), fetch.strip(" ·")) if p)
    return govde + (f"\n   {ayrinti}" if ayrinti else "")


def format_deferred_alert_summary(records: List[dict], toplam: int = None) -> str:
    """Bekletilmiş düşük öncelikli adayları tek kısa kapanış bölümüne çevir.

    `toplam` verilirse (tampondaki gerçek aday sayısı) kesilenler görünür olur:
    başlıkta "12/21 gösteriliyor" ve altta "… 9 aday daha (tam liste: /formasyonlar)".
    Neden: eşik üstü adaylar sabit bir limitle kırpılıyordu ve kaç tanesinin
    gösterilmediği hiçbir yerde yazmıyordu (kullanıcı: "18 üretiliyor, 3-5'inden
    bahsediliyor").
    """
    if not records:
        return ""
    gosterilen = len(records)
    try:
        toplam_sayi = int(toplam) if toplam is not None else gosterilen
    except (TypeError, ValueError):
        toplam_sayi = gosterilen
    toplam_sayi = max(toplam_sayi, gosterilen)
    # Başlık + alt not ayrı satırlar: "… (12/21 gösteriliyor)" tek satırda
    # 370 px'e çıkıp parça parça kayıyordu.
    baslik = "📡 Gün içi izleme adayları"
    if toplam_sayi > gosterilen:
        # Ayraçla birleştirme: 300 px'ı geçip ortadan ikiye iniyor — her bilgi
        # kendi satırında okunur.
        baslik += f"\n   {gosterilen}/{toplam_sayi} gösteriliyor\n   en yüksek puanlılar"
    else:
        baslik += "\n   en yüksek puanlılar"
    # Politika gereği buffer yalnız WATCH_STATES'teki adayları tutar; state her
    # satırda tekrarlanınca 10 satırlık listede 10 kez aynı kelime okunuyordu.
    # Tek durum varsa başlıkta söylenir, satırlardan düşürülür.
    tek_state = ""
    durumlar = {str(r.get("state") or "") for r in records}
    if len(durumlar) == 1:
        tek_state = STATE_TR.get(durumlar.pop(), "")
    if tek_state:
        baslik += f"\n   {tek_state.lower()}"
    lines = []
    for record in records:
        stock = str(record.get("stock") or "?")
        timeframe = _TF_KISA.get(str(record.get("timeframe") or "").lower(),
                                 str(record.get("timeframe") or ""))
        pattern = str(record.get("pattern_name") or "formasyon")
        state = "" if tek_state else STATE_TR.get(str(record.get("state") or ""),
                                                  str(record.get("state") or "izlemede"))
        try:
            quality = f"kalite {float(record.get('quality') or 0):.0f}"
        except (TypeError, ValueError):
            quality = ""
        contraction = record.get("contraction")
        try:
            contraction_text = f"daralma %{float(contraction) * 100:.0f}" if contraction is not None else ""
        except (TypeError, ValueError):
            contraction_text = ""
        # Ayraç her yerde " · " (eskiden "—", "," ve " · " karışıktı: aynı
        # uygulamada üç farklı madde biçimi okunurluğu bozuyor).
        # /canli satır biçimi: "HISSE TF DESEN q<KALİTE> · <durum>". Başa "• " ve
        # araya fazladan " · " eklemek satırı 300 px'ın üstüne taşıyıp ikiye
        # bölüyordu; liste zaten tek satırda okunuyor.
        quality = quality.replace("kalite ", "q")
        # Madde iki satıra tasarlanır: "hisse + TF + desen + puan" birinci satırda,
        # "durum + daralma + kritik" ikincide. Tek satırda 359 px'a çıkıyordu ve
        # otomatik bölme ayraçları yutunca kelimeler çarpışıyordu.
        ust = " ".join(p for p in ("• " + f"{stock} {timeframe}".strip(), pattern) if p)
        if quality:
            ust += f" {quality}"
        try:
            _kritik = float(record.get("critical_price") or 0)
        except (TypeError, ValueError):
            _kritik = 0.0
        alt = " · ".join(p for p in ("" if tek_state
                                     else kisa_durum(str(record.get("state") or "")),
                                     contraction_text,
                                     sayi(_kritik) if _kritik > 0 else "")
                        if p)
        lines.append(ust)
        if alt:
            lines.append(f"   {alt}")
    if toplam_sayi > gosterilen:
        lines.append(f"… {toplam_sayi - gosterilen} aday daha")
        lines.append("   tam liste: /formasyonlar")
    return baslik + "\n" + "\n".join(lines)


def _istanbul_zamani(ham):
    """Kuyruk JSON'undaki ISO damgayı İstanbul'a normalize et; bozuksa None."""
    if ham is None:
        return None
    try:
        zaman = ham if isinstance(ham, datetime) else datetime.fromisoformat(
            str(ham).replace("Z", "+00:00"))
        return (ISTANBUL_TZ.localize(zaman) if zaman.tzinfo is None
                else zaman.astimezone(ISTANBUL_TZ))
    except (TypeError, ValueError, OverflowError):
        return None


def format_urgent_alert_queue_summary(
    records: List[dict], sessiz_gecersizlesme: int = 0
) -> str:
    """Kapanışta bekleyen teyitli alarmları tek, tarih/saatli bölüme çevir.

    Kuyruktaki olaylar ayrı ayrı gönderilmez; kapanış özeti başarılı olursa bu
    bölümde bir kez gösterilir. Mum damgası olayın zamanını, kuyruk damgası ise
    bildirim engelinin ne zaman başladığını ayırt eder.
    """
    try:
        sessiz_adet = max(0, int(sessiz_gecersizlesme or 0))
    except (TypeError, ValueError, OverflowError):
        sessiz_adet = 0
    if not records and sessiz_adet <= 0:
        return ""
    lines = []
    for item in records or []:
        if not isinstance(item, dict):
            continue
        data = item.get("veri")
        if not isinstance(data, dict):
            continue
        stock = str(data.get("stock_name") or "?").strip().upper()
        timeframe = tf_kisa(data.get("timeframe"))
        state_key = str(data.get("state") or "").strip().upper()
        state = STATE_TR.get(state_key) or kisa_durum(state_key)
        pattern = str(data.get("pattern_name") or "formasyon").strip()
        try:
            quality = f"q{float(data.get('confidence_score')):.0f}" \
                if data.get("confidence_score") is not None else ""
        except (TypeError, ValueError, OverflowError):
            quality = ""
        satir = f"• {stock} {timeframe} · {pattern} · {state}"
        if quality:
            satir += f" · {quality}"
        lines.append(satir)

        ayrinti = str(data.get("bar_metni") or "").strip()
        if not ayrinti:
            bar = _istanbul_zamani(data.get("bar_time") or data.get("timestamp"))
            kapanis = _istanbul_zamani(data.get("bar_kapanis"))
            if bar is not None:
                ayrinti = mum_kapanis_metni(str(data.get("timeframe") or ""), bar, kapanis)
        kuyruk = _istanbul_zamani(item.get("kuyruk_zaman"))
        if kuyruk is not None:
            ayrinti = " · ".join(x for x in (ayrinti, f"kuyruk {kuyruk:%H:%M}") if x)
        if ayrinti:
            lines.append(f"   {ayrinti}")
    parcalar = []
    if lines:
        parcalar.append(
            "📬 Kapanışta özete eklenen teyitli bildirimler\n"
            "   Kota/cooldown nedeniyle beklemişti.\n" + "\n".join(lines)
        )
    if sessiz_adet > 0:
        parcalar.append(
            f"ℹ️ Bildirilmemiş teyit iptali: {sessiz_adet} geçersizleşme (anlık push atlandı)"
        )
    return "\n\n".join(parcalar)
