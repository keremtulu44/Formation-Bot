#!/usr/bin/env python3
"""arastirma_cikti/* + backfill_data/* → Supabase dz_* (FAZ 1 depolama hattı).

Bu betik ÜRETMEZ; `arastirma_kosu.py` ürettiği gözlem satırlarını dz şemasının
kolonlarına eşler ve (istek hâlinde) PostgREST ile upsert eder. Canlı yola
dokunmaz (şema sözleşmesi: dz_* yalnız scripts/backfill/* kullanır).

Kullanım:

    # 1) Üretim + doğrulama (AĞ YOK): dz_yukleme/ altına dz satırları + kapsam raporu
    python scripts/backfill/dz_yukleme.py --seri-limit 3
    python scripts/backfill/dz_yukleme.py

    # 2) Supabase yükleme (kullanıcı makinesi; SUPABASE_URL + SERVICE_ROLE_KEY)
    python scripts/backfill/dz_yukleme.py --sadece-yukle

Tasarım kararları:

**Eşleme tek yerde, sözlükle birlikte.** dz şeması motor-native kolon adlarını
bekler; arastirma_cikti düzleştirilmiş ölçüm satırıdır. Hangi kolonun nereden
geldiği (veya neden NULL kaldığı) `KAPSAM` raporunda toplanır — sessiz veri
kaybı yoktur.

**Çerçeve bağımlılıkları araştırma yüküyle aynıdır.** touch indeksleri,
arrival_previous_close, pencere_* ve confirmation OHLC arşiv çerçevesinden
türetilir (`research.arsiv.tf_frame` — koşuyla birebir aynı resample).

**Idempotent.** Tüm upsert'ler doğal anahtar/PK üzerinde merge-duplicates ile
gider; tekrar koşu çoğaltma üretmez. Yükleme kipi `durum.json` ile devam eder.

**Kırılma izolasyonu.** Eşleme hatası bir seriyi durdurmaz; satır atlanır ve
`kapsam_raporu.json` içinde hata olarak sayılır (sessiz kısmi başarı yasak).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO = Path(__file__).resolve().parent.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

KATEGORILER = ("zone", "dokunus", "swing", "event")
TABLO_KATEGORI = {
    "zone": "dz_zones",
    "dokunus": "dz_zone_touches",
    "swing": "dz_ms_swings",
    "event": "dz_ms_events",
    "bars": "dz_bars",
}
# on_conflict hedefleri (şemadaki doğal anahtar/K2 + PK).
ON_CONFLICT = {
    "dz_zones": "symbol,timeframe,family,direction,dogum_bar_time",
    "dz_zone_touches": "touch_id",
    "dz_ms_swings": "symbol,timeframe,scope,side,confirm_bar_time,price",
    "dz_ms_events": "symbol,timeframe,scope,event_type,confirmed_at,broken_level",
    "dz_bars": "symbol,timeframe,bar_time",
}
VARSAYILAN_CIKTI = "dz_yukleme"
HORIZON_ANA = 12  # olcum.HORIZONLAR'ın maksimumu; status/window_complete bu pencerenin


# ---------------------------------------------------------------------------
# Şema sözlüğü (dz_*.sql'den otomatik — el yazımı liste yok)
# ---------------------------------------------------------------------------

def sema_kolonlari(sema_yolu: Path | None = None) -> dict[str, list[str]]:
    """supabase_backfill_schema.sql içinden tablo → kolon listesi üretir."""
    yol = sema_yolu or (REPO / "supabase_backfill_schema.sql")
    sql = yol.read_text(encoding="utf-8")
    sonuc: dict[str, list[str]] = {}
    for bulma in re.finditer(r"create table if not exists public\.(dz_\w+)\s*\((.*?)\n\);", sql, re.S):
        tablo, govde = bulma.group(1), bulma.group(2)
        kolonlar: list[str] = []
        for satir in govde.split("\n"):
            s = satir.strip().rstrip(",")
            if not s or s.startswith(("--", "constraint", "primary", "(")):
                continue
            if s.lower().startswith(("unique ", "check ", "foreign ", "primary ")):
                continue
            kolonlar.append(s.split()[0])
        sonuc[tablo] = kolonlar
    eksik = set(TABLO_KATEGORI.values()) - set(sonuc)
    if eksik:
        raise RuntimeError(f"şemada tablo bulunamadı: {sorted(eksik)}")
    return sonuc


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _sayi(deger: Any) -> float | None:
    if deger is None:
        return None
    if isinstance(deger, bool):
        return None
    try:
        d = float(deger)
    except (TypeError, ValueError):
        return None
    return d if math.isfinite(d) else None


def _tam(deger: Any) -> int | None:
    d = _sayi(deger)
    return int(d) if d is not None else None


def _metin(deger: Any) -> str | None:
    if deger is None:
        return None
    s = str(deger)
    return s if s and s.lower() != "none" else None


def _bar_zamani(ts: Any) -> str | None:
    """K1: 'YYYY-MM-DD HH:MM:SS+03:00' (ISO T yok)."""
    import pandas as pd

    if ts is None:
        return None
    if isinstance(ts, str):
        if "T" in ts:
            ts = pd.Timestamp(ts)
        else:
            return ts
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        import pytz

        t = t.tz_localize("Europe/Istanbul")
    metin = t.strftime("%Y-%m-%d %H:%M:%S%z")
    return f"{metin[:-2]}:{metin[-2:]}"


class SeriBaglam:
    """Bir (symbol, timeframe) serisi için türetilmiş çerçeveli bağlam."""

    def __init__(self, symbol: str, timeframe: str, bar_sayisi: int):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bar_sayisi = bar_sayisi
        self.first_bar_time: str | None = None
        self._zaman_indeks: dict[Any, int] = {}
        self._frame: Any = None
        self.hata: str | None = None

    def cerceve_yukle(self) -> Any:
        if self._frame is not None:
            return self._frame
        from research import arsiv

        frame = arsiv.tf_frame(self.symbol, self.timeframe)
        self._frame = frame
        self.first_bar_time = _bar_zamani(frame.index[0]) if len(frame) else None
        self._zaman_indeks = {pd_ts: i for i, pd_ts in enumerate(frame.index)}
        return frame

    def indeks(self, bar_time: str | None) -> int | None:
        if not bar_time:
            return None
        import pandas as pd

        try:
            return self._zaman_indeks.get(pd.Timestamp(bar_time))
        except (TypeError, ValueError):
            return None

    def kapanis_once(self, indeks: int | None) -> float | None:
        if indeks is None or indeks <= 0:
            return None
        frame = self.cerceve_yukle()
        if indeks - 1 >= len(frame):
            return None
        return float(frame.iloc[indeks - 1]["close"])

    def ohlc(self, indeks: int | None) -> tuple[float | None, float | None, float | None]:
        if indeks is None:
            return None, None, None
        frame = self.cerceve_yukle()
        if not (0 <= indeks < len(frame)):
            return None, None, None
        satir = frame.iloc[indeks]
        return _sayi(satir["high"]), _sayi(satir["low"]), _sayi(satir["close"])

    def seritamamla(self) -> None:
        from research import arsiv

        self._frame = None
        self._zaman_indeks = {}
        arsiv._OBELLEK.clear()


# ---------------------------------------------------------------------------
# Eşleme — zone
# ---------------------------------------------------------------------------

def zone_satiri(satir: Mapping[str, Any], ctx: SeriBaglam, run_id: str) -> dict[str, Any]:
    """arastirma zone satırı → dz_zones (kapsam raporu: NULL alanlar listelenir)."""
    return {
        "zone_id": _metin(satir.get("zone_id")),
        "symbol": _metin(satir.get("symbol")) or ctx.symbol,
        "timeframe": _metin(satir.get("timeframe")) or ctx.timeframe,
        "family": _metin(satir.get("family")),
        "direction": _metin(satir.get("direction")),
        "dogum_bar_time": _metin(satir.get("dogum_bar_time")),
        "dogum_bar_index": _tam(satir.get("dogum_index")),
        "pencere_ilk_bar": ctx.first_bar_time,
        "pencere_bar_sayisi": _tam(satir.get("bar_sayisi")) or ctx.bar_sayisi,
        "zone_lower": _sayi(satir.get("zone_lower")),
        "zone_upper": _sayi(satir.get("zone_upper")),
        "yukseklik": _sayi(satir.get("yukseklik_fiyat")),
        "yukseklik_atr": _sayi(satir.get("yukseklik_atr")),
        "atr_at_dogum": _sayi(satir.get("atr_at_birth")),
        # quality + OB/FVG native skor alanları arastirma_cikti'de üretilmez (NULL)
        "terminal_bar_time": _metin(satir.get("terminal_bar_time")),
        "terminal_state": _metin(satir.get("native_terminal_state")),
        "terminal_reason": _metin(satir.get("native_terminal_reason")),
        "terminal_category": _metin(satir.get("native_terminal_category")),
        "price_violation": bool(satir.get("native_price_violation")),
        "full_fill": bool(satir.get("native_full_fill")),
        "sansur": bool(satir.get("sansur")),
        "engine_version": _metin(satir.get("engine_version")),
        "config_hash": _metin(satir.get("config_hash")),
        "kaynak": "backfill",
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Eşleme — dokunus
# ---------------------------------------------------------------------------

def boundary_anchored(arrival: str | None) -> str:
    """Şema yorumu: UST/ALT yalnız FROM_ABOVE/FROM_BELOW; diğerleri BELIRSIZ."""
    if arrival == "FROM_ABOVE":
        return "UST"
    if arrival == "FROM_BELOW":
        return "ALT"
    return "BELIRSIZ"


def dokunus_satiri(satir: Mapping[str, Any], ctx: SeriBaglam, run_id: str) -> dict[str, Any]:
    """arastirma dokunus satırı → dz_zone_touches.

    Yön-çapalı excursion `repoh{10,12}_full_window_*` (directional_excursions
    semantiği — şemanın beklediği ölçü). Şekil metrikleri `yon_*` bloğundan.
    """
    baslangic = _metin(satir.get("dokunus_baslangic_bar_time"))
    bitis = _metin(satir.get("dokunus_bitis_bar_time"))
    zone_id = _metin(satir.get("zone_id"))
    dokunus_no = _tam(satir.get("dokunus_no")) or 0
    bas_idx = ctx.indeks(baslangic)
    bit_idx = ctx.indeks(bitis)
    arrival = _metin(satir.get("arrival_side"))

    gozlenen = _tam(satir.get("gozlenen_bar")) or 0
    observed = min(HORIZON_ANA, gozlenen)
    fav10 = _sayi(satir.get("repoh10_full_window_favorable_excursion_atr"))
    fav12 = _sayi(satir.get("repoh12_full_window_favorable_excursion_atr"))
    yon_h10 = _sayi(satir.get("yon_h10"))
    yon_h12 = _sayi(satir.get("yon_h12"))

    return {
        "touch_id": f"{zone_id}|touch{dokunus_no}|{baslangic}",
        "zone_id": zone_id,
        "symbol": _metin(satir.get("symbol")) or ctx.symbol,
        "timeframe": _metin(satir.get("timeframe")) or ctx.timeframe,
        "family": _metin(satir.get("family")),
        "direction": _metin(satir.get("direction")),
        "touch_number": dokunus_no,
        "touch_bar_count": _tam(satir.get("dokunus_bar_sayisi")),
        "touch_start": baslangic,
        "touch_end": bitis,
        "touch_start_index": bas_idx,
        "touch_end_index": bit_idx,
        "arrival_side": arrival,
        "approach_direction": _metin(satir.get("approach_direction")),
        "arrival_previous_close": ctx.kapanis_once(bas_idx),
        "boundary_anchored": boundary_anchored(arrival),
        # remaining/fill/wick/close kolonları arastirma_cikti'de üretilmez (NULL)
        "atr_at_touch": _sayi(satir.get("atr_at_touch")),
        "favorable_atr_h10": fav10,
        "adverse_atr_h10": _sayi(satir.get("repoh10_full_window_adverse_excursion_atr")),
        "favorable_atr_h12": fav12,
        "adverse_atr_h12": _sayi(satir.get("repoh12_full_window_adverse_excursion_atr")),
        "kenar_yonlu_tepki_atr_h10": _sayi(satir.get("kenar_h10")),
        "kenar_yonlu_tepki_atr_h12": _sayi(satir.get("kenar_h12")),
        # kenar-yönlü TERS h10 ölçüsü kaynakta üretilmiyor (NULL + kapsam raporu)
        "peak_excursion_atr": _sayi(satir.get("yon_tepe_atr")),
        "bars_to_peak": _tam(satir.get("yon_tepe_bar")),
        "peak_share_at_1": _sayi(satir.get("yon_pay_1")),
        "peak_share_at_3": _sayi(satir.get("yon_pay_3")),
        "peak_share_at_5": _sayi(satir.get("yon_pay_5")),
        # bars_in_profit: kaynakta ölçülmemiş (NULL + kapsam raporu)
        "decay_ratio": _sayi(satir.get("yon_h10_decay")),
        "horizon_10_12_farki": (fav12 - fav10) if (fav10 is not None and fav12 is not None) else None,
        "observed_post_touch_bars": observed,
        "window_complete": bool(satir.get("repoh12_window_complete")),
        "status": _metin(satir.get("repoh12_window_status")) or "COMPLETE",
        "native_terminal_at_touch": bool(satir.get("terminal_dokunusta")),
        "vp_data_ready": satir.get("vp_data_ready") if isinstance(satir.get("vp_data_ready"), bool) else None,
        "vp_volume_usable": satir.get("vp_volume_usable") if isinstance(satir.get("vp_volume_usable"), bool) else None,
        "vp_capital_usable": satir.get("vp_capital_usable") if isinstance(satir.get("vp_capital_usable"), bool) else None,
        "vp_rvol": _sayi(satir.get("vp_rvol")),
        "vp_volume_z_score": _sayi(satir.get("vp_volume_z_score")),
        "vp_volume_percent_rank": _sayi(satir.get("vp_volume_percent_rank")),
        "vp_capital_z_score": _sayi(satir.get("vp_capital_z_score")),
        "vp_directional_value_pressure_10": _sayi(satir.get("vp_directional_value_pressure_10")),
        "vp_net_progress_atr": _sayi(satir.get("vp_net_progress_atr")),
        "vp_directional_efficiency": _sayi(satir.get("vp_directional_efficiency")),
        "vp_effort_result_class": _metin(satir.get("vp_effort_result_class")),
        # participation_stage / up_confirmed / down_confirmed: vp_ornek'te yok (NULL)
        "engine_version": _metin(satir.get("engine_version")),
        "config_hash": _metin(satir.get("config_hash")),
        "kaynak": "backfill",
        "run_id": run_id,
        # yon_h10/h12 tepe-şekil için ayrıca korunmaz; horizon farkı yukarıda
        "_yon_h10": yon_h10,  # iç denetim için (çıkarılır)
    }


# ---------------------------------------------------------------------------
# Eşleme — swing (JSONL satır birimi swing × rol aralığı; dz birim swing)
# ---------------------------------------------------------------------------

def swing_grup_satiri(satirlar: list[Mapping[str, Any]], ctx: SeriBaglam, run_id: str) -> dict[str, Any]:
    """Aynı swing'e ait rol-aralığı satırlarını tek dz_ms_swings satırına indirger.

    İLK satır (ilk rol aralığı ya da rol-atanmadi çapası) esas alınır:
    deneme/engelleme ölçümleri rol çapasına göre yapılır ve dz tek satır taşır.
    """
    ilk = satirlar[0]
    scope = (_metin(ilk.get("scope")) or "").lower() or None
    side = (_metin(ilk.get("side")) or "").lower() or None
    rol = next((_metin(s.get("rol")) for s in satirlar if _metin(s.get("rol"))), None)
    kapanis_zamani = _metin(ilk.get("confirm_bar_time"))
    fiyat = _sayi(ilk.get("price"))
    sembol = _metin(ilk.get("symbol")) or ctx.symbol
    tf = _metin(ilk.get("timeframe")) or ctx.timeframe
    return {
        "swing_id": f"{sembol}:{tf}:{scope}:{side}:{kapanis_zamani}:{fiyat}",
        "symbol": sembol,
        "timeframe": tf,
        "scope": scope,
        "side": side,
        "identity": _tam(ilk.get("identity")),
        "pencere_ilk_bar": ctx.first_bar_time,
        "pencere_bar_sayisi": ctx.bar_sayisi,
        "structural_role": rol or _metin(ilk.get("structural_role_final")),
        "swing_class": _metin(ilk.get("swing_class")),
        "state": _metin(ilk.get("state")),
        "source_bar": _tam(ilk.get("source_bar")),
        "confirm_bar": _tam(ilk.get("confirm_bar")),
        "confirm_bar_time": kapanis_zamani,
        "source_bar_time": _metin(ilk.get("source_bar_time")),
        "price": fiyat,
        "atr_at_source": _sayi(ilk.get("atr_at_source")),
        "prominence_atr": _sayi(ilk.get("prominence_atr")),
        "distance_atr": _sayi(ilk.get("distance_atr")),
        # distance_pct: kaynakta oran üretilmiyor (NULL + kapsam raporu)
        "finalized": bool(ilk.get("finalized")) if isinstance(ilk.get("finalized"), bool) else None,
        "locked": bool(ilk.get("locked")) if isinstance(ilk.get("locked"), bool) else None,
        "quality": _sayi(ilk.get("quality")),
        "broken": bool(ilk.get("broken")) if isinstance(ilk.get("broken"), bool) else None,
        "broken_bar": _tam(ilk.get("broken_bar")),
        "broken_bar_time": _metin(ilk.get("broken_bar_time")),
        "bars_to_break": _tam(ilk.get("bars_to_break")),
        "sansur": "SAGDAN_SANSURLU" if ilk.get("bars_to_break_sansur") else "YOK",
        "deneme_025_atr": _tam(ilk.get("deneme_epizot_025")),
        "deneme_015_atr": _tam(ilk.get("deneme_epizot_015")),
        "deneme_050_atr": _tam(ilk.get("deneme_epizot_050")),
        # ilk/son_deneme_bar_time: kaynakta bar zamanı olarak üretilmiyor (NULL)
        "engelledi": ilk.get("engelledi_025") if isinstance(ilk.get("engelledi_025"), bool) else None,
        "red_magnitude_atr": _sayi(ilk.get("red_magnitude_atr")),
        "max_yaklasma_atr": _sayi(ilk.get("max_yaklasma_atr")),
        "engine_version": _metin(ilk.get("engine_version")),
        "config_hash": _metin(ilk.get("config_hash")),
        "kaynak": "backfill",
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Eşleme — event
# ---------------------------------------------------------------------------

def _yon_sayi(yon: str | None) -> int:
    return 1 if yon == "UP" else (-1 if yon == "DOWN" else 0)


def event_satiri(
    satir: Mapping[str, Any],
    ctx: SeriBaglam,
    run_id: str,
    swing_kaynak: Mapping[tuple[str, int], tuple[int | None, str | None]],
) -> dict[str, Any] | None:
    """arastirma event satırı → dz_ms_events.

    Onay barı yoksa (olculmedi) satır ATLANIR: confirmed_at NOT NULL + PK
    parçasıdır; sayaç kapsam raporuna yazılır.
    """
    onay_zamani = _metin(satir.get("event_bar_time"))
    if not onay_zamani:
        return None
    sembol = _metin(satir.get("symbol")) or ctx.symbol
    tf = _metin(satir.get("timeframe")) or ctx.timeframe
    scope = (_metin(satir.get("scope")) or "").lower() or None
    olay_tipi = _metin(satir.get("event_type"))
    kirilim_seviye = _sayi(satir.get("broken_level"))
    aday_idx = ctx.indeks(_metin(satir.get("candidate_bar_time")))
    olay_idx = ctx.indeks(onay_zamani)
    _, _, onay_kapanis = ctx.ohlc(olay_idx)
    referans = _sayi(satir.get("referans_kapanis"))
    onay_yuksek, onay_dusuk, _ = ctx.ohlc(olay_idx)

    kiran_id = _tam(satir.get("broken_swing_identity"))
    kiran_kaynak: tuple[int | None, str | None] | None = None
    if kiran_id is not None:
        kiran_kaynak = swing_kaynak.get((scope or "", kiran_id))
    sansur = bool(satir.get("sansur"))

    devam_h10 = _sayi(satir.get("devam_h10"))
    devam_h12 = _sayi(satir.get("devam_h12"))

    return {
        "event_id": f"{sembol}:{tf}:{scope}:{olay_tipi}:{onay_zamani}:{kirilim_seviye}",
        "symbol": sembol,
        "timeframe": tf,
        "scope": scope,
        "event_type": olay_tipi,
        "direction": _yon_sayi(_metin(satir.get("direction"))),
        "identity": _tam(satir.get("identity")),
        "event_uid": _metin(satir.get("event_uid")),
        "pencere_ilk_bar": ctx.first_bar_time,
        "pencere_bar_sayisi": ctx.bar_sayisi,
        "candidate_bar": _tam(satir.get("candidate_bar")),
        "candidate_at": _metin(satir.get("candidate_bar_time")),
        "event_bar": _tam(satir.get("event_bar")),
        "confirmed_at": onay_zamani,
        "broken_swing_identity": kiran_id,
        "broken_source_bar": kiran_kaynak[0] if kiran_kaynak else None,
        "broken_source_at": kiran_kaynak[1] if kiran_kaynak else None,
        "broken_level": kirilim_seviye,
        # origin_swing_identity kaynakta üretilmiyor → origin_source_* NULL
        "origin_price": _sayi(satir.get("origin_price")),
        "quality": _sayi(satir.get("quality")),
        "confirmation_status": _metin(satir.get("confirmation_status")),
        "validity": _metin(satir.get("validity")),
        "relevance": _metin(satir.get("relevance")),
        "outcome": _metin(satir.get("outcome")),
        "bos_maturity": _metin(satir.get("bos_maturity")),
        "age_bars": _tam(satir.get("age_bars")),
        "confirmed_by_event_uid": _metin(satir.get("confirmed_by")),
        "failed_by_event_uid": _metin(satir.get("failed_by")),
        "confirmation_high": onay_yuksek,
        "confirmation_low": onay_dusuk,
        "confirmation_close": referans if referans is not None else onay_kapanis,
        "atr_at_confirm": _sayi(satir.get("atr_at_event")),
        "follow_atr_h10": devam_h10,
        "follow_atr_h12": devam_h12,
        # ters_yon_atr_h10: kaynakta yalnız ters_h12 üretiliyor (NULL + rapor)
        "bars_to_peak": _tam(satir.get("devam_tepe_bar")),
        "peak_share_at_5": _sayi(satir.get("devam_pay_5")),
        "decay_ratio": _sayi(satir.get("devam_h12_decay")),
        "devamlilik_sinifi": _metin(satir.get("devamlilik_sinifi")),
        "status": "RIGHT_CENSORED_DATA_END" if sansur else "COMPLETE",
        "vp_data_ready": satir.get("vp_data_ready") if isinstance(satir.get("vp_data_ready"), bool) else None,
        "vp_volume_usable": satir.get("vp_volume_usable") if isinstance(satir.get("vp_volume_usable"), bool) else None,
        "vp_rvol": _sayi(satir.get("vp_rvol")),
        "vp_volume_percent_rank": _sayi(satir.get("vp_volume_percent_rank")),
        "vp_effort_result_class": _metin(satir.get("vp_effort_result_class")),
        "engine_version": _metin(satir.get("engine_version")),
        "config_hash": _metin(satir.get("config_hash")),
        "kaynak": "backfill",
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# dz_bars — backfill_data CSV'leri
# ---------------------------------------------------------------------------

def bars_satirlari(sembol: str, df: Any, run_id: str) -> list[dict[str, Any]]:
    """Arşiv CSV çerçevesinden dz_bars satırları (K5 bayrakları türetilir)."""
    satirlar: list[dict[str, Any]] = []
    onceki_kapanis: float | None = None
    for satir in df.itertuples(index=False):
        bar_time = _bar_zamani(satir.bar_time if isinstance(satir.bar_time, str) else satir.Index)
        yuksek, dusuk, kapanis, acilis = _sayi(satir.high), _sayi(satir.low), _sayi(satir.close), _sayi(satir.open)
        hacim = _sayi(satir.volume)
        nan_ohlc = any(d is None or (isinstance(d, float) and math.isnan(d)) for d in (acilis, yuksek, dusuk, kapanis))
        # K5: split adayı |open-prev_close|/prev_close > %10 (şema formülü)
        split = False
        if onceki_kapanis and onceki_kapanis > 0 and acilis is not None and math.isfinite(acilis):
            split = abs(acilis - onceki_kapanis) / onceki_kapanis > 0.10
        satirlar.append({
            "symbol": sembol,
            "timeframe": "1h" if getattr(satir, "interval", "1h") == "1h" else "1d",
            "bar_time": bar_time,
            "open": acilis if not (acilis is not None and math.isnan(acilis)) else None,
            "high": yuksek if yuksek is None or not math.isnan(yuksek) else None,
            "low": dusuk if dusuk is None or not math.isnan(dusuk) else None,
            "close": kapanis if kapanis is None or not math.isnan(kapanis) else None,
            "volume": hacim if hacim is None or not math.isnan(hacim) else None,
            "nan_ohlc": bool(nan_ohlc),
            "sifir_hacim": hacim is not None and not math.isnan(hacim) and float(hacim) == 0.0,
            "split_adayi": split,
            "kaynak": "backfill",
            "run_id": run_id,
        })
        if kapanis is not None and math.isfinite(kapanis):
            onceki_kapanis = kapanis
    return satirlar


# ---------------------------------------------------------------------------
# Üretim (AĞ YOK)
# ---------------------------------------------------------------------------

def _jsonl_dizin(yol: Path) -> list[tuple[str, str, int, int]]:
    """(symbol, tf, start_offset, end_offset) aralıkları; grup sırası zorunlu."""
    araliklar: list[tuple[str, str, int, int]] = []
    gorulen: set[tuple[str, str]] = set()
    offset = 0
    with yol.open("rb") as f:
        for satir in f:
            try:
                kayit = json.loads(satir)
            except json.JSONDecodeError:
                offset += len(satir)
                continue
            anahtar = (str(kayit.get("symbol")), str(kayit.get("timeframe")))
            son = len(araliklar) - 1
            if son >= 0 and (araliklar[son][0], araliklar[son][1]) == anahtar:
                araliklar[son] = (anahtar[0], anahtar[1], araliklar[son][2], offset + len(satir))
            elif anahtar in gorulen:
                raise RuntimeError(
                    f"{yol.name}: {anahtar} serisi grupsuz tekrar ediyor — koşu sırası bozulmuş"
                )
            else:
                araliklar.append((anahtar[0], anahtar[1], offset, offset + len(satir)))
                gorulen.add(anahtar)
            offset += len(satir)
    return araliklar


def _seri_satirlari(yol: Path, bas: int, son: int) -> list[dict[str, Any]]:
    satirlar: list[dict[str, Any]] = []
    with yol.open("rb") as f:
        f.seek(bas)
        ham = f.read(son - bas)  # tek okuma: satır ortası bölünmesin
    for satir in ham.splitlines():
        if satir.strip():
            satirlar.append(json.loads(satir))
    return satirlar


def uret(args: argparse.Namespace) -> dict[str, Any]:
    """arastirma_cikti → dz_yukleme/*.jsonl + kapsam_raporu.json (AĞ YOK)."""
    from research import arsiv

    cikti = REPO / args.cikti
    cikti.mkdir(parents=True, exist_ok=True)
    arastirma = REPO / "arastirma_cikti"
    sema = sema_kolonlari()
    run_id = args.run_id or f"dz-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"

    meta_yol = arastirma / "meta.jsonl"
    if not meta_yol.exists():
        raise SystemExit(f"önce arastirma_kosu çalıştırılmalı: {meta_yol} yok")
    meta_map: dict[tuple[str, str], dict[str, Any]] = {}
    with meta_yol.open(encoding="utf-8") as f:
        for satir in f:
            kayit = json.loads(satir)
            meta_map[(kayit["symbol"], kayit["timeframe"])] = kayit
    hatalar_meta: list[dict[str, Any]] = []
    hata_yol = arastirma / "hatalar.jsonl"
    if hata_yol.exists():
        with hata_yol.open(encoding="utf-8") as f:
            for satir in f:
                hatalar_meta.append(json.loads(satir))

    plan = sorted(meta_map)
    if args.seri_limit:
        plan = plan[: args.seri_limit]
    kategoriler = [k.strip() for k in args.kategori.split(",") if k.strip()]
    gecersiz = set(kategoriler) - set(KATEGORILER)
    if gecersiz:
        raise SystemExit(f"geçersiz kategori: {sorted(gecersiz)}")

    # aralıklar (yalnız seçilen kategoriler)
    dizinler = {k: _jsonl_dizin(arastirma / f"{k}.jsonl") for k in kategoriler if (arastirma / f"{k}.jsonl").exists()}

    kapsam: dict[str, Any] = {"run_id": run_id, "seri": len(plan), "tablolar": {}, "hatalar": [], "atlananlar": {}}
    uretilen = {k: 0 for k in kategoriler}
    atlanan = {"event_onay_yok": 0}

    dosyalar = {k: (cikti / f"{TABLO_KATEGORI[k]}.jsonl").open("w", encoding="utf-8") for k in kategoriler}
    try:
        for sira, (sembol, tf) in enumerate(plan, 1):
            meta = meta_map[(sembol, tf)]
            ctx = SeriBaglam(sembol, tf, int(meta.get("bar_sayisi") or 0))
            try:
                ctx.cerceve_yukle()
            except Exception as exc:  # noqa: BLE001 — seri izolasyon
                kapsam["hatalar"].append({"seri": [sembol, tf], "adim": "cerceve", "hata": f"{type(exc).__name__}: {exc}"})
                continue

            # swing kategorisi önce: event kırılım kaynağı için (scope, identity)
            swing_kaynak: dict[tuple[str, int], tuple[int | None, str | None]] = {}
            swing_gruplar: dict[tuple, list[dict[str, Any]]] = {}
            if "swing" in dizinler:
                swing_satirlari = [
                    s for (a_sym, a_tf, bas, son) in dizinler["swing"]
                    if a_sym == sembol and a_tf == tf
                    for s in _seri_satirlari(arastirma / "swing.jsonl", bas, son)
                ]
                grup_key = lambda s: (  # noqa: E731
                    s.get("symbol"), s.get("timeframe"), _metin(s.get("scope")),
                    _metin(s.get("side")), _metin(s.get("confirm_bar_time")), _sayi(s.get("price")),
                )
                for s in swing_satirlari:
                    swing_gruplar.setdefault(grup_key(s), []).append(s)
                for grup in swing_gruplar.values():
                    ilk = grup[0]
                    kimlik = _tam(ilk.get("identity"))
                    if kimlik is not None:
                        swing_kaynak.setdefault(
                            ((_metin(ilk.get("scope")) or "").lower(), kimlik),
                            (_tam(ilk.get("source_bar")), _metin(ilk.get("source_bar_time"))),
                        )
                if "swing" in dosyalar:
                    for grup in swing_gruplar.values():
                        satir = swing_grup_satiri(grup, ctx, run_id)
                        dosyalar["swing"].write(json.dumps(_temizle(satir), ensure_ascii=False) + "\n")
                        uretilen["swing"] += 1

            for kategori in kategoriler:
                if kategori == "swing":
                    continue
                araliklar = dizinler.get(kategori) or []
                dosya = arastirma / f"{kategori}.jsonl"
                for a_sym, a_tf, bas, son in araliklar:
                    if a_sym != sembol or a_tf != tf:
                        continue
                    for kayit in _seri_satirlari(dosya, bas, son):
                        try:
                            if kategori == "zone":
                                cikti_satir = zone_satiri(kayit, ctx, run_id)
                            elif kategori == "dokunus":
                                cikti_satir = dokunus_satiri(kayit, ctx, run_id)
                            else:
                                cikti_satir = event_satiri(kayit, ctx, run_id, swing_kaynak)
                                if cikti_satir is None:
                                    atlanan["event_onay_yok"] += 1
                                    continue
                            dosyalar[kategori].write(json.dumps(_temizle(cikti_satir), ensure_ascii=False) + "\n")
                            uretilen[kategori] += 1
                        except Exception as exc:  # noqa: BLE001 — satır izolasyonu
                            kapsam["hatalar"].append({
                                "seri": [sembol, tf], "kategori": kategori,
                                "hata": f"{type(exc).__name__}: {exc}",
                                "iz": traceback.format_exc(limit=3),
                            })
            ctx.seritamamla()
            if sira % 25 == 0 or sira == len(plan):
                print(f"[dz] {sira}/{len(plan)} seri · " + " ".join(f"{k}={v}" for k, v in uretilen.items()), flush=True)
    finally:
        for f in dosyalar.values():
            f.close()

    # kapsam raporu: her tablo için üretilen kolonlar + NULL kalanlar + fazlalar
    for kategori in kategoriler:
        tablo = TABLO_KATEGORI[kategori]
        beklenen = sema[tablo]
        dolu: set[str] = set()
        ornek_dosya = cikti / f"{tablo}.jsonl"
        if ornek_dosya.exists():
            with ornek_dosya.open(encoding="utf-8") as f:
                for satir in f:
                    kayit = json.loads(satir)
                    dolu.update(k for k, v in kayit.items() if v is not None)
                    if len(dolu) == len(beklenen):
                        break
        # DB varsayılanı olan kolonlar "null" sayılmaz (created_at/ingested_at
        # default now() ile dolar; satırda taşımak zorunlu değil).
        db_varsayilan = {"created_at", "ingested_at"}
        eksikler = sorted(set(beklenen) - dolu - db_varsayilan)
        kapsam["tablolar"][tablo] = {
            "beklenen": len(beklenen),
            "dolu": len([k for k in beklenen if k in dolu]),
            "kapsam": round(len([k for k in beklenen if k in dolu]) / max(1, len(beklenen)), 3),
            "null_kalanlar": eksikler,
        }
    kapsam["atlananlar"] = atlanan
    kapsam["uretilen"] = uretilen
    kapsam["arastirma_hata_sayisi"] = len(hatalar_meta)
    kapsam["ms_hatali_seri"] = [
        [m.get("symbol"), m.get("timeframe"), m.get("ms_hata")]
        for m in meta_map.values() if m.get("ms_hata")
    ]
    (cikti / "kapsam_raporu.json").write_text(
        json.dumps(kapsam, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: kapsam["tablolar"][k] for k in kapsam["tablolar"]}, ensure_ascii=False, indent=2))
    print(f"[dz] üretildi: {cikti} · run_id={run_id}")
    return kapsam


def _temizle(satir: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in satir.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Yükleme (PostgREST; kullanıcı makinesi)
# ---------------------------------------------------------------------------

def _istek(url: str, headers: Mapping[str, str], payload: Any, method: str = "POST") -> None:
    import requests

    son_hata: Exception | None = None
    for deneme in range(5):
        try:
            yanit = requests.request(method, url, headers=dict(headers), json=payload, timeout=60)
            if yanit.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {yanit.status_code}: {yanit.text[:300]}", response=yanit)
            yanit.raise_for_status()
            return
        except Exception as exc:  # noqa: BLE001 — yeniden denenir
            son_hata = exc
            bekle = 2 ** deneme
            print(f"    ⚠️ deneme {deneme + 1}/5 başarısız ({exc}); {bekle}s bekleniyor", flush=True)
            time.sleep(bekle)
    raise RuntimeError(f"istek 5 denemede de başarısız: {son_hata}")


def yukle(args: argparse.Namespace) -> None:
    """dz_yukleme/*.jsonl → PostgREST upsert (idempotent, kipli devam)."""
    import requests

    url_taban = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anahtar = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url_taban or not anahtar:
        raise SystemExit("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY gerekli (bot ile aynı sözleşmesi)")
    basliklar = {
        "apikey": anahtar,
        "Authorization": f"Bearer {anahtar}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    cikti = REPO / args.cikti
    durum_yolu = cikti / "durum.json"
    durum = json.loads(durum_yolu.read_text()) if durum_yolu.exists() else {}

    kategoriler = [k.strip() for k in args.kategori.split(",") if k.strip()]
    if getattr(args, "bars", False) and "bars" not in kategoriler:
        kategoriler.append("bars")
    toplam = 0
    for kategori in kategoriler:
        tablo = TABLO_KATEGORI.get(kategori, kategori if kategori in TABLO_KATEGORI.values() else None)
        if tablo is None:
            continue
        dosya = cikti / f"{tablo}.jsonl"
        if not dosya.exists():
            print(f"[atla] {dosya.name} yok")
            continue
        bayrak = f"{tablo}:offset"
        ofset = int(durum.get(bayrak, 0))
        if ofset:
            print(f"[devam] {tablo}: {ofset} bayttan")
        parti: list[dict[str, Any]] = []
        parti_bayt = 0
        hedef = f"{url_taban}/rest/v1/{tablo}"
        sorgu = f"?on_conflict={ON_CONFLICT[tablo]}"
        with dosya.open("rb") as f:
            f.seek(ofset)
            kuyruk = f.read()
        satir_baslar: list[int] = []
        konum = ofset
        for satir in kuyruk.splitlines():
            if not satir.strip():
                konum += len(satir) + 1
                continue
            satir_baslar.append(konum)
            konum += len(satir) + 1
        # partiler
        for i in range(0, len(satir_baslar), args.parti):
            bit = min(i + args.parti, len(satir_baslar))
            bas0, son0 = satir_baslar[i], (satir_baslar[bit] + 1 if bit < len(satir_baslar) else ofset + len(kuyruk))
            blok = kuyruk[bas0 - ofset: son0 - ofset]
            satirlar = [json.loads(s) for s in blok.splitlines() if s.strip()]
            _istek(hedef + sorgu, basliklar, satirlar)
            toplam += len(satirlar)
            durum[bayrak] = son0
            durum_yolu.write_text(json.dumps(durum))
            print(f"  {tablo}: {bit}/{len(satir_baslar)} satır ({toplam} toplam)", flush=True)
        durum.pop(bayrak, None)
        durum_yolu.write_text(json.dumps(durum))
    print(f"[dz] yükleme bitti · {toplam} satır")


def parti_boyut_kontrol(payload: list[dict[str, Any]], maks_bayt: int = 4_000_000) -> int:
    """Test için: JSON bayt boyutu."""
    return len(json.dumps(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="arastirma_cikti + backfill_data → dz_* hattı")
    parser.add_argument("--cikti", default=VARSAYILAN_CIKTI, help="dz satır çıktısı dizini")
    parser.add_argument("--seri-limit", type=int, default=0, help="kaç (symbol,tf) serisi (0 = hepsi)")
    parser.add_argument("--kategori", default="zone,dokunus,swing,event", help="üretilecek/yüklenecek kategoriler (bars ayrı bayrak)")
    parser.add_argument("--bars", action="store_true", help="dz_bars CSV üretimi de yapılsın (ağsız)")
    parser.add_argument("--yukle", action="store_true", help="üret Sonra PostgREST'e yükle")
    parser.add_argument("--sadece-yukle", action="store_true", help="üretme, mevcut dz_yukleme/ dosyalarını yükle")
    parser.add_argument("--parti", type=int, default=800, help="PostgREST satır/parti")
    parser.add_argument("--run-id", default="", help="K3 run_id (varsayılan: zaman damgalı)")
    args = parser.parse_args(argv)

    if not args.sadece_yukle:
        uret(args)
        if args.bars:
            uret_bars(args)
    if args.yukle or args.sadece_yukle:
        yukle(args)
    return 0


def uret_bars(args: argparse.Namespace) -> None:
    """backfill_data/*.csv.gz → dz_yukleme/dz_bars.jsonl (ağsız)."""
    import gzip

    import pandas as pd

    cikti = REPO / args.cikti
    cikti.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"dz-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    adet = 0
    with (cikti / "dz_bars.jsonl").open("w", encoding="utf-8") as cikti_dosya:
        for csv_yol in sorted((REPO / "backfill_data").glob("*_*.csv.gz")):
            parca = csv_yol.name.rsplit("_", 1)
            if len(parca) != 2 or parca[1].replace(".csv.gz", "") not in ("1h", "1d"):
                continue
            sembol, aralik = parca[0], parca[1].replace(".csv.gz", "")
            with gzip.open(csv_yol, "rt", encoding="utf-8") as f:
                df = pd.read_csv(f)
            if "bar_time" not in df.columns:
                continue
            df["interval"] = aralik
            for satir in bars_satirlari(sembol, df, run_id):
                cikti_dosya.write(json.dumps(_temizle(satir), ensure_ascii=False) + "\n")
                adet += 1
            if args.seri_limit and adet >= args.seri_limit * 4000:
                break
    print(f"[dz] dz_bars üretildi: {adet} satır")


if __name__ == "__main__":
    raise SystemExit(main())
