# notifier/format_summary.py — kapanış özeti / public izleme satırları (Faz 1).

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

from notifier.format_kart import devamlilik_puani  # tek yönlü: format_kart → yok

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
    # 2026-10-25: sıralama ölçüsü devamlılık puanı (ölçülmüş fazla), geometri değil.
    # Kartla aynı sayı okunsun diye puan burada da hesaplanır.
    def _sira_degeri(f: Dict) -> float:
        p = devamlilik_puani(f)
        if p is not None:
            return float(p)
        try:
            return float(f.get('confidence_score') or 0) * 0.5   # kapsam dışı: geriye düşsün
        except (TypeError, ValueError):
            return 0.0

    try:
        adaylar.sort(key=_sira_degeri, reverse=True)
    except (TypeError, ValueError):
        pass
    sonuc = []
    for f in adaylar[:adet]:
        sonuc.append({"stock": f.get("stock_name"), "timeframe": f.get("timeframe"),
                      "pattern_name": f.get("pattern_name"),
                      "quality": devamlilik_puani(f)})
    return sonuc


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


PIYASA_SEMBOLLERI = ("XU100", "XAUUSD", "XAGUSD")


def piyasa_snapshot(deque_manager) -> Dict[str, Dict]:
    """Gunluk kapanistan piyasa ozeti: XU100 + XAUUSD/XAGUSD (fallback-safe)."""
    sonuc: Dict[str, Dict] = {}
    if deque_manager is None:
        return sonuc
    for sym in PIYASA_SEMBOLLERI:
        try:
            df = deque_manager.to_gunluk_dataframe(sym)  # type: ignore[attr-defined]
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        try:
            son = float(df.iloc[-1]["close"])
        except Exception:
            continue
        deg = None
        if len(df) >= 2:
            try:
                onceki = float(df.iloc[-2]["close"])
                if onceki:
                    deg = (son - onceki) / onceki * 100.0
            except Exception:
                deg = None
        sonuc[sym] = {"fiyat": son, "degisim": deg}
    return sonuc


def movers_snapshot(deque_manager, limit: int = 3) -> Dict[str, List[Dict]]:
    """1g gunluk kapanistan en cok yukselen/dusen (fallback-safe)."""
    if deque_manager is None:
        return {"yukselen": [], "dusen": []}
    try:
        from config import sembol_turu as _tur
    except Exception:
        _tur = lambda s: "hisse"  # type: ignore
    adaylar: List[Dict] = []
    for sym in ACTIVE_STOCKS:
        try:
            if _tur(sym) != "hisse":
                continue
        except Exception:
            pass
        try:
            df = deque_manager.to_gunluk_dataframe(sym)  # type: ignore[attr-defined]
        except Exception:
            continue
        if df is None or len(df) < 2:
            continue
        try:
            son = float(df.iloc[-1]["close"])
            onceki = float(df.iloc[-2]["close"])
            if not onceki:
                continue
            pct = (son - onceki) / onceki * 100.0
            adaylar.append({"sembol": sym, "fiyat": son, "degisim": pct})
        except Exception:
            continue
    try:
        yukselen = sorted([a for a in adaylar if a["degisim"] > 0],
                          key=lambda x: x["degisim"], reverse=True)[: max(0, int(limit))]
        dusen = sorted([a for a in adaylar if a["degisim"] < 0],
                       key=lambda x: x["degisim"])[: max(0, int(limit))]
    except Exception:
        yukselen, dusen = [], []
    return {"yukselen": yukselen, "dusen": dusen}


def _format_piyasa_satirlari(piyasa: Dict[str, Dict]) -> List[str]:
    satirlar: List[str] = []
    if not isinstance(piyasa, dict) or not piyasa:
        return satirlar
    for sym in PIYASA_SEMBOLLERI:
        veri = piyasa.get(sym)
        if not isinstance(veri, dict):
            continue
        fiyat = veri.get("fiyat")
        deg = veri.get("degisim")
        fiyat_str = _sayı(fiyat, 2) if fiyat is not None else ""
        if deg is None:
            satirlar.append(f"• {sym} {fiyat_str}".strip())
        else:
            try:
                ok = "↑" if float(deg) > 0 else ("↓" if float(deg) < 0 else "→")
                pct = f"%{abs(float(deg)):.2f}".replace(".", ",")
            except Exception:
                ok, pct = "", ""
            satirlar.append(f"• {sym} {fiyat_str} {ok} {pct}".replace("  ", " ").strip())
    return satirlar


def _format_movers_satirlari(movers: Dict[str, List[Dict]]) -> List[str]:
    satirlar: List[str] = []
    if not isinstance(movers, dict):
        return satirlar
    yukselen = movers.get("yukselen") or []
    dusen = movers.get("dusen") or []
    if yukselen:
        try:
            parca = " · ".join(
                f"{a.get('sembol')} %{abs(float(a.get('degisim') or 0)):.2f}".replace(".", ",")
                for a in yukselen[:3] if isinstance(a, dict) and a.get("sembol")
            )
            if parca:
                satirlar.append(f"• Yükselen: {parca}")
        except Exception:
            pass
    if dusen:
        try:
            parca = " · ".join(
                f"{a.get('sembol')} %{abs(float(a.get('degisim') or 0)):.2f}".replace(".", ",")
                for a in dusen[:3] if isinstance(a, dict) and a.get("sembol")
            )
            if parca:
                satirlar.append(f"• Düşen: {parca}")
        except Exception:
            pass
    return satirlar


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


