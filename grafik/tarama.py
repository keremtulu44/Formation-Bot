# grafik/tarama.py — tarama anı kopya/meta yazıcıları (Faz 2).

from __future__ import annotations

from bisect import bisect_right
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
        "stabil": None,   # Günlük yapısal destek stepline projeksiyonu
        "stabil_direnc": None,  # Bağımsız günlük yapısal direnç projeksiyonu
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
    goruntu["stabil"] = _stabil_verisi(sonuclar, tf, sol, sag, zamanlar[sol:sag])
    goruntu["stabil_direnc"] = _stabil_direnc_verisi(sonuclar, tf, sol, sag, zamanlar[sol:sag])
    # Cross-domain bridge: event timestamps must match this chart's native bars.
    from domain_engines.stabil.structure_context import barrier_reason, events_for_bars, marker_state
    ms_result = sonuclar.get("market_structure") if isinstance(sonuclar, Mapping) else None
    structure_events = events_for_bars(ms_result, zamanlar)
    for layer, direction, keys in (
        (goruntu["stabil"], "UP", ("reclaim_barlar", "momentum_barlar")),
        (goruntu["stabil_direnc"], "DOWN", ("donus_barlar", "momentum_barlar")),
    ):
        if not layer:
            continue
        layer["baglam_bastirilan"] = []
        layer["iptal_barlar"] = []
        for key in keys:
            kept = []
            for bar in layer.get(key, []):
                status = marker_state(sol + bar, direction, tf, structure_events, sag - 1)
                if status in {"opposite_structure", "invalidated_by_opposite_bos"}:
                    layer["baglam_bastirilan"].append({"bar": bar, "tur": key, "neden": status})
                    if status == "invalidated_by_opposite_bos":
                        layer["iptal_barlar"].append(bar)
                else:
                    kept.append(bar)
            layer[key] = kept
    # Same-bar S/R corridor and current pattern boundary. Pattern snapshots do
    # not carry historical geometry, so never back-project today's pattern.
    from domain_engines.stabil.signals import _causal_atr14
    import numpy as np
    try:
        atr_values = _causal_atr14(
            np.asarray(sutun["yuksek"], dtype=float),
            np.asarray(sutun["dusuk"], dtype=float),
            np.asarray(sutun["kapanis"], dtype=float), period=14)
    except (TypeError, ValueError, IndexError):
        atr_values = []
    support_layer = goruntu["stabil"] or {}
    resistance_layer = goruntu["stabil_direnc"] or {}
    for layer, other, direction, keys, boundary, other_role in (
        (support_layer, resistance_layer, 1, ("reclaim_barlar", "momentum_barlar"), "upper_now", "alt"),
        (resistance_layer, support_layer, -1, ("donus_barlar", "momentum_barlar"), "lower_now", "ust"),
    ):
        if not layer:
            continue
        for key in keys:
            kept = []
            for bar in layer.get(key, []):
                source_bar = sol + bar
                close = _gercek(sutun["kapanis"][source_bar]) if source_bar < n else None
                atr = _gercek(atr_values[source_bar]) if source_bar < len(atr_values) else None
                barriers = []
                levels, roles = other.get("seviyeler", []), other.get("renkler", [])
                if bar < len(levels) and bar < len(roles) and roles[bar] == other_role:
                    barriers.append(("stabil_koridoru", _gercek(levels[bar])))
                # Only the current snapshot is known to exist at this bar.
                state = str(formasyon.get("state") or "").upper()
                # Native PatternCandidate carries validity and geometry, but
                # its lifecycle state lives in the enclosing snapshot.
                active_candidate = bool(_alan(cift, "valid", False)) and not state
                active_state = state not in {"", "BASARISIZ", "IPTAL", "FORMASYON_GECERSIZ",
                                             "KIRILIM_GECERSIZ", "KIRILIM_GECERSIZLESTI"}
                if (source_bar == n - 1 and alarm_turu != "gecersiz"
                        and (active_candidate or active_state)):
                    barriers.append(("formasyon_siniri", _gercek(formasyon.get(boundary))))
                reason = barrier_reason(close, atr, "UP" if direction == 1 else "DOWN", barriers)
                if reason:
                    layer.setdefault("baglam_bastirilan", []).append({"bar": bar, "tur": key, "neden": reason})
                else:
                    kept.append(bar)
            layer[key] = kept
    direnc = goruntu["stabil_direnc"]
    if direnc and direnc.get("neden") and not direnc.get("hazir"):
        goruntu["uyarilar"].append(_stabil_direnc_uyarisi(str(direnc["neden"])))
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


def _zaman_anahtari(deger: Any) -> Optional[int]:
    """Timestamp'i İstanbul nanosaniye anahtarına çevirir; okunamazsa None."""
    try:
        import pandas as pd

        ts = pd.Timestamp(deger)
        if pd.isna(ts):
            return None
        if ts.tzinfo is None:
            ts = ts.tz_localize("Europe/Istanbul")
        else:
            ts = ts.tz_convert("Europe/Istanbul")
        return int(ts.value)
    except Exception:
        return None


def _stabil_klasik_dilim(projeksiyon: list[Any], davranislar: list[Any],
                         sol: int, sag: int) -> tuple[list[Any], list[Any]]:
    """Zaman damgası yoksa eski indeks tabanlı hizalama (geri uyumlu yol)."""
    pencere_boy = max(0, int(sag) - int(sol))
    if len(projeksiyon) >= sag:
        return (projeksiyon[sol:sag],
                davranislar[sol:sag] if len(davranislar) >= sag else [])
    if len(projeksiyon) == pencere_boy:
        return (projeksiyon,
                davranislar if len(davranislar) == pencere_boy else [])
    if len(projeksiyon) > pencere_boy:
        return (projeksiyon[-pencere_boy:],
                davranislar[-pencere_boy:] if len(davranislar) >= pencere_boy else [])
    eksik_bas = [None] * (pencere_boy - len(projeksiyon))
    dav_dilim = ([None] * (pencere_boy - len(davranislar)) + davranislar) if davranislar else []
    return eksik_bas + projeksiyon, dav_dilim


def _stabil_zamanli_dilim(projeksiyon: list[Any], davranislar: list[Any],
                          sol: int, sag: int, tf: str,
                          zamanlar: Optional[Sequence[Any]]) -> Optional[tuple[list[Any], list[Any]]]:
    """Kadraj mumlarını domain'in KAPANIŞ zamanlarıyla eşleştirir.

    `prepare_causal_ohlcv` geçersiz/açık mumları çıkarabildiği için projeksiyon
    grafik çerçevesinden kısa olabilir. Salt indeks dilimleme bu durumda `▲`
    işaretlerini kaydırabilir veya tamamen düşürebilir. Burada görünür her mumun
    close_time'ı, projeksiyondaki en geç `bar_close_time <= close_time` kaydına
    bağlanır; kesimden sonraki mumlar için destek uydurulmaz.
    """
    pencere_boy = max(0, int(sag) - int(sol))
    if not zamanlar or len(zamanlar) != pencere_boy or not projeksiyon:
        return None
    try:
        import pandas as pd
        from data import mum_kapanis_anlari

        close_times = mum_kapanis_anlari(pd.DatetimeIndex(zamanlar), str(tf).lower())
    except Exception:
        return None
    if len(close_times) != pencere_boy:
        return None

    gorunur_anahtarlar = [_zaman_anahtari(t) for t in close_times]
    projeksiyon_anahtarlari = [_zaman_anahtari(_alan(pt, "bar_close_time")) for pt in projeksiyon]
    if any(k is None for k in (*gorunur_anahtarlar, *projeksiyon_anahtarlari)):
        return None
    if any(b < a for a, b in zip(gorunur_anahtarlar, gorunur_anahtarlar[1:])):
        return None
    if any(b < a for a, b in zip(projeksiyon_anahtarlari, projeksiyon_anahtarlari[1:])):
        return None

    davranis_by_index: dict[int, Any] = {}
    for pos, bhv in enumerate(davranislar):
        try:
            idx = int(_alan(bhv, "bar_index", pos))
        except (TypeError, ValueError):
            idx = pos
        davranis_by_index[idx] = bhv

    son_projeksiyon_zamani = projeksiyon_anahtarlari[-1]
    dilim: list[Any] = []
    dav_dilim: list[Any] = []
    for anahtar in gorunur_anahtarlar:
        if anahtar < projeksiyon_anahtarlari[0] or anahtar > son_projeksiyon_zamani:
            dilim.append(None)
            dav_dilim.append(None)
            continue
        pos = bisect_right(projeksiyon_anahtarlari, anahtar) - 1
        nokta = projeksiyon[pos]
        dilim.append(nokta)
        try:
            bar_idx = int(_alan(nokta, "bar_index", pos))
        except (TypeError, ValueError):
            bar_idx = pos
        # Desteği eski noktayla uzatabiliriz; ancak eski barın OK işareti
        # eksik/farklı zamanlı her muma tekrar çizilemez.
        dav_dilim.append(davranis_by_index.get(bar_idx)
                         if projeksiyon_anahtarlari[pos] == anahtar else None)
    return dilim, dav_dilim


def _stabil_verisi(sonuclar: Any, tf: str, sol: int, sag: int,
                   zamanlar: Optional[Sequence[Any]] = None) -> Optional[dict[str, Any]]:
    """Günlük yapısal destek stepline + `▲` işaretlerini kadraja hizalar."""
    sol_i, sag_i = int(sol), int(sag)
    if not sonuclar or sag_i <= sol_i:
        return None
    kayit = None
    if isinstance(sonuclar, Mapping):
        if "stabil" in sonuclar:
            kayit = sonuclar.get("stabil")
        elif tf in sonuclar and isinstance(sonuclar.get(tf), Mapping):
            kayit = sonuclar[tf].get("stabil")
    else:
        kayit = _alan(sonuclar, "stabil")
    if kayit is None or _alan(kayit, "error") or bool(_alan(kayit, "skipped", False)):
        return None

    ayrinti = _alan(kayit, "details", {}) or {}
    sonuc_nesne = _alan(kayit, "result")
    projeksiyon = list(
        _alan(ayrinti, "bar_projection")
        or _alan(sonuc_nesne, "bar_projection")
        or ()
    )
    davranislar = list(
        _alan(ayrinti, "bar_behaviors")
        or _alan(sonuc_nesne, "bar_behaviors")
        or ()
    )
    pencere_boy = max(0, sag_i - sol_i)
    bos = {"hazir": False, "seviyeler": [], "renkler": [], "durumlar": [],
           "reclaim_barlar": [], "momentum_barlar": [], "dikey_barlar": [],
           "dikey_deneme_barlar": [], "son_seviye": None,
           "son_durum": "NO_SUPPORT", "konum": None}
    if not projeksiyon or pencere_boy <= 0:
        return bos

    eslesen = _stabil_zamanli_dilim(projeksiyon, davranislar, sol_i, sag_i, tf, zamanlar)
    dilim, dav_dilim = eslesen if eslesen is not None else _stabil_klasik_dilim(
        projeksiyon, davranislar, sol_i, sag_i
    )

    seviyeler: list[Optional[float]] = []
    renkler: list[Optional[str]] = []
    durumlar: list[str] = []
    for nokta in dilim:
        if nokta is None:
            seviyeler.append(None)
            renkler.append(None)
            durumlar.append("NO_SUPPORT")
            continue
        seviye = _gercek(_alan(nokta, "support_level"))
        rol = str(_alan(nokta, "color_role") or "")
        durum = _ad(_alan(nokta, "validity")) or "NO_SUPPORT"
        if seviye is None:
            seviyeler.append(None)
            renkler.append(None)
            durumlar.append(durum)
            continue
        if rol == "above" or durum == "ACTIVE":
            renk = "ust"
        elif rol == "below" or durum in {"BREACHED", "BELOW_FLOOR"}:
            renk = "alt"
        else:
            renk = None
        seviyeler.append(seviye)
        renkler.append(renk)
        durumlar.append(durum)

    try:
        from domain_engines.stabil.signals import STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI
    except ImportError:
        STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI = frozenset({
            "long_base_breakout", "upward_rebase_momentum",
        })

    reclaim_barlar: list[int] = []
    momentum_barlar: list[int] = []
    dikey_barlar: list[int] = []
    dikey_deneme_barlar: list[int] = []
    for idx_b, bhv in enumerate(dav_dilim):
        if bhv is None:
            continue
        if bool(_alan(bhv, "vertical_support", False)):
            dikey_barlar.append(int(idx_b))
        if _alan(bhv, "vertical_attempt_kind"):
            dikey_deneme_barlar.append(int(idx_b))
        if _alan(bhv, "reclaim_kind") in {"multi_bar_recovery", "intrabar_sweep_reclaim"}:
            reclaim_barlar.append(int(idx_b))
        if _alan(bhv, "momentum_kind") in STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI:
            momentum_barlar.append(int(idx_b))

    son_seviye = next((v for v in reversed(seviyeler) if v is not None), None)
    son_renk = next((r for r in reversed(renkler) if r is not None), None)
    son_durum = durumlar[-1] if durumlar else "NO_SUPPORT"
    konum = _alan(ayrinti, "latest_support_relation") or _alan(sonuc_nesne, "latest_support_relation")
    return {
        "hazir": any(v is not None for v in seviyeler),
        "seviyeler": seviyeler,
        "renkler": renkler,
        "durumlar": durumlar,
        "reclaim_barlar": reclaim_barlar,
        "momentum_barlar": momentum_barlar,
        "dikey_barlar": dikey_barlar,
        "dikey_deneme_barlar": dikey_deneme_barlar,
        "son_seviye": son_seviye,
        "son_renk": son_renk,
        "son_durum": son_durum,
        "konum": str(konum) if konum else None,
    }



def _stabil_direnc_uyarisi(neden: str) -> str:
    """Kullanıcıya görünen kısa neden; ayrıntılı kod snapshot metadata'dadır."""
    if str(neden).startswith("daily_on_closed_session:"):
        gun = str(neden).partition(":")[2]
        return f"Stabil direnç gösterilemedi: BIST kapalı olan {gun} tarihinde günlük mum var"
    aciklamalar = {
        "missing_source": "gerekli günlük veya saatlik kaynak yok",
        "no_completed_bars": "kapanmış kaynak mumu yok",
        "no_complete_target_bucket": "tam hedef mum yok",
        "missing_daily_session": "günlük işlem seansı eksik",
        "daily_on_closed_session": "kapalı günde günlük mum var",
        "duplicate_daily_session": "günlük seans tekrarlı",
        "missing_or_invalid_target_bucket": "hedef zaman diliminde eksik veya hatalı kova",
        "incomplete_hourly_bucket": "mumun saatlik bileşenleri eksik",
        "missing_hourly_source": "saatlik kaynak hedef mumu karşılamıyor",
        "incomplete_or_invalid_flag": "kaynakta tamamlanmamış veya belirsiz mum var",
        "insufficient_continuous_buckets": "sağlayıcı boşluğu sonrası kesintisiz kova kalmadı",
        "invalid_ohlcv": "kaynak fiyat/hacim verisi hatalı",
        "invalid_timestamp": "kaynak zamanları doğrulanamadı",
        "invalid_cutoff": "kapanış sınırı doğrulanamadı",
        "invalid_columns": "kaynak sütunları doğrulanamadı",
        "target_source_mismatch": "hedef mum saatlik kaynakla uyuşmuyor",
        "daily_target_source_mismatch": "günlük grafik kaynakla uyuşmuyor",
        "daily_split_scale_unverified": "geçmiş fiyat ölçeği doğrulanamadı",
        "unknown_session": "işlem takvimi doğrulanamadı",
        "calendar_close_mismatch": "yarım gün kapanışı doğrulanamadı",
        "unsupported_session": "bu sembolün seansı desteklenmiyor",
        "unsupported_timeframe": "zaman dilimi desteklenmiyor",
        "insufficient_history_for_resistance": "günlük direnç geçmişi henüz yeterli değil",
        "invalid_time_alignment": "mum kapanış zamanları eşleştirilemedi",
        "future_daily_snapshot": "günlük bilginin zamanı doğrulanamadı",
        "missing_daily_snapshot": "günlük bilginin kapanış zamanı yok",
        "empty_projection": "direnç projeksiyonu yok",
    }
    aciklama = aciklamalar.get(neden, "hesap veya kaynak doğrulanamadı")
    return f"Stabil direnç gösterilemedi: {aciklama}"


def _stabil_direnc_verisi(sonuclar: Any, tf: str, sol: int, sag: int,
                          zamanlar: Optional[Sequence[Any]] = None) -> Optional[dict[str, Any]]:
    """Direnci yalnız aynı kapanış anındaki grafiğe bağla; indeksle tahmin etme.

    Destek köprüsünden farklı olarak eksik zamana önceki çizgi taşınmaz. Bir
    basamak konektörünün geometrisi de yeni bir sinyal/uyarı yaratmaz: okların
    türü yalnız bağımsız direnç motorunun aynı mumdaki davranışından gelir.
    """
    if not sonuclar or int(sag) <= int(sol):
        return None
    if isinstance(sonuclar, Mapping):
        kayit = sonuclar.get("stabil_direnc")
        if kayit is None and isinstance(sonuclar.get(tf), Mapping):
            kayit = sonuclar[tf].get("stabil_direnc")
    else:
        kayit = _alan(sonuclar, "stabil_direnc")
    if kayit is None:
        return None
    status = _ad(_alan(kayit, "status")) or "UNAVAILABLE"
    neden = _alan(kayit, "reason")
    bos: dict[str, Any] = {
        "hazir": False, "durum": status, "neden": str(neden) if neden else None,
        "seviyeler": [], "renkler": [], "durumlar": [],
        "donus_barlar": [], "momentum_barlar": [], "dikey_barlar": [],
        "dikey_deneme_barlar": [], "son_seviye": None, "son_renk": None,
    }
    # A partial/failed result is never a trustworthy price line, even if a
    # caller accidentally supplied old projection points alongside the error.
    if status != "READY":
        bos["neden"] = bos["neden"] or "empty_projection"
        return bos
    projeksiyon = list(_alan(kayit, "bar_projection") or ())
    davranislar = list(_alan(kayit, "bar_behaviors") or ())
    if not projeksiyon:
        bos["neden"] = bos["neden"] or "empty_projection"
        return bos
    pencere_boy = int(sag) - int(sol)
    if zamanlar is None or len(zamanlar) != pencere_boy:
        bos["neden"] = "invalid_time_alignment"
        return bos
    try:
        import pandas as pd
        from data import mum_kapanis_anlari

        gorunur = [_zaman_anahtari(t) for t in
                   mum_kapanis_anlari(pd.DatetimeIndex(zamanlar), str(tf).lower())]
        p_zamanlar = [_zaman_anahtari(_alan(p, "bar_close_time")) for p in projeksiyon]
        b_zamanlar = [_zaman_anahtari(_alan(b, "bar_close_time")) for b in davranislar]
        for anahtarlar in (gorunur, p_zamanlar, b_zamanlar):
            if any(k is None for k in anahtarlar) or any(b <= a for a, b in zip(anahtarlar, anahtarlar[1:])):
                bos["neden"] = "invalid_time_alignment"
                return bos
        for p, p_zaman in zip(projeksiyon, p_zamanlar):
            gun = _alan(p, "daily_as_of")
            # Warmup points may have neither a daily snapshot nor a level, but
            # a price without the date that made it knowable is not drawable.
            if gun is None and _gercek(_alan(p, "resistance_level")) is not None:
                bos["neden"] = "missing_daily_snapshot"
                return bos
            gun_zaman = _zaman_anahtari(gun) if gun is not None else None
            if gun is not None and (gun_zaman is None or gun_zaman > p_zaman):
                bos["neden"] = "future_daily_snapshot"
                return bos
        p_map = dict(zip(p_zamanlar, projeksiyon))
        b_map = dict(zip(b_zamanlar, davranislar))
    except Exception:  # noqa: BLE001 - yanlış hizalanmış katman çizilmez
        bos["neden"] = "invalid_time_alignment"
        return bos

    seviyeler: list[Optional[float]] = []
    renkler: list[Optional[str]] = []
    durumlar: list[str] = []
    donus: list[int] = []
    momentum: list[int] = []
    dikey: list[int] = []
    uyari: list[int] = []
    for idx, anahtar in enumerate(gorunur):
        nokta, bhv = p_map.get(anahtar), b_map.get(anahtar)
        sv = _gercek(_alan(nokta, "resistance_level")) if nokta is not None else None
        rol = str(_alan(nokta, "color_role") or "") if nokta is not None else ""
        renk = {"red": "alt", "green": "ust"}.get(rol)
        if sv is None or sv <= 0 or renk is None:
            seviyeler.append(None)
            renkler.append(None)
            durumlar.append("NO_RESISTANCE")
            continue
        seviyeler.append(sv)
        renkler.append(renk)
        durumlar.append(_ad(_alan(nokta, "validity")) or "NO_RESISTANCE")
        if bhv is None:
            continue
        # Zaman tam eşleşse bile başka bir barın davranışı bu çizgiye ait olamaz.
        if _alan(bhv, "bar_index") != _alan(nokta, "bar_index"):
            continue
        bhv_seviye = _gercek(_alan(bhv, "resistance_level"))
        if bhv_seviye is None or abs(bhv_seviye - sv) > max(1e-8, abs(sv) * 1e-9):
            continue
        if bool(_alan(bhv, "vertical_resistance", False)):
            dikey.append(idx)
            if _alan(bhv, "vertical_attempt_kind"):
                uyari.append(idx)
            continue
        if _alan(bhv, "return_kind") in {"close_return_below", "intrabar_sweep_rejection"}:
            donus.append(idx)
        elif _alan(bhv, "momentum_kind") in {"long_ceiling_breakdown", "downward_rebase_momentum"}:
            momentum.append(idx)

    return {
        "hazir": any(v is not None for v in seviyeler), "durum": status,
        "neden": str(neden) if neden else None,
        "seviyeler": seviyeler, "renkler": renkler, "durumlar": durumlar,
        "donus_barlar": donus, "momentum_barlar": momentum,
        "dikey_barlar": dikey, "dikey_deneme_barlar": uyari,
        # A missing last projection must not leave a stale price chip.
        "son_seviye": seviyeler[-1] if seviyeler else None,
        "son_renk": renkler[-1] if renkler else None,
    }

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
            "stabil": {"hazir": False, "cizildi": False, "son_seviye": None,
                       "son_renk": None, "gorunur_bar": 0, "kadrajda": False},
            "stabil_direnc": {"hazir": False, "cizildi": False, "son_seviye": None,
                              "son_renk": None, "gorunur_bar": 0, "kadrajda": False},
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
    # Sabit PID adı /tmp'de symlink saldırısına ve aynı hedefe eşzamanlı
    # yazımlarda çakışmaya açıktı. mkstemp benzersiz, 0600 ve O_EXCL kullanır.
    fd, gecici = tempfile.mkstemp(prefix=f".{os.path.basename(yol)}.", suffix=".tmp", dir=klasor)
    try:
        with os.fdopen(fd, "wb") as akis:
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


