"""Batch 8 / C2 — Raporlama katmanı: main.py'den ayrılan SAF metin/sayı üretimi.

Bu modüldeki fonksiyonlar canlı durumu (LiveState, global sayaçlar) OKUMAZ; kayıt
listelerini/damgaları parametre olarak alır. Böylece Telegram mesajlarının biçimi
main döngüsünden bağımsız test edilebilir hale gelir; `main.py` ince
orkestratöre doğru küçülür.

Davranış değişmedi: metinler birebir aynı (yalnız taşıma).
"""

import logging
from datetime import datetime
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
    "RETEST_BEKLENIYOR": "Retest bekleniyor",
    "RETEST_EDILIYOR": "Retest ediliyor",
    "RETEST_BASARILI": "Retest başarılı",
    "FORMASYON_TAMAMLANDI": "Formasyon tamamlandı",
}

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
    return f"{fark / 3600:.1f} sa önce"

def sayi(deger, basamak=2, varsayilan="—"):
    try:
        return f"{float(deger):.{basamak}f}"
    except (TypeError, ValueError):
        return varsayilan


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
            f"puan {panel_aday_puani(f):.1f} · q{sayi(f.get('quality'), 0)} "
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
    return f"📡 Son tamamlanmış mum: {zaman} · veri yaşı {yas_metni}{eski}{fetch}"


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
    baslik = "📡 Gün içi izleme adayları"
    if toplam_sayi > gosterilen:
        baslik += f" ({gosterilen}/{toplam_sayi} gösteriliyor)"
    else:
        baslik += " (en yüksek puanlılar)"
    lines = []
    for record in records:
        stock = str(record.get("stock") or "?")
        timeframe = str(record.get("timeframe") or "")
        pattern = str(record.get("pattern_name") or "formasyon")
        state = STATE_TR.get(str(record.get("state") or ""), str(record.get("state") or "izlemede"))
        try:
            quality = f"kalite {float(record.get('quality') or 0):.0f}"
        except (TypeError, ValueError):
            quality = ""
        contraction = record.get("contraction")
        try:
            contraction_text = f", daralma %{float(contraction) * 100:.0f}" if contraction is not None else ""
        except (TypeError, ValueError):
            contraction_text = ""
        lines.append(f"• {stock} {timeframe} {pattern} — {state}, {quality}{contraction_text}".strip())
    if toplam_sayi > gosterilen:
        lines.append(f"… {toplam_sayi - gosterilen} aday daha (tam liste: /formasyonlar)")
    return baslik + "\n" + "\n".join(lines)
