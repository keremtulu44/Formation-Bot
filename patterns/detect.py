# --- YÜKSEK SEVİYE TESPİT VE GERİYE DÖNÜK (BATCH) ARAYÜZ ---
# Eski diagnostic'ler (test_*.py, collective_test.py, check_4_candidates.py) bu imzaları
# kullanıyor. Hepsi artık Pine-birebir motorun üstünde ince sarmalayıcı.

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .candidate import PatternCandidate
from .constants import ST_DEFINED, ST_NONE
from .lifecycle import ArgentEngine, EngineSnapshot, PatternLifecycleManager  # noqa: F401 (re-export)

logger = logging.getLogger(__name__)

TRIANGLE_FAMILIES = ("Üçgen", "Kama")
SPECIALIZED_FAMILIES = ("Bayrak", "Flama")

# "Tespit var" sayılacak canlı stateler. Terminal (COMPLETED/FAILED/INVALID/TIMEOUT) ve
# WEAK formlar Pine'da hayalet olarak GÖSTERİLİR ama sinyal değildir; break lifecycle'ı da
# ayrı bir olay akışıdır. Diagnostic sarmalayıcıları yalnız canlı formasyonu raporlar.
LIVE_STATES = ("ADAY_OLUSUYOR", "GEOMETRI_ADAYI", "FORMASYON_TANIMLANDI",
               "OLGUNLASIYOR", "SIKISMA_GUCLENIYOR", "KIRILIM_HAZIRLIGI")


def run_engine(df: pd.DataFrame, profile: str = "Dengeli", mintick: float = 0.01) -> EngineSnapshot:
    """Tek seferlik çalıştırma: df'in tamamını bar bar işler, son barın anlık görüntüsünü döner."""
    engine = ArgentEngine(profile=profile, mintick=mintick)
    return engine.process(df)


def _usable_active(snap: EngineSnapshot, families: Tuple[str, ...]) -> Optional[PatternCandidate]:
    """Canlı state + kalite eşiği + aile filtresi — Pine'ın 'kullanılabilir formasyon' kavramı."""
    a = snap.active
    if a is None or snap.state not in LIVE_STATES:
        return None
    min_q = (snap.min_specialized_quality if a.family in SPECIALIZED_FAMILIES else snap.min_raw_quality)
    if snap.effective_quality is None or snap.effective_quality < min_q:
        return None
    if a.family not in families:
        return None
    return a


def _logs_from_snapshot(snap: EngineSnapshot, verbose: bool) -> List[str]:
    logs = [f"Motor (Pine v0.4.6 birebir): bar {snap.bar_index}, state {snap.state}, "
            f"aktif {snap.active.pattern_type if snap.active else 'Yok'} "
            f"kalite {snap.effective_quality:.1f}" if snap.active else
            f"Motor (Pine v0.4.6 birebir): bar {snap.bar_index}, state {snap.state}, aktif Yok"]
    if verbose:
        for ev in snap.events[-8:]:
            q = f" q{ev['quality']:.0f}" if isinstance(ev.get("quality"), (int, float)) else ""
            logs.append(f"  olay: {ev['name']}{q}")
    return logs


def find_best_triangle_candidate(df: pd.DataFrame, profile: str = "Dengeli",
                                 verbose: bool = False) -> Tuple[Optional[PatternCandidate], List[str]]:
    """Eski API: canlı üçgen/kama formasyonu varsa döner (terminal hayaletler sayılmaz)."""
    snap = run_engine(df, profile)
    logs = _logs_from_snapshot(snap, verbose)
    usable = _usable_active(snap, TRIANGLE_FAMILIES)
    return (usable, logs) if usable else (None, logs)


def find_best_flag_candidate(df: pd.DataFrame, profile: str = "Dengeli",
                             verbose: bool = False) -> Tuple[Optional[PatternCandidate], List[str]]:
    """Eski API: canlı bayrak/flama formasyonu varsa döner."""
    snap = run_engine(df, profile)
    logs = _logs_from_snapshot(snap, verbose)
    usable = _usable_active(snap, SPECIALIZED_FAMILIES)
    return (usable, logs) if usable else (None, logs)


def detect_patterns(df_1h: pd.DataFrame, df_2h: Optional[pd.DataFrame] = None,
                    df_4h: Optional[pd.DataFrame] = None, df_1d: Optional[pd.DataFrame] = None,
                    stock_name: str = "", profile: str = "Dengeli",
                    verbose: bool = False) -> Optional[Dict]:
    """Ana tespit fonksiyonu — eski dict sözleşmesi korunur."""
    if df_1h is None or len(df_1h) < 50:
        logger.debug(f"{stock_name} için yetersiz veri: {0 if df_1h is None else len(df_1h)}")
        return None
    try:
        snap = run_engine(df_1h, profile)
        best = _usable_active(snap, TRIANGLE_FAMILIES + SPECIALIZED_FAMILIES)
        if best is None:
            if verbose:
                logger.info(f"{stock_name} - Formasyon yok: state {snap.state} - {snap.invalid_reason}")
            return None
        result = {
            "stock_name": stock_name,
            "timeframe": "1h",
            "pattern_name": best.pattern_type,
            "family": best.family,
            "classic_dir": best.classic_dir,
            "confidence_score": snap.effective_quality,
            "critical_price_level": best.upper_now,
            "upper_level": best.upper_now,
            "lower_level": best.lower_now,
            "contraction": best.contraction,
            "progress": best.progress,
            "apex_bar": best.apex_bar,
            "start_bar": best.start_bar,
            "end_bar": best.end_bar,
            "geometry_score": best.geometry_score,
            "touch_score": best.touch_score,
            "maturity_score": best.maturity_score,
            "contraction_score": best.contraction_score,
            "timestamp": df_1h.index[-1] if hasattr(df_1h.index[-1], "strftime") else pd.Timestamp.now(),
            "state": snap.state,
            "upper_touches": best.upper_touches,
            "lower_touches": best.lower_touches,
            "violation_penalty": best.historical_violation_penalty,
            "has_pole": best.has_pole,
            "pole_quality": best.pole_quality if best.has_pole else None,
            "break_dir": snap.break_dir,
            "events": snap.events,
            "logs": _logs_from_snapshot(snap, verbose),
        }
        logger.info(f"{stock_name} - {best.pattern_type} bulundu: kalite {snap.effective_quality:.1f} state {snap.state}")
        return result
    except Exception as e:
        logger.error(f"{stock_name} pattern tespit hatası: {e}", exc_info=True)
        return None


def scan_for_first_detection(df: pd.DataFrame, profile: str = "Dengeli",
                             families: Tuple[str, ...] = TRIANGLE_FAMILIES + SPECIALIZED_FAMILIES,
                             min_quality: Optional[float] = None) -> Tuple[Optional[Tuple[int, PatternCandidate, float]], EngineSnapshot]:
    """DataFrame'i bar bar besler; İLK canlı formasyon tespitini döner.

    Döner: ((bar, candidate, kalite) | None, son snapshot)
    Neden? Lifecycle motorunda formasyon kırılabilir/timeout olabilir; 'tespit edildi mi?'
    sorusunun doğru cevabı 'seri boyunca herhangi bir barda canlı formasyon var mı?'dır.
    """
    engine = ArgentEngine(profile=profile)
    snap = engine.process(df.head(0))
    first_hit = None
    for i in range(2 * engine.pivot_len + 1, len(df) + 1):
        snap = engine.process(df.iloc[:i])
        usable = _usable_active(snap, families)
        if usable is not None and (min_quality is None or snap.effective_quality >= min_quality):
            first_hit = (snap.bar_index, usable, snap.effective_quality)
            break
    return first_hit, snap


def create_mock_data(n_bars: int = 100) -> pd.DataFrame:
    """Test için mock OHLCV data (eski hali korundu)."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq="h")
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars) * 0.3)
    low = close - np.abs(np.random.randn(n_bars) * 0.3)
    open_ = close + np.random.randn(n_bars) * 0.1
    volume = np.random.randint(100000, 1000000, n_bars)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume},
                        index=dates)
