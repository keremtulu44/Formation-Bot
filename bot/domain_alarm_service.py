"""Yeni domain tetiklemeli bildirim kanalı (kullanıcı kararı, 2026-11-03).

Mevcut formasyon push'u, 4S Stabil geri alım alarmı, replay sonuçları ve kart
metinleri **değiştirilmez**. Bu modül yalnızca ek bir aday üretir: BOS/CHoCH,
formasyon, OB/FVG tepkisi veya grafikteki RVOL mantığıyla olağandışı hacim
olduğunda, o anki **native basamaklı** Stabil desteğine bakılır.

Kural:
* `dist_atr >= YENI_DOMAIN_ALARM_DIST_ATR_ALT` (varsayılan -3.0) HARD alt sınır.
* Üst sınır YOK: fiyat desteğin 5 ATR üstünde de tetikleyebilir.
* Hacim hard `AND` kapısı DEĞİLDİR; kendi başına ayrı tetikleyicidir.
* Bildirim ana DM + public hedefe gider ve kart `🆕 YENİ` ile işaretlenir.
* Aynı sembol/TF/bar tekrar basılmaz; bar bazlı cooldown korunur.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd

import config
from data import bar_kapandi_mi, mum_kapanis_ani
from domain_engines.stabil import format_stabil_card_lines
from notification_context import (
    _alarm_tf_rvol,
    _domain,
    _event_rows,
    _field,
    _number,
    _token,
    _usable_export,
)
from notifier.format_kart import _kart_mum_damgasi, _mum_damgasi_ekle
from notifier.util import TF_KISA, _KART_MAKS_SATIR, _satir
from state.paths import yeni_domain_alarm_state_yolu

logger = logging.getLogger(__name__)

YENI_KART_ISARETI = "🆕 YENİ"
_UST_TF = {"1h": "4h", "2h": "4h", "4h": "1d"}
_ALT_TF = {"1d": "4h"}
_GECERSIZ_FORMASYON = {"FORMASYON_GECERSIZ", "YOK", "ST_NONE", "NONE", ""}


@dataclass(frozen=True, slots=True)
class DomainAlarmCandidate:
    symbol: str
    timeframe: str
    bar_open: str
    bar_close: str
    bar_label: str
    bar_index: int
    close_price: float
    support_level: float | None
    dist_atr: float
    relation: str
    reasons: tuple[str, ...]
    volume_rvol: float | None
    volume_tier: str | None
    volume_source: str
    data_quality: str
    card_lines: tuple[str, ...]
    rank_score: float
    grafik_verisi: dict[str, Any] | None = None
    grafik_verisi_public: dict[str, Any] | None = None
    # Recent completed bar labels allow cooldown to survive rolling windows,
    # whose frame-relative last index may remain constant indefinitely.
    recent_bar_opens: tuple[str, ...] = ()

    @property
    def dedup_key(self) -> str:
        """Kalıcı state slot anahtarı: **sembol|TF** (bar DEĞİL).

        Bar anahtarı kullanıldığında her yeni mum yeni bir slot açıyor,
        ``_zaten_gonderildi`` slotun ``last_bar_index``'ini hiç bulamıyor ve
        ``YENI_DOMAIN_ALARM_COOLDOWN_BAR`` sessizce devre dışı kalıyordu.
        Aynı barı iki kez basmayı yine engeller (``last_bar_open`` eşitliği);
        cooldown de artık gerçekten uygulanır. Replay ``cooldown_uygula`` ile
        aynı semantik: sembol/TF başına N bar sessizlik.
        """
        return f"{self.symbol}|{self.timeframe}"

    @property
    def bar_key(self) -> str:
        """Bar düzeyi kimlik (aynı bar iki kez basılmasın)."""
        return f"{self.symbol}|{self.timeframe}|{self.bar_open}"

    @property
    def reason_signature(self) -> str:
        return "|".join(sorted(self.reasons))


def _tr_sayi(deger: float | None, ondalik: int = 2) -> str:
    if deger is None:
        return "—"
    try:
        v = float(deger)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if not math.isfinite(v):
        return "—"
    kalip = f"{v:,.{ondalik}f}"
    return kalip.replace(",", "_").replace(".", ",").replace("_", ".")


def _tf_etiket(tf: str) -> str:
    return TF_KISA.get(str(tf).lower(), str(tf))


def _grafik_verisi_uret(
    stock: str,
    tf: str,
    frame: pd.DataFrame,
    frames: Mapping[str, pd.DataFrame],
    results: Mapping[str, Any],
    simdiki_zaman: datetime,
    baglam: Mapping[str, Any] | None,
    *,
    direnc_gunluk_ham: pd.DataFrame | None = None,
    direnc_saatlik_ham: pd.DataFrame | None = None,
    direnc_cache: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Eski alarm kareleriyle birebir aynı `grafik.kare_listesi` çağrısı.

    Yeni kart için ayrı bir çizim yolu yok: aynı `cift`, aynı domain
    `sonuclar`, aynı kapanmış çerçeveler ve aynı alarm overlay bilgisi
    kullanılır. Public taraf da eski karardaki 2 kare + üst/alt TF kuralını
    izler.
    """
    try:
        import grafik
        if not grafik.grafik_aktif_mi():
            return None, None
        baglam = baglam or {}
        cift = baglam.get("cift")
        state = str(baglam.get("state") or "").strip().upper()
        alarm_turu = (
            grafik.alarm_turu_bul(state) if cift is not None and state else None
        )
        alarm_bar = None
        if cift is not None:
            try:
                ham_bar = int(baglam.get("alarm_bar"))
                if ham_bar >= 0:
                    alarm_bar = ham_bar
            except (TypeError, ValueError, OverflowError):
                alarm_bar = None
        ek = {k: v for k, v in frames.items() if k != tf}
        grafik_sonuclari = results
        try:
            from domain_engines.stabil.chart_bridge import add_chart_resistance, alarm_chart_timeframes

            public_tf = _UST_TF.get(tf) or _ALT_TF.get(tf)
            secilen_tfler = alarm_chart_timeframes(
                tf, frames, grafik.grafik_kare_adedi(), public_tf=public_tf,
                single=alarm_turu == "gecersiz",
            )
            grafik_sonuclari = add_chart_resistance(
                stock, {**frames, tf: frame}, results, daily_frame=direnc_gunluk_ham,
                hourly_frame=direnc_saatlik_ham, as_of_close=simdiki_zaman,
                timeframes=secilen_tfler, cache=direnc_cache,
            )
        except Exception as exc:  # noqa: BLE001 - mevcut grafik yine hazırlanır
            logger.warning("Domain direnç grafiği atlandı (%s/%s): %s", stock, tf, type(exc).__name__)
        ortak = {
            "sonuclar": grafik_sonuclari,
            "alarm_turu": alarm_turu,
            "alarm_bar": alarm_bar,
            "sembol": str(stock).upper(),
            "zaman_damgasi": frame.index[-1],
            "simdi": simdiki_zaman,
        }
        dm = grafik.kare_listesi(cift, tf, frame, ek_cerceveler=ek, **ortak)
        if not dm.get("goruntular"):
            dm = None
        ust_tf = _UST_TF.get(tf)
        rol = "ust"
        if ust_tf is None:
            ust_tf = _ALT_TF.get(tf)
            rol = "alt"
        ust_cerceve = frames.get(ust_tf) if ust_tf else None
        pub_ek = {ust_tf: ust_cerceve} if ust_tf and ust_cerceve is not None else {}
        pub = grafik.kare_listesi(
            cift, tf, frame, ek_cerceveler=pub_ek, adet=2, **ortak
        )
        if pub.get("goruntular"):
            if len(pub["goruntular"]) > 1:
                pub["goruntular"][1]["rol"] = rol
        else:
            pub = None
        return dm, pub
    except Exception as exc:  # noqa: BLE001 - grafik alarmı düşürmesin
        logger.debug("Yeni domain grafik verisi üretilemedi (%s/%s): %s", stock, tf, exc)
        return None, None


def _cfg_sayi(ad: str, varsayilan: float) -> float:
    try:
        return float(getattr(config, ad, varsayilan))
    except (TypeError, ValueError, OverflowError):
        return varsayilan


def _cfg_int(ad: str, varsayilan: int) -> int:
    try:
        return max(1, int(getattr(config, ad, varsayilan)))
    except (TypeError, ValueError, OverflowError):
        return varsayilan


def _token_temiz(deger: Any) -> str:
    return str(_token(deger) or "").strip()


def _stabil_bilgisi(results: Mapping[str, Any], tf: str,
                    frame: pd.DataFrame, formations=()) -> dict[str, Any] | None:
    """O anki native basamaklı destek + `dist_atr` + ilişki + 2 satırlık kart."""
    entry = _domain(results, tf, "stabil")
    if entry is None or _field(entry, "error") or bool(_field(entry, "skipped", False)):
        return None

    details = _field(entry, "details", {}) or {}
    out = _field(entry, "result")
    bhv = _field(details, "latest_behavior") or _field(out, "latest_behavior")
    if bhv is None:
        return None

    dist = _number(_field(bhv, "dist_atr"))
    if dist is None or not math.isfinite(dist):
        # Hard alt sınır doğrulanamıyorsa UNKNOWN; sessiz "geçti" denmez.
        return None

    alt_sinir = _cfg_sayi("YENI_DOMAIN_ALARM_DIST_ATR_ALT", -3.0)
    if dist < alt_sinir:
        return None

    sup = _number(_field(bhv, "support_level"))
    if sup is None:
        projeksiyon = _field(details, "bar_projection") or _field(out, "bar_projection") or ()
        if projeksiyon:
            sup = _number(_field(projeksiyon[-1], "support_level"))

    try:
        close = float(frame["close"].iloc[-1])
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        close = _number(_field(bhv, "close_price"))
    if close is None or not math.isfinite(close):
        return None

    relation = str(
        _field(details, "latest_support_relation")
        or _field(out, "latest_support_relation")
        or ""
    ).strip()
    if not relation:
        if dist > 0.25:
            relation = "destek üstünde"
        elif dist < -0.15:
            relation = "destek altında"
        else:
            relation = "destekte"

    # The domain card and chart must not advertise an upward signal that a
    # same-bar, aligned opposing structure suppresses.
    from domain_engines.stabil.structure_context import behavior_for_structure
    projection = _field(details, "bar_projection") or _field(out, "bar_projection") or ()
    close_times = [_field(point, "bar_close_time") for point in projection]
    card_behavior = behavior_for_structure(bhv, _domain(results, tf, "market_structure"), close_times, tf)
    # Use only same-bar available formation and resistance; missing sources
    # remain unknown. This affects display copy, not other domain events.
    from domain_engines.stabil.structure_context import barrier_reason, mask_behavior, pattern_is_active
    barriers = []
    for formation in formations or ():
        try:
            aligned = (formation.get("timeframe") == tf and
                       pd.Timestamp(formation.get("bar_time")) == pd.Timestamp(frame.index[-1]))
        except (TypeError, ValueError, IndexError):
            aligned = False
        if aligned and pattern_is_active(formation.get("state")):
            barriers.append(("formasyon_siniri", formation.get("upper")))
            break
    resistance = _domain(results, tf, "stabil_direnc")
    points = _field(resistance, "bar_projection") or ()
    if points:
        point = points[-1]
        try:
            expected_close = mum_kapanis_ani(frame.index[-1], tf)
            aligned = pd.Timestamp(_field(point, "bar_close_time")) == pd.Timestamp(expected_close)
        except (TypeError, ValueError, IndexError):
            aligned = False
        if aligned and str(_field(point, "color_role") or "") == "red":
            barriers.insert(0, ("stabil_koridoru", _field(point, "resistance_level")))
    try:
        from domain_engines.stabil.signals import _causal_atr14
        atr = _causal_atr14(frame["high"].to_numpy(dtype=float), frame["low"].to_numpy(dtype=float),
                            frame["close"].to_numpy(dtype=float), period=14)[-1]
        if barrier_reason(close, atr, "UP", barriers):
            card_behavior = mask_behavior(card_behavior)
    except (KeyError, ValueError, TypeError, IndexError):
        pass
    try:
        kart = tuple(
            format_stabil_card_lines(
                price=close, support_level=sup, behavior=card_behavior,
            )[:2]
        )
    except Exception as exc:  # noqa: BLE001 - kart satırı alarmı düşürmesin
        logger.debug("Yeni domain Stabil kart satırı atlandı: %s", exc)
        kart = ()

    kalite = _token_temiz(_field(entry, "data_quality")) or "OK"
    if kalite == "READY":
        kalite = "OK"

    return {
        "dist_atr": float(dist),
        "support_level": sup,
        "close_price": close,
        "relation": relation,
        "card_lines": kart,
        "data_quality": kalite,
        "behavior": bhv,
    }


def _bos_ve_choch_sebepleri(results: Mapping[str, Any], tf: str,
                            frame_len: int) -> list[str]:
    """Yalnız son 2 bardaki teyitli/aktif BOS-CHoCH olaylarını al."""
    export = _usable_export(_domain(results, tf, "market_structure"))
    if export is None:
        return []
    esik_bar = max(0, frame_len - 2)
    bulunan: list[str] = []
    for event in _event_rows(export):
        tip = _token_temiz(_field(event, "event_type"))
        if tip not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
            continue
        if _token_temiz(_field(event, "confirmation_status")) != "CONFIRMED":
            continue
        if _token_temiz(_field(event, "validity")) == "FAILED":
            continue
        if _token_temiz(_field(event, "relevance")) in {"SUPERSEDED", "HISTORICAL"}:
            continue
        if not bool(_field(event, "is_active", True)):
            continue
        bar = _number(_field(event, "event_bar"))
        if bar is None or bar < esik_bar:
            continue
        yon = _number(_field(event, "direction")) or 0.0
        ok = "↑" if yon > 0 else ("↓" if yon < 0 else "")
        kisa = "CHoCH" if "CHOCH" in tip else "BOS"
        bulunan.append(f"{kisa} {ok}".strip())
    return sorted(set(bulunan))


# FVG motorunda yalnızca aktif/canlı durumlar fiyat-içi bölge tepkisi üretir;
# CANDIDATE (2), FULL_FILL (7), FAILED_REACTION (9) ve diğer terminal durumlar
# canlı bölge değildir. REACTION (±8) ise motor tarafından `event` alanına
# yazılır (aktif FVG temizlendiği için top/bottom/state None olur).
_FVG_AKTIF_DURUMLAR = frozenset({3, 4, 5, 6})


def _bolge_sebepleri(results: Mapping[str, Any], tf: str,
                     close: float) -> list[str]:
    """OB/FVG: fiyat aktif bölgenin içindeyse veya FVG `reaksiyon` olayındaysa."""
    bulunan: list[str] = []
    for alan, tip, yanlar in (
        ("order_block", "OB", ("bull", "bear")),
        ("fvg", "FVG", ("bull_fvg", "bear_fvg")),
    ):
        entry = _domain(results, tf, alan)
        quality = _token_temiz(_field(entry, "data_quality"))
        # OB/FVG deliberately freeze their previous export on incomplete or
        # gap bars; that historical snapshot is not a fresh trigger.
        if quality and quality != "OK":
            continue
        export = _usable_export(entry)
        if export is None:
            continue
        for anahtar in yanlar:
            yan = _field(export, anahtar)
            if yan is None:
                continue
            yon = "boğa" if "bull" in anahtar else "ayı"
            state = _number(_field(yan, "state"))
            event = _number(_field(yan, "event"))
            reaksiyon = bool(
                tip == "FVG" and (
                    (event is not None and abs(int(event)) == 8)
                    or (state is not None and abs(int(state)) == 8)
                )
            )
            if reaksiyon:
                bulunan.append(f"{tip} {yon} reaksiyon")
                continue
            top = _number(_field(yan, "top"))
            bottom = _number(_field(yan, "bottom"))
            if top is None or bottom is None or top < bottom:
                continue
            if tip == "FVG" and (state is None or abs(int(state)) not in _FVG_AKTIF_DURUMLAR):
                continue
            if bottom <= close <= top:
                bulunan.append(f"{tip} {yon} bölge tepkisi")
    return sorted(set(bulunan))


def _hacim_bilgisi(results: Mapping[str, Any], tf: str,
                   frame: pd.DataFrame) -> dict[str, Any]:
    """Grafikteki RVOL mantığı: motor `rvol`, yoksa `hacim / SMA20` yerel."""
    rvol = _number(_alarm_tf_rvol(results, tf))
    kaynak = "motor"
    if rvol is None or rvol <= 0 or not math.isfinite(rvol):
        rvol = None
        kaynak = "yerel"
        try:
            hacimler = pd.to_numeric(frame["volume"], errors="coerce").astype(float)
            if len(hacimler) >= 20:
                ortalama = float(hacimler.iloc[-20:].mean())
                son = float(hacimler.iloc[-1])
                if ortalama > 0 and math.isfinite(son) and math.isfinite(ortalama):
                    rvol = son / ortalama
        except Exception as exc:  # noqa: BLE001 - hacim alanı alarmı düşürmesin
            logger.debug("Yerel RVOL hesaplanamadı: %s", exc)

    vp = _domain(results, tf, "volume_participation")
    details = _field(vp, "details", {}) or {} if vp is not None else {}
    metrics = _field(details, "latest_metrics")
    volume_usable = _field(metrics, "volume_usable", True) if metrics is not None else True
    if volume_usable is None:
        volume_usable = True

    esik5 = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_5X", 5.0)
    esik10 = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_10X", 10.0)
    suphe = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_SUPHE", 50.0)

    tier: str | None = None
    if rvol is not None and math.isfinite(rvol):
        if rvol >= esik10:
            tier = "10×"
        elif rvol >= esik5:
            tier = "5×"

    veri_suphe = bool(
        rvol is not None and (rvol >= suphe or not bool(volume_usable))
    )
    return {
        "rvol": rvol,
        "source": kaynak,
        "tier": tier,
        "veri_suphe": veri_suphe,
        "sebep": f"hacim {tier}" if tier else None,
    }


def _formasyon_sebepleri(kayitlar: Sequence[Mapping[str, Any]] | None,
                         tf: str) -> list[str]:
    if not kayitlar:
        return []
    tekrar = bool(getattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", True))
    anlik = {str(s).upper() for s in getattr(config, "ALERT_STATES", ())}
    bulunan: list[str] = []
    for kayit in kayitlar:
        if not isinstance(kayit, Mapping):
            continue
        if str(kayit.get("timeframe", "")).lower() != str(tf).lower():
            continue
        state = str(kayit.get("state") or "").strip().upper()
        bildirim = str(kayit.get("notification_state") or state).strip().upper()
        if state in _GECERSIZ_FORMASYON or bildirim in _GECERSIZ_FORMASYON:
            continue
        if not tekrar and bildirim in anlik:
            # Operatör 0 verirse eski anlık push ile aynı olayda ikinci kart
            # üretme; BOS/OB/FVG/hacim tetikleyicileri yine çalışır.
            continue
        try:
            q = float(kayit.get("quality") or 0.0)
            min_q = float(kayit.get("min_quality") or 0.0)
        except (TypeError, ValueError, OverflowError):
            continue
        if q < min_q:
            continue
        tip = str(kayit.get("pattern_name") or "formasyon").strip()
        bulunan.append(f"formasyon: {tip} · {state or bildirim}")
    return sorted(set(bulunan))


# --- Alarm politikası (P0/P6/P4; ölçüm: research/alarm_politika.py) -----------
# Replay `baglam_satiri` ile BİREBİR aynı formüller; yalnız son bar (index=-1)
# canlıda değerlendirilir. ATR: `_causal_atr14` (Wilder 14) — replay'in
# `compute_wilder_atr`'siyle son barda aynı değer (ikisi de SMA-seedli RMA).
# Yetersiz veri (sikisma için 50 bar, kosu için 6 bar + ATR>0) → alan None;
# politika varsayılanları replay ile aynıdır (sikisma None→1.0 geçer,
# kosu None→0.0 kalır). Yani kısa çerçeve P6/P4'te fail-open geçer.

_YALNIZ_ZAYIF_KANALLAR = frozenset({"OB", "FVG", "BOS", "CHoCH"})


def _baglam_sikisma_kosu(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    """Son barın (sikisma, kosu) bağlamı; hesaplanamazsa None.

    sikisma = son 10 bar aralığı / son 50 bar aralığı (50 bar gerekir).
    kosu = son 6 barın yönlü getirisi / ATR (6 bar + ATR>0 gerekir).
    """
    try:
        n = len(frame)
        if n < 7:
            return None, None
        yuksek = frame["high"].astype(float).to_numpy()
        dusuk = frame["low"].astype(float).to_numpy()
        kapanis = frame["close"].astype(float).to_numpy()
        index = n - 1
        sikisma: float | None = None
        if index >= 50:
            kisa = float(yuksek[index - 9: index + 1].max() - dusuk[index - 9: index + 1].min())
            uzun = float(yuksek[index - 49: index + 1].max() - dusuk[index - 49: index + 1].min())
            if uzun > 0 and math.isfinite(kisa) and math.isfinite(uzun):
                sikisma = round(kisa / uzun, 4)
        kosu: float | None = None
        # Replay `compute_wilder_atr` ilk ATR'yi ancak 14. barda (index 13)
        # üretir; aynı eşiği kullanmazsak erken barlarda canlı kosu üretip
        # replay None derdi. Parite için ikisi de 14 bar ister.
        if index >= 13:
            try:
                from domain_engines.stabil.signals import _causal_atr14
                atr = float(_causal_atr14(yuksek, dusuk, kapanis, period=14)[-1])
            except Exception:  # noqa: BLE001 - ATR yoksa kosu None kalır
                atr = float("nan")
            if math.isfinite(atr) and atr > 0:
                kosu = round(float(kapanis[index] - kapanis[index - 6]) / atr, 4)
        return sikisma, kosu
    except Exception:  # noqa: BLE001 - bağlam alarmı düşürmesin
        return None, None


def _kanallar_from_sebepler(sebepler: Sequence[str]) -> frozenset[str]:
    """Canlı sebep metinlerini replay `kanallar` kümesine çevirir."""
    kanallar: set[str] = set()
    for sebep in sebepler:
        s = str(sebep)
        if s.startswith("BOS"):
            kanallar.add("BOS")
        elif s.startswith("CHoCH"):
            kanallar.add("CHoCH")
        elif s.startswith("OB"):
            kanallar.add("OB")
        elif s.startswith("FVG"):
            kanallar.add("FVG")
        elif s.startswith("formasyon"):
            kanallar.add("FORMASYON")
        elif s.startswith("hacim"):
            kanallar.add("HACIM")
    return frozenset(kanallar)


def _politika_gecer(sebepler: Sequence[str], hacim_tier: str | None,
                    sikisma: float | None, kosu: float | None) -> bool:
    """Seçili politikaya göre aday geçer mi? (P0 her zaman geçer.)

    P6: kosu>=1.0 veya sikisma>=1.0 (sikisma None→1.0, kosu None→0.0).
    P4: P3 katmanı (yalnız OB/FVG/BOS/CHoCH sessiz; hacim/formasyon geçer)
        + bağlam; hacim ≥5× bağlamı baypas eder.
    """
    politika = str(getattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P0")).strip().upper()
    if politika == "P0":
        return True
    sik = 1.0 if sikisma is None else float(sikisma)
    kos = 0.0 if kosu is None else float(kosu)
    baglam_gecer = bool(kos >= 1.0 or sik >= 1.0)
    if politika == "P6":
        return baglam_gecer
    if politika == "P4":
        kanallar = _kanallar_from_sebepler(sebepler)
        if not kanallar:
            return False
        hacim_var = str(hacim_tier or "") in {"5×", "5x", "10×", "10x"}
        if hacim_var:
            return True
        if "FORMASYON" in kanallar:
            return baglam_gecer
        if kanallar <= _YALNIZ_ZAYIF_KANALLAR:
            return False
        return baglam_gecer
    return True


def evaluate_domain_alarm_candidates(
    stock: str,
    all_tfs: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    results: Mapping[str, Any],
    simdiki_zaman: datetime,
    *,
    formasyon_kayitlari: Sequence[Mapping[str, Any]] | None = None,
    bar_metni_fn: Any = None,
    grafik_baglami: Mapping[str, Mapping[str, Any]] | None = None,
    direnc_gunluk_ham: pd.DataFrame | None = None,
) -> list[DomainAlarmCandidate]:
    """Bir sembol için yeni kanal adaylarını üret; canlı state'e yazmaz."""
    if not bool(getattr(config, "YENI_DOMAIN_ALARM", True)):
        return []
    if (
        str(getattr(config, "sembol_turu", lambda _s: "")(stock)).lower() == "makro"
        and not bool(getattr(config, "MAKRO_ALARM", False))
    ):
        return []
    if not isinstance(results, Mapping) or not isinstance(frames, Mapping):
        return []

    taze_sinir = _cfg_int("YENI_DOMAIN_ALARM_TAZE_DK", 390)
    adaylar: list[DomainAlarmCandidate] = []
    # Yalnız bu sembol/tarama anı için: birden çok alarm adayı aynı grafiğin
    # direnç hesabını tekrar çalıştırmasın. Kill-switch kapalıyken boş kalır.
    direnc_cache: dict[str, Any] = {}

    for tf, frame in frames.items():
        tf = str(tf).lower()
        if tf not in results or not isinstance(frame, pd.DataFrame) or len(frame) < 30:
            continue
        per_tf = results.get(tf)
        if not isinstance(per_tf, Mapping):
            continue

        try:
            son_acilis = frame.index[-1]
            if not bar_kapandi_mi(son_acilis, tf, now=simdiki_zaman):
                continue
            kapanis = mum_kapanis_ani(son_acilis, tf)
            if kapanis is None:
                continue
            simdi_ts = pd.Timestamp(simdiki_zaman)
            kapanis_ts = pd.Timestamp(kapanis)
            if simdi_ts.tzinfo is None:
                simdi_ts = simdi_ts.tz_localize("Europe/Istanbul")
            if kapanis_ts.tzinfo is None:
                kapanis_ts = kapanis_ts.tz_localize("Europe/Istanbul")
            yas_dk = (simdi_ts - kapanis_ts).total_seconds() / 60.0
            if yas_dk < -1.0 or yas_dk > taze_sinir:
                continue
        except Exception as exc:  # noqa: BLE001 - bozuk TF diğerlerini engellemesin
            logger.debug("Yeni domain bar kontrolü atlandı %s/%s: %s", stock, tf, exc)
            continue

        stabil = _stabil_bilgisi(results, tf, frame, formasyon_kayitlari)
        if stabil is None:
            continue

        close = float(stabil["close_price"])
        sebepler: list[str] = []
        sebepler.extend(_bos_ve_choch_sebepleri(results, tf, len(frame)))
        sebepler.extend(_bolge_sebepleri(results, tf, close))
        sebepler.extend(_formasyon_sebepleri(formasyon_kayitlari, tf))

        hacim = _hacim_bilgisi(results, tf, frame)
        if hacim["sebep"]:
            sebepler.append(hacim["sebep"])
        sebepler = sorted(set(s for s in sebepler if s))
        if not sebepler:
            continue

        # Alarm politikası (P0/P6/P4): P0 her tetik; P6/P4 bağlam ister.
        # Filtre aday üretimini engeller; dedup/cooldown'a dokunmaz.
        _politika = str(getattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P0")).strip().upper()
        if _politika in ("P6", "P4"):
            _sikisma, _kosu = _baglam_sikisma_kosu(frame)
            if not _politika_gecer(sebepler, hacim["tier"], _sikisma, _kosu):
                logger.debug(
                    "Yeni domain aday politika %s ile elendi %s/%s (sikisma=%s kosu=%s sebepler=%s)",
                    _politika, stock, tf, _sikisma, _kosu, sebepler,
                )
                continue

        kalite = str(stabil["data_quality"] or "OK")
        if hacim["veri_suphe"]:
            kalite = "VERI_SUPHE"

        try:
            bar_label = (
                str(bar_metni_fn(tf, son_acilis, kapanis) or "")
                if callable(bar_metni_fn)
                else kapanis_ts.strftime("%d.%m %H:%M")
            )
        except Exception:  # noqa: BLE001 - etiket alarmı düşürmesin
            bar_label = kapanis_ts.strftime("%d.%m %H:%M")

        puan = float(len(sebepler))
        if hacim["tier"] == "10×":
            puan += 4.0
        elif hacim["tier"] == "5×":
            puan += 2.0
        if stabil["dist_atr"] < 0:
            puan += 1.5  # çöküş / risk tarafı
        if any("BOS" in s or "CHoCH" in s for s in sebepler):
            puan += 1.0

        grafik_verisi, grafik_verisi_public = _grafik_verisi_uret(
            stock, tf, frame, frames, results, simdiki_zaman,
            (grafik_baglami or {}).get(tf),
            direnc_gunluk_ham=direnc_gunluk_ham,
            direnc_saatlik_ham=all_tfs.get("1h") if isinstance(all_tfs, Mapping) else None,
            direnc_cache=direnc_cache,
        )

        adaylar.append(
            DomainAlarmCandidate(
                symbol=str(stock).upper(),
                timeframe=tf,
                bar_open=pd.Timestamp(son_acilis).isoformat(),
                bar_close=pd.Timestamp(kapanis).isoformat(),
                bar_label=bar_label,
                bar_index=int(len(frame) - 1),
                close_price=close,
                support_level=stabil["support_level"],
                dist_atr=float(stabil["dist_atr"]),
                relation=str(stabil["relation"]),
                reasons=tuple(sebepler),
                volume_rvol=hacim["rvol"],
                volume_tier=hacim["tier"],
                volume_source=str(hacim["source"]),
                data_quality=kalite,
                card_lines=tuple(stabil["card_lines"]),
                rank_score=puan,
                grafik_verisi=grafik_verisi,
                grafik_verisi_public=grafik_verisi_public,
                recent_bar_opens=tuple(
                    pd.Timestamp(ts).isoformat()
                    for ts in frame.index[-_cfg_int("YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6):]
                ),
            )
        )

    return adaylar


# --- Kalıcı dedup / cooldown -------------------------------------------------

def _state_yolu(state_path: str | None = None) -> str:
    return state_path or yeni_domain_alarm_state_yolu()


def _load_state(state_path: str | None = None) -> dict[str, Any]:
    yol = _state_yolu(state_path)
    try:
        if os.path.exists(yol):
            with open(yol, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("slots"), dict):
                return raw
    except Exception as exc:  # noqa: BLE001 - bozuk state taramayı durdurmasın
        logger.warning("Yeni domain alarm state okunamadı (%s): %s", yol, exc)
    return {"version": 1, "slots": {}}


def _save_state(state: Mapping[str, Any], state_path: str | None = None) -> None:
    """State'i **atomik** yaz (tmp + os.replace).

    Doğrudan yazmada süreç tam o anda SIGTERM/OOM ile ölürse dosya yarım kalır;
    bir sonraki açılışta JSON okunamaz, state sıfırlanır ve tüm cooldown
    slotları kaybolur — deploy sonrası art arda mükerrer alarm demek.
    ``bot/stabil_service.py::_save_alarm_state`` ile aynı desen.
    """
    yol = _state_yolu(state_path)
    try:
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        tmp = f"{yol}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(state), f, ensure_ascii=False, indent=2)
        os.replace(tmp, yol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Yeni domain alarm state yazılamadı (%s): %s", yol, exc)


def _ts_utc(value: Any) -> pd.Timestamp:
    """Naive zaman damgalarını Europe/Istanbul olarak kabul edip UTC'ye çevir."""
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("NaT")
    if ts.tzinfo is None:
        ts = ts.tz_localize("Europe/Istanbul")
    return ts.tz_convert("UTC")


def _zaten_gonderildi(slot: Mapping[str, Any] | None, cand: DomainAlarmCandidate) -> bool:
    """Aynı bar iki kez basılmasın; sembol/TF başına N bar sessizlik uygula.

    Slot anahtarı artık ``sembol|TF`` (bar değil), bu yüzden ``last_bar_index``
    her zaman bulunur ve ``YENI_DOMAIN_ALARM_COOLDOWN_BAR`` gerçekten çalışır.
    Eski (bar anahtarlı) state dosyaları yeni anahtarı içermez; deploy sonrası
    ilk alarm geçer, sonra cooldown devreye girer.
    """
    if not slot:
        return False
    if str(slot.get("last_bar_open") or "") == cand.bar_open:
        return True
    cooldown = _cfg_int("YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6)
    if cand.recent_bar_opens and slot.get("last_bar_open"):
        # Count actual distinct completed bars, not positions in a rolling
        # frame. If the available history is too short, fail closed instead of
        # guessing elapsed bars from wall-clock time or a shifted index.
        try:
            previous = _ts_utc(slot["last_bar_open"])
            current = _ts_utc(cand.bar_open)
            history = pd.DatetimeIndex([_ts_utc(v) for v in cand.recent_bar_opens])
            if len(history) == 0 or history[-1] != current:
                return True
            if current <= previous:
                return True
            if not history.is_monotonic_increasing or history.has_duplicates:
                return True
            return int(((history > previous) & (history <= current)).sum()) < cooldown
        except (TypeError, ValueError, OverflowError):
            return True
    # Compatibility for callers without bar history and older stored slots.
    try:
        son_index = int(slot["last_bar_index"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (cand.bar_index - son_index) < cooldown


def _isaretle(slots: dict[str, Any], cand: DomainAlarmCandidate) -> None:
    mevcut = slots.get(cand.dedup_key)
    if mevcut and mevcut.get("last_bar_open") and cand.bar_open:
        try:
            if _ts_utc(cand.bar_open) < _ts_utc(mevcut["last_bar_open"]):
                return
        except (TypeError, ValueError, OverflowError):
            pass
    slots[cand.dedup_key] = {
        "last_bar_open": cand.bar_open,
        "last_bar_close": cand.bar_close,
        "last_bar_index": cand.bar_index,
        "reason_signature": cand.reason_signature,
        "volume_tier": cand.volume_tier,
        "data_quality": cand.data_quality,
    }


# --- Kart metinleri ----------------------------------------------------------

def _yon_isareti(cand: DomainAlarmCandidate) -> str:
    """Eski kartın ▲/▼/◆ dili: yön yalnız gerçek tetikleyiciden okunur."""
    metin = " ".join(cand.reasons)
    if "↑" in metin:
        return "▲"
    if "↓" in metin:
        return "▼"
    return "◆"


def _kart_bloklarini_sigdir(bloklar: list[list[str]]) -> list[list[str]]:
    """Eski kartın 22 satır tavanı: çekirdek blok ve yasal satır korunur."""
    icerik = sum(len(b) for b in bloklar)
    while icerik > _KART_MAKS_SATIR and len(bloklar) > 2:
        hedef = bloklar[-2]
        if len(hedef) <= 1:
            icerik -= len(hedef)
            bloklar.pop(-2)
        else:
            hedef.pop()
            icerik -= 1
    return bloklar


def format_domain_alarm_card(cand: DomainAlarmCandidate) -> str:
    """Eski sade kartla aynı blok dili; yalnız yeni kanal için gerekli bilgi."""
    tf_label = _tf_etiket(cand.timeframe)
    bloklar: list[list[str]] = []

    # BLOK 1 · OLAY: kimlik, tetikleyici, mum, kapanış.
    blok: list[str] = []
    _satir(blok, f"{YENI_KART_ISARETI} {_yon_isareti(cand)} "
                 f"{cand.symbol.upper()} {tf_label} TETİKLEME")
    if cand.reasons:
        _satir(blok, "· " + " · ".join(cand.reasons[:2]))
        if len(cand.reasons) > 2:
            _satir(blok, f"· +{len(cand.reasons) - 2} tetikleyici daha")
    else:
        _satir(blok, "· domain tetikleyici")
    damga = _kart_mum_damgasi(
        {"bar_time": cand.bar_open, "bar_kapanis": cand.bar_close}
    )
    if damga:
        _mum_damgasi_ekle(blok, damga)
    else:
        _satir(blok, f"🕒 {cand.bar_label} mumu")
    _satir(blok, f"· kapanış {_tr_sayi(cand.close_price)}")
    bloklar.append(blok)

    # BLOK 3 · YAPI: native basamaklı destek + ilişki/ATR.
    blok = []
    for satir in cand.card_lines[:2]:
        _satir(blok, str(satir))
    _satir(blok, f"· {cand.relation} · {_tr_sayi(cand.dist_atr, 2)} ATR")
    bloklar.append(blok)

    # BLOK 5 · KATILIM: grafiğin RVOL bilgisi; eşik sebebi üstte zaten var.
    if cand.volume_tier and cand.volume_rvol is not None:
        blok = []
        _satir(blok, f"hacim: RVOL {_tr_sayi(cand.volume_rvol, 1)}× "
                     f"· {cand.volume_source}")
        bloklar.append(blok)

    # BLOK 6 · SINIR: yalnız veri kalitesi uyarısı; uydurma koşul satırı yok.
    if cand.data_quality == "VERI_SUPHE":
        blok = []
        _satir(blok, "⚠ hacim uç değeri: veri kalitesi kontrolü gerekli")
        bloklar.append(blok)
    elif cand.data_quality not in {"OK", ""}:
        blok = []
        _satir(blok, f"⚠ veri kalitesi: {cand.data_quality}")
        bloklar.append(blok)

    # BLOK 7 · CTA: eski kartla birebir aynı yasal satır.
    bloklar.append(["• yatırım tavsiyesi değildir"])
    bloklar = _kart_bloklarini_sigdir(bloklar)
    return "\n\n".join("\n".join(b) for b in bloklar if b)


def format_domain_alarm_summary_card(cands: Sequence[DomainAlarmCandidate]) -> str:
    """Burst özeti de eski toplu kartın sade blok dilini kullanır."""
    adet = len(cands)
    bloklar: list[list[str]] = []
    blok: list[str] = []
    _satir(blok, f"{YENI_KART_ISARETI} · DOMAİN TOPLU ÖZET (+{adet})")
    ilk = cands[0] if cands else None
    if ilk is not None:
        damga = _kart_mum_damgasi(
            {"bar_time": ilk.bar_open, "bar_kapanis": ilk.bar_close}
        )
        if damga:
            _mum_damgasi_ekle(blok, damga)
        else:
            _satir(blok, f"🕒 {ilk.bar_label} mumu")
    _satir(blok, "Aynı taramada destek alt sınırını geçen diğer adaylar:")
    bloklar.append(blok)

    def aday_satirlari(ayrintili: bool) -> list[str]:
        satirlar: list[str] = []
        for c in cands[:10]:
            if ayrintili:
                metin = (f"• {c.symbol} {_tf_etiket(c.timeframe)}: {c.relation} "
                         f"({_tr_sayi(c.dist_atr, 1)} ATR) · {' · '.join(c.reasons[:2])}")
            else:
                # Önce kimlikleri koru: uzun sebepler satır sınırında kesilip
                # bazı semboller görünmeden gönderildi diye işaretlenmemeli.
                metin = f"• {c.symbol} {_tf_etiket(c.timeframe)} · {_tr_sayi(c.dist_atr, 1)} ATR"
            _satir(satirlar, metin)
        if adet > 10:
            _satir(satirlar, f"• … ve {adet - 10} aday daha")
        _satir(satirlar, "› /stabil")
        return satirlar

    bloklar.append(aday_satirlari(True))
    bloklar.append(["• yatırım tavsiyesi değildir"])
    if sum(len(b) for b in bloklar) > _KART_MAKS_SATIR:
        bloklar[-2] = aday_satirlari(False)
    # Dispatch en fazla 5 adayı sayfaladığı için isimler burada kırpılmaz.
    return "\n\n".join("\n".join(b) for b in bloklar if b)


def _deliver_message(notifier: Any, text: str, *, public_event_id=None,
                     public_identity=None, public_graphics=None, dm_graphics=None,
                     dm_text: str | None = None, public_text: str | None = None) -> dict[str, bool]:
    """DM ve public için bağımsız teslim/kuyruk durumunu takip et."""
    dm_on = bool(getattr(config, "YENI_DOMAIN_ALARM_DM", True))
    pub_on = bool(getattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True))
    dm_body = dm_text if dm_text else text
    pub_body = public_text if public_text else text
    dm_ok = dm_accepted = pub_ok = pub_accepted = False
    dm_managed = public_managed = False
    dm_required = dm_on and notifier is not None and getattr(notifier, "enabled", True) is not False
    pub_required = pub_on and notifier is not None and getattr(notifier, "public_enabled", True) is not False

    if dm_required:
        send_text = getattr(notifier, "send_text", None)
        queue_dm = getattr(notifier, "dm_ozel_gonder", None)
        if public_event_id and callable(queue_dm):
            dm_managed = True
            try:
                dm_accepted, dm_ok = queue_dm(
                    public_event_id, dm_body, identity=public_identity, graphics=dm_graphics)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Yeni domain DM kuyruğu başarısız: %s", type(exc).__name__)
        elif callable(send_text):
            try:
                res = send_text(dm_body)
                dm_ok = bool(res[0] if isinstance(res, tuple) else res)
                dm_accepted = dm_ok
            except Exception as exc:  # noqa: BLE001
                logger.warning("Yeni domain DM gönderim hatası: %s", type(exc).__name__)

    if pub_on and notifier is not None:
        public_acik = getattr(notifier, "public_enabled", None)
        send_pub = getattr(notifier, "send_to_public", None)
        queue_pub = getattr(notifier, "public_ozel_gonder", None)
        if public_acik is not False and public_event_id and callable(queue_pub):
            public_managed = True
            try:
                pub_accepted, pub_ok = queue_pub(
                    public_event_id, pub_body, identity=public_identity, graphics=public_graphics)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Yeni domain public kuyruğu başarısız: %s", type(exc).__name__)
        elif public_acik is not False and callable(send_pub):
            try:
                pub_ok = bool(send_pub(pub_body))
                pub_accepted = pub_ok
            except Exception as exc:  # noqa: BLE001
                logger.warning("Yeni domain public gönderim hatası: %s", type(exc).__name__)
        if dm_ok and public_acik is False:
            logger.warning("Yeni domain DM gitti, public hedef kapalı; kanal kopyası gönderilmedi")
        elif dm_ok and not (pub_ok or pub_accepted):
            logger.warning("Yeni domain DM gitti ancak public kopyası saklanamadı/gönderilmedi")

    recorded = ((not dm_required or dm_ok or dm_accepted)
                and (not pub_required or pub_ok or pub_accepted)
                and (dm_ok or dm_accepted or pub_ok or pub_accepted))
    return {"dm": bool(dm_ok), "public": bool(pub_ok), "any": bool(dm_ok or pub_ok),
            "recorded": bool(recorded), "dm_managed": dm_managed, "public_managed": public_managed}


def _deliver_charts(notifier: Any, cand: DomainAlarmCandidate,
                    sonuc: Mapping[str, bool]) -> None:
    """Metnin ardından ESKİ grafik teslim yollarıyla aynı kareleri gönder."""
    if notifier is None:
        return
    kimlik = {
        "stock_name": cand.symbol,
        "timeframe": cand.timeframe,
        "state": "YENI_DOMAIN",
        "pattern_name": "DOMAİN TETİKLEME",
    }
    if sonuc.get("dm") and not sonuc.get("dm_managed") and cand.grafik_verisi:
        ekle = getattr(notifier, "grafik_kuyruga_ekle", None)
        if callable(ekle):
            try:
                ekle({**kimlik, "grafik_verisi": cand.grafik_verisi}, gonder=True)
            except Exception as exc:  # noqa: BLE001 - görsel metni düşürmesin
                logger.warning("Yeni domain DM grafiği kuyruğa alınamadı: %s", exc)
    if sonuc.get("public") and not sonuc.get("public_managed") and cand.grafik_verisi_public:
        bagla = getattr(notifier, "public_grafik_bagla", None)
        if callable(bagla):
            try:
                bagla(kimlik, cand.grafik_verisi_public)
            except Exception as exc:  # noqa: BLE001 - görsel metni düşürmesin
                logger.warning("Yeni domain public grafiği gönderilemedi: %s", exc)


def dispatch_domain_alarm_candidates(
    candidates: Sequence[DomainAlarmCandidate],
    notifier: Any,
    *,
    state_path: str | None = None,
    frames_by_symbol: Mapping[str, Any] | None = None,
    router: Any = None,
) -> dict[str, int]:
    """Adayları tekilleştir, burst kuralıyla gönder, state'e işaretle."""
    ozet = {"aday": len(candidates), "tekil_gonderilen": 0,
            "toplu_ozet": 0, "filtrelendi": 0}
    if not candidates or not bool(getattr(config, "YENI_DOMAIN_ALARM", True)):
        return ozet

    # Aynı sembol/TF/bar için en yüksek puanlı tek aday.
    # Gruplama `bar_key` ile yapılır (dedup_key artık sembol|TF; aynı TF'nin
    # iki farklı barı burada birleşmemeli). State slotu ise `dedup_key` ile
    # yazılır, böylece cooldown sembol/TF düzeyinde tutulur.
    en_iyi: dict[str, DomainAlarmCandidate] = {}
    for cand in candidates:
        onceki = en_iyi.get(cand.bar_key)
        if onceki is None or cand.rank_score > onceki.rank_score:
            en_iyi[cand.bar_key] = cand
    sirali = sorted(en_iyi.values(), key=lambda c: (-c.rank_score, c.symbol, c.timeframe))

    state = _load_state(state_path)
    slots = state.setdefault("slots", {})
    degisti = False
    # Burst sınırı tekrarlı adaylar çıkarıldıktan sonra uygulanmalı. Aksi halde
    # önceki turda gönderilmiş iki yüksek puanlı aday, yeni iki olayı tekil kart
    # ve görsel yerine gereksizce toplu özete itiyordu. Aynı batch içinde aynı
    # sembol/TF'nin cooldown içindeki ikinci barı da elenir.
    gecici_slots: dict[str, Any] = dict(slots)
    yeni_adaylar: list[DomainAlarmCandidate] = []
    for cand in sirali:
        if _zaten_gonderildi(gecici_slots.get(cand.dedup_key), cand):
            continue
        yeni_adaylar.append(cand)
        _isaretle(gecici_slots, cand)
    ozet["filtrelendi"] += len(sirali) - len(yeni_adaylar)

    ust_sinir = _cfg_int("YENI_DOMAIN_ALARM_TEKIL_UST_SINIR", 3)
    if len(yeni_adaylar) <= ust_sinir:
        tekil_liste = list(yeni_adaylar)
        toplu_liste: list[DomainAlarmCandidate] = []
    else:
        tekil_liste = list(yeni_adaylar[:2])
        toplu_liste = list(yeni_adaylar[2:])

    from public_aux_outbox import auxiliary_event_id

    dm_ai_hedef = bool(
        getattr(config, "YENI_DOMAIN_ALARM_DM", True)
        and getattr(notifier, "enabled", False)
        and config.ai_yorum_dm_enabled()
    )
    pub_ai_hedef = bool(
        getattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
        and getattr(notifier, "public_enabled", False)
        and config.ai_yorum_public_enabled()
    )
    gonderilen: list[DomainAlarmCandidate] = []
    for cand in tekil_liste:
        identity = {"stock_name": cand.symbol, "timeframe": cand.timeframe,
                    "state": "YENI_DOMAIN", "pattern_name": "DOMAİN TETİKLEME"}
        duz_metin = format_domain_alarm_card(cand)
        dm_metin = duz_metin
        pub_metin = duz_metin
        if (dm_ai_hedef or pub_ai_hedef) and frames_by_symbol and cand.symbol in frames_by_symbol:
            try:
                from ai_prompt.service import build_ai_replacement_text_for_signal

                df_1h, df_1d, as_of_dt = frames_by_symbol[cand.symbol]
                ai_text = build_ai_replacement_text_for_signal(
                    symbol=cand.symbol,
                    timeframe=cand.timeframe,
                    pattern_name="Teknik Tetikleme",
                    state="YENI_DOMAIN",
                    close_price=cand.close_price,
                    bar_metni=cand.bar_label,
                    df_1h=df_1h,
                    df_1d=df_1d,
                    as_of=as_of_dt,
                    router=router,
                )
                if ai_text:
                    if config.ai_yorum_dm_enabled():
                        dm_metin = ai_text
                    if config.ai_yorum_public_enabled():
                        pub_metin = ai_text
            except Exception as ai_err:  # noqa: BLE001 - AI hatasında düz kart gider
                logger.warning("Yeni domain AI yorumu atlandı (%s %s): %s",
                               cand.symbol, cand.timeframe, type(ai_err).__name__)
        sonuc = _deliver_message(
            notifier, duz_metin,
            dm_text=dm_metin,
            public_text=pub_metin,
            public_event_id=auxiliary_event_id("domain", [(cand.symbol, cand.timeframe, cand.bar_open)]),
            public_identity=identity, public_graphics=cand.grafik_verisi_public,
            dm_graphics=cand.grafik_verisi,
        )
        if sonuc["any"]:
            _deliver_charts(notifier, cand, sonuc)
            ozet["tekil_gonderilen"] += 1
        if sonuc["recorded"]:
            # Public bütçe nedeniyle bekliyorsa da ayrı, kalıcı kuyruk vardır.
            gonderilen.append(cand)

    # Bir kartın satır tavanına sığmayan adaylar sessizce kaybolmasın;
    # her sayfa yalnız içinde listelenen semboller için teslim mührü alır.
    for baslangic in range(0, len(toplu_liste), 5):
        sayfa = toplu_liste[baslangic:baslangic + 5]
        sonuc = _deliver_message(
            notifier, format_domain_alarm_summary_card(sayfa),
            public_event_id=auxiliary_event_id(
                "domain-summary", [(c.symbol, c.timeframe, c.bar_open) for c in sayfa]),
        )
        if sonuc["any"]:
            ozet["toplu_ozet"] += 1
        if sonuc["recorded"]:
            gonderilen.extend(sayfa)

    for cand in gonderilen:
        _isaretle(slots, cand)
        degisti = True
    if degisti:
        _save_state(state, state_path)
    return ozet


__all__ = [
    "DomainAlarmCandidate",
    "YENI_KART_ISARETI",
    "dispatch_domain_alarm_candidates",
    "evaluate_domain_alarm_candidates",
    "format_domain_alarm_card",
    "format_domain_alarm_summary_card",
]
