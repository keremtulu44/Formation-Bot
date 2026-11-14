"""Gölge v2 nedensel veri adaptörü — tüm katmanları tek bar-kapanış ekseninde hizalar.

Hizalanan katmanlar (her biri kendi ham motorunu hiç değiştirmeden çağırır):
1. `Stabil S`: `build_daily_support_observations` + `build_support_lifecycle_timeline` + `evaluate_bar_behaviors`
2. `Stabil R`: `build_daily_resistance_history` + `evaluate_resistance_bar_behaviors`
3. `Market Structure`: `MarketStructureEngine.update` (bar-by-bar anlık görüntü; PH/PL/WH/WL rolleri + taze BOS/CHoCH)
4. `Formasyon`: `_AsOfArgentEngine` alt-sınıfı (yalnız alt-sınıfta `_process_bar` kaydı; canlı sınıfa dokunulmaz)
5. `Volume Participation`: `VolumeParticipationEngine.update` (bar-by-bar as-of; S32 `volume_usable` kapısı)
6. `OB / FVG` (yalnız Mod 1/Mod 2 + karşı engel denetimi için): `available_index <= i < native_terminal_index`
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from directional_zone_replay import replay_fvg_zones, replay_ob_zones
from domain_engines.market_structure import MarketStructureConfig, MarketStructureEngine
from domain_engines.stabil import (
    StabilTrendConfig,
    build_daily_support_observations,
    build_support_lifecycle_timeline,
    prepare_causal_ohlcv,
    project_support_to_bar_closes,
)
from domain_engines.stabil.resistance import (
    build_daily_resistance_history,
    evaluate_resistance_bar_behaviors,
    project_resistance_to_bar_closes,
)
from domain_engines.stabil.signals import _causal_atr14, evaluate_bar_behaviors
from domain_engines.volume_participation import VolumeParticipationEngine
from patterns.lifecycle import (
    ST_BREAK_ATTEMPT,
    ST_BREAK_CANDIDATE,
    ST_BREAK_CONFIRMED,
    ST_BREAK_FAILED,
    ST_COMPLETED,
    ST_INVALID,
    ST_NONE,
    ST_RETESTING,
    ST_RETEST_OK,
    ST_RETEST_WAIT,
    ArgentEngine,
)
from patterns.mathutil import f_line_price
from patterns.pole import PoleInfo, find_pole

from .modeller import BOS_TAZELIK_PENCERE, BarDurum, BlokBand, SeriVerisi

_FRM_KIRILIM_VE_SONRASI = frozenset({
    ST_BREAK_ATTEMPT,
    ST_BREAK_CANDIDATE,
    ST_BREAK_CONFIRMED,
    ST_RETEST_WAIT,
    ST_RETESTING,
    ST_RETEST_OK,
})
_FRM_OLU_VEYA_BOS = frozenset({
    ST_NONE,
    ST_INVALID,
    ST_BREAK_FAILED,
    ST_COMPLETED,
})


@dataclass(frozen=True, slots=True)
class GunlukBaglam:
    """Sembol başına bir kez hesaplanan günlük Stabil S/R + günlük ATR bağlamı."""

    sembol: str
    daily_clean: pd.DataFrame
    daily_close_times: tuple[Any, ...]
    atr_1d: np.ndarray
    support_timeline: tuple[Any, ...]
    resistance_history: Any


@dataclass(frozen=True, slots=True)
class _FrmBarSnap:
    valid: bool
    stable_id: str
    state: str
    prev_state: str
    pattern_type: str
    classic_dir: int
    break_dir: int
    upper_now: float | None
    lower_now: float | None
    broken_boundary: float | None
    contraction: float | None


class _AsOfArgentEngine(ArgentEngine):
    """ArgentEngine'in küresel sınıfına dokunmadan bar-bazlı as-of durum yakalayan yerel alt-sınıf."""

    def __init__(
        self,
        profile: str = "Dengeli",
        mintick: float = 0.01,
        use_breakout_quality_filter: bool = True,
        timeframe: str | None = None,
    ) -> None:
        super().__init__(
            profile=profile,
            mintick=mintick,
            use_breakout_quality_filter=use_breakout_quality_filter,
            timeframe=timeframe,
        )
        self.bar_snapshots: list[_FrmBarSnap] = []
        self._det_id_map: dict[str, str] = {}
        self._asof_bar: int = -1

    def reset(self) -> None:
        super().reset()
        self.bar_snapshots = []
        self._det_id_map = {}
        self._asof_bar = -1

    def find_pole_ctx(self, end_bar: int, end_price: float, direction: int) -> PoleInfo:
        """Nedensel as-of direk tespiti: `len(close)` gelecege sızmasın diye `0.._asof_bar` kesiti kullanır."""
        b = self._asof_bar
        if b < 0:
            return super().find_pole_ctx(end_bar, end_price, direction)
        n_asof = b + 1
        return find_pole(
            self.close[:n_asof],
            self.high[:n_asof],
            self.low[:n_asof],
            self.atr_array[:n_asof],
            self.safe_atr,
            self.high_side,
            self.low_side,
            end_bar,
            end_price,
            direction,
            self.min_pole_atr,
            self.min_pole_efficiency,
            self.max_pole_bars,
            self.min_pole_quality,
            self.touch_atr_mult,
            self.max_path_sample,
            self.max_history_offset,
            self.mintick,
        )

    def _process_bar(self, b: int) -> None:
        self._asof_bar = b
        prev_state = self.pattern_state
        super()._process_bar(b)
        act = self.active if getattr(self.active, "valid", False) else None
        det_id = ""
        if act is not None and act.stable_id:
            raw_id = str(act.stable_id)
            if raw_id not in self._det_id_map:
                self._det_id_map[raw_id] = f"frm_{b}_{len(self._det_id_map)}"
            det_id = self._det_id_map[raw_id]
        broken_boundary: float | None = None
        if (
            act is not None
            and self.break_candidate_dir in (-1, 1)
            and self.break_line_x1 is not None
            and self.break_line_x2 is not None
            and self.break_line_y1 is not None
            and self.break_line_y2 is not None
        ):
            try:
                val = float(
                    f_line_price(
                        self.break_line_x1,
                        self.break_line_y1,
                        self.break_line_x2,
                        self.break_line_y2,
                        b,
                    )
                )
                if math.isfinite(val) and val > 0:
                    broken_boundary = val
            except Exception:
                broken_boundary = None

        upper_now: float | None = None
        lower_now: float | None = None
        contraction: float | None = None
        if act is not None:
            if act.upper_now is not None and math.isfinite(float(act.upper_now)):
                upper_now = float(act.upper_now)
            if act.lower_now is not None and math.isfinite(float(act.lower_now)):
                lower_now = float(act.lower_now)
            if getattr(act, "contraction", None) is not None and math.isfinite(float(act.contraction)):
                contraction = float(act.contraction)

        self.bar_snapshots.append(
            _FrmBarSnap(
                valid=act is not None,
                stable_id=det_id,
                state=str(self.pattern_state),
                prev_state=str(prev_state),
                pattern_type=str(act.pattern_type or "") if act is not None else "",
                classic_dir=int(act.classic_dir or 0) if act is not None else 0,
                break_dir=int(self.break_candidate_dir or 0),
                upper_now=upper_now,
                lower_now=lower_now,
                broken_boundary=broken_boundary,
                contraction=contraction,
            )
        )


def _enum_str(val: Any) -> str:
    if val is None:
        return ""
    return str(getattr(val, "value", val))


def hazirla_gunluk_baglam(
    sembol: str,
    daily_raw: pd.DataFrame | None = None,
    *,
    cutoff_close: Any | None = None,
    kok: Any | None = None,
    config: StabilTrendConfig | None = None,
) -> GunlukBaglam:
    """Sembol için günlük Stabil S + Stabil R + ATR_1d bağlamını nedensel olarak kurar."""
    if daily_raw is None:
        from research.arsiv import tf_frame

        daily_raw = tf_frame(sembol, "1d", kok)

    cfg = config or StabilTrendConfig()
    d_clean, d_err = prepare_causal_ohlcv(
        daily_raw,
        symbol=sembol,
        timeframe="1d",
        cutoff_close=cutoff_close,
    )
    if d_err and d_clean.empty:
        raise ValueError(f"{sembol}/1d günlük çerçeve hazırlanamadı: {d_err}")

    d_highs = d_clean["high"].to_numpy(dtype=float)
    d_lows = d_clean["low"].to_numpy(dtype=float)
    d_closes = d_clean["close"].to_numpy(dtype=float)
    atr_1d = _causal_atr14(d_highs, d_lows, d_closes, period=14)

    support_obs = build_daily_support_observations(d_clean, config=cfg)
    support_tl = build_support_lifecycle_timeline(
        support_obs,
        min_tick=cfg.min_tick,
        include_prefix_events=True,
    )
    res_hist = build_daily_resistance_history(
        d_clean,
        config=cfg,
        include_prefix_events=True,
    )
    return GunlukBaglam(
        sembol=sembol,
        daily_clean=d_clean,
        daily_close_times=tuple(d_clean["timestamp"]),
        atr_1d=atr_1d,
        support_timeline=support_tl,
        resistance_history=res_hist,
    )


def _atr_1d_at(baglam: GunlukBaglam, close_ts: Any) -> float | None:
    times = baglam.daily_close_times
    if not times or close_ts is None:
        return None
    idx = bisect_right(times, close_ts) - 1
    if idx < 0 or idx >= len(baglam.atr_1d):
        return None
    val = float(baglam.atr_1d[idx])
    return val if math.isfinite(val) and val > 0 else None


def seriyi_hazirla(
    sembol: str,
    tf: str,
    *,
    raw_frame: pd.DataFrame | None = None,
    daily_raw: pd.DataFrame | None = None,
    gunluk_baglam: GunlukBaglam | None = None,
    cutoff_close: Any | None = None,
    kok: Any | None = None,
    profile: str = "Dengeli",
    bloklari_yukle: bool = True,
) -> SeriVerisi:
    """Bir (sembol, tf) için tüm katmanları tam olarak aynı kapalı bar (0..N-1) ekseninde hazırlar."""
    if tf not in BOS_TAZELIK_PENCERE:
        raise ValueError(f"Desteklenmeyen zaman dilimi: {tf}")

    if raw_frame is None:
        from research.arsiv import tf_frame

        raw_frame = tf_frame(sembol, tf, kok)

    baglam = gunluk_baglam or hazirla_gunluk_baglam(
        sembol,
        daily_raw=daily_raw,
        cutoff_close=cutoff_close,
        kok=kok,
    )

    target_clean, t_err = prepare_causal_ohlcv(
        raw_frame,
        symbol=sembol,
        timeframe=tf,
        cutoff_close=cutoff_close,
    )
    if t_err and target_clean.empty:
        raise ValueError(f"{sembol}/{tf} hedef çerçeve hazırlanamadı: {t_err}")

    n = len(target_clean)
    if n == 0:
        return SeriVerisi(sembol=sembol, tf=tf, barlar=())

    close_times = list(target_clean["timestamp"])
    opens = target_clean["open"].to_numpy(dtype=float)
    highs = target_clean["high"].to_numpy(dtype=float)
    lows = target_clean["low"].to_numpy(dtype=float)
    closes = target_clean["close"].to_numpy(dtype=float)
    volumes = target_clean["volume"].to_numpy(dtype=float)
    atr_tf_arr = _causal_atr14(highs, lows, closes, period=14)
    safe_atr_arr = np.empty(n, dtype=float)
    for i in range(n):
        v = float(atr_tf_arr[i])
        if not math.isfinite(v) or v <= 0:
            v = max(float(highs[i] - lows[i]), float(closes[i]) * 0.005, 1e-6)
        safe_atr_arr[i] = v

    # 1. Stabil S (bar_close_time ekseninde tam hizalı)
    sup_proj = project_support_to_bar_closes(close_times, baglam.support_timeline)
    sup_bhv = evaluate_bar_behaviors(
        sembol,
        tf,
        target_clean,
        sup_proj,
        baglam.support_timeline,
        min_tick=0.01,
    )

    # 2. Stabil R (aynalı çekirdek, bar_close_time ekseninde tam hizalı)
    r_hatali = False
    res_proj: tuple[Any, ...] = ()
    res_bhv: tuple[Any, ...] = ()
    try:
        res_proj = project_resistance_to_bar_closes(close_times, baglam.resistance_history)
        res_bhv = evaluate_resistance_bar_behaviors(
            sembol,
            tf,
            target_clean,
            res_proj,
            baglam.resistance_history,
            min_tick=0.01,
        )
    except Exception:
        r_hatali = True

    # 3. Market Structure (bar-by-bar as-of replay; dış swing, roller, PH/PL yaşı & teması, taze BOS/CHOCH)
    ms_hatali = False
    ms_up_now = [False] * n
    ms_dn_now = [False] * n
    ms_fresh_dir = [0] * n
    ms_ext_state = ["STATE_NEUTRAL"] * n
    ms_ext_dir = [0] * n
    ms_bos_move_atr: list[float | None] = [None] * n
    ms_prot_high: list[float | None] = [None] * n
    ms_prot_low: list[float | None] = [None] * n
    ms_weak_high: list[float | None] = [None] * n
    ms_weak_low: list[float | None] = [None] * n
    ms_prot_high_tc = [0] * n
    ms_prot_low_tc = [0] * n
    ms_prot_high_age = [0] * n
    ms_prot_low_age = [0] * n
    ms_unbroken_highs: list[tuple[float, ...]] = [() for _ in range(n)]
    ms_unbroken_lows: list[tuple[float, ...]] = [() for _ in range(n)]
    ms_up_broken_lvls: list[tuple[float, ...]] = [() for _ in range(n)]
    ms_dn_broken_lvls: list[tuple[float, ...]] = [() for _ in range(n)]

    ohlcv_records = target_clean[["timestamp", "open", "high", "low", "close", "volume"]].to_dict("records")

    try:
        ms = MarketStructureEngine(MarketStructureConfig(profile=profile))
        win = BOS_TAZELIK_PENCERE[tf]
        last_ext_dir = 0
        last_ext_bar = -999
        last_bos_move: float | None = None
        seen_uids: set[str] = set()
        recent_up_broken: list[float] = []
        recent_dn_broken: list[float] = []
        swing_touches: dict[int, int] = {}

        for i, row in enumerate(ohlcv_records):
            res = ms.update(row)
            has_ext_bos = any(
                ev.startswith("EXTERNAL:EVENT_BOS:") or ev.startswith("EXTERNAL:EVENT_CHOCH:")
                for ev in (res.events if res is not None else ())
            )
            if has_ext_bos:
                for ev_rec in ms.event_history:
                    if ev_rec.event_bar != i or ev_rec.event_uid in seen_uids:
                        continue
                    if ev_rec.scope == "EXTERNAL" and ev_rec.event_type in ("EVENT_BOS", "EVENT_CHOCH"):
                        seen_uids.add(ev_rec.event_uid)
                        d_int = int(ev_rec.direction)
                        if d_int > 0:
                            ms_up_now[i] = True
                            last_ext_dir = 1
                            last_ext_bar = i
                            if ev_rec.broken_level is not None and math.isfinite(float(ev_rec.broken_level)):
                                bl = float(ev_rec.broken_level)
                                last_bos_move = abs(float(closes[i]) - bl) / float(safe_atr_arr[i])
                                recent_up_broken.append(bl)
                                if len(recent_up_broken) > 12:
                                    recent_up_broken.pop(0)
                            else:
                                last_bos_move = abs(float(closes[i]) - float(opens[i])) / float(safe_atr_arr[i])
                        elif d_int < 0:
                            ms_dn_now[i] = True
                            last_ext_dir = -1
                            last_ext_bar = i
                            if ev_rec.broken_level is not None and math.isfinite(float(ev_rec.broken_level)):
                                bl = float(ev_rec.broken_level)
                                last_bos_move = abs(float(closes[i]) - bl) / float(safe_atr_arr[i])
                                recent_dn_broken.append(bl)
                                if len(recent_dn_broken) > 12:
                                    recent_dn_broken.pop(0)
                            else:
                                last_bos_move = abs(float(closes[i]) - float(opens[i])) / float(safe_atr_arr[i])

            fresh_active = last_ext_bar >= 0 and (i - last_ext_bar) <= win
            ms_fresh_dir[i] = last_ext_dir if fresh_active else 0
            ms_bos_move_atr[i] = last_bos_move if fresh_active else None

            swings = ms.external_swings
            atr_i = float(safe_atr_arr[i])
            for s in swings:
                if s.valid and not s.broken and s.price is not None and s.confirm_bar is not None and i > s.confirm_bar:
                    if s.side == "HIGH" and float(highs[i]) >= float(s.price) - 0.15 * atr_i:
                        swing_touches[s.identity] = swing_touches.get(s.identity, 0) + 1
                    elif s.side == "LOW" and float(lows[i]) <= float(s.price) + 0.15 * atr_i:
                        swing_touches[s.identity] = swing_touches.get(s.identity, 0) + 1

            ctx = ms.external_context
            ms_ext_state[i] = str(ctx.state)
            ms_ext_dir[i] = int(ctx.direction)
            lvls = res.levels if res is not None else {}
            ph_v = lvls.get("external_protected_high")
            pl_v = lvls.get("external_protected_low")
            wh_v = lvls.get("external_weak_high")
            wl_v = lvls.get("external_weak_low")
            ms_prot_high[i] = float(ph_v) if ph_v is not None else None
            ms_prot_low[i] = float(pl_v) if pl_v is not None else None
            ms_weak_high[i] = float(wh_v) if wh_v is not None else None
            ms_weak_low[i] = float(wl_v) if wl_v is not None else None

            for s in reversed(swings):
                if not s.valid or s.broken or s.price is None:
                    continue
                if ph_v is not None and s.identity == ctx.protected_high_identity and ms_prot_high_age[i] == 0:
                    ms_prot_high_age[i] = i - (s.source_bar if s.source_bar is not None else i)
                    ms_prot_high_tc[i] = swing_touches.get(s.identity, 0)
                if pl_v is not None and s.identity == ctx.protected_low_identity and ms_prot_low_age[i] == 0:
                    ms_prot_low_age[i] = i - (s.source_bar if s.source_bar is not None else i)
                    ms_prot_low_tc[i] = swing_touches.get(s.identity, 0)
                if (ph_v is None or ms_prot_high_age[i] > 0) and (pl_v is None or ms_prot_low_age[i] > 0):
                    break

            ms_unbroken_highs[i] = tuple(
                sorted({float(s.price) for s in swings if s.valid and not s.broken and s.side == "HIGH" and s.price is not None})
            )
            ms_unbroken_lows[i] = tuple(
                sorted({float(s.price) for s in swings if s.valid and not s.broken and s.side == "LOW" and s.price is not None})
            )
            ms_up_broken_lvls[i] = tuple(recent_up_broken)
            ms_dn_broken_lvls[i] = tuple(recent_dn_broken)
    except Exception:
        ms_hatali = True

    # 4. Volume Participation (bar-by-bar as-of; S32 09:30 / endeks koruma bayrağı)
    vp_hatali = False
    vp_ready = [False] * n
    vp_usable = [False] * n
    vp_rvol: list[float | None] = [None] * n
    vp_rtv: list[float | None] = [None] * n
    vp_p5: list[float | None] = [None] * n
    vp_eff: list[float | None] = [None] * n
    vp_erc = ["NEUTRAL"] * n
    vp_state = ["PARTICIPATION_PENDING"] * n
    vp_dir = [0] * n
    try:
        vp = VolumeParticipationEngine()
        for i, row in enumerate(ohlcv_records):
            vp.update(row)
            m = vp.metrics_history[-1] if vp.metrics_history else None
            e = vp.export_contract
            if m is not None:
                vp_ready[i] = bool(m.data_ready)
                vp_usable[i] = bool(m.volume_usable)
                vp_rvol[i] = float(m.rvol) if m.rvol is not None and math.isfinite(float(m.rvol)) else None
                vp_rtv[i] = float(m.rtv) if m.rtv is not None and math.isfinite(float(m.rtv)) else None
                vp_p5[i] = (
                    float(m.directional_value_pressure_5)
                    if m.directional_value_pressure_5 is not None and math.isfinite(float(m.directional_value_pressure_5))
                    else None
                )
                vp_eff[i] = (
                    float(m.directional_efficiency)
                    if m.directional_efficiency is not None and math.isfinite(float(m.directional_efficiency))
                    else None
                )
                vp_erc[i] = _enum_str(m.effort_result_class) or "NEUTRAL"
            if e is not None:
                vp_state[i] = str(e.state or "PARTICIPATION_PENDING")
                vp_dir[i] = int(e.direction or 0)
    except Exception:
        vp_hatali = True

    # 5. Formasyon (bar-by-bar _AsOfArgentEngine)
    frm_hatali = False
    frm_snaps: list[_FrmBarSnap] = []
    try:
        df_frm = target_clean.set_index("timestamp", drop=False)
        eng = _AsOfArgentEngine(profile=profile, timeframe=tf)
        eng.process(df_frm, tam_yeniden=True)
        frm_snaps = eng.bar_snapshots
        if len(frm_snaps) != n:
            frm_hatali = True
    except Exception:
        frm_hatali = True

    # 6. OB / FVG blokları (anti-lookahead: available_index <= i < native_terminal_index ve contacts < i)
    blok_hatali = False
    blok_bull_at: list[tuple[BlokBand, ...]] = [() for _ in range(n)]
    blok_bear_at: list[tuple[BlokBand, ...]] = [() for _ in range(n)]
    if bloklari_yukle:
        try:
            ob_zones = replay_ob_zones(sembol, tf, target_clean)
            if tf in ("2h", "4h", "1d"):
                fvg_zones, _, _ = replay_fvg_zones(sembol, tf, target_clean)
            else:
                fvg_zones = []
            bull_lists: list[list[BlokBand]] = [[] for _ in range(n)]
            bear_lists: list[list[BlokBand]] = [[] for _ in range(n)]
            for z in list(ob_zones) + list(fvg_zones):
                a_idx = int(z["available_index"])
                t_idx_raw = z.get("native_terminal_index")
                t_idx = int(t_idx_raw) if t_idx_raw is not None else n
                start = max(0, a_idx)
                end = min(n, t_idx)
                if start >= end:
                    continue
                lo = float(z["zone_lower"])
                hi = float(z["zone_upper"])
                atr_avail = float(safe_atr_arr[a_idx]) if 0 <= a_idx < n else float(safe_atr_arr[start])
                h_atr = round(max(0.0, hi - lo) / max(atr_avail, 1e-6), 4)
                contacts = [int(c["index"]) for c in z.get("contact_bars", [])]
                fam = str(z["family"])
                z_dir = str(z["direction"])
                dest = bull_lists if z_dir == "bullish" else bear_lists
                for idx_bar in range(start, end):
                    tc_asof = sum(1 for c in contacts if c < idx_bar)
                    dest[idx_bar].append(
                        BlokBand(
                            family=fam,
                            direction=z_dir,
                            lower=lo,
                            upper=hi,
                            available_index=a_idx,
                            height_atr=h_atr,
                            touch_count_asof=tc_asof,
                        )
                    )
            blok_bull_at = [tuple(lst) for lst in bull_lists]
            blok_bear_at = [tuple(lst) for lst in bear_lists]
        except Exception:
            blok_hatali = True

    # Birleştirme: bar 0..n-1
    barlar: list[BarDurum] = []
    for i in range(n):
        c_ts = close_times[i]
        c_ist = c_ts.tz_convert("Europe/Istanbul") if getattr(c_ts, "tzinfo", None) is not None else pd.Timestamp(c_ts)
        is_kisa_1800 = (tf == "4h" and c_ist.hour == 18 and c_ist.minute == 0)

        atr_tf = float(safe_atr_arr[i])
        atr_1d = _atr_1d_at(baglam, c_ts)

        sb = sup_bhv[i]
        sp = sup_proj[i]

        if not r_hatali and i < len(res_bhv) and i < len(res_proj):
            rb = res_bhv[i]
            rp = res_proj[i]
            r_level = float(rb.resistance_level) if rb.resistance_level is not None else None
            r_val = _enum_str(rp.validity)
            r_reg = _enum_str(rb.regime)
            r_unch = int(rb.unchanged_days)
            r_fix = bool(rb.fixed_resistance)
            r_vert = bool(rb.vertical_resistance)
            r_ret = rb.return_kind
            r_mom = rb.momentum_kind
            r_vatt = rb.vertical_attempt_kind
            r_tc = int(rb.touch_count)
        else:
            r_level = None
            r_val = "UNAVAILABLE"
            r_reg = "UNAVAILABLE"
            r_unch = 0
            r_fix = False
            r_vert = False
            r_ret = None
            r_mom = None
            r_vatt = None
            r_tc = 0

        if not frm_hatali and i < len(frm_snaps):
            fs = frm_snaps[i]
            f_aktif = fs.valid
            f_id = fs.stable_id
            f_st = fs.state
            f_pst = fs.prev_state
            f_pt = fs.pattern_type
            f_cd = fs.classic_dir
            f_bd = fs.break_dir
            f_up = fs.upper_now
            f_lo = fs.lower_now
            f_bb = fs.broken_boundary
            f_con = fs.contraction
            f_w_atr = round((f_up - f_lo) / atr_tf, 4) if (f_up is not None and f_lo is not None and atr_tf > 0) else None
            f_icerde = (
                f_aktif
                and f_st not in _FRM_KIRILIM_VE_SONRASI
                and f_st not in _FRM_OLU_VEYA_BOS
                and f_up is not None
                and f_lo is not None
                and f_lo <= float(closes[i]) <= f_up
            )
        else:
            f_aktif = False
            f_id = ""
            f_st = ST_NONE
            f_pst = ST_NONE
            f_pt = ""
            f_cd = 0
            f_bd = 0
            f_up = None
            f_lo = None
            f_bb = None
            f_con = None
            f_w_atr = None
            f_icerde = False

        barlar.append(
            BarDurum(
                i=i,
                bar_close_time=c_ist.isoformat(),
                open=float(opens[i]),
                high=float(highs[i]),
                low=float(lows[i]),
                close=float(closes[i]),
                volume=float(volumes[i]),
                atr_tf=atr_tf,
                atr_1d=atr_1d,
                is_kisa_1800=is_kisa_1800,
                s_level=float(sb.support_level) if sb.support_level is not None else None,
                s_validity=_enum_str(sp.validity),
                s_regime=_enum_str(sb.regime),
                s_unchanged_days=int(sb.unchanged_days),
                s_fixed=bool(sb.fixed_support),
                s_vertical=bool(sb.vertical_support),
                s_reclaim_kind=sb.reclaim_kind,
                s_momentum_kind=sb.momentum_kind,
                s_vertical_attempt=sb.vertical_attempt_kind,
                s_touch_count=int(sb.touch_count),
                r_level=r_level,
                r_validity=r_val,
                r_regime=r_reg,
                r_unchanged_days=r_unch,
                r_fixed=r_fix,
                r_vertical=r_vert,
                r_return_kind=r_ret,
                r_momentum_kind=r_mom,
                r_vertical_attempt=r_vatt,
                r_touch_count=r_tc,
                ms_bos_up_now=ms_up_now[i],
                ms_bos_down_now=ms_dn_now[i],
                ms_fresh_dir=ms_fresh_dir[i],
                ms_unbroken_highs=ms_unbroken_highs[i],
                ms_unbroken_lows=ms_unbroken_lows[i],
                ms_down_broken_levels=ms_dn_broken_lvls[i],
                ms_up_broken_levels=ms_up_broken_lvls[i],
                frm_aktif=f_aktif,
                frm_stable_id=f_id,
                frm_state=f_st,
                frm_prev_state=f_pst,
                frm_pattern_type=f_pt,
                frm_classic_dir=f_cd,
                frm_break_dir=f_bd,
                frm_upper_now=f_up,
                frm_lower_now=f_lo,
                frm_broken_boundary=f_bb,
                frm_icerde=f_icerde,
                blok_bull=blok_bull_at[i],
                blok_bear=blok_bear_at[i],
                ms_ext_state=ms_ext_state[i],
                ms_ext_dir=ms_ext_dir[i],
                ms_bos_move_atr=ms_bos_move_atr[i],
                ms_protected_high=ms_prot_high[i],
                ms_protected_low=ms_prot_low[i],
                ms_weak_high=ms_weak_high[i],
                ms_weak_low=ms_weak_low[i],
                ms_protected_high_tc=ms_prot_high_tc[i],
                ms_protected_low_tc=ms_prot_low_tc[i],
                ms_protected_high_age=ms_prot_high_age[i],
                ms_protected_low_age=ms_prot_low_age[i],
                vp_data_ready=vp_ready[i],
                vp_volume_usable=vp_usable[i],
                vp_rvol=vp_rvol[i],
                vp_rtv=vp_rtv[i],
                vp_pressure_5=vp_p5[i],
                vp_directional_efficiency=vp_eff[i],
                vp_effort_result_class=vp_erc[i],
                vp_state=vp_state[i],
                vp_direction=vp_dir[i],
                frm_width_atr=f_w_atr,
                frm_contraction=f_con,
            )
        )

    return SeriVerisi(
        sembol=sembol,
        tf=tf,
        barlar=tuple(barlar),
        r_hatali=r_hatali,
        frm_hatali=frm_hatali,
        ms_hatali=ms_hatali,
        blok_hatali=blok_hatali,
        vp_hatali=vp_hatali,
    )
