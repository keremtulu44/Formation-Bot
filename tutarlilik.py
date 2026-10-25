# -*- coding: utf-8 -*-
"""Canlı–replay tutarlılık denetimi.

NE SORAR
--------
"Canlıda gönderdiğimiz uyarıyı, aynı barlarla yeniden oynattığımızda motor yine
üretiyor mu?" Üretmiyorsa üç şeyden biri olmuştur:

  1. **Veri boşluğu** — canlıdaki bar serisi ile bugünkü seri aynı değil
     (eksik bar, yeniden çekilmiş/kaymış geçmiş, sessiz 404).
  2. **Motor sapması** — aynı girdi, farklı çıktı (deterministik olmayan yol,
     artımlı/tekil durum farkı).
  3. **Arayüz sapması** — uyarı, motorun o an üretmediği bir şeyi söylemiş.

Üçü de kullanıcının göremeyeceği türden hatalardır: mesaj doğru görünür, ölçüm
yanlış olur. Bu modül onları gece, tek tek yeniden oynatarak yakalar.

NASIL ÇALIŞIR
-------------
* Girdi: `ileri_test` defterindeki kayıtlar (yani GERÇEKTEN gönderilmiş uyarılar).
* Bar serisi kaydın barında KESİLİR: sonraki barlar motora verilmez (ileriye
  bakış yok).
* Motor, canlının kullandığı sınıfın aynısıdır (`ArgentEngine`), profil de aynı.
* Karşılaştırma: aile · yön · kırılım seviyesi (tolerans %0,5).

SINIR
-----
Canlıda motor 360 barlık deque ile besleniyor; replay de aynı pencereyi kullanır
(`DEQUE_MAXLEN`). Yine de bu bir **eşleşme** kontrolüdür, kanıt değil: aynı
sonucu vermesi motorun doğru olduğunu göstermez, farklı sonucu vermesi ise
kesin bir tutarsızlıktır. Ölçüm iddiası üretmez, hiçbir eşiği değiştirmez.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

AZAMI_DENETIM = 10          # gece başına en fazla kaç uyarı yeniden oynatılır
MIN_BAR = 60                # bundan kısa seride replay anlamsız
SEVIYE_TOLERANS = 0.005     # %0,5
GERIYE_GUN = 3              # son kaç günün uyarıları denetlenir
BUTCE_SN = 90.0             # işin duvar saati bütçesi: gece işi taramayı bekletmesin


def seviye(active: Any, yon: int, durum: str) -> Optional[float]:
    """Uyarıdaki kırılım seviyesi — `main._alert_break_level` ile aynı kural.

    (Kopya tutuluyor çünkü `main` import etmek döngüsel bağımlılık yaratır;
     eşitlik `test_tutarlilik.py` içinde ayrıca sınanır.)
    """
    aday = []
    if durum in {"KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"}:
        ad = "frozen_upper_boundary_at_break" if yon == 1 else "frozen_lower_boundary_at_break"
        aday.append(getattr(active, ad, None))
    aday.append(getattr(active, "upper_now" if yon == 1 else "lower_now", None))
    for ham in aday:
        try:
            deger = float(ham)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(deger):
            return deger
    return None


def _aile(active: Any) -> str:
    return str(getattr(active, "family", "") or "")


def _desen(active: Any) -> str:
    return str(getattr(active, "pattern_type", "") or getattr(active, "family", "") or "")


def denetle(kayit: Dict, df: Any, *, motor_kur: Optional[Callable[[str], Any]] = None,
            min_bar: int = MIN_BAR) -> Dict[str, Any]:
    """Tek kaydı yeniden oynatır. Döner: {"sonuc": "ayni"|"sapma"|"veri_yok", ...}."""
    sembol = str(kayit.get("sembol") or "")
    tf = str(kayit.get("tf") or "").lower()
    temel = {"sembol": sembol, "tf": tf, "bar": kayit.get("bar"), "desen": kayit.get("desen")}
    if df is None or len(df) == 0:
        return {**temel, "sonuc": "veri_yok", "neden": "bar serisi yok"}
    try:
        bar = datetime.fromisoformat(str(kayit.get("bar")))
    except (TypeError, ValueError):
        return {**temel, "sonuc": "veri_yok", "neden": "bar zamanı okunamadı"}

    try:
        index = df.index
        if getattr(index, "tz", None) is not None and bar.tzinfo is None:
            bar = bar.tz_localize(index.tz)
        elif getattr(index, "tz", None) is None and bar.tzinfo is not None:
            bar = bar.tz_convert(None)
        gecmis = df[index <= bar]
    except Exception:  # noqa: BLE001 - bozuk indeks denetimi engeller
        return {**temel, "sonuc": "veri_yok", "neden": "indeks okunamadı"}

    if len(gecmis) < min_bar:
        return {**temel, "sonuc": "veri_yok", "neden": f"yetersiz bar ({len(gecmis)})"}
    # Canlı deque penceresi kadar geriye bak (360 bar): aynı koşullar.
    try:
        from config import DEQUE_MAXLEN
        pencere = gecmis.tail(int(DEQUE_MAXLEN))
    except Exception:  # noqa: BLE001
        pencere = gecmis

    kur = motor_kur or _motor_kur
    try:
        motor = kur(tf)
        snap = motor.process(pencere, tam_yeniden=True)
    except Exception as exc:  # noqa: BLE001 - tek kayıt denetimi düşürmemeli
        return {**temel, "sonuc": "veri_yok", "neden": f"motor hatası: {exc}"}

    aktif = getattr(snap, "active", None)
    if aktif is None:
        return {**temel, "sonuc": "sapma", "neden": "replay'de aktif formasyon yok",
                "bulunan": None}

    yon = int(getattr(snap, "break_dir", 0) or 0)
    bulunan = {
        "desen": _desen(aktif),
        "aile": _aile(aktif),
        "yon": yon,
        "seviye": seviye(aktif, int(kayit.get("yon") or 1), str(kayit.get("durum") or "")),
        "durum": str(getattr(snap, "state", "") or ""),
    }

    beklenen_yon = int(kayit.get("yon") or 0)
    beklenen_desen = str(kayit.get("desen") or "")
    beklenen_seviye = kayit.get("giris")

    nedenler: List[str] = []
    if beklenen_desen and bulunan["desen"] and beklenen_desen != bulunan["desen"]:
        nedenler.append(f"desen: {beklenen_desen} → {bulunan['desen']}")
    if beklenen_yon in (1, -1) and bulunan["yon"] and beklenen_yon != bulunan["yon"]:
        nedenler.append(f"yön: {beklenen_yon} → {bulunan['yon']}")
    if beklenen_seviye and bulunan["seviye"]:
        try:
            fark = abs(float(bulunan["seviye"]) - float(beklenen_seviye)) / float(beklenen_seviye)
        except (TypeError, ValueError, ZeroDivisionError):
            fark = None
        if fark is not None and fark > SEVIYE_TOLERANS:
            nedenler.append(f"seviye: {float(beklenen_seviye):.4f} → "
                            f"{float(bulunan['seviye']):.4f} (%{fark*100:.2f})")
    if nedenler:
        return {**temel, "sonuc": "sapma", "neden": " · ".join(nedenler), "bulunan": bulunan}
    return {**temel, "sonuc": "ayni", "bulunan": bulunan}


def _motor_kur(tf: str):
    from patterns.lifecycle import ArgentEngine
    import config
    return ArgentEngine(profile=config.PROFILE, timeframe=tf)


def gunluk(kayitlar: List[Dict], *, getir: Optional[Callable[[str, str], Any]] = None,
           simdi: Optional[datetime] = None, azami: int = AZAMI_DENETIM,
           geriye_gun: int = GERIYE_GUN, butce_sn: float = BUTCE_SN,
           motor_kur: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """Son günlerin uyarılarını yeniden oynatır. Mesaj atmaz, dosya yazmaz."""
    simdi = simdi or datetime.now()
    if getir is None:
        from ileri_test import _varsayilan_getir as getir  # noqa: N806

    esik = simdi - timedelta(days=max(1, int(geriye_gun)))
    adaylar: List[Dict] = []
    for kayit in kayitlar or []:
        if not isinstance(kayit, dict):
            continue
        try:
            bar = datetime.fromisoformat(str(kayit.get("bar")))
        except (TypeError, ValueError):
            continue
        if bar.tzinfo is None and simdi.tzinfo is not None:
            bar = bar.replace(tzinfo=simdi.tzinfo)
        if bar >= esik:
            adaylar.append(kayit)
    # En yeni önce: güncel uyarıların tutarlılığı daha değerli.
    adaylar.sort(key=lambda k: str(k.get("bar") or ""), reverse=True)
    secilen = adaylar[:max(0, int(azami))]

    onbellek: Dict[tuple, Any] = {}
    denetimler: List[Dict] = []
    baslama = time.monotonic()
    kalan = 0
    for kayit in secilen:
        # Bütçe aşılırsa kalanlar ertesi geceye kalır: gece işi taramayı bekletmez.
        if butce_sn and (time.monotonic() - baslama) > float(butce_sn):
            kalan = len(secilen) - len(denetimler)
            logger.info("Tutarlılık bütçesi doldu (%ss); %d kayıt ertelendi",
                        butce_sn, kalan)
            break
        anahtar = (kayit.get("sembol"), kayit.get("tf"))
        if anahtar not in onbellek:
            try:
                onbellek[anahtar] = getir(kayit.get("sembol"), kayit.get("tf"))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Tutarlılık verisi alınamadı (%s): %s", anahtar, exc)
                onbellek[anahtar] = None
        denetimler.append(denetle(kayit, onbellek[anahtar], motor_kur=motor_kur))

    sayim = {"kontrol": len(denetimler), "ayni": 0, "sapma": 0, "veri_yok": 0}
    for d in denetimler:
        sayim[d["sonuc"]] = sayim.get(d["sonuc"], 0) + 1
    sapmalar = [d for d in denetimler if d["sonuc"] == "sapma"]
    return {**sayim, "sapmalar": sapmalar, "detay": denetimler, "kalan": kalan,
            "gun": simdi.date().isoformat()}


def ozet(sonuc: Dict[str, Any]) -> str:
    """Tek paragraflık insan özeti (log ve gece raporu için)."""
    if not sonuc or not sonuc.get("kontrol"):
        if sonuc and sonuc.get("kalan"):
            return (f"Tutarlılık: 0 denetim · {sonuc['kalan']} kayıt bütçe nedeniyle "
                    "ertelendi (ertesi gece yeniden denenir).")
        return "Tutarlılık: denetlenecek uyarı yok (defter boş ya da yeni kayıt yok)."
    satir = (f"Tutarlılık: {sonuc['kontrol']} uyarı yeniden oynatıldı · "
             f"aynı {sonuc['ayni']} · sapma {sonuc['sapma']} · veri yok {sonuc['veri_yok']}")
    if sonuc.get("kalan"):
        satir += f" · {sonuc['kalan']} kayıt bütçe nedeniyle ertelendi"
    if sonuc["sapma"]:
        ornek = sonuc["sapmalar"][0]
        satir += (f" · ilk sapma: {ornek.get('sembol')} {ornek.get('tf')} "
                  f"{ornek.get('bar')} — {ornek.get('neden')}")
    return satir
