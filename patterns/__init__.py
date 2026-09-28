# --- PATTERNS PAKETİ ---
# ARGENT v0.4.6 FINAL EXPORT Pine Script'in Python'a birebir çevirisi.
# Tek dosya yerine modüler yapı (kullanıcı isteği):
#
#   constants.py  — state sabitleri + tip yardımcıları (EXPORT contract ÇEVİLMEDİ)
#   indicators.py — ta.atr (Wilder RMA, SMA tohumlu) + ta.sma
#   mathutil.py   — f_clamp/smoothstep/band/line_price/breakout_strength
#   pivots.py     — pivot kabul motoru (aynı-bar çift pivot çözümü dahil)
#   pole.py       — direk motoru (path stats, local extreme break)
#   violation.py  — sınır ihlal taraması + ceza + cache
#   candidate.py  — f_build_candidate + refresh + freeze/snapshot (S1 survival dahil)
#   selection.py  — selection priority (recency/proximity/continuity) + replacement
#   lifecycle.py  — bar-bar motor (ArgentEngine) + PatternLifecycleManager
#   detect.py     — yüksek seviye API + eski batch sarmalayıcılar
#   legacy.py     — eski f_build_triangle_candidate imzası (diagnostic uyumu)

from .constants import (PATTERN_TYPE_MAP, ST_BREAK_ATTEMPT, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED,
                        ST_BREAK_FAILED, ST_BREAK_TIMEOUT, ST_CANDIDATE, ST_COMPLETED, ST_COMPRESSING,
                        ST_DEFINED, ST_GEOMETRY, ST_INVALID, ST_MATURING, ST_NONE, ST_PREP,
                        ST_RETESTING, ST_RETEST_OK, ST_RETEST_WAIT, ST_WEAK,
                        f_classic_direction, f_is_break_lifecycle, f_is_flag, f_is_pennant,
                        f_is_specialized, f_is_terminal)
from .indicators import calculate_atr, calculate_sma
from .mathutil import (f_age_quality, f_band_quality, f_cleanliness_quality, f_clamp,
                       f_contraction_quality, f_depth_quality, f_duration_quality,
                       f_inverse_smoothstep, f_line_price, f_progress_quality, f_slope,
                       f_smoothstep)
from .pivots import PivotSide, find_pivots
from .pole import PoleInfo, find_pole
from .candidate import (PatternCandidate, build_candidate, effective_raw_quality,
                        freeze_pattern_quality, hard_geometry_invalid, refresh_active_candidate,
                        reset_quality_snapshot)
from .selection import (candidate_preferred, continuity_score, quality_priority_gap,
                        replacement_margin, selection_score)
from .lifecycle import ArgentEngine, EngineSnapshot, PatternLifecycleManager
from .detect import (create_mock_data, detect_patterns, find_best_flag_candidate,
                     find_best_triangle_candidate, run_engine, scan_for_first_detection)
from .legacy import f_build_triangle_candidate, find_pole

__all__ = [
    # sabitler
    "PATTERN_TYPE_MAP",
    "ST_NONE", "ST_CANDIDATE", "ST_GEOMETRY", "ST_DEFINED", "ST_MATURING", "ST_COMPRESSING",
    "ST_PREP", "ST_BREAK_ATTEMPT", "ST_BREAK_CANDIDATE", "ST_BREAK_CONFIRMED", "ST_RETEST_WAIT",
    "ST_RETESTING", "ST_RETEST_OK", "ST_BREAK_TIMEOUT", "ST_BREAK_FAILED", "ST_WEAK", "ST_INVALID",
    "ST_COMPLETED",
    "f_classic_direction", "f_is_break_lifecycle", "f_is_flag", "f_is_pennant",
    "f_is_specialized", "f_is_terminal",
    # göstergeler
    "calculate_atr", "calculate_sma",
    # matematik
    "f_age_quality", "f_band_quality", "f_cleanliness_quality", "f_clamp", "f_contraction_quality",
    "f_depth_quality", "f_duration_quality", "f_inverse_smoothstep", "f_line_price",
    "f_progress_quality", "f_slope", "f_smoothstep",
    # pivot / direk
    "PivotSide", "find_pivots", "PoleInfo", "find_pole",
    # aday
    "PatternCandidate", "build_candidate", "effective_raw_quality", "freeze_pattern_quality",
    "hard_geometry_invalid", "refresh_active_candidate", "reset_quality_snapshot",
    # seçim
    "candidate_preferred", "continuity_score", "quality_priority_gap", "replacement_margin",
    "selection_score",
    # motor + yönetici
    "ArgentEngine", "EngineSnapshot", "PatternLifecycleManager",
    # yüksek seviye + legacy
    "detect_patterns", "find_best_triangle_candidate", "find_best_flag_candidate", "run_engine",
    "create_mock_data", "f_build_triangle_candidate",
]
