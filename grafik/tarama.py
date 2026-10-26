# grafik/tarama.py — tarama anı kopya/meta yazıcıları (Faz 2).

from __future__ import annotations

import io
import textwrap
import logging
import math
import os
import shutil
import tempfile
import time
import uuid
import threading
from functools import wraps
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from reporting.format import sayi
import chart_experience as deneyim
from telegram_measure import SATIR_BUTCE, genislik as _genislik_16

import grafik as _pkg  # yamalı adlar için geç bağlama (plan §3)

log = logging.getLogger("grafik")  # eski kayıt adıyla aynı (__name__ yerine)

from grafik.core import (  # noqa: F401
    SABITLER,
    _TF_KISA,
    _ad,
    _alan,
    _bar_kapandi_mi,
    _cerceve_ayristir,
    _gercek,
    _kadrajla,
    _ortam_sayi,
    _tam,
    _tarih,
    kare_mum_tavani,
)
from grafik.geometry import (  # noqa: F401
    _bant_temaslari,
    _zone_havuzu,
)
from grafik.indicators import (  # noqa: F401
    _grafik_dis_yapi,
    _grafik_yapi_metni,
    _grafik_zone,
)
from grafik.overlays import (  # noqa: F401
    _ALARM_TURU,
    _alarm_kopyala,
    _formasyon_kopyala,
    _isaret_listesi,
)

def anlik_goruntu(cift: Any = None, tf: str = "1h", cerceve: Any = None, *,
                  sonuclar: Optional[Mapping[str, Any]] = None,
                  alarm_turu: Optional[str] = None, alarm_bar: Optional[int] = None,
                  sembol: str = "", zaman_damgasi: Any = None,
                  simdi: Optional[datetime] = None,
                  kare_mum: Optional[int] = None,
                  etiket_detay: Optional[bool] = None,
                  veri_kaynagi: Optional[str] = None,
                  tarihsel: bool = False) -> dict[str, Any]:
    """Tarama anındaki veriyi çizilebilir sözlüğe kopyalar (§2, §14.1).

    `cift`: kartın beslendiği formasyon kaydı (`PatternCandidate` veya payload
    sözlüğü). `sonuclar`: `run_domain_engines` çıktısı — G1'de yalnız *varlığı*
    not edilir (G2 zone'ları, G3 yapı/şerit buradan okunur); motor çağrılmaz.
    `alarm_turu` `aday/kritik/teyit/retest/gecersiz/ihlal`, `alarm_bar` çerçeve
    değeri mum indeksi. Hiçbiri zorunlu değil: verisi olmayan katman çizilmez.
    `etiket_detay` None ise `SABITLER["etiket_detay"]` (§2.6: `evidence_text`
    ancak istenirse karenin içine yazılır).
    """
    tf = str(tf or "1h")
    veri = _cerceve_ayristir(cerceve)
    zamanlar = [_tarih(z) for z in (veri.get("zaman") or [])]
    sutun = {ad: list(veri.get(ad) or []) for ad in ("acilis", "yuksek", "dusuk", "kapanis", "hacim")}
    n = min([len(zamanlar)] + [len(v) for v in sutun.values() if v] or [0])
    uyari: list[str] = []

    # --- yalnız kapanmış mumlar (§0.6): son bar kapalı değilse çizime girmez.
    son_bar_kapali = True
    goruntu_not = ""
    if n and zamanlar[-1] is not None and _bar_kapandi_mi is not None:
        try:
            son_bar_kapali = bool(_bar_kapandi_mi(zamanlar[-1], tf, now=simdi))
        except Exception:  # pragma: no cover - zamanlama yardımcısı takılırsa çiz
            son_bar_kapali = True
    if n and not son_bar_kapali:
        n -= 1
        zamanlar = zamanlar[:n]
        sutun = {ad: v[:n] for ad, v in sutun.items()}
        # Açık bar çizilmemesi normal (§0.6) → dipnot değil, meta'da durur.
        goruntu_not = "son bar açıktı: çizime alınmadı"

    formasyon = _formasyon_kopyala(cift)
    durum = str(formasyon.get("state") or "")
    if alarm_turu is None:
        alarm_turu = _ALARM_TURU.get(durum)

    kare = int(kare_mum if kare_mum else kare_mum_tavani(tf))
    sol, sag, tavan_kalkti = _kadrajla(n, formasyon.get("start_bar"), kare_mum, tf=tf)
    goruntu: dict[str, Any] = {
        "surum": 1,
        "sembol": str(sembol or "").upper(),
        "tf": tf,
        "tf_kisa": _TF_KISA.get(tf, tf),
        "zaman_damgasi": (str(zaman_damgasi) if zaman_damgasi is not None
                          else (zamanlar[-1].isoformat() if zamanlar and zamanlar[-1] else None)),
        "son_bar_ts": zamanlar[-1].isoformat() if n and zamanlar and zamanlar[-1] else None,
        "son_kapanis": (sutun["kapanis"][-1] if n and sutun["kapanis"] else None),
        "son_bar_kapali": son_bar_kapali,
        "bar_sayisi": n,
        "kare_mum": kare,
        "sol": sol,
        "sag": sag,
        "tavan_kalkti": tavan_kalkti,
        "zamanlar": zamanlar[sol:sag],
        **{ad: v[sol:sag] for ad, v in sutun.items()},
        "formasyon": formasyon,
        "alarm": None,
        "temas": [],
        "hacimsiz_bar": sum(1 for x in sutun["hacim"][sol:sag] if x is None or x <= 0),
        "budama": [],
        "eksik_katmanlar": [],
        "notlar": [],           # meta'da durur, karenin altına yazılmaz (§0.6 normal durum)
        "uyarilar": uyari,
        "zone": None,     # G2: {"cizilen": n, "elenen": n}
        "olay": None,     # G3: {"cizilen": n, "elenen": n}
        "serit": None,    # G3: {"degerler": [...], "esik": x, "kaynak": "..."}
    }
    if tavan_kalkti:
        yas = n - int(formasyon["start_bar"])
        goruntu["budama"].append(
            f"kadraj: formasyon {yas} barlık → {sag - sol} mumluk pencereye kırpıldı")
    if _alan(cift, "violation_history_truncated"):
        goruntu["uyarilar"].append("ihlal geçmişi kırpılmış: sayılar eksik görünebilir")
    goruntu["zone"] = _zone_havuzu(sonuclar, tf, goruntu["son_kapanis"], sol, sag, cerceve)
    if goruntu["zone"].get("hata"):
        goruntu["eksik_katmanlar"] = sorted(set(goruntu["eksik_katmanlar"])
                                            | set(goruntu["zone"]["hata"]))
    # Şerit çerçeveden TÜRETİLİR (yerel rvol için motor gerekmez); motor serisi
    # varsa o kullanılır (§2.1). Yapı katmanı `sonuclar` olmadan var olamaz.
    if n and sag:
        try:
            goruntu["serit"] = _serit_verisi(sonuclar, sutun["hacim"], sol, sag, n)
        except Exception as hata:
            log.warning("grafik: şerit katmanı kurulamadı (%s)", hata)
            goruntu["eksik_katmanlar"].append("serit")
    goruntu["olay"] = _olay_verisi(sonuclar, sol, sag,
                                  bool(SABITLER["etiket_detay"]) if etiket_detay is None
                                  else bool(etiket_detay))
    for e in ((goruntu["olay"] or {}).get("zaman_cizelgesi", []) +
              (goruntu["olay"] or {}).get("seviyeler", [])):
        idx = e.get("kaynak_bar")
        if not e.get("zaman") and idx is not None and 0 <= idx < len(zamanlar):
            e["zaman"] = zamanlar[idx].isoformat() if zamanlar[idx] else None
    if (goruntu["olay"] or {}).get("hata"):
        goruntu["eksik_katmanlar"] = sorted(set(goruntu["eksik_katmanlar"])
                                            | set(goruntu["olay"]["hata"]))
    # `sonuclar` yoksa bölge/yapı katmanları YOKTUR — bu veri bozukluğu değil
    # (§0.12w: dipnot yalnız veri sorununa); izi `meta["zone"]["sirala"]` ve
    # `meta["olay"]` sıfırlarında taşınır.
    goruntu["guven"] = deneyim.trust_payload(
        goruntu, sonuclar, now=simdi or datetime.now().astimezone(),
        source=veri_kaynagi, historical=tarihsel,
        anchor=zamanlar[0] if zamanlar else None)
    if not n or not sag:
        goruntu["uyarilar"].append("kare boş: çizim yok")
        return goruntu

    # --- kartın yapı satırı (L11): üst blokta gri satır olarak çizilir. Metin
    # `notification_context`ten GELİYOR (kartın kendi biçimleyicisi), burada yeni
    # cümle kurulmuyor → kare ile kart ayrışamaz.
    goruntu["yapı_satırı"] = _yapı_satırı(sonuclar, tf, goruntu.get("son_kapanis"))

    # --- temas mumları (§2.4) — bant verisi varsa.
    alt, ust = formasyon.get("lower_now"), formasyon.get("upper_now")
    if alt is not None and ust is not None:
        try:
            goruntu["temas"] = [i - sol for i in
                                _bant_temaslari(sutun["yuksek"], sutun["dusuk"], alt, ust, sol, sag)]
        except Exception as hata:  # pragma: no cover - katman çizimi durdurmaz (§2.9)
            log.warning("grafik: temas hesabı başarısız (%s)", hata)
            goruntu["eksik_katmanlar"].append("temas")
    elif formasyon:
        goruntu["uyarilar"].append("bant verisi yok: temas adedi hesaplanamadı")
    # Temas noktaları sayı olarak korunur; grafikteki daire işaretleri kaldırıldı.
    goruntu["temas_isaret"] = []
    goruntu["isaretler"] = _isaret_listesi(formasyon, goruntu["kapanis"], goruntu["yuksek"],
                                           sol, sag - sol)

    if goruntu_not:
        goruntu["notlar"].append(goruntu_not)
    goruntu["alarm"] = _alarm_kopyala(cift, alarm_turu, alarm_bar, sol, sag, goruntu)
    if (goruntu["alarm"] or {}).get("bar_disarida"):
        # Alarm mumu kadraj dışında kaldı: çizilmemesi bilgi kaybıdır → bildirilir.
        goruntu["uyarilar"].append("alarm mumu kadraj dışında: mum işaretlenmedi")
    return goruntu


def _yapı_satırı(sonuclar: Any, tf: str, son_kapanis: Optional[float]) -> str:
    """Kartın `🏗 Piyasa Yapısı` bloğunun İLK satırı, birebir (yalnız `• ` öneki düşer).

    Neden biçimleyiciyi yeniden kullanıyoruz: karenin karttan farklı bir cümle
    kurmaması gerekiyor (§14.1 "uydurma alan yok"). Motor hiç yoksa/ayrıksa `''`
    döner ve DIPNOT YAZILMAZ — yokluk zaten `meta["eksik_katmanlar"]`da (`ms`).
    Biçimlendirme hatası kareyi asla düşürmez (§2.9).
    """
    if not sonuclar:
        return ""
    try:
        from notification_context import domain_bolumleri

        # 2026-10-23: kare başlığı da KART diliyle konuşur (`1g yön yukarı
        # (iç ve dış yapı)`); klasik metin `1g yapı: dış yükseliş` jargondu.
        # `klasik` biçim geri dönüş yolu olarak `notification_context`te duruyor.
        bolumler = domain_bolumleri({tf: sonuclar}, son_kapanis, stil="kart",
                                    alarm_tf=tf)
        satirlar = (bolumler.get("yapi_ozet") or bolumler.get("yapi") or [])
    except Exception as hata:  # noqa: BLE001 - kart satırı kareyi engellemez
        log.debug("grafik: yapı satırı alınamadı (%s: %s)", type(hata).__name__, hata)
        return ""
    if not satirlar:
        return ""
    satir = str(satirlar[0]).strip().lstrip("◈•").strip()
    return _grafik_yapi_metni(satir)


def _serit_verisi(sonuclar: Optional[Mapping[str, Any]], hacimler: Sequence[Any],
                  sol: int, sag: int, n: int) -> dict[str, Any]:
    """Katılım şeridi (§2.1) — kaynak motorun BAR BAR serisi, yoksa yerel rvol.

    `vp.details["metrics_history"]` her bar için `VolumeParticipationMetrics`
    veriyor (ölçüm: 1s 360/360 dolu; `rvol`, `volume_level`, `effort_result_class`
    alanları var). Motor serisi hazır değilse (4s ölçümü: `data_ready=False`,
    export `rvol=None`) `hacim / SMA(hacim, 20)` YEREL hesaplanır ve karede
    `rvol · yerel hesap` yazılır — kullanıcı onayı bu etiketi şart koşuyor.
    Kurallar: yalnız spike (≥ `serit_esik`, en sert `serit_maks`); `▲` yalnız
    motorun `volume_level` dayanağıyla; `!` yalnız son `son_mum_isaret` (15) barda
    `HIGH/VERY_HIGH_EFFORT_WEAK_RESULT`; `hacim ≤ 0` bar çizilmez ve sayılır.
    `minimum_history=150` DÜŞÜRÜLMEZ — o yüzden 4s/1g karesinde motor serisi
    gelmeyebilir; bu "yetersiz geçmiş" olarak bildirilir, eşik düşürülmez.
    Dizinler GÖRÜNÜNE göre döner (`sol` çıkarılır): `_serit_ciz` görünüyü kullanır.
    """
    hacimler = list(hacimler or [])
    n = max(n, len(hacimler))
    uzunluk = int(SABITLER["hacim_uzunluk"])
    rvol_yerel: list[Optional[float]] = [None] * n
    pencere: list[float] = []
    toplam = 0.0
    for i in range(n):
        v = _gercek(hacimler[i]) if i < len(hacimler) else None
        pencere.append(v if v is not None else 0.0)
        toplam += v if v is not None else 0.0
        if len(pencere) > uzunluk:
            toplam -= pencere.pop(0)
        ortalama = toplam / len(pencere) if pencere else 0.0
        if v is not None and ortalama > 0:
            rvol_yerel[i] = v / ortalama

    motor: list[Optional[float]] = []
    seviye: list[str] = []
    capa: list[int] = []
    veri_hazir = False
    vp = (sonuclar.get("volume_participation") if isinstance(sonuclar, Mapping)
          else _alan(sonuclar, "volume_participation")) if sonuclar else None
    if vp is not None:
        try:
            gecmis = list(_alan(_alan(vp, "details", {}) or {}, "metrics_history", ()) or ())
            motor = [None] * len(gecmis)
            seviye = [""] * len(gecmis)
            for i, m in enumerate(gecmis):
                if bool(_alan(m, "data_ready", False)):
                    veri_hazir = True
                motor[i] = _gercek(_alan(m, "rvol"))
                seviye[i] = _ad(_alan(m, "volume_level"))
                if _ad(_alan(m, "effort_result_class")) in ("HIGH_EFFORT_WEAK_RESULT",
                                                            "VERY_HIGH_EFFORT_WEAK_RESULT"):
                    capa.append(i)
        except Exception as hata:
            log.warning("grafik: şerit serisi okunamadı (%s)", hata)
            motor, seviye, capa = [], [], []
    kaynak = ("motor" if (motor and veri_hazir) else
              "yerel hesap" if any(v is not None for v in rvol_yerel) else "yok")
    ham = list(motor) if kaynak == "motor" else list(rvol_yerel)
    ham = (ham + [None] * n)[:n]
    degerler = ham[sol:sag]
    esik = float(SABITLER["serit_esik"])
    tum = [i for i, v in enumerate(degerler) if v is not None and float(v) >= esik]
    spike = sorted(sorted(tum, key=lambda i: (-float(degerler[i]), -i))
                   [: int(SABITLER["serit_maks"])])
    yildiz = [i for i in spike if kaynak == "motor" and (sol + i) < len(seviye)
              and seviye[sol + i] in ("HIGH", "ABNORMAL")]
    capa = [i - sol for i in capa if i >= sag - int(SABITLER["son_mum_isaret"])
            and sol <= i < sag]
    hacimsiz = 0
    for i in range(sol, sag):
        v = _gercek(hacimler[i]) if i < len(hacimler) else None
        if v is None or v <= 0.0:
            hacimsiz += 1
    tepe = max((float(degerler[i]) for i in spike), default=None) if spike else None
    return {"degerler": degerler, "esik": esik, "spike": spike, "yildiz": yildiz,
            "capa": capa, "kaynak": kaynak, "hacimsiz": hacimsiz,
            "yetersiz": kaynak == "yok", "yerel": kaynak == "yerel hesap",
            "tepe": tepe, "elenen_spike": max(0, len(tum) - len(spike)),
            "uzunluk": uzunluk}


def _olay_verisi(sonuclar: Optional[Mapping[str, Any]], sol: int, sag: int,
                 etiket_detay: bool = False) -> dict[str, Any]:
    """Yalnız dış PH/PL/WH/WL seviyeleri + dış BOS·CHoCH.

    Internal swing ve adaylar grafiğe alınmaz. Sağ cetveldeki PH/PL/WH/WL
    dış scope'un güvenli export seviyeleridir;
    motor export'u yoksa yalnız rolü açıkça atanmış external swing'lerden türetilir.
    Olay çizgileri ayrı sözleşme olarak EXTERNAL, onaylı ve geçerli BOS/CHoCH'tur.
    """
    ms = (sonuclar.get("market_structure") if isinstance(sonuclar, Mapping)
          else _alan(sonuclar, "market_structure")) if sonuclar else None
    if ms is None:
        return {}
    try:
        detay = _alan(ms, "details", {}) or {}
    except Exception as hata:
        log.warning("grafik: yapı verisi okunamadı (%s)", hata)
        return {"hata": ["ms"]}

    # Internal pivots/candidates are not part of the chart contract.
    swinglar: list[dict[str, Any]] = []
    swing_maks = 0
    olay_maks = int(_ortam_sayi("GRAFIK_OLAY_MAKS", SABITLER["olay_maks"]))
    elenen = 0

    # Seviyelerde önce motorun safety-gated export'unu kullan. Eski/yalın sonuç
    # nesneleri export taşımıyorsa, aynı rolü taşıyan dış swing'lerden geri dönüş
    # sağlanır. Sırf swing_class PH/PL olduğu için korunan seviye üretme.
    roller = {
        "PROTECTED_HIGH": ("PH", "external_protected_high"),
        "PROTECTED_LOW": ("PL", "external_protected_low"),
        "WEAK_HIGH": ("WH", "external_weak_high"),
        "WEAK_LOW": ("WL", "external_weak_low"),
    }
    dis_kayitlar: dict[str, dict[str, Any]] = {}
    for b in (_alan(detay, "external_swings", ()) or ()):
        rol = _ad(_alan(b, "structural_role"))
        if rol not in roller:
            continue
        ham_durum = _ad(_alan(b, "state"))
        if "BROKEN" in ham_durum or bool(_alan(b, "broken")):
            continue
        fiyat = _gercek(_alan(b, "price"))
        if fiyat is None:
            continue
        bar = _tam(_alan(b, "source_bar"))
        onceki = dis_kayitlar.get(rol)
        if onceki is not None and (bar is None or
                                   (onceki.get("kaynak_bar") is not None and
                                    int(bar) <= int(onceki["kaynak_bar"]))):
            continue
        etiket, _ = roller[rol]
        dis_kayitlar[rol] = {"bar": (bar - sol) if bar is not None else None,
                             "kaynak_bar": bar, "fiyat": fiyat,
                             "etiket": etiket, "rol": rol,
                             "yon": "ust" if rol.endswith("HIGH") else "alt"}

    export = _alan(ms, "export")
    seviyeler: list[dict[str, Any]] = []
    for rol, (etiket, export_alan) in roller.items():
        # Export nesnesi varsa o tek doğruluk kaynağıdır; None seviyeyi çizme.
        export_fiyat = _gercek(_alan(export, export_alan)) if export is not None else None
        if export is not None and export_fiyat is None:
            continue
        kayit = dis_kayitlar.get(rol)
        if export is None and kayit is None:
            continue
        seviye = dict(kayit or {"bar": None, "kaynak_bar": None,
                               "etiket": etiket, "rol": rol,
                               "yon": "ust" if rol.endswith("HIGH") else "alt"})
        if export_fiyat is not None:
            seviye["fiyat"] = export_fiyat
        if seviye.get("fiyat") is None:
            continue
        seviyeler.append(seviye)

    zaman_cizelgesi = []
    for e in (_alan(detay, "event_history", ()) or ()):
        if _ad(_alan(e, "scope")) != "EXTERNAL":
            continue
        bar = _tam(_alan(e, "event_bar"))
        zaman_cizelgesi.append({"scope": "EXTERNAL", "kaynak_bar": bar,
            "tur": _ad(_alan(e, "event_type")).replace("EVENT_", ""),
            "yon": _ad(_alan(e, "direction")), "seviye": _gercek(_alan(e, "broken_level")),
            "zaman": str(_alan(e, "timestamp") or _alan(e, "event_time") or "") or None,
            "yas": _tam(_alan(e, "age_bars")), "teyit": _ad(_alan(e, "confirmation_status")),
            "gecerlilik": _ad(_alan(e, "validity")), "guncellik": _ad(_alan(e, "relevance"))})
    olaylar: list[dict[str, Any]] = []
    for b in (_alan(detay, "event_history", ()) or ()):
        if _ad(_alan(b, "scope")) != "EXTERNAL":
            continue
        tur = _ad(_alan(b, "event_type")).replace("EVENT_", "")
        if tur not in ("BOS", "CHOCH"):
            continue
        if _ad(_alan(b, "confirmation_status")) != "CONFIRMED":
            continue
        if _ad(_alan(b, "validity")) != "VALID":
            continue
        bar = _tam(_alan(b, "event_bar"))
        if bar is None:
            continue
        # FAZ 3 §4.2 (Line Truncation): kırılım çizgisi "oluştuğu pivot"tan
        # başlar. Pivot barı motorun kendi alanıdır (`origin_source_bar`);
        # uydurulmaz, yoksa çizgi kırılım mumundan başlar (eski davranış).
        _pivot = _tam(_alan(b, "origin_source_bar"))
        olaylar.append({"bar": bar - sol, "kaynak_bar": bar,
                        "aday_bar": (_tam(_alan(b, "candidate_bar")) - sol)
                        if _tam(_alan(b, "candidate_bar")) is not None else None,
                        "pivot_bar": (_pivot - sol) if _pivot is not None else None,
                        "pivot_kaynak_bar": _pivot,
                        "pivot_fiyat": _gercek(_alan(b, "origin_price")),
                        "tur": "BOS" if tur == "BOS" else "CHoCH",
                        "yon": "ust" if _ad(_alan(b, "direction")).startswith("UP") else "alt",
                        "seviye": _gercek(_alan(b, "broken_level")),
                        "kimlik": _tam(_alan(b, "identity")),
                        "nitelik": _gercek(_alan(b, "quality")),
                        "yas": _tam(_alan(b, "age_bars")),
                        "kanit": str(_alan(b, "evidence_text") or "") if etiket_detay else ""})
    olaylar.sort(key=lambda b: -int(b["bar"]))
    olay_elenen = max(0, len(olaylar) - olay_maks)
    olaylar = sorted(olaylar[:olay_maks], key=lambda b: int(b["bar"]))
    kritik = None
    if olaylar:
        son_olay = olaylar[-1]
        if son_olay.get("seviye") is not None:
            kritik = {"seviye": son_olay["seviye"], "bar": son_olay["bar"],
                     "kaynak_bar": son_olay.get("kaynak_bar"), "tur": son_olay["tur"],
                     "yon": son_olay["yon"],
                     "pivot_bar": son_olay.get("pivot_bar"),
                     "pivot_kaynak_bar": son_olay.get("pivot_kaynak_bar")}
    return {"swinglar": swinglar, "seviyeler": seviyeler,
            "zaman_cizelgesi": zaman_cizelgesi,
            "olaylar": olaylar, "kritik": kritik,
            "cizilen": len(swinglar) + len(seviyeler) + len(olaylar),
            "elenen": elenen + olay_elenen,
            "kapak": {"swing": swing_maks, "olay": olay_maks},
            "hata": []}


def _zone_meta(zone: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["zone"]`: §2'deki `{cizilen, elenen}` + G2 izleri (test yüzeyi)."""
    # Alanlar her durumda AYNI biçimde döner (§13 JSONL okuyucusu dalgalanmasın):
    # boşsa sayaçlar 0, `sirala` "zone verisi yok" (motorlar hiç çağrılmadı).
    if not zone:
        return {"cizilen": 0, "elenen": 0, "tip": {"ob": 0, "fvg": 0, "eng": 0},
                "kaynak_disi": 0, "kapak": {}, "sirala": "zone verisi yok", "atr": None,
                "cikarim": {}, "hata": [], "kayitlar": [], "etiket_atlandi": 0,
                "etiket_ic": 0, "etiket_serit": 0,
                "dolgu": 0, "orta": 0, "kunye": 0}
    kayitlar = list(_grafik_zone(zone).get("cizilen") or [])
    return {"cizilen": len(kayitlar), "elenen": int(zone.get("elenen") or 0),
            "tip": {t: sum(1 for b in kayitlar if b["tip"] == t) for t in ("ob", "fvg", "eng")},
            "kaynak_disi": int(zone.get("kaynak_disi") or 0),
            "kapak": dict(zone.get("kapak") or {}), "sirala": zone.get("sirala"),
            "atr": zone.get("atr"), "cikarim": dict(zone.get("cikarim") or {}),
            "hata": list(zone.get("hata") or []),
            "etiket_atlandi": int(zone.get("etiket_atlandi") or 0),
            # GÖRSEL-4: etiket kutunun İÇİNDE mi (`etiket_ic`) yoksa kutu sığmadığı
            # için sağ şerit yedeğine mi taşındı (`etiket_serit`)?
            "etiket_ic": int(zone.get("etiket_ic") or 0),
            "etiket_serit": int(zone.get("etiket_serit") or 0),
            # GÖRSEL-5: doluluk cetveli / %50 orta çizgisi / künye sayaçları.
            "dolgu": int(zone.get("dolgu") or 0),
            "orta": int(zone.get("orta") or 0),
            "kunye": int(zone.get("kunye") or 0),
            "kayitlar": [{k: b.get(k) for k in ("tip", "yon", "alt", "ust", "mum_alt", "mum_ust",
                                                "kaynak", "kayit_kaynagi", "tamamlandi", "taraf",
                                                "durum", "doluluk", "mitigated_percentage", "gap",
                                                "x0", "x1", "mesafe", "mesafe_atr", "vurgu", "zaman")}
                         for b in kayitlar]}


def _olay_meta(olay: Optional[Mapping[str, Any]], ozet: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """`meta["olay"]`: §2'deki `{cizilen, elenen}` + G3 izleri (§13 biçimi)."""
    ozet = dict(ozet or {})
    olay = _grafik_dis_yapi(olay or {})
    if not olay:
        return {"cizilen": 0, "elenen": 0, "swing": 0, "dis_seviye": 0,
                "bos_choc": 0, "kritik": None, "kapak": {}, "etiket_atlandi": 0,
                "kritik_cizildi": False, "kritik_atlandi": 0, "capa": 0,
                "hata": [], "phpl_serit": 0, "whwl_serit": 0}
    return {"cizilen": int(olay.get("cizilen") or 0), "elenen": int(olay.get("elenen") or 0),
            "swing": 0,
            "dis_seviye": len(olay.get("seviyeler") or []),
            "bos_choc": len(olay.get("olaylar") or []),
            "kritik": (olay.get("kritik") or {}).get("seviye"),
            "kapak": dict(olay.get("kapak") or {}),
            "olay_barlari": [b.get("kaynak_bar") for b in (olay.get("olaylar") or [])],
            "etiket_atlandi": int(ozet.get("etiket_atlandi") or 0),
            "kritik_cizildi": bool(ozet.get("kritik")),
            "kritik_atlandi": int(ozet.get("kritik_atlandi") or 0),
            "capa": int(ozet.get("capa") or 0),
            "phpl_serit": int(ozet.get("phpl_serit") or 0),
            "whwl_serit": int(ozet.get("whwl_serit") or 0),
            "hata": list(olay.get("hata") or [])}


def _serit_meta(serit: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["serit"]`: `{acik, esik, spike}` (§2) + kaynak/hacimsiz izleri."""
    if not serit:
        return {"acik": False, "esik": None, "spike": [], "kaynak": "yok", "yerel": False,
                "hacimsiz": 0, "elenen_spike": 0, "capa": 0, "yetersiz": False,
                "uzunluk": None, "rozet": 0, "rozet_artis": 0, "rozet_dusus": 0,
                "rozet_taze_artis": None, "rozet_taze_dusus": None}
    return {"acik": True, "esik": serit.get("esik"), "spike": list(serit.get("spike") or []),
            "kaynak": serit.get("kaynak"), "yerel": bool(serit.get("yerel")),
            "hacimsiz": int(serit.get("hacimsiz") or 0),
            "elenen_spike": int(serit.get("elenen_spike") or 0),
            "capa": len(serit.get("capa") or []), "yetersiz": bool(serit.get("yetersiz")),
            "tepe": serit.get("tepe"), "uzunluk": serit.get("uzunluk")}


def _meta_kur(goruntu: Mapping[str, Any], tf: str, olcu: Mapping[str, Any]) -> dict[str, Any]:
    """§2'deki `meta` iskeleti — testler piksele değil bu sözlüğe bakıyor (§6.1)."""
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    return {
        "sem": goruntu.get("sembol") or "",
        "tf": _TF_KISA.get(tf, tf),
        "mum_sayisi": int(olcu["bar"]),
        "bar_basina_px": round(float(olcu["px_bar"]), 2),
        "temas": [int(i) for i in (goruntu.get("temas") or [])],
        "temas_isaret": [int(i) for i in (goruntu.get("temas_isaret") or [])],
        "isaretler": [{"ad": x["ad"], "bar": x["bar"]} for x in (goruntu.get("isaretler") or [])],
        "cizgiler": {
            "formasyon_ust": formasyon.get("upper_now"),
            "formasyon_alt": formasyon.get("lower_now"),
            "alarm": {"deger": alarm.get("deger"), "tur": alarm.get("tur"),
                      "etiket": alarm.get("etiket"), "bar": alarm.get("bar"),
                      "durum": alarm.get("durum"), "kapanis": alarm.get("kapanis"),
                      "bar_disarida": bool(alarm.get("bar_disarida"))},
            "kritik": None,        # G3 (§0.12f)
        },
        "zone": _zone_meta(goruntu.get("zone")),
        "olay": _olay_meta(goruntu.get("olay")),
        "serit": _serit_meta(goruntu.get("serit")),
        "budama": list(goruntu.get("budama") or []),
        "notlar": list(goruntu.get("notlar") or []),
        "eksik_katmanlar": sorted(set(goruntu.get("eksik_katmanlar") or [])),
        "hacimsiz_bar": int(goruntu.get("hacimsiz_bar") or 0),
        "son_bar_ts": goruntu.get("son_bar_ts"),
        "kare": {"genislik": int(olcu["genislik"]), "yukseklik": int(olcu["yukseklik"]),
                 "sol": goruntu.get("sol"), "sag": goruntu.get("sag"),
                 "dpi": int(SABITLER["dpi"]), "cekme": bool(olcu["cekme"])},
        "uyarilar": list(goruntu.get("uyarilar") or []),
        "red": False,
        "surum": 1,
    }


def _atom_yaz(yol: str, veri: bytes) -> None:
    """Geçici dosyaya yaz + `os.replace` (§0.12p: kare /tmp'de üretilir).

    Neden atomik: gönderici kuyruğu dosyayı okurken yarı yazılmış PNG görmesin.
    """
    klasor = os.path.dirname(os.path.abspath(yol)) or "."
    os.makedirs(klasor, exist_ok=True)
    gecici = os.path.join(klasor, f".{os.path.basename(yol)}.{os.getpid()}.tmp")
    try:
        with open(gecici, "wb") as akis:
            akis.write(veri)
        os.replace(gecici, yol)
    finally:
        try:
            os.remove(gecici)
        except OSError:
            pass


def girdi_ozeti(goruntu: Mapping[str, Any]) -> str:
    """Aynı girdi → aynı özet (§6.5: determinizm piksel hash'inde değil, meta'da)."""
    parcalar = [f"{ad}={goruntu.get(ad)}" for ad in
                 ("surum", "sembol", "tf", "son_bar_ts", "son_kapanis", "sol", "sag",
                  "bar_sayisi", "hacimsiz_bar", "tavan_kalkti")]
    parcalar.append("isaretler=" + ",".join(
        f"{x['ad']}@{x['bar']}" for x in (goruntu.get("isaretler") or [])))
    parcalar.append("notlar=" + ",".join(str(x) for x in (goruntu.get("notlar") or [])))
    parcalar.append("temas=" + ",".join(str(i) for i in (goruntu.get("temas") or [])))
    for ad in ("budama", "uyarilar", "eksik_katmanlar"):
        parcalar.append(ad + "=" + ",".join(str(x) for x in (goruntu.get(ad) or [])))
    for ad in ("formasyon", "alarm"):
        deger = goruntu.get(ad) or {}
        parcalar.append(ad + "=" + ",".join(f"{k}:{v}" for k, v in sorted(deger.items())))
    return "|".join(parcalar)


