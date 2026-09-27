# --- İHLAL (VIOLATION) TARAMASI ---
# Pine: f_violation_penalty_from_stats + f_boundary_violation_stats_range + ihlal cache'i.
# Cache'in sonuç-equivalance'ı korunuyor: aynı geometri için tam tarama bir kez, sonra delta.

from typing import Dict, List, Optional, Tuple

from .mathutil import f_clamp, f_line_price

CLOSE_BUF_MULT = {"Hassas": 0.05, "Seçici": 0.07, "Dengeli": 0.06}
WICK_BUF_MULT = {"Hassas": 0.13, "Seçici": 0.18, "Dengeli": 0.15}
CLOSE_PENALTY = {"Hassas": 10.0, "Seçici": 16.0, "Dengeli": 13.0}
WICK_PENALTY = {"Hassas": 3.0, "Seçici": 7.0, "Dengeli": 5.0}
MAX_ACCEPTED_VIOLATION = {"Hassas": 0.90, "Seçici": 0.55, "Dengeli": 0.72}


def violation_penalty_from_stats(total_close_violations: int, total_wick_violations: int,
                                 maximum_violation: float, history_truncated: bool,
                                 profile: str) -> float:
    """Pine: f_violation_penalty_from_stats."""
    close_penalty = CLOSE_PENALTY.get(profile, 13.0)
    wick_penalty = WICK_PENALTY.get(profile, 5.0)
    repeat_penalty = 10.0 if total_close_violations >= 2 else 0.0
    truncation_penalty = 4.0 if history_truncated else 0.0
    return f_clamp(
        float(total_close_violations) * close_penalty
        + float(total_wick_violations) * wick_penalty
        + maximum_violation * 18.0 + repeat_penalty + truncation_penalty, 0.0, 70.0)


def boundary_violation_stats_range(upper_x1: int, upper_y1: float, upper_x2: int, upper_y2: float,
                                   lower_x1: int, lower_y1: float, lower_x2: int, lower_y2: float,
                                   geometry_start_bar: int, requested_start_bar: int, requested_end_bar: int,
                                   apply_maximum_window: bool, profile: str,
                                   close: List[float], high: List[float], low: List[float],
                                   atr_array: List[float], safe_atr: float,
                                   max_violation_scan: int, max_history_offset: int,
                                   mintick: float) -> Tuple[int, int, int, int, float, float, float, int, bool]:
    """Pine: f_boundary_violation_stats_range — eğimli sınırlar boyunca tam/pencere taraması.

    Döner: (upperClose, lowerClose, upperWick, lowerWick, maxUpper, maxLower, penalty, scannedBars, truncated)
    """
    upper_close_violations = 0
    lower_close_violations = 0
    upper_wick_violations = 0
    lower_wick_violations = 0
    max_upper_violation = 0.0
    max_lower_violation = 0.0
    scanned_bars = 0

    n = len(close)
    safe_end_bar = min(requested_end_bar, n - 1)
    available_start_bar = max(requested_start_bar, max(0, (n - 1) - max_history_offset))
    scan_start_bar = max(available_start_bar, safe_end_bar - max_violation_scan + 1) if apply_maximum_window else available_start_bar
    history_truncated = apply_maximum_window and scan_start_bar > geometry_start_bar

    if safe_end_bar >= scan_start_bar:
        close_buf_mult = CLOSE_BUF_MULT.get(profile, 0.06)
        wick_buf_mult = WICK_BUF_MULT.get(profile, 0.15)
        for scan_bar in range(scan_start_bar, safe_end_bar + 1):
            if scan_bar < 0 or scan_bar >= n:
                continue
            hist_atr_raw = atr_array[scan_bar] if scan_bar < len(atr_array) else safe_atr
            if hist_atr_raw is None or hist_atr_raw != hist_atr_raw or hist_atr_raw <= 0:
                hist_atr_raw = safe_atr
            historical_atr = max(hist_atr_raw, mintick * 10.0)
            close_violation_buffer = max(mintick * 2.0, historical_atr * close_buf_mult)
            wick_violation_buffer = max(mintick * 2.0, historical_atr * wick_buf_mult)
            upper_boundary = f_line_price(upper_x1, upper_y1, upper_x2, upper_y2, scan_bar)
            lower_boundary = f_line_price(lower_x1, lower_y1, lower_x2, lower_y2, scan_bar)
            c = close[scan_bar]
            hi = high[scan_bar]
            lo = low[scan_bar]
            upper_close_broken = c > upper_boundary + close_violation_buffer
            lower_close_broken = c < lower_boundary - close_violation_buffer
            upper_wick_broken = (not upper_close_broken) and hi > upper_boundary + wick_violation_buffer
            lower_wick_broken = (not lower_close_broken) and lo < lower_boundary - wick_violation_buffer
            if upper_close_broken:
                upper_close_violations += 1
            if lower_close_broken:
                lower_close_violations += 1
            if upper_wick_broken:
                upper_wick_violations += 1
            if lower_wick_broken:
                lower_wick_violations += 1
            upper_excess = ((c - upper_boundary - close_violation_buffer) / historical_atr if upper_close_broken
                            else (hi - upper_boundary - wick_violation_buffer) / historical_atr if upper_wick_broken
                            else 0.0)
            lower_excess = ((lower_boundary - c - close_violation_buffer) / historical_atr if lower_close_broken
                            else (lower_boundary - lo - wick_violation_buffer) / historical_atr if lower_wick_broken
                            else 0.0)
            max_upper_violation = max(max_upper_violation, upper_excess)
            max_lower_violation = max(max_lower_violation, lower_excess)
            scanned_bars += 1

    total_close = upper_close_violations + lower_close_violations
    total_wick = upper_wick_violations + lower_wick_violations
    penalty = violation_penalty_from_stats(total_close, total_wick,
                                           max(max_upper_violation, max_lower_violation),
                                           history_truncated, profile)
    return (upper_close_violations, lower_close_violations, upper_wick_violations, lower_wick_violations,
            max_upper_violation, max_lower_violation, penalty, scanned_bars, history_truncated)


class ViolationCache:
    """Pine: violation cache dizileri — geometri anahtarı -> istatistik + lastProcessedBar.

    MAX_VIOLATION_CACHE dolunca en eski kayıt atılır (array.shift karşılığı).
    """

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self._data: Dict[str, Dict] = {}

    def get(self, key: str) -> Optional[Dict]:
        return self._data.get(key)

    def set(self, key: str, stats: Dict) -> None:
        if key in self._data:
            self._data[key] = stats
            return
        if len(self._data) >= self.max_entries:
            oldest = next(iter(self._data))
            self._data.pop(oldest)
        self._data[key] = stats
