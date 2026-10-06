from __future__ import annotations

from dataclasses import replace
from typing import Any
import math

from .fvg_engulfing_engine import (
    ATR_LENGTH,
    CONFLICT_PROGRESS_FACTOR,
    DOJI_BODY_ATR,
    DOJI_BODY_SHARE,
    ENGULFING_NEUTRAL_FLOW_FACTOR,
    FLOW_LENGTH,
    FVG_CANDIDATE_QUALITY_OFFSET,
    FVG_CANDIDATE_SIZE_FACTOR,
    FVG_DISPLACEMENT_EXTRA_FACTOR,
    FVG_PROGRESS_EXTRA_FACTOR,
    FVG_SIZE_EXTRA_FACTOR,
    LARGE_GAP_BREAK_ATR,
    LARGE_GAP_REAL_PROGRESS_FACTOR,
    LOCAL_CONTEXT_LENGTH,
    MINIMUM_HISTORY_BARS,
    PREVIOUS_ZONE_LOWER_SHARE,
    PREVIOUS_ZONE_UPPER_SHARE,
    REJECTION_CONFLICT_MARGIN,
    RETENTION_CLOSE_FLOOR,
    RETENTION_CLOSE_OFFSET,
    RETENTION_EFFICIENCY_FACTOR,
    SHOCK_CLOSE_LOWER,
    SHOCK_CLOSE_UPPER,
    SHOCK_DIRECTIONLESS_BODY_SHARE,
    SHOCK_DIRECTIONLESS_WICK_SHARE,
    SHOCK_JUMP_FACTOR,
    SHOCK_MIDDLE_HIGH,
    SHOCK_MIDDLE_LOW,
    VERY_STRONG_ENGULFING_FACTOR,
    VERY_STRONG_ENGULFING_RATIO_FACTOR,
    _clamp,
    _ratio_score,
    _rma,
    _safe_div,
)
from .fvg_engulfing_final import (
    FvgEngulfingEngine as _FinalFvgEngulfingEngine,
    _LifecycleMetrics,
)
from .fvg_engulfing_models import FvgDirection


class FvgEngulfingEngine(_FinalFvgEngulfingEngine):
    """Final public facade with prefix-stable detector replay caches.

    Detector metrics for bar ``i`` depend only on rows ``<= i``. Retaining those
    rows removes the historical full-series recomputation that previously happened
    on every append. True-range/RMA is intentionally rebuilt as a cheap reference
    series so source-gap reset semantics remain byte-for-byte canonical.
    """

    def _reset_runtime_detector(self) -> None:
        self._runtime_series_cache: list[dict[str, Any]] = []
        self._runtime_candidate_core_buy: list[bool] = []
        self._runtime_candidate_core_sell: list[bool] = []
        self._runtime_candidate_raw_buy: list[bool] = []
        self._runtime_candidate_raw_sell: list[bool] = []
        self._runtime_confirmed_buy: list[bool] = []
        self._runtime_confirmed_sell: list[bool] = []
        self._runtime_range_to_atr: list[float] = []
        self._runtime_body_to_atr: list[float] = []

    def reset(self) -> None:
        super().reset()
        self._reset_runtime_detector()

    def _calculate_series(self) -> list[dict[str, Any]]:
        n = len(self._rows)
        if not hasattr(self, "_runtime_series_cache"):
            self._reset_runtime_detector()
        if len(self._runtime_series_cache) > n:
            self._reset_runtime_detector()
        if len(self._runtime_series_cache) == n:
            return self._runtime_series_cache

        mintick = self.config.minimum_tick
        t = self._thresholds
        tr: list[float | None] = []
        for index, row in enumerate(self._rows):
            if not self._valid[index]:
                tr.append(None)
                continue
            prev_close = self._rows[index - 1]["close"] if index > 0 and self._valid[index - 1] else None
            value = row["high"] - row["low"]
            if prev_close is not None:
                value = max(value, abs(row["high"] - prev_close), abs(row["low"] - prev_close))
            tr.append(max(value, 0.0))
        atr = _rma(tr, ATR_LENGTH)

        out = self._runtime_series_cache
        candidate_core_buy = self._runtime_candidate_core_buy
        candidate_core_sell = self._runtime_candidate_core_sell
        candidate_raw_buy = self._runtime_candidate_raw_buy
        candidate_raw_sell = self._runtime_candidate_raw_sell
        confirmed_buy = self._runtime_confirmed_buy
        confirmed_sell = self._runtime_confirmed_sell
        range_to_atr_series = self._runtime_range_to_atr
        body_to_atr_series = self._runtime_body_to_atr

        def valid_range(start: int, end: int) -> bool:
            return start >= 0 and all(self._valid[j] for j in range(start, end + 1))

        for i in range(len(out), n):
            r = self._rows[i]
            m: dict[str, Any] = {
                "data_ready": False,
                "bullish_fvg_candidate": False, "bearish_fvg_candidate": False,
                "bullish_fvg_active": False, "bearish_fvg_active": False,
                "bullish_engulfing": False, "bearish_engulfing": False,
                "bullish_fvg_quality": 0.0, "bearish_fvg_quality": 0.0,
                "bullish_engulfing_quality": 0.0, "bearish_engulfing_quality": 0.0,
                "bull_fvg_lower": math.nan, "bull_fvg_upper": math.nan,
                "bear_fvg_lower": math.nan, "bear_fvg_upper": math.nan,
                "bull_fvg_gap_size": 0.0, "bear_fvg_gap_size": 0.0,
                "bull_fvg_gap_atr": 0.0, "bear_fvg_gap_atr": 0.0,
                "formation_atr": math.nan, "safe_prior_atr": math.nan,
                "swallowed_lower": math.nan, "swallowed_upper": math.nan,
                "swallowed_size": 0.0, "swallowed_atr": 0.0,
                "bull_embedded_contribution": 0.0, "bear_embedded_contribution": 0.0,
                "bull_fvg_evidence": 0, "bear_fvg_evidence": 0,
            }
            out.append(m)
            candidate_core_buy.append(False)
            candidate_core_sell.append(False)
            candidate_raw_buy.append(False)
            candidate_raw_sell.append(False)
            confirmed_buy.append(False)
            confirmed_sell.append(False)
            range_to_atr_series.append(0.0)
            body_to_atr_series.append(0.0)
            if not self._valid[i]:
                continue

            o, h, l, c = r["open"], r["high"], r["low"], r["close"]
            candle_range = max(h - l, 0.0)
            body = abs(c - o)
            upper_wick = max(h - max(o, c), 0.0)
            lower_wick = max(min(o, c) - l, 0.0)
            safe_body = max(body, mintick)
            prior_atr = atr[i - 1] if i > 0 else None
            safe_prior_atr = max(prior_atr if prior_atr is not None else mintick, mintick)
            m["safe_prior_atr"] = safe_prior_atr
            range_to_atr = _safe_div(candle_range, safe_prior_atr, 0.0, mintick)
            body_to_atr = _safe_div(body, safe_prior_atr, 0.0, mintick)
            body_share = _safe_div(body, candle_range, 0.0, mintick)
            close_loc = 0.5 if candle_range <= 1e-10 else _safe_div(c - l, candle_range, 0.5, mintick)
            upper_wick_body = _safe_div(upper_wick, safe_body, 0.0, mintick)
            lower_wick_body = _safe_div(lower_wick, safe_body, 0.0, mintick)
            upper_wick_atr = _safe_div(upper_wick, safe_prior_atr, 0.0, mintick)
            lower_wick_atr = _safe_div(lower_wick, safe_prior_atr, 0.0, mintick)
            gap_abs = abs(o - self._rows[i - 1]["close"]) if i > 0 and self._valid[i - 1] else 0.0
            gap_atr = _safe_div(gap_abs, safe_prior_atr, 0.0, mintick)
            bull = c > o
            bear = c < o
            range_to_atr_series[i] = range_to_atr
            body_to_atr_series[i] = body_to_atr

            flow_ready = valid_range(i - FLOW_LENGTH, i)
            local_ready = valid_range(i - LOCAL_CONTEXT_LENGTH, i - 1)
            compression_ready = valid_range(i - 5, i)
            minimum_history_ready = i >= MINIMUM_HISTORY_BARS - 1
            atr_ready = atr[i] is not None and prior_atr is not None
            previous_ready = i >= 1 and self._valid[i - 1]
            data_ready = minimum_history_ready and atr_ready and previous_ready and flow_ready and compression_ready and local_ready
            imbalance_ready = data_ready and i >= 2 and self._valid[i - 2] and atr[i - 2] is not None
            m["data_ready"] = data_ready
            if not data_ready:
                continue

            green_share = sum(self._rows[j]["close"] > self._rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
            red_share = sum(self._rows[j]["close"] < self._rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
            higher_close_share = sum(self._rows[j]["close"] > self._rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
            lower_close_share = sum(self._rows[j]["close"] < self._rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
            net_progress = c - self._rows[i - FLOW_LENGTH]["close"]
            net_progress_atr = _safe_div(net_progress, atr[i] or mintick, 0.0, mintick)
            path = sum(abs(self._rows[j]["close"] - self._rows[j - 1]["close"]) for j in range(i - 3, i + 1))
            directional_efficiency = _safe_div(abs(net_progress), path, 0.0, mintick)
            prev_local_high = max(self._rows[j]["high"] for j in range(i - LOCAL_CONTEXT_LENGTH, i))
            prev_local_low = min(self._rows[j]["low"] for j in range(i - LOCAL_CONTEXT_LENGTH, i))
            new_local_high = h >= prev_local_high
            new_local_low = l <= prev_local_low

            primitive_lower = lower_wick_body >= t.minimum_rejection_wick_body and lower_wick_atr >= t.minimum_rejection_wick_atr and close_loc >= t.rejection_close_location and lower_wick >= upper_wick * t.minimum_wick_dominance and new_local_low
            primitive_upper = upper_wick_body >= t.minimum_rejection_wick_body and upper_wick_atr >= t.minimum_rejection_wick_atr and close_loc <= 1.0 - t.rejection_close_location and upper_wick >= lower_wick * t.minimum_wick_dominance and new_local_high
            strong_buy = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location and net_progress_atr > 0.0
            strong_sell = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location and net_progress_atr < 0.0

            prev_range = max(self._rows[i - 1]["high"] - self._rows[i - 1]["low"], 0.0)
            prev_upper_zone = self._rows[i - 1]["low"] + prev_range * PREVIOUS_ZONE_UPPER_SHARE
            prev_lower_zone = self._rows[i - 1]["low"] + prev_range * PREVIOUS_ZONE_LOWER_SHARE
            buy_evidence = [bull, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc >= t.minimum_continuation_close_location, upper_wick_body <= t.maximum_opposing_wick_body, net_progress_atr >= t.minimum_continuation_progress_atr, directional_efficiency >= t.minimum_continuation_efficiency, higher_close_share >= 0.50, green_share >= 0.50, c > self._rows[i - 1]["close"], c >= self._rows[i - 1]["high"] or c >= prev_upper_zone]
            sell_evidence = [bear, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc <= 1.0 - t.minimum_continuation_close_location, lower_wick_body <= t.maximum_opposing_wick_body, net_progress_atr <= -t.minimum_continuation_progress_atr, directional_efficiency >= t.minimum_continuation_efficiency, lower_close_share >= 0.50, red_share >= 0.50, c < self._rows[i - 1]["close"], c <= self._rows[i - 1]["low"] or c <= prev_lower_zone]
            buy_veto = primitive_upper or strong_sell
            sell_veto = primitive_lower or strong_buy
            buy_flow_count = sum(buy_evidence[5:])
            sell_flow_count = sum(sell_evidence[5:])
            buy_base = bull and (buy_evidence[1] or buy_evidence[2]) and (buy_evidence[3] or (close_loc >= RETENTION_CLOSE_FLOOR and buy_evidence[4])) and buy_flow_count >= 2 and sum(buy_evidence) >= t.continuation_evidence_minimum and not buy_veto
            sell_base = bear and (sell_evidence[1] or sell_evidence[2]) and (sell_evidence[3] or (close_loc <= 1.0 - RETENTION_CLOSE_FLOOR and sell_evidence[4])) and sell_flow_count >= 2 and sum(sell_evidence) >= t.continuation_evidence_minimum and not sell_veto
            if buy_base and sell_base:
                conflict_threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
                if net_progress_atr > conflict_threshold:
                    sell_base = False
                elif net_progress_atr < -conflict_threshold:
                    buy_base = False
                else:
                    buy_base = sell_base = False
            candidate_core_buy[i] = buy_base
            candidate_core_sell[i] = sell_base

            extreme = range_to_atr >= t.shock_range_atr or body_to_atr >= t.shock_body_atr
            upper_wick_range = _safe_div(upper_wick, candle_range, 0.0, mintick)
            lower_wick_range = _safe_div(lower_wick, candle_range, 0.0, mintick)
            shock_up = extreme and bull and close_loc >= SHOCK_CLOSE_UPPER and net_progress_atr > 0
            shock_down = extreme and bear and close_loc <= SHOCK_CLOSE_LOWER and net_progress_atr < 0
            shock_directionless = extreme and body_share <= SHOCK_DIRECTIONLESS_BODY_SHARE and upper_wick_range >= SHOCK_DIRECTIONLESS_WICK_SHARE and lower_wick_range >= SHOCK_DIRECTIONLESS_WICK_SHARE and SHOCK_MIDDLE_LOW <= close_loc <= SHOCK_MIDDLE_HIGH
            prior_range_max = max(range_to_atr_series[max(0, i - 3):i], default=0.0)
            prior_body_max = max(body_to_atr_series[max(0, i - 3):i], default=0.0)
            abrupt = range_to_atr >= prior_range_max * SHOCK_JUMP_FACTOR or body_to_atr >= prior_body_max * SHOCK_JUMP_FACTOR
            pre_buy = any(candidate_core_buy[max(0, i - 3):i])
            pre_sell = any(candidate_core_sell[max(0, i - 3):i])
            one_bar_shock = (shock_up and abrupt and not pre_buy) or (shock_down and abrupt and not pre_sell) or (shock_directionless and abrupt and not pre_buy and not pre_sell)
            candidate_raw_buy[i] = buy_base and not one_bar_shock
            candidate_raw_sell[i] = sell_base and not one_bar_shock

            confirm_n = t.continuation_confirmation_bars
            buy_sequence = i >= confirm_n - 1 and all(candidate_raw_buy[i - k] for k in range(confirm_n))
            sell_sequence = i >= confirm_n - 1 and all(candidate_raw_sell[i - k] for k in range(confirm_n))
            buy_retention_close = max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - RETENTION_CLOSE_OFFSET)
            sell_retention_close = 1.0 - buy_retention_close
            retention_eff = t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR
            hard_seller = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location
            hard_buyer = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location
            buy_retention = net_progress_atr > 0 and close_loc >= buy_retention_close and directional_efficiency >= retention_eff and not primitive_upper and not hard_seller and not candidate_raw_sell[i]
            sell_retention = net_progress_atr < 0 and close_loc <= sell_retention_close and directional_efficiency >= retention_eff and not primitive_lower and not hard_buyer and not candidate_raw_buy[i]
            confirmed_buy[i] = buy_sequence and buy_retention
            confirmed_sell[i] = sell_sequence and sell_retention
            if confirmed_buy[i] and confirmed_sell[i]:
                conflict_threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
                if net_progress_atr > conflict_threshold:
                    confirmed_sell[i] = False
                elif net_progress_atr < -conflict_threshold:
                    confirmed_buy[i] = False
                else:
                    confirmed_buy[i] = confirmed_sell[i] = False

            prev_body = abs(self._rows[i - 1]["close"] - self._rows[i - 1]["open"])
            safe_prev_body = max(prev_body, mintick)
            prev_body_atr = _safe_div(prev_body, safe_prior_atr, 0.0, mintick)
            prev_body_range = _safe_div(prev_body, prev_range, 0.0, mintick)
            previous_bull = self._rows[i - 1]["close"] > self._rows[i - 1]["open"]
            previous_bear = self._rows[i - 1]["close"] < self._rows[i - 1]["open"]
            previous_doji = prev_body_range <= DOJI_BODY_SHARE or prev_body_atr <= DOJI_BODY_ATR
            body_ratio = _safe_div(body, safe_prev_body, 0.0, mintick)
            body_progress_ex_gap = max(body - gap_abs, 0.0)
            bull_coverage = o <= self._rows[i - 1]["close"] and c >= self._rows[i - 1]["open"]
            bear_coverage = o >= self._rows[i - 1]["close"] and c <= self._rows[i - 1]["open"]
            bull_large_gap_progress = body_progress_ex_gap >= prev_body * LARGE_GAP_REAL_PROGRESS_FACTOR and c >= self._rows[i - 1]["open"] + safe_prior_atr * LARGE_GAP_BREAK_ATR
            bear_large_gap_progress = body_progress_ex_gap >= prev_body * LARGE_GAP_REAL_PROGRESS_FACTOR and c <= self._rows[i - 1]["open"] - safe_prior_atr * LARGE_GAP_BREAK_ATR
            bull_gap_quality = gap_atr <= t.maximum_engulfing_gap_atr or bull_large_gap_progress
            bear_gap_quality = gap_atr <= t.maximum_engulfing_gap_atr or bear_large_gap_progress
            very_strong_bull_engulf = bull and body_to_atr >= t.minimum_engulfing_body_atr * VERY_STRONG_ENGULFING_FACTOR and body_ratio >= t.minimum_engulfing_body_ratio * VERY_STRONG_ENGULFING_RATIO_FACTOR and close_loc >= t.engulfing_close_location and directional_efficiency >= retention_eff
            very_strong_bear_engulf = bear and body_to_atr >= t.minimum_engulfing_body_atr * VERY_STRONG_ENGULFING_FACTOR and body_ratio >= t.minimum_engulfing_body_ratio * VERY_STRONG_ENGULFING_RATIO_FACTOR and close_loc <= 1.0 - t.engulfing_close_location and directional_efficiency >= retention_eff
            prev_bull_quality = prev_body_atr >= t.minimum_previous_body_atr or very_strong_bear_engulf
            prev_bear_quality = prev_body_atr >= t.minimum_previous_body_atr or very_strong_bull_engulf
            bull_micro = not previous_doji or very_strong_bull_engulf
            bear_micro = not previous_doji or very_strong_bear_engulf
            bull_context = net_progress_atr <= t.minimum_continuation_progress_atr * ENGULFING_NEUTRAL_FLOW_FACTOR or new_local_low or primitive_lower or very_strong_bull_engulf
            bear_context = net_progress_atr >= -t.minimum_continuation_progress_atr * ENGULFING_NEUTRAL_FLOW_FACTOR or new_local_high or primitive_upper or very_strong_bear_engulf
            bull_engulf = previous_bear and bull and bull_coverage and body_to_atr >= t.minimum_engulfing_body_atr and prev_bear_quality and body_ratio >= t.minimum_engulfing_body_ratio and close_loc >= t.engulfing_close_location and bull_gap_quality and bull_micro and bull_context
            bear_engulf = previous_bull and bear and bear_coverage and body_to_atr >= t.minimum_engulfing_body_atr and prev_bull_quality and body_ratio >= t.minimum_engulfing_body_ratio and close_loc <= 1.0 - t.engulfing_close_location and bear_gap_quality and bear_micro and bear_context
            m["bullish_engulfing"] = bull_engulf
            m["bearish_engulfing"] = bear_engulf
            if bull_engulf:
                m["bullish_engulfing_quality"] = _clamp(_ratio_score(body_to_atr, t.minimum_engulfing_body_atr, mintick) * 0.25 + _ratio_score(body_ratio, t.minimum_engulfing_body_ratio, mintick) * 0.20 + _clamp(close_loc * 100.0, 0.0, 100.0) * 0.20 + 15.0 + 10.0 + 10.0, 0.0, 100.0)
            if bear_engulf:
                m["bearish_engulfing_quality"] = _clamp(_ratio_score(body_to_atr, t.minimum_engulfing_body_atr, mintick) * 0.25 + _ratio_score(body_ratio, t.minimum_engulfing_body_ratio, mintick) * 0.20 + _clamp((1.0 - close_loc) * 100.0, 0.0, 100.0) * 0.20 + 15.0 + 10.0 + 10.0, 0.0, 100.0)
            swallowed_lower = min(self._rows[i - 1]["open"], self._rows[i - 1]["close"])
            swallowed_upper = max(self._rows[i - 1]["open"], self._rows[i - 1]["close"])
            swallowed_size = swallowed_upper - swallowed_lower
            m["swallowed_lower"], m["swallowed_upper"], m["swallowed_size"] = swallowed_lower, swallowed_upper, swallowed_size
            m["swallowed_atr"] = _safe_div(swallowed_size, safe_prior_atr, 0.0, mintick)

            lower_rejection = primitive_lower and not strong_sell and not confirmed_sell[i] and close_loc > SHOCK_CLOSE_LOWER
            upper_rejection = primitive_upper and not strong_buy and not confirmed_buy[i] and close_loc < SHOCK_CLOSE_UPPER
            if lower_rejection and upper_rejection:
                lower_dom = lower_wick >= upper_wick * REJECTION_CONFLICT_MARGIN
                upper_dom = upper_wick >= lower_wick * REJECTION_CONFLICT_MARGIN
                if lower_dom and not upper_dom:
                    upper_rejection = False
                elif upper_dom and not lower_dom:
                    lower_rejection = False
                else:
                    lower_rejection = upper_rejection = False

            if not imbalance_ready:
                continue
            bull_geom = l > self._rows[i - 2]["high"]
            bear_geom = h < self._rows[i - 2]["low"]
            bull_lower = self._rows[i - 2]["high"] if bull_geom else math.nan
            bull_upper = l if bull_geom else math.nan
            bear_lower = h if bear_geom else math.nan
            bear_upper = self._rows[i - 2]["low"] if bear_geom else math.nan
            bull_gap_size = bull_upper - bull_lower if bull_geom else 0.0
            bear_gap_size = bear_upper - bear_lower if bear_geom else 0.0
            formation_atr = atr[i - 1] or mintick
            safe_formation_atr = max(formation_atr, mintick)
            m["formation_atr"] = formation_atr
            bull_gap_atr = _safe_div(bull_gap_size, safe_formation_atr, 0.0, mintick)
            bear_gap_atr = _safe_div(bear_gap_size, safe_formation_atr, 0.0, mintick)
            middle = self._rows[i - 1]
            middle_range = max(middle["high"] - middle["low"], 0.0)
            middle_body = abs(middle["close"] - middle["open"])
            middle_body_atr = _safe_div(middle_body, safe_formation_atr, 0.0, mintick)
            middle_body_share = _safe_div(middle_body, middle_range, 0.0, mintick)
            middle_close_loc = 0.5 if middle_range <= 1e-10 else _safe_div(middle["close"] - middle["low"], middle_range, 0.5, mintick)
            middle_bull = middle["close"] > middle["open"]
            middle_bear = middle["close"] < middle["open"]
            three_progress = c - self._rows[i - 2]["close"]
            three_progress_atr = _safe_div(three_progress, safe_formation_atr, 0.0, mintick)
            three_path = abs(middle["close"] - self._rows[i - 2]["close"]) + abs(c - middle["close"])
            three_eff = _safe_div(abs(three_progress), three_path, 0.0, mintick)
            opening_gap = abs(middle["open"] - self._rows[i - 2]["close"])
            opening_gap_atr = _safe_div(opening_gap, safe_formation_atr, 0.0, mintick)
            large_open_gap = opening_gap_atr > t.maximum_fvg_opening_gap_atr
            bull_size_pass = bull_gap_atr >= t.minimum_fvg_size_atr
            bear_size_pass = bear_gap_atr >= t.minimum_fvg_size_atr
            body_atr_pass = middle_body_atr >= t.minimum_displacement_body_atr
            body_share_pass = middle_body_share >= t.minimum_displacement_body_share
            bull_middle_close = middle_close_loc >= t.minimum_displacement_close_location
            bear_middle_close = middle_close_loc <= 1.0 - t.minimum_displacement_close_location
            bull_displacement = middle_bull and body_atr_pass and body_share_pass and bull_middle_close
            bear_displacement = middle_bear and body_atr_pass and body_share_pass and bear_middle_close
            bull_progress_pass = three_progress_atr >= t.minimum_fvg_progress_atr
            bear_progress_pass = three_progress_atr <= -t.minimum_fvg_progress_atr
            eff_pass = three_eff >= t.minimum_fvg_efficiency
            bull_accept = bull_geom and c >= bull_upper
            bear_accept = bear_geom and c <= bear_lower
            bull_invalid = bull_geom and c <= bull_lower
            bear_invalid = bear_geom and c >= bear_upper
            bull_direction = bull_progress_pass and eff_pass and bull_accept
            bear_direction = bear_progress_pass and eff_pass and bear_accept
            bull_extra = middle_body_atr >= t.minimum_displacement_body_atr * FVG_DISPLACEMENT_EXTRA_FACTOR and three_progress_atr >= t.minimum_fvg_progress_atr * FVG_PROGRESS_EXTRA_FACTOR and bull_gap_atr >= t.minimum_fvg_size_atr * FVG_SIZE_EXTRA_FACTOR and bull_accept
            bear_extra = middle_body_atr >= t.minimum_displacement_body_atr * FVG_DISPLACEMENT_EXTRA_FACTOR and three_progress_atr <= -t.minimum_fvg_progress_atr * FVG_PROGRESS_EXTRA_FACTOR and bear_gap_atr >= t.minimum_fvg_size_atr * FVG_SIZE_EXTRA_FACTOR and bear_accept
            bull_defense = not large_open_gap or bull_extra
            bear_defense = not large_open_gap or bear_extra
            bull_evidence = sum([bull_geom, bull_size_pass, middle_bull, body_atr_pass, body_share_pass, bull_middle_close, bull_progress_pass, eff_pass, bull_accept, not bull_invalid]) if bull_geom else 0
            bear_evidence = sum([bear_geom, bear_size_pass, middle_bear, body_atr_pass, body_share_pass, bear_middle_close, bear_progress_pass, eff_pass, bear_accept, not bear_invalid]) if bear_geom else 0
            bull_disp_evidence = sum([middle_bull, body_atr_pass, body_share_pass, bull_middle_close])
            bear_disp_evidence = sum([middle_bear, body_atr_pass, body_share_pass, bear_middle_close])
            bull_alignment = confirmed_buy[i] or bull_engulf or lower_rejection or (bull and close_loc >= t.minimum_continuation_close_location)
            bear_alignment = confirmed_sell[i] or bear_engulf or upper_rejection or (bear and close_loc <= 1.0 - t.minimum_continuation_close_location)
            bull_counter_absent = not confirmed_sell[i] and not bear_engulf and not upper_rejection
            bear_counter_absent = not confirmed_buy[i] and not bull_engulf and not lower_rejection
            bull_embedded = (5.0 if bull_alignment else 0.0) + (5.0 if bull_counter_absent else 0.0) if bull_geom else 0.0
            bear_embedded = (5.0 if bear_alignment else 0.0) + (5.0 if bear_counter_absent else 0.0) if bear_geom else 0.0

            def fvg_quality(is_bull: bool) -> float:
                geom = bull_geom if is_bull else bear_geom
                if not geom:
                    return 0.0
                gap_metric = bull_gap_atr if is_bull else bear_gap_atr
                close_metric = middle_close_loc if is_bull else 1.0 - middle_close_loc
                progress_metric = max(three_progress_atr, 0.0) if is_bull else max(-three_progress_atr, 0.0)
                defense = bull_defense if is_bull else bear_defense
                invalid = bull_invalid if is_bull else bear_invalid
                alignment = bull_alignment if is_bull else bear_alignment
                counter_absent = bull_counter_absent if is_bull else bear_counter_absent
                return _clamp(_ratio_score(gap_metric, t.minimum_fvg_size_atr, mintick) * 0.15 + _ratio_score(middle_body_atr, t.minimum_displacement_body_atr, mintick) * 0.15 + _ratio_score(middle_body_share, t.minimum_displacement_body_share, mintick) * 0.12 + _ratio_score(close_metric, t.minimum_displacement_close_location, mintick) * 0.12 + _ratio_score(progress_metric, t.minimum_fvg_progress_atr, mintick) * 0.12 + _ratio_score(three_eff, t.minimum_fvg_efficiency, mintick) * 0.12 + (12.0 if defense and not invalid else 0.0) + (5.0 if alignment else 0.0) + (5.0 if counter_absent else 0.0), 0.0, 100.0)

            bull_quality = fvg_quality(True)
            bear_quality = fvg_quality(False)
            min_candidate_evidence = max(t.minimum_fvg_evidence - 1, 5)
            min_candidate_quality = max(t.minimum_fvg_quality - FVG_CANDIDATE_QUALITY_OFFSET, 30.0)
            bull_candidate_size = bull_gap_atr >= t.minimum_fvg_size_atr * FVG_CANDIDATE_SIZE_FACTOR
            bear_candidate_size = bear_gap_atr >= t.minimum_fvg_size_atr * FVG_CANDIDATE_SIZE_FACTOR
            bull_candidate_direction = three_progress_atr > 0.0 and bull_accept
            bear_candidate_direction = three_progress_atr < 0.0 and bear_accept
            bull_active = imbalance_ready and bull_geom and bull_size_pass and bull_displacement and bull_direction and bull_defense and not bull_invalid and bull_evidence >= t.minimum_fvg_evidence and bull_quality >= t.minimum_fvg_quality
            bear_active = imbalance_ready and bear_geom and bear_size_pass and bear_displacement and bear_direction and bear_defense and not bear_invalid and bear_evidence >= t.minimum_fvg_evidence and bear_quality >= t.minimum_fvg_quality
            bull_candidate = imbalance_ready and bull_geom and not bull_active and bull_candidate_size and bull_disp_evidence >= 3 and bull_candidate_direction and bull_defense and not bull_invalid and bull_evidence >= min_candidate_evidence and bull_quality >= min_candidate_quality
            bear_candidate = imbalance_ready and bear_geom and not bear_active and bear_candidate_size and bear_disp_evidence >= 3 and bear_candidate_direction and bear_defense and not bear_invalid and bear_evidence >= min_candidate_evidence and bear_quality >= min_candidate_quality
            m.update({"bullish_fvg_active": bull_active, "bearish_fvg_active": bear_active, "bullish_fvg_candidate": bull_candidate, "bearish_fvg_candidate": bear_candidate, "bullish_fvg_quality": bull_quality, "bearish_fvg_quality": bear_quality, "bull_fvg_lower": bull_lower, "bull_fvg_upper": bull_upper, "bear_fvg_lower": bear_lower, "bear_fvg_upper": bear_upper, "bull_fvg_gap_size": bull_gap_size, "bear_fvg_gap_size": bear_gap_size, "bull_fvg_gap_atr": bull_gap_atr, "bear_fvg_gap_atr": bear_gap_atr, "bull_embedded_contribution": bull_embedded, "bear_embedded_contribution": bear_embedded, "bull_fvg_evidence": bull_evidence, "bear_fvg_evidence": bear_evidence})

        return out

    def _lifecycle_metrics(self, i: int) -> _LifecycleMetrics:
        rows = self._rows
        t = self._thresholds
        tick = self.config.minimum_tick
        r = rows[i]
        o, h, l, c = r["open"], r["high"], r["low"], r["close"]
        candle_range = max(h - l, 0.0)
        body = abs(c - o)
        bull, bear = c > o, c < o
        close_loc = 0.5 if candle_range <= 1e-10 else _safe_div(c - l, candle_range, 0.5, tick)

        tr: list[float | None] = []
        for j, bar in enumerate(rows):
            if not self._valid[j]:
                tr.append(None)
                continue
            prev = rows[j - 1]["close"] if j > 0 and self._valid[j - 1] else None
            value = bar["high"] - bar["low"]
            if prev is not None:
                value = max(value, abs(bar["high"] - prev), abs(bar["low"] - prev))
            tr.append(max(value, 0.0))
        atr = _rma(tr, ATR_LENGTH)
        prior_atr = atr[i - 1] if i > 0 and atr[i - 1] is not None else tick
        safe_prior_atr = max(prior_atr, tick)
        body_to_atr = _safe_div(body, safe_prior_atr, 0.0, tick)
        net_progress = c - rows[i - FLOW_LENGTH]["close"]
        net_progress_atr = _safe_div(net_progress, atr[i] or tick, 0.0, tick)
        path = sum(abs(rows[j]["close"] - rows[j - 1]["close"]) for j in range(i - 3, i + 1))
        efficiency = _safe_div(abs(net_progress), path, 0.0, tick)
        higher_share = sum(rows[j]["close"] > rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
        lower_share = sum(rows[j]["close"] < rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0

        current_series = self._calculate_series()
        m = current_series[i]
        bull_engulf = bool(m["bullish_engulfing"])
        bear_engulf = bool(m["bearish_engulfing"])
        upper_wick = max(h - max(o, c), 0.0)
        lower_wick = max(min(o, c) - l, 0.0)
        safe_body = max(body, tick)
        upper_wick_body = _safe_div(upper_wick, safe_body, 0.0, tick)
        lower_wick_body = _safe_div(lower_wick, safe_body, 0.0, tick)
        upper_wick_atr = _safe_div(upper_wick, safe_prior_atr, 0.0, tick)
        lower_wick_atr = _safe_div(lower_wick, safe_prior_atr, 0.0, tick)
        prev_high = max(rows[j]["high"] for j in range(i - 4, i))
        prev_low = min(rows[j]["low"] for j in range(i - 4, i))
        primitive_lower = lower_wick_body >= t.minimum_rejection_wick_body and lower_wick_atr >= t.minimum_rejection_wick_atr and close_loc >= t.rejection_close_location and lower_wick >= upper_wick * t.minimum_wick_dominance and l <= prev_low
        primitive_upper = upper_wick_body >= t.minimum_rejection_wick_body and upper_wick_atr >= t.minimum_rejection_wick_atr and close_loc <= 1.0 - t.rejection_close_location and upper_wick >= lower_wick * t.minimum_wick_dominance and h >= prev_high
        strong_buy = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location and net_progress_atr > 0
        strong_sell = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location and net_progress_atr < 0
        prev = rows[i - 1]
        prev_range = max(prev["high"] - prev["low"], 0.0)
        body_share = _safe_div(body, candle_range, 0.0, tick)
        green_share = sum(rows[j]["close"] > rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
        red_share = sum(rows[j]["close"] < rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
        buy_e = [bull, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc >= t.minimum_continuation_close_location, upper_wick_body <= t.maximum_opposing_wick_body, net_progress_atr >= t.minimum_continuation_progress_atr, efficiency >= t.minimum_continuation_efficiency, higher_share >= .5, green_share >= .5, c > prev["close"], c >= prev["high"] or c >= prev["low"] + prev_range * .70]
        sell_e = [bear, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc <= 1.0 - t.minimum_continuation_close_location, lower_wick_body <= t.maximum_opposing_wick_body, net_progress_atr <= -t.minimum_continuation_progress_atr, efficiency >= t.minimum_continuation_efficiency, lower_share >= .5, red_share >= .5, c < prev["close"], c <= prev["low"] or c <= prev["low"] + prev_range * .30]
        buy_base = bull and (buy_e[1] or buy_e[2]) and (buy_e[3] or (close_loc >= RETENTION_CLOSE_FLOOR and buy_e[4])) and sum(buy_e[5:]) >= 2 and sum(buy_e) >= t.continuation_evidence_minimum and not (primitive_upper or strong_sell)
        sell_base = bear and (sell_e[1] or sell_e[2]) and (sell_e[3] or (close_loc <= 1.0 - RETENTION_CLOSE_FLOOR and sell_e[4])) and sum(sell_e[5:]) >= 2 and sum(sell_e) >= t.continuation_evidence_minimum and not (primitive_lower or strong_buy)
        if buy_base and sell_base:
            threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
            if net_progress_atr > threshold:
                sell_base = False
            elif net_progress_atr < -threshold:
                buy_base = False
            else:
                buy_base = sell_base = False
        extreme = (candle_range / safe_prior_atr >= t.shock_range_atr) or (body_to_atr >= t.shock_body_atr)
        one_bar_shock = extreme and ((bull and close_loc >= SHOCK_CLOSE_UPPER and net_progress_atr > 0) or (bear and close_loc <= SHOCK_CLOSE_LOWER and net_progress_atr < 0) or (body_share <= SHOCK_DIRECTIONLESS_BODY_SHARE and SHOCK_MIDDLE_LOW <= close_loc <= SHOCK_MIDDLE_HIGH))
        buy_candidate = buy_base and not one_bar_shock
        sell_candidate = sell_base and not one_bar_shock
        buy_confirmed = buy_candidate and close_loc >= max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - .12) and efficiency >= t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR and net_progress_atr > 0
        sell_confirmed = sell_candidate and close_loc <= 1.0 - max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - .12) and efficiency >= t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR and net_progress_atr < 0
        return _LifecycleMetrics(c, l, h, bull, bear, close_loc, body_to_atr, net_progress_atr, efficiency, higher_share, lower_share, buy_candidate, sell_candidate, buy_confirmed, sell_confirmed, primitive_lower, primitive_upper, bull_engulf, bear_engulf)

    def _repair_candidate_alignment(self, idx: int, metrics: _LifecycleMetrics) -> None:
        candidates = [formation for formation in self._fvg_formations if formation.formation_index == idx]
        if not candidates:
            return
        for formation in candidates:
            if formation.direction is FvgDirection.BULLISH:
                aligned = metrics.buy_continuation_confirmed or metrics.buy_continuation_candidate or metrics.bullish_engulfing or metrics.lower_rejection or (metrics.candle_bullish and metrics.close_location >= self._thresholds.minimum_continuation_close_location)
                counter_absent = not metrics.sell_continuation_confirmed and not metrics.bearish_engulfing and not metrics.upper_rejection
            else:
                aligned = metrics.sell_continuation_confirmed or metrics.sell_continuation_candidate or metrics.bearish_engulfing or metrics.upper_rejection or (metrics.candle_bearish and metrics.close_location <= 1.0 - self._thresholds.minimum_continuation_close_location)
                counter_absent = not metrics.buy_continuation_confirmed and not metrics.bullish_engulfing and not metrics.lower_rejection
            expected_embedded = (5.0 if aligned else 0.0) + (5.0 if counter_absent else 0.0)
            delta = expected_embedded - formation.embedded_candle_contribution
            if abs(delta) <= 1e-12:
                continue
            position = self._fvg_formations.index(formation)
            self._fvg_formations[position] = replace(formation, quality=max(0.0, min(100.0, formation.quality + delta)), embedded_candle_contribution=expected_embedded)
