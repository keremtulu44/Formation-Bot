"""Causal behavioral classification, strong reclaim systematic, and card/command copy for Stabil.

All rules in this module are strictly causal, read-only interpretations of the
unmodified `05_stabil.txt` support/trend outputs plus closed bar OHLCV:
- Strong reclaim systematic (`close_reclaim` + `intrabar_sweep_reclaim`) validated
  causally across the live `config.BIST_50` symbol universe and 100-stock archive.
- Separate strong upward-momentum classification for chart arrows; it stays
  independent from reclaim alerts and does not require a fixed horizontal support.
- Fixed 2-line Telegram card copy (`Stabil destek: ...`, `Stabil yapı: ...`)
  kept safely within `config.TELEGRAM_SATIR_PX` (283 px).
- Curated live bucket classifier for `/stabil` and `/stabil <SEMBOL>`.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .candidate_regime import (
    CandidateLineRegime,
    CandidateRegimePoint,
    classify_candidate_support_regimes,
)
from .stabil_support_lifecycle import (
    StabilSupportLifecycleSnapshot,
    SupportProgression,
    SupportValidity,
)
from .stabil_trend_engine import StabilTrendConfig


#: Grafikte `▲` ile gösterilen, geri alımdan AYRI güçlü yukarı momentum türleri.
#: Eşikler `/stabil` komutundaki replay-grounded "güçlü çıkış" kuralıyla aynıdır;
#: native 05_stabil.txt pivot/destek matematiği değiştirilmez.
STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI = frozenset({
    "long_base_breakout",        # Oturmuş yatay zeminden güçlü gövdeyle kopuş
    "upward_rebase_momentum",    # Destek yukarı basamak yaparken gelen güçlü mum
})

_GUCLU_YUKARI_GOVDE_ATR = 0.35
_GUCLU_YUKARI_KAPANIS_POZ = 0.65
_GUCLU_YUKARI_HACIM_ORAN = 1.10
_GUCLU_YUKARI_COK_GUCLU_GOVDE_ATR = 0.50
_GUCLU_YUKARI_COOLDOWN_BAR = 3


def _enum_value(value: Any) -> str:
    """StrEnum / düz metin / eski kayıtlar için tek karşılaştırma biçimi."""
    raw = getattr(value, "value", getattr(value, "name", value))
    return str(raw or "").upper()


def _tr_sayi(deger: float | None, ondalik: int = 2) -> str:
    if deger is None or not math.isfinite(float(deger)):
        return "—"
    v = float(deger)
    if abs(v) >= 1000 and ondalik == 2:
        ondalik = 1
    kalip = f"{v:,.{ondalik}f}"
    return kalip.replace(",", "_").replace(".", ",").replace("_", ".")


def _is_index_symbol(symbol: str) -> bool:
    clean = str(symbol or "").strip().upper().replace(".IS", "")
    if clean in {"XU100", "XU30", "XU50", "XBANK", "XUSIN"}:
        return True
    try:
        import config

        return config.sembol_turu(clean) == "endeks"
    except Exception:
        return False


def _causal_atr14(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Strictly causal Wilder/RMA 14-bar ATR over target timeframe bars."""
    n = len(closes)
    out = np.full(n, np.nan, dtype=float)
    if n == 0:
        return out
    tr = np.empty(n, dtype=float)
    tr[0] = max(0.0, float(highs[0] - lows[0]))
    for i in range(1, n):
        hl = float(highs[i] - lows[i])
        hc = abs(float(highs[i] - closes[i - 1]))
        lc = abs(float(lows[i] - closes[i - 1]))
        tr[i] = max(hl, hc, lc)
    if n < period:
        acc = 0.0
        for i in range(n):
            acc += tr[i]
            out[i] = acc / float(i + 1)
        return out
    seed = float(np.mean(tr[:period]))
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = ((prev * (period - 1)) + tr[i]) / float(period)
        out[i] = prev
    for i in range(period - 1):
        out[i] = float(np.mean(tr[: i + 1]))
    return out


def _causal_vol_ratio20(volumes: np.ndarray, window: int = 20) -> np.ndarray:
    """Strictly causal volume / prior-20-bar mean volume ratio."""
    n = len(volumes)
    out = np.full(n, np.nan, dtype=float)
    for i in range(n):
        v = float(volumes[i]) if math.isfinite(float(volumes[i])) else 0.0
        if v <= 0.0 or i < 5:
            continue
        start = max(0, i - window)
        hist = volumes[start:i]
        pos = hist[hist > 0.0]
        if len(pos) < 5:
            continue
        avg = float(np.mean(pos))
        if avg > 0.0:
            out[i] = v / avg
    return out


@dataclass(frozen=True, slots=True)
class StabilBarBehavior:
    bar_index: int
    bar_close_time: Any
    support_level: float | None
    close_price: float | None
    pct_vs_support: float | None
    dist_atr: float | None
    low_dist_atr: float | None
    body_atr: float | None
    close_pos: float | None
    vol_ratio: float | None
    fixed_support: bool
    regime: str  # CandidateLineRegime value
    unchanged_days: int
    touch_count: int
    prev_breach_bars: int
    prev_breach_depth_atr: float
    reclaim_kind: str | None  # "close_reclaim" | "intrabar_sweep_reclaim" | None
    weak_reclaim: bool
    rank_score: float
    # Geri alımdan bağımsız, grafikte ayrı `▲` ile gösterilen güçlü yukarı mum.
    # Varsayılan değer eski kayıtlar / sentetik kart davranışlarıyla uyumludur.
    momentum_kind: str | None = None
    # Dikey rejim bir gözlenen/proxy yapı uyarısıdır; satış emri veya yön garantisi değildir.
    vertical_support: bool = False
    vertical_attempt_kind: str | None = None


def evaluate_bar_behaviors(
    symbol: str,
    timeframe: str,
    target_clean: pd.DataFrame,
    bar_projection: Sequence[Any],
    support_timeline: Sequence[StabilSupportLifecycleSnapshot],
    *,
    min_tick: float = 0.01,
) -> tuple[StabilBarBehavior, ...]:
    """Compute causal per-bar Stabil behavioral descriptors & strong reclaim signals."""
    n = min(len(target_clean), len(bar_projection))
    if n == 0:
        return ()

    opens = target_clean["open"].to_numpy(dtype=float)[:n]
    highs = target_clean["high"].to_numpy(dtype=float)[:n]
    lows = target_clean["low"].to_numpy(dtype=float)[:n]
    closes = target_clean["close"].to_numpy(dtype=float)[:n]
    volumes = target_clean["volume"].to_numpy(dtype=float)[:n]

    atr_arr = _causal_atr14(highs, lows, closes, period=14)
    vol_ratio_arr = _causal_vol_ratio20(volumes, window=20)
    is_index = _is_index_symbol(symbol)
    tol = max(float(min_tick) * 0.5, 1e-6)

    # Map daily_as_of -> CandidateRegimePoint causally
    regime_points: tuple[CandidateRegimePoint, ...] = (
        classify_candidate_support_regimes(support_timeline)
        if support_timeline
        else ()
    )
    daily_times = [snap.as_of for snap in support_timeline]
    vertical_up_max_age = 2 * StabilTrendConfig().daily_pivot_len

    def _regime_at(daily_as_of: Any) -> tuple[str, int, bool]:
        if not regime_points or daily_as_of is None:
            return CandidateLineRegime.UNAVAILABLE.value, 0, False
        try:
            idx = bisect_right(daily_times, daily_as_of) - 1
        except TypeError:
            idx = -1
        if idx < 0 or idx >= len(regime_points):
            return CandidateLineRegime.UNAVAILABLE.value, 0, False
        rp = regime_points[idx]
        age = int(rp.bars_since_support or 0)
        # BREACHED_FIXED_SUPPORT, yükselen kademe üzerinde fiyat aşağı
        # kapandığında STEPPING_UP etiketinin önüne geçer. Bu etiket önceliği
        # yakın dönemdeki dikey proxy'yi / uyarıyı kaybettirmemeli.
        recently_rebased_up = (
            rp.progression is SupportProgression.REBASED_HIGHER
            and rp.bars_since_support is not None
            and age <= vertical_up_max_age
        )
        return rp.regime.value, age, recently_rebased_up

    out: list[StabilBarBehavior] = []
    touch_count = 0
    last_touch_bar = -999
    separated_since_touch = True
    breach_bars = 0
    max_breach_depth_atr = 0.0
    prev_sup: float | None = None
    prev_close: float | None = None
    last_momentum_bar = -999

    for i in range(n):
        pt = bar_projection[i]
        sup = pt.support_level
        c = float(closes[i])
        o = float(opens[i])
        h = float(highs[i])
        lo = float(lows[i])
        atr = float(atr_arr[i]) if math.isfinite(float(atr_arr[i])) and atr_arr[i] > 0 else np.nan
        vr = float(vol_ratio_arr[i]) if math.isfinite(float(vol_ratio_arr[i])) else None

        rng = max(h - lo, 0.0)
        close_pos = ((c - lo) / rng) if rng > 1e-9 else 0.5
        body_atr = ((c - o) / atr) if math.isfinite(atr) and atr > 0 else None

        if sup is None or not math.isfinite(float(sup)) or float(sup) <= 0:
            out.append(
                StabilBarBehavior(
                    bar_index=i,
                    bar_close_time=pt.bar_close_time,
                    support_level=None,
                    close_price=c,
                    pct_vs_support=None,
                    dist_atr=None,
                    low_dist_atr=None,
                    body_atr=body_atr,
                    close_pos=close_pos,
                    vol_ratio=vr,
                    fixed_support=False,
                    regime=CandidateLineRegime.UNAVAILABLE.value,
                    unchanged_days=0,
                    touch_count=0,
                    prev_breach_bars=0,
                    prev_breach_depth_atr=0.0,
                    reclaim_kind=None,
                    weak_reclaim=False,
                    rank_score=0.0,
                    momentum_kind=None,
                )
            )
            prev_sup = None
            prev_close = c
            touch_count = 0
            breach_bars = 0
            max_breach_depth_atr = 0.0
            last_momentum_bar = -999
            continue

        sup_f = float(sup)
        fixed_support = prev_sup is not None and abs(sup_f - prev_sup) <= max(tol, 1e-6 * max(1.0, sup_f))
        if not fixed_support:
            touch_count = 0
            last_touch_bar = -999
            separated_since_touch = True
            breach_bars = 0
            max_breach_depth_atr = 0.0

        pct_vs = ((c - sup_f) / sup_f) * 100.0
        dist_atr = ((c - sup_f) / atr) if math.isfinite(atr) and atr > 0 else None
        low_dist_atr = ((lo - sup_f) / atr) if math.isfinite(atr) and atr > 0 else None
        regime_val, unchanged_days, recently_rebased_up = _regime_at(pt.daily_as_of)
        # Stepline'ın aynı mumdaki gerçek seviye değişimini ve nedensel aday
        # kademe rejimlerini birlikte koru. Görsel "dikey" ile bu proxy'nin
        # birebir örtüştüğü iddiası yok; kullanıcı politikası fail-closed'dur.
        vertical_support = (
            regime_val in {CandidateLineRegime.STEPPING_UP.value, CandidateLineRegime.STEPPING_DOWN.value}
            or recently_rebased_up
            or (prev_sup is not None and not fixed_support)
        )

        # Independent support touch tracking while above/near same horizontal line
        if dist_atr is not None and low_dist_atr is not None:
            if dist_atr >= 0.55:
                separated_since_touch = True
            near_touch = (-0.15 <= dist_atr <= 0.45) and (low_dist_atr <= 0.25)
            if near_touch and separated_since_touch and (i - last_touch_bar >= 4):
                touch_count += 1
                last_touch_bar = i
                separated_since_touch = False

        # Snapshot prior breach stats before updating with current bar
        prior_breach_bars = breach_bars
        prior_breach_depth = max_breach_depth_atr

        reclaim_kind: str | None = None
        weak_reclaim = False
        momentum_kind: str | None = None

        if (
            fixed_support
            and prev_sup is not None
            and prev_close is not None
            and dist_atr is not None
            and low_dist_atr is not None
            and body_atr is not None
        ):
            was_below = prev_close < (prev_sup - tol)
            now_above = c > (sup_f + tol)
            was_above = prev_close >= (prev_sup - tol)

            vol_ok_close = (
                (vr is not None and vr >= 1.0)
                or body_atr >= 0.45
                or (is_index and body_atr >= 0.38)
            )
            vol_ok_sweep = (
                (vr is not None and vr >= 1.0)
                or body_atr >= 0.50
                or (is_index and body_atr >= 0.40)
            )

            if was_below and now_above:
                if (
                    0.0 < prior_breach_depth <= 1.50
                    and body_atr >= 0.32
                    and close_pos >= 0.65
                    and dist_atr >= 0.05
                    and vol_ok_close
                ):
                    reclaim_kind = "close_reclaim"
                else:
                    weak_reclaim = True
            elif (
                was_above
                and now_above
                and (-1.20 <= low_dist_atr <= -0.08)
                and dist_atr >= 0.08
                and body_atr >= 0.35
                and close_pos >= 0.68
                and vol_ok_sweep
            ):
                reclaim_kind = "intrabar_sweep_reclaim"

        # Güçlü YUKARI mum ayrı bir olaydır: destek altına hiç sarkmadan da
        # gelebilir ve çizgi yukarı basamak yaptığı barda `fixed_support=False`
        # olur. Bu yüzden geri alımın `fixed_support` kapısına BAĞLI DEĞİLDİR.
        # Eşikler `/stabil` "güçlü çıkış" kuralıyla aynı; yalnızca kapalı mum,
        # geçmiş ATR/hacim ve o ana kadar bilinen native destek kullanılır.
        if (
            reclaim_kind is None
            and not weak_reclaim
            and pct_vs > 0.0
            and dist_atr is not None
            and body_atr is not None
            and body_atr >= _GUCLU_YUKARI_GOVDE_ATR
            and close_pos >= _GUCLU_YUKARI_KAPANIS_POZ
            and touch_count < 3
            and ((vr is not None and vr >= _GUCLU_YUKARI_HACIM_ORAN)
                 or body_atr >= _GUCLU_YUKARI_COK_GUCLU_GOVDE_ATR)
            and _enum_value(getattr(pt, "validity", None)) == SupportValidity.ACTIVE.value
            and (i - last_momentum_bar) >= _GUCLU_YUKARI_COOLDOWN_BAR
        ):
            long_base = unchanged_days >= 20 and 0.15 <= dist_atr <= 1.80
            step_up = (
                regime_val == CandidateLineRegime.STEPPING_UP.value
                or _enum_value(getattr(pt, "progression", None)) == SupportProgression.REBASED_HIGHER.value
            )
            stepping = step_up and 0.10 <= dist_atr <= 1.60
            if long_base or stepping:
                momentum_kind = (
                    "long_base_breakout" if long_base else "upward_rebase_momentum"
                )

        vertical_attempt_kind = None
        if vertical_support:
            # Dikey/kademeli destek üzerinde yukarı deneme, geri alım veya
            # momentum olsa bile ▲ üretme. İşaret ve alarm aynı kaynaktan
            # beslendiği için güçlü geri alım alarmına da dönüşmez.
            vertical_attempt_kind = reclaim_kind or ("weak_reclaim" if weak_reclaim else None) or momentum_kind
            if vertical_attempt_kind is None and prev_close is not None and prev_sup is not None:
                if prev_close < prev_sup - tol and h >= sup_f - tol:
                    vertical_attempt_kind = "touch_from_below"
            reclaim_kind = None
            momentum_kind = None
            weak_reclaim = False
        elif momentum_kind is not None:
            last_momentum_bar = i

        # Update breach state after evaluating current bar
        if c < (sup_f - tol):
            breach_bars += 1
            if dist_atr is not None:
                max_breach_depth_atr = max(max_breach_depth_atr, max(0.0, -dist_atr))
        else:
            breach_bars = 0
            max_breach_depth_atr = 0.0

        rank_score = 0.0
        if reclaim_kind is not None and body_atr is not None:
            vol_bonus = min(0.8, max(0.0, (vr - 1.0) * 0.4)) if vr is not None else 0.15
            base_bonus = 0.35 if unchanged_days >= 20 else (0.15 if unchanged_days >= 8 else 0.0)
            exhaustion_pen = -0.25 if touch_count >= 3 else (0.15 if touch_count == 2 else 0.0)
            rank_score = round(
                float(body_atr) * 1.4
                + float(close_pos) * 0.8
                + vol_bonus
                + base_bonus
                + exhaustion_pen,
                4,
            )

        out.append(
            StabilBarBehavior(
                bar_index=i,
                bar_close_time=pt.bar_close_time,
                support_level=sup_f,
                close_price=c,
                pct_vs_support=pct_vs,
                dist_atr=dist_atr,
                low_dist_atr=low_dist_atr,
                body_atr=body_atr,
                close_pos=close_pos,
                vol_ratio=vr,
                fixed_support=fixed_support,
                regime=regime_val,
                unchanged_days=unchanged_days,
                touch_count=touch_count,
                prev_breach_bars=prior_breach_bars,
                prev_breach_depth_atr=prior_breach_depth,
                reclaim_kind=reclaim_kind,
                weak_reclaim=weak_reclaim,
                rank_score=rank_score,
                momentum_kind=momentum_kind,
                vertical_support=vertical_support,
                vertical_attempt_kind=vertical_attempt_kind,
            )
        )
        prev_sup = sup_f
        prev_close = c

    return tuple(out)


def _pick_fitting_line(candidates: Sequence[str], fallback: str) -> str:
    try:
        import config
        from telegram_measure import genislik

        budget = float(getattr(config, "TELEGRAM_SATIR_PX", 283))
        for cand in candidates:
            if genislik(cand) <= budget:
                return cand
    except Exception:
        if candidates:
            return candidates[0]
    return fallback


def describe_behavior_structure_short(bhv: StabilBarBehavior | None) -> str:
    """Short plain-Turkish phrase for `Stabil yapı: <phrase>` (fits <= 283px)."""
    if bhv is None or bhv.support_level is None:
        return "destek henüz oluşmadı"

    if getattr(bhv, "vertical_attempt_kind", None):
        return "dikey destek · yukarı deneme"
    if bhv.reclaim_kind == "close_reclaim":
        if bhv.vol_ratio is not None and bhv.vol_ratio >= 1.15:
            return "hacimli güçlü geri alım"
        return "güçlü geri alım"
    if bhv.reclaim_kind == "intrabar_sweep_reclaim":
        return "silkeleme sonrası dönüş"
    if bhv.weak_reclaim:
        return "cılız geri alım (zayıf)"

    pct = bhv.pct_vs_support or 0.0
    dist_atr = bhv.dist_atr

    # Price below support
    if pct < -0.02:
        if bhv.regime == CandidateLineRegime.STEPPING_DOWN.value:
            return "destek kademe iniyor"
        if dist_atr is not None and dist_atr < -1.20:
            return "derin kırılım, baskı var"
        return "sığ sarkma (izlemede)"

    # Price at/above support
    if bhv.touch_count >= 3:
        return "çok test edildi, yorgun"
    if bhv.regime == CandidateLineRegime.LONG_HORIZONTAL.value:
        if bhv.touch_count == 2:
            return "uzun yatay · 2. test"
        return "uzun yatay zemin"
    if bhv.regime == CandidateLineRegime.STEPPING_UP.value:
        return "yükselen kademe"
    if bhv.regime == CandidateLineRegime.HORIZONTAL_AFTER_DROP.value:
        return "düşüş sonrası yatay"
    if bhv.regime == CandidateLineRegime.STEPPING_DOWN.value:
        return "inen çizgi üstü (zayıf)"
    if bhv.touch_count == 2:
        return "yatay destek (2. test)"
    return "taze yatay destek"


def format_stabil_card_lines(
    *,
    price: float | None,
    support_level: float | None,
    behavior: StabilBarBehavior | None = None,
    min_tick: float = 0.01,
) -> list[str]:
    """Return the fixed 2-line Telegram card block for `BLOK 3 · YAPI`.

    Line 1: `Stabil destek: 172,10 (+%2,4 üstte)` (auto-compacts for wide index numbers)
    Line 2: `Stabil yapı: uzun yatay zemin`
    """
    sup = support_level
    if sup is None and behavior is not None:
        sup = behavior.support_level
    p = price
    if p is None and behavior is not None:
        p = behavior.close_price

    if sup is None or not math.isfinite(float(sup)) or float(sup) <= 0:
        return []

    sup_f = float(sup)
    sup_txt = _tr_sayi(sup_f, 2)
    tol = max(float(min_tick) * 0.5, 1e-6)

    if p is not None and math.isfinite(float(p)):
        p_f = float(p)
        diff = p_f - sup_f
        pct = (diff / sup_f) * 100.0
        pct_s = _tr_sayi(abs(pct), 1)
        if abs(diff) <= tol:
            line1 = _pick_fitting_line(
                (
                    f"Stabil destek: {sup_txt} (tam hizada)",
                    f"Stabil destek: {sup_txt} (%0,0)",
                ),
                f"Stabil destek: {sup_txt}",
            )
        elif diff > 0:
            line1 = _pick_fitting_line(
                (
                    f"Stabil destek: {sup_txt} (+%{pct_s} üstünde)",
                    f"Stabil destek: {sup_txt} (+%{pct_s} üstte)",
                    f"Stabil destek: {sup_txt} (+%{pct_s} üst)",
                    f"Stabil destek: {sup_txt} (+%{pct_s})",
                ),
                f"Stabil destek: {sup_txt}",
            )
        else:
            line1 = _pick_fitting_line(
                (
                    f"Stabil destek: {sup_txt} (-%{pct_s} altında)",
                    f"Stabil destek: {sup_txt} (-%{pct_s} altta)",
                    f"Stabil destek: {sup_txt} (-%{pct_s} alt)",
                    f"Stabil destek: {sup_txt} (-%{pct_s})",
                ),
                f"Stabil destek: {sup_txt}",
            )
    else:
        line1 = f"Stabil destek: {sup_txt}"

    yapi_txt = describe_behavior_structure_short(behavior)
    line2 = _pick_fitting_line(
        (f"Stabil yapı: {yapi_txt}",),
        f"Stabil yapı: {yapi_txt[:22]}",
    )
    return [line1, line2]


@dataclass(frozen=True, slots=True)
class LiveStabilSummary:
    symbol: str
    bucket: str  # "guclu_cikis" | "saglam_zemin" | "sig_sarkma" | "zayif_dusus" | "notr"
    priority: float
    close_price: float | None
    support_level: float | None
    pct_vs_support: float | None
    dist_atr: float | None
    unchanged_days: int
    touch_count: int
    regime: str
    reclaim_kind: str | None
    reclaim_bars_ago: int | None
    headline_tr: str
    detail_tr: str


def summarize_symbol_for_command(
    symbol: str,
    stabil_4h_output: Any,
    stabil_1d_output: Any | None = None,
) -> LiveStabilSummary | None:
    """Classify a symbol into replay-grounded behavioral buckets for `/stabil`."""
    bhvs: Sequence[StabilBarBehavior] = getattr(stabil_4h_output, "bar_behaviors", ()) or ()
    if not bhvs:
        bhvs = getattr(stabil_1d_output, "bar_behaviors", ()) or ()
    if not bhvs:
        return None

    last = bhvs[-1]
    if last.support_level is None or last.close_price is None:
        return None

    vertical = bool(getattr(last, "vertical_support", False)) or last.regime in {
        CandidateLineRegime.STEPPING_UP.value, CandidateLineRegime.STEPPING_DOWN.value,
    }
    # Check if strong reclaim happened on the latest bar or 1-2 closed 4H bars ago (~1 trading day)
    recent_reclaim_kind: str | None = None
    reclaim_bars_ago: int | None = None
    lookback = min(3, len(bhvs))
    for offset in range(lookback):
        cand = bhvs[-1 - offset]
        if cand.reclaim_kind is not None:
            # Still valid only if current close remains above support
            if not vertical and (last.pct_vs_support or 0.0) > 0.0:
                recent_reclaim_kind = cand.reclaim_kind
                reclaim_bars_ago = offset
            break

    sup_txt = _tr_sayi(last.support_level, 2)
    pct = float(last.pct_vs_support or 0.0)
    dist = float(last.dist_atr) if last.dist_atr is not None else 0.0
    body = float(last.body_atr) if last.body_atr is not None else 0.0
    vr = last.vol_ratio

    pct_etiket = (
        f"+%{_tr_sayi(abs(pct), 1)}"
        if pct >= 0
        else f"-%{_tr_sayi(abs(pct), 1)}"
    )

    # Dikey deneme bullish başlıkla pazarlanmaz; ▼ yalnız yapı uyarısıdır.
    if getattr(last, "vertical_attempt_kind", None):
        return LiveStabilSummary(
            symbol=symbol, bucket="zayif_dusus", priority=70.0,
            close_price=last.close_price, support_level=last.support_level,
            pct_vs_support=pct, dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days, touch_count=last.touch_count,
            regime=last.regime, reclaim_kind=None, reclaim_bars_ago=None,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — dikey destek, yukarı deneme",
            detail_tr="Kademe sürerken yukarı deneme uyarıdır; aşağı ok kesin düşüş tahmini değildir.",
        )

    # 1. GÜÇLÜ ÇIKIŞ / TAZE GERİ ALIM
    if recent_reclaim_kind is not None:
        zaman_notu = "son 4S mumda" if reclaim_bars_ago == 0 else f"{reclaim_bars_ago} mum önce"
        tur_notu = (
            "kapanışla güçlü geri alım"
            if recent_reclaim_kind == "close_reclaim"
            else "fitille silkeleme sonrası dönüş"
        )
        prio = 100.0 + float(bhvs[-1 - (reclaim_bars_ago or 0)].rank_score) * 10.0 - float(reclaim_bars_ago or 0) * 3.0
        return LiveStabilSummary(
            symbol=symbol,
            bucket="guclu_cikis",
            priority=prio,
            close_price=last.close_price,
            support_level=last.support_level,
            pct_vs_support=pct,
            dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days,
            touch_count=last.touch_count,
            regime=last.regime,
            reclaim_kind=recent_reclaim_kind,
            reclaim_bars_ago=reclaim_bars_ago,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — {tur_notu} ({zaman_notu})",
            detail_tr=(
                f"Destek üstünde güçlü mumla tutundu ({zaman_notu}); geçmiş testlerde "
                f"ilk mumda tutunma oranı yüksek kurulum."
            ),
        )

    # Uzun yatay zeminden taze güçlü kopuş veya kademe yükselten güçlü momentum
    if (
        pct > 0.0
        and not vertical
        and last.touch_count < 3
        and body >= 0.35
        and (last.close_pos or 0.5) >= 0.65
        and ((vr is not None and vr >= 1.1) or body >= 0.50)
        and (
            (last.unchanged_days >= 20 and 0.15 <= dist <= 1.80)
            or (last.regime == CandidateLineRegime.STEPPING_UP.value and 0.10 <= dist <= 1.60)
        )
    ):
        etiket = (
            f"{last.unchanged_days}g yatay zeminden hacimli kalkış"
            if last.unchanged_days >= 20
            else "yükselen kademeden güçlü ivme"
        )
        prio = 80.0 + body * 10.0 + (2.0 if last.unchanged_days >= 20 else 0.0)
        return LiveStabilSummary(
            symbol=symbol,
            bucket="guclu_cikis",
            priority=prio,
            close_price=last.close_price,
            support_level=last.support_level,
            pct_vs_support=pct,
            dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days,
            touch_count=last.touch_count,
            regime=last.regime,
            reclaim_kind=None,
            reclaim_bars_ago=None,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — {etiket}",
            detail_tr="Oturmuş destek üstünden güçlü gövdeyle uzaklaşıyor.",
        )

    # 2. SAĞLAM YATAY ZEMİN / 2. TEST TUTUNANLAR
    if (
        pct >= 0.0
        and last.touch_count < 3
        and not vertical
        and 0.0 <= dist <= 1.25
        and (last.unchanged_days >= 20 or last.touch_count == 2)
    ):
        neden = (
            f"{last.unchanged_days}g yatay zemin"
            if last.unchanged_days >= 20
            else "2. bağımsız destek testi tuttu"
        )
        if last.unchanged_days >= 20 and last.touch_count == 2:
            neden = f"{last.unchanged_days}g yatay zemin · 2. test"
        prio = 60.0 + min(20.0, float(last.unchanged_days) * 0.3) - abs(dist - 0.35) * 5.0
        return LiveStabilSummary(
            symbol=symbol,
            bucket="saglam_zemin",
            priority=prio,
            close_price=last.close_price,
            support_level=last.support_level,
            pct_vs_support=pct,
            dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days,
            touch_count=last.touch_count,
            regime=last.regime,
            reclaim_kind=None,
            reclaim_bars_ago=None,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — {neden}",
            detail_tr="Uzun yatay baz veya 2. temas desteği koruyor; desteğe yakın sağlıklı bölge.",
        )

    # 3. SIĞ SARKMA (GERİ ALIM İZLENENLER)
    if (
        pct < 0.0
        and -1.20 <= dist < 0.0
        and last.regime != CandidateLineRegime.STEPPING_DOWN.value
    ):
        prio = 50.0 - abs(dist) * 10.0 + (4.0 if last.unchanged_days >= 15 else 0.0)
        return LiveStabilSummary(
            symbol=symbol,
            bucket="sig_sarkma",
            priority=prio,
            close_price=last.close_price,
            support_level=last.support_level,
            pct_vs_support=pct,
            dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days,
            touch_count=last.touch_count,
            regime=last.regime,
            reclaim_kind=None,
            reclaim_bars_ago=None,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — sığ sarkma, geri alım beklenir",
            detail_tr="Henüz derin kırılıma dönmedi; ancak hacimli ve güçlü gövdeli geri alım olmadan erken girilmez.",
        )

    # 4. ZAYIF / YORULAN DESTEK VEYA SAĞLAM DÜŞÜŞ BASKISI
    if (
        (pct < 0.0 and (dist < -1.20 or last.regime == CandidateLineRegime.STEPPING_DOWN.value))
        or (pct >= 0.0 and last.touch_count >= 3 and dist <= 0.80)
        or last.weak_reclaim
    ):
        if pct < 0.0 and last.regime == CandidateLineRegime.STEPPING_DOWN.value:
            etiket = "destek kademe indiriyor (düşüş baskısı)"
            detay = "Çizgi aşağı basamaklıyor; yeni yatay zemin kurmadan dönüş zayıf kalır."
            prio = 75.0 + abs(dist) * 4.0
        elif pct < 0.0:
            etiket = "derin kırılım (sağlam düşüş)"
            detay = "Destek belirgin kırıldı; geçmiş testlerde bu derinlikten hızlı toparlanma oranı düşüktür."
            prio = 70.0 + abs(dist) * 5.0
        elif last.weak_reclaim:
            etiket = "cılız geri alım (teyitsiz)"
            detay = "Çizgi üstüne zayıf gövdeyle çıktı; tekrar sarkma riski yüksektir."
            prio = 66.0
        else:
            etiket = f"{last.touch_count}. destek testi (yorulma riski)"
            detay = "Destek 3+ kez test edildi; geçmiş veride çok test edilen çizgilerde kırılım riski artar."
            prio = 65.0 + float(last.touch_count) * 3.0
        return LiveStabilSummary(
            symbol=symbol,
            bucket="zayif_dusus",
            priority=prio,
            close_price=last.close_price,
            support_level=last.support_level,
            pct_vs_support=pct,
            dist_atr=last.dist_atr,
            unchanged_days=last.unchanged_days,
            touch_count=last.touch_count,
            regime=last.regime,
            reclaim_kind=None,
            reclaim_bars_ago=None,
            headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — {etiket}",
            detail_tr=detay,
        )

    # 5. NÖTR / OLAĞAN SEYİR (tek sembol sorgusu için tam bilgi taşır)
    yapi = describe_behavior_structure_short(last)
    return LiveStabilSummary(
        symbol=symbol,
        bucket="notr",
        priority=20.0,
        close_price=last.close_price,
        support_level=last.support_level,
        pct_vs_support=pct,
        dist_atr=last.dist_atr,
        unchanged_days=last.unchanged_days,
        touch_count=last.touch_count,
        regime=last.regime,
        reclaim_kind=None,
        reclaim_bars_ago=None,
        headline_tr=f"{symbol} · destek {sup_txt} ({pct_etiket}) — {yapi}",
        detail_tr="Destekle uyumlu olağan seyirde; uç bir kırılım veya taze geri alım sinyali yok.",
    )
