# --- ARGENT MOTORU (BAR-BAR YAŞAM DÖNGÜSÜ) ---
# Pine: Bölüm 17-20'nin birebir karşılığı. Pine her barı sırayla işler; bu motor da öyle yapar.
# Eski Python yaklaşımı (tüm DataFrame'i son barda toplu tarama + adayı her seferinde yeniden
# bulma) Teşhis A1/A2/A3 hatalarının kök nedeniydi. Bu motor:
#   * pivotları Pine kurallarıyla bar bar kabul eder (aynı-bar çift pivot dahil),
#   * yeni pivot geldiğinde 6x6 pivot kombinasyonunu tarar, selection priority ile seçer,
#   * aktif formasyonu her bar hafifçe günceller (violation incremental),
#   * kırılım anında kaliteyi dondurur ve yaşam döngüsü boyunca KIRILIM ÇİZGİSİNİ (pivotlar)
#     ve dondurulmuş buffer/toleransı kullanır — dışarıdan gelen yeni adayla KARŞIŞTIRMAZ,
#   * timeout/failed/invalid/completed/weak/geometry state'lerini üretir.
#
# EXPORT contract (f_export_* plotları) ve alertcondition/alert çağrıları bilerek çevrilmedi;
# bunun yerine Python dostu `events` listesi üretilir (notifier kullanır).

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .candidate import (PatternCandidate, build_candidate, effective_raw_quality,
                        effective_break_buffer, effective_retest_tolerance,
                        freeze_pattern_quality, hard_geometry_invalid,
                        refresh_active_candidate, reset_quality_snapshot)
from .constants import (ST_BREAK_ATTEMPT, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_BREAK_FAILED,
                        ST_BREAK_TIMEOUT, ST_CANDIDATE, ST_COMPLETED, ST_COMPRESSING, ST_DEFINED,
                        ST_GEOMETRY, ST_INVALID, ST_MATURING, ST_NONE, ST_PREP, ST_RETESTING,
                        ST_RETEST_OK, ST_RETEST_WAIT, ST_WEAK, f_is_dead_state,
                        f_is_break_lifecycle, f_is_flag, f_is_pennant, f_is_specialized, f_is_terminal)
from .indicators import calculate_atr, volume_sma_series
from .mathutil import (f_age_quality, f_cleanliness_quality, f_clamp, f_contraction_quality,
                       f_depth_quality, f_duration_quality, f_inverse_smoothstep, f_line_price,
                       f_progress_quality, f_smoothstep, f_breakout_strength)
from .pivots import PivotSide, choose_same_bar_pivot, is_pivot_high, is_pivot_low
from .pole import PoleInfo, efficiency_between, find_pole, range_between
from .selection import (candidate_preferred, continuity_score, identity_compatible,
                        quality_priority_gap, replacement_margin, same_completed_structure,
                        selection_score)
from .violation import MAX_ACCEPTED_VIOLATION, ViolationCache

# === PHASE 1: Persistent Formation Identity yardımcıları ====================
# Formation matematiğine, geometriye, kaliteye, continuity_score eşiklerine
# veya lifecycle state geçişlerine DOKUNMAZ. Yalnız mevcut `identity_compatible`
# + `continuity_score` (değiştirilmemiş eşiklerle) ile restart re-attach yapar.

def _new_stable_id() -> str:
    """Yeni formation için benzersiz, restart-safe UUID (motor-içi `identity` ayrıdır)."""
    return str(uuid.uuid4())


def _parse_stock_tf(key: str):
    """Manager anahtarı ``STOCK_TF`` -> (stock, tf). Sembol '_' içermez varsayımı."""
    stock, tf = key.rsplit("_", 1)
    return stock, tf


def _match_persisted_anchor(engine, candidate: "PatternCandidate") -> Optional[str]:
    """Restart sonrası: (stock,tf) anchor'ıyla `candidate`'ı eşleştir.

    Eşleşme için mevcut kurallar kullanılır (eşik DEĞİŞTİRİLMEDİ):
      * identity_compatible (family + classic_dir)
      * continuity_score >= 60
    Uyum sağlanırsa eski stable_id döner, yoksa None.
    """
    key = getattr(engine, "_key", None)
    if not key:
        return None
    stock, tf = _parse_stock_tf(key)
    from state import formation_identity as fid
    anchor = fid.load_anchor(stock, tf)
    if not anchor:
        return None
    # Eksik/bozuk anchor (eski yazım, elle düzenleme): eşleştirme denenmez,
    # formation gerçekten yeni kabul edilir. `continuity_score` bar farkı
    # hesabı yaptığı için start_bar şart; family ise identity_compatible şartı.
    if not anchor.get("stable_id") or not anchor.get("family"):
        return None
    if not isinstance(anchor.get("start_bar"), int):
        return None
    prev = PatternCandidate()
    prev.valid = True
    prev.family = anchor.get("family")
    prev.classic_dir = anchor.get("classic_dir") or 0
    prev.pattern_type = anchor.get("pattern_type")
    prev.start_bar = anchor.get("start_bar")
    prev.apex_bar = anchor.get("apex_bar")
    prev.hb1, prev.hb2 = anchor.get("hb1"), anchor.get("hb2")
    prev.lb1, prev.lb2 = anchor.get("lb1"), anchor.get("lb2")
    prev.hp1, prev.hp2 = anchor.get("hp1"), anchor.get("hp2")
    prev.lp1, prev.lp2 = anchor.get("lp1"), anchor.get("lp2")
    if not identity_compatible(prev, candidate):
        return None
    if continuity_score(engine, prev, candidate) >= 60.0:
        return anchor.get("stable_id")
    return None


def _match_registry(engine, candidate: "PatternCandidate") -> Optional[str]:
    """Faz 2.1: history defterinden candidate ile aynı formation'ın stable_id'si.

    Faz 1'in tek slot'lu anchor'una kıyasla iki iyileştirme taşır:
      1) (stock,tf) başına birden fazla kayıt -> aynı penceredeki 2. formasyon
         doğru kimliğine ulaşır,
      2) bar-time alignment -> pencere kaydıkça bar indeksleri kayar;
         kayıtlar doğum barının MUTLAK zamanından hizalanır.

    Eşleşme kuralları AYNEN korunur (eşik DEĞİŞTİRİLMEDİ):
      * identity_compatible (family + classic_dir)
      * continuity_score >= 60
    Ek güvenlik: terminal kayıtlar asla eşleşmez ve doğum barı pencerede
    olmayan kayıtlar atlanır. Registry boş/bozuk/hatalı ise None döner ve
    çağıran Faz 1 anchor yoluna düşer.
    """
    try:
        from state import formation_history as fh
    except Exception:
        return None
    key = getattr(engine, "_key", None)
    if not key:
        return None
    stock, tf = _parse_stock_tf(key)
    kullanilan = getattr(engine, "_p2_kullanilan", None)
    return fh.eslestir(engine, candidate, kullanilan=kullanilan, stock=stock, tf=tf)


def _save_formation_anchor(engine, candidate: "PatternCandidate") -> None:
    """Mevcut formation'ın minimum anchor'unu (stock,tf) anahtarıyla sakla."""
    key = getattr(engine, "_key", None)
    if not key or not candidate.valid or not candidate.stable_id:
        return
    stock, tf = _parse_stock_tf(key)
    birth_bar_time = None
    try:
        sb = candidate.start_bar
        if sb is not None and getattr(engine, "index_values", None) is not None \
                and 0 <= sb < len(engine.index_values):
            birth_bar_time = str(engine.index_values[sb])
    except Exception:
        birth_bar_time = None
    from state import formation_identity as fid
    fid.save_anchor({
        "stable_id": candidate.stable_id,
        "stock": stock,
        "timeframe": tf,
        "family": candidate.family,
        "classic_dir": candidate.classic_dir,
        "pattern_type": candidate.pattern_type,
        "start_bar": candidate.start_bar,
        "apex_bar": candidate.apex_bar,
        "hb1": candidate.hb1, "hb2": candidate.hb2,
        "lb1": candidate.lb1, "lb2": candidate.lb2,
        "hp1": candidate.hp1, "hp2": candidate.hp2,
        "lp1": candidate.lp1, "lp2": candidate.lp2,
        "birth_bar_time": birth_bar_time,
    })

try:
    from config import get_profile_params
except ImportError:  # patterns paketi bağımsız da kullanılabilsin
    def get_profile_params(profile: str) -> Dict:
        raise RuntimeError("config.py bulunamadı: get_profile_params sağlanmalı")


@dataclass
class EngineSnapshot:
    """Bir process() çağrısının sonucu."""
    state: str = ST_NONE
    previous_state: str = ST_NONE
    break_dir: int = 0
    invalid_reason: str = "Yok"
    active: Optional[PatternCandidate] = None
    effective_quality: Optional[float] = None
    events: List[Dict] = field(default_factory=list)
    bar_index: int = -1
    log: str = ""
    min_raw_quality: float = 46.0
    min_specialized_quality: float = 50.0
    retest_seen: bool = False


class ArgentEngine:
    """Tek hisse-tek timeframe için Pine v0.4.6 karar çekirdeği."""

    def __init__(self, profile: str = "Dengeli", mintick: float = 0.01,
                 use_breakout_quality_filter: bool = True):
        from config import TERMINAL_TAZE_BAR, FAILED_PATTERN_PENALTY_BARS
        self._key = None  # Phase 1: (stock,tf) anahtarı manager tarafından atanır
        self.terminal_taze_bar = TERMINAL_TAZE_BAR
        self.failed_penalty_bars = FAILED_PATTERN_PENALTY_BARS
        self.profile = profile
        self.mintick = mintick
        self.use_breakout_quality_filter = use_breakout_quality_filter
        p = get_profile_params(profile)
        self.params = p
        self.pivot_len = p["pivot_len"]
        self.min_age = p["min_age"]
        self.min_touch_gap = p["min_touch_gap"]
        self.touch_atr_mult = p["touch_atr_mult"]
        self.min_contraction = p["min_contraction_pct"] / 100.0
        self.base_break_atr = p["break_atr_mult"]
        self.confirm_window = p["confirm_window"]
        self.min_pole_atr = p["min_pole_atr"]
        self.min_pole_efficiency = p["min_pole_efficiency"]
        self.max_pole_bars = p["max_pole_bars"]
        self.max_consolidation_bars = p["max_consolidation_bars"]
        self.min_raw_quality = p["min_raw_quality"]
        self.min_specialized_quality = p["min_specialized_quality"]
        self.min_pole_quality = p["min_pole_quality"]
        self.min_break_strength = p["min_break_strength"]
        self.retest_window = p["retest_window"]
        self.retest_hold_window = p["retest_hold_window"]
        self.flat_slope_norm_tol = p["flat_slope_norm_tol"]
        self.min_slope_norm_tol = p["min_slope_norm_tol"]
        self.parallel_slope_norm_tol = self.flat_slope_norm_tol * 0.75
        self.max_pole_link_bars = max(self.pivot_len * 2, self.min_touch_gap + 2)  # Pine: bölüm 2

        self.max_pivots = 24
        self.search_pivots = 6
        self.max_path_sample = 120
        self.max_violation_scan = 220
        self.max_history_offset = 900

        # Kalıcı state (Pine var değişkenleri)
        self.high_side = PivotSide(self.max_pivots)
        self.low_side = PivotSide(self.max_pivots)
        self.pending_pole = PoleInfo()
        self.active = PatternCandidate()
        self.next_pattern_identity = 0
        self.last_accepted_pivot_type = 0
        self.pattern_state = ST_NONE
        self.last_pattern_state = ST_NONE
        # pattern_state EN SON hangi barda değişti? (ölü formasyon tazelik kontrolü için)
        self.pattern_state_bar = -1
        self.invalid_reason = "Yok"
        self.break_candidate_bar: Optional[int] = None
        self.break_confirmed_bar: Optional[int] = None
        self.break_candidate_dir = 0
        self.break_line_x1: Optional[int] = None
        self.break_line_y1: Optional[float] = None
        self.break_line_x2: Optional[int] = None
        self.break_line_y2: Optional[float] = None
        self.retest_success_bar: Optional[int] = None
        self._retest_seen: bool = False
        self.last_failed_bar: int = -9999
        self.completed_type = "Yok"
        self.completed_start_bar: Optional[int] = None
        self.completed_end_bar: Optional[int] = None
        self.completed_hb1: Optional[int] = None
        self.completed_hb2: Optional[int] = None
        self.completed_lb1: Optional[int] = None
        self.completed_lb2: Optional[int] = None
        self.completed_upper_at_end: Optional[float] = None
        self.completed_lower_at_end: Optional[float] = None
        self.completed_geometry_atr: Optional[float] = None
        self.violation_cache = ViolationCache(100)

        # Bar bağlamı (process içinde dolar)
        self.bar_index = -1
        self.open: List[float] = []
        self.high: List[float] = []
        self.low: List[float] = []
        self.close: List[float] = []
        self.volume: List[float] = []
        self.atr_array: List[float] = []
        self.vol_sma: List[float] = []
        self.safe_atr = mintick * 10.0
        self.tol = mintick * 2.0
        self.break_buffer = mintick * 2.0

        self._bars_done = 0
        self._last_index_value = None
        self.events: List[Dict] = []
        self.index_values = None
        # --- Faz 2.2: history defteri için scan kapsamlı takip ---
        # `_p2_births`: bu scan'de doğan formation'lar (doğum snapshot'ı için).
        # `_p2_kullanilan`: bu scan'de bağlanmış stable_id'ler. Aynı stable_id
        # iki farklı candidate'a atanamaz (deterministik "ilk gelen alır").
        self._p2_births: List["PatternCandidate"] = []
        self._p2_kullanilan: set = set()
        # --- Faz 2.3: geometry evolution snapshot'ları ---
        # `_p2_geo`: bu scan'de ANLAMLI state geçişlerinde yakalanan geometry
        # snapshot'ları. Per-bar DEĞİL: yalnızca lifecycle'nin kendi "anlamlı
        # aşama" tespiti (prev_state != state) tetikler. Böylece disk yazımı
        # state geçişi sayısıyla sınırlı kalır.
        self._p2_geo: List[Dict[str, Any]] = []

    # ---------- yüksek seviye API ----------

    def reset(self) -> None:
        """Tüm kalıcı state'i sıfırla (yeni/bozulan veri akışı)."""
        # Phase 1: `_key`, motorun formation/lifecycle state'i DEĞİL — manager'ın
        # bu motoru hangi (stock, timeframe) kaydına bağladığını tutan metadata'dır.
        # Reset tüm formation state'ini (aktif aday, state makinesi, sayaçlar,
        # pivot kilitleri) __init__ ile tamamen temizler; bu metadata ise korunur.
        # Korunmasaydı `tam_yeniden=True` taramasında (process -> reset -> __init__)
        # anahtar silinir ve `_match_persisted_anchor` / `_save_formation_anchor`
        # erken çıkarak restart re-attach'i ve anchor yazımını sessizce devre
        # dışı bırakır (her turda yeni stable_id üretilir).
        anahtar = getattr(self, "_key", None)
        self.__init__(self.profile, self.mintick, self.use_breakout_quality_filter)
        self._key = anahtar

    def process(self, df: pd.DataFrame, tam_yeniden: bool = False) -> EngineSnapshot:
        """DataFrame'i (artabilir) motora ver. Yeni barlar sırayla işlenir.
        tam_yeniden=True: tüm pencere sıfırdan deterministik yeniden oynatılır.
        Canlı taramada KULLANILMALI: 1h penceresi 360'ta doygun olunca her yeni mumda
        en eski düşer; resample edilmiş 2h/4h/1d kovalarının kenar değerleri sessizce
        değişir — artımlı işleme bunu güvenli karşılayamaz, tam tekrar tutarlılığı
        garantiler (~0.1-0.3s, geri test = canlı birebir)."""
        if df is None or len(df) == 0:
            return EngineSnapshot(state=self.pattern_state, previous_state=self.last_pattern_state,
                                  break_dir=self.break_candidate_dir, invalid_reason=self.invalid_reason,
                                  active=self.active if self.active.valid else None,
                                  bar_index=self.bar_index, log="Veri yok",
                                  retest_seen=self._retest_seen)
        if tam_yeniden and self._bars_done > 0:
            self.reset()
        # Veri akışı değişti mi? (kısaltıldı / uyumsuz index) -> sıfırla ve baştan
        incremental = (not tam_yeniden and self._bars_done > 0 and len(df) >= self._bars_done
                       and self._last_index_value is not None
                       and df.index[self._bars_done - 1] == self._last_index_value)
        if not incremental and self._bars_done > 0:
            self.reset()
        self.events = []
        self.index_values = df.index

        self.open = df["open"].to_numpy(dtype=float).tolist()
        self.high = df["high"].to_numpy(dtype=float).tolist()
        self.low = df["low"].to_numpy(dtype=float).tolist()
        self.close = df["close"].to_numpy(dtype=float).tolist()
        if "volume" in df.columns:
            self.volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).to_numpy(dtype=float).tolist()
        else:
            self.volume = [0.0] * len(df)
        atr_series = calculate_atr(df, 14)
        self.atr_array = atr_series.to_numpy(dtype=float).tolist()
        vs = volume_sma_series(df, 20)
        self.vol_sma = vs.tolist()

        start = self._bars_done if (incremental or self._bars_done == 0) else 0
        if not incremental:
            start = 0
        self._bars_done = len(df)
        self._last_index_value = df.index[-1]

        prev_state = self.pattern_state
        new_events: List[Dict] = []
        # Faz 2.2: her process() çağrısı yeni bir scan kapsamı açar. Doğum
        # kayıtları ve kullanılmış stable_id'ler bu scan'a özgüdür; böylece
        # aynı stable_id iki farklı candidate'a atanamaz.
        self._p2_births = []
        self._p2_kullanilan = set()
        # Faz 2.3: geometry snapshot'ları da bu scan'a özgüdür (tam_yeniden
        # replay'de tekrar yakalanır; yazım tarafında (tur, bar_time) dedup'ı
        # gereksiz çoğalmayı engeller).
        self._p2_geo = []
        for b in range(start, len(df)):
            before = len(self.events)
            self._process_bar(b)
            new_events.extend(self.events[before:])

        snap = self._snapshot(prev_state, new_events, df)
        return snap

    def _snapshot(self, prev_state: str, events: List[Dict], df: pd.DataFrame) -> EngineSnapshot:
        active = self.active if self.active.valid else None
        eff_q = effective_raw_quality(self.active) if self.active.valid else None

        # --- ÖLÜ FORMASYON FİLTRESİ (FAZ 1 / teşhis C2) ---
        # Terminal state = canlı takip edilecek formasyon YOK: kırılım+retest tamamlandı,
        # kırılım başarısız/teyit alamadı veya formasyon geçersiz. Motor bunu içeride
        # takip etmeye devam eder (replacement-margin için gerekli) ama dışarıya
        # "canlı formasyon" olarak raporlanmamalı.
        # Ölçüm: gerçek BIST verisinde 80 formasyondan 44'ü terminaldi ve hepsi
        # ALERT_STATES'teki FORMASYON_TAMAMLANDI sayesinde her taramada mesaj
        # üretiyordu -> alert akışının %55'i günler önce biten formasyonlardı.
        # İSTİSNA: terminal geçiş son TERMINAL_TAZE_BAR bar içindeyse (taze olay)
        # bir kez raporlanır, böylece "az önce tamamlandı" bilgisi kaçmaz.
        dead_age = None
        if active is not None and f_is_dead_state(self.pattern_state):
            if self.pattern_state_bar >= 0:
                dead_age = self.bar_index - self.pattern_state_bar
            if dead_age is None or dead_age > self.terminal_taze_bar:
                active = None
                eff_q = None

        if active is None:
            if dead_age is not None:
                log = (f"Ölü formasyon ({self.pattern_state}, {dead_age} bar önce bitti) "
                       f"- canlı takip yok")
            else:
                log = f"Formasyon yok (state {self.pattern_state})"
        else:
            log = (f"{active.pattern_type} kalite {eff_q:.0f} state {self.pattern_state}"
                   + (f" yön {self.break_candidate_dir}" if self.break_candidate_dir != 0 else ""))
        return EngineSnapshot(state=self.pattern_state, previous_state=prev_state,
                              break_dir=self.break_candidate_dir, invalid_reason=self.invalid_reason,
                              active=active, effective_quality=eff_q, events=events,
                              bar_index=self.bar_index, log=log,
                              retest_seen=self._retest_seen)

    # ---------- yardımcılar (candidate.py'nin kullandığı bağlam) ----------

    def atr_at(self, bar: int) -> float:
        v = self.atr_array[bar] if 0 <= bar < len(self.atr_array) else None
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return self.safe_atr
        return v

    def depth_quality(self, depth):
        return f_depth_quality(depth)

    def duration_quality(self, ratio):
        return f_duration_quality(ratio)

    def efficiency_between(self, start_bar: int, end_bar: int) -> float:
        return efficiency_between(self.close, start_bar, end_bar, self.max_path_sample, self.mintick)

    def pair_geometry_atr(self, first: PatternCandidate, second: PatternCandidate) -> float:
        first_atr = max(first.geometry_atr if first.geometry_atr is not None else self.safe_atr, self.mintick * 10.0)
        second_atr = max(second.geometry_atr if second.geometry_atr is not None else self.safe_atr, self.mintick * 10.0)
        return max((first_atr + second_atr) * 0.5, self.mintick * 10.0)

    def touch_stats(self, side: PivotSide, x1: int, y1: float, x2: int, y2: float,
                    start_bar: int, end_bar: int, tolerance: float) -> Tuple[int, float, Optional[int], Optional[int]]:
        """Pine: f_touch_stats — (count, avgDistance, firstTouch, lastTouch)."""
        touch_count = 0
        first_touch = None
        last_touch = None
        last_accepted = None
        distance_sum = 0.0
        for i in range(len(side.prices)):
            pivot_bar = side.bars[i]
            if start_bar <= pivot_bar <= end_bar:
                expected = f_line_price(x1, y1, x2, y2, pivot_bar)
                distance = abs(side.prices[i] - expected)
                if distance <= tolerance and (last_accepted is None or pivot_bar - last_accepted >= self.min_touch_gap):
                    touch_count += 1
                    distance_sum += distance / max(tolerance, self.mintick)
                    if first_touch is None:
                        first_touch = pivot_bar
                    last_touch = pivot_bar
                    last_accepted = pivot_bar
        average_distance = distance_sum / touch_count if touch_count > 0 else 10.0
        return touch_count, average_distance, first_touch, last_touch

    def refresh_selection_score(self, candidate: PatternCandidate) -> float:
        if candidate.valid and not f_is_terminal(self.pattern_state):
            return selection_score(self, candidate)
        return candidate.selection_score

    def find_pole_ctx(self, end_bar: int, end_price: float, direction: int) -> PoleInfo:
        return find_pole(self.close, self.high, self.low, self.atr_array, self.safe_atr,
                         self.high_side, self.low_side, end_bar, end_price, direction,
                         self.min_pole_atr, self.min_pole_efficiency, self.max_pole_bars,
                         self.min_pole_quality, self.touch_atr_mult, self.max_path_sample,
                         self.max_history_offset, self.mintick)

    def lock_used_pivots(self, candidate: PatternCandidate) -> None:
        self.high_side.lock_by_bar(candidate.hb1)
        self.high_side.lock_by_bar(candidate.hb2)
        self.low_side.lock_by_bar(candidate.lb1)
        self.low_side.lock_by_bar(candidate.lb2)

    # ---------- tek bar işleme ----------

    def _process_bar(self, b: int) -> None:
        self.bar_index = b
        atr_b = self.atr_at(b)
        self.safe_atr = max(atr_b, self.mintick * 10.0)
        self.tol = max(self.mintick * 2.0, self.safe_atr * self.touch_atr_mult)
        self.break_buffer = max(self.mintick * 2.0, self.safe_atr * self.base_break_atr)
        vol_sma_b = self.vol_sma[b] if b < len(self.vol_sma) else None

        # --- Bölüm 17: pivot üretimi ---
        new_high_pivot, new_low_pivot = self._confirm_pivots(b)
        new_pivot = new_high_pivot or new_low_pivot

        # --- yeni direk (pendingPole) ---
        if new_high_pivot:
            src = b - self.pivot_len
            recent = self.find_pole_ctx(src, self.high[src], 1)
            if recent.valid and (not self.pending_pole.valid or recent.end_bar > self.pending_pole.end_bar
                                 or recent.quality > self.pending_pole.quality + 8.0):
                self.pending_pole = recent
                self._emit("POLE", "Yukarı direk teyitli" if recent.direction == 1 else "Aşağı direk teyitli",
                           recent.direction, recent.quality, recent.end_price)
        if new_low_pivot:
            src = b - self.pivot_len
            recent = self.find_pole_ctx(src, self.low[src], -1)
            if recent.valid and (not self.pending_pole.valid or recent.end_bar > self.pending_pole.end_bar
                                 or recent.quality > self.pending_pole.quality + 8.0):
                self.pending_pole = recent
                self._emit("POLE", "Yukarı direk teyitli" if recent.direction == 1 else "Aşağı direk teyitli",
                           recent.direction, recent.quality, recent.end_price)

        # --- yeni pivot geldi: aktif güncelle + kombine tarama ---
        if new_pivot and self.active.valid and not f_is_break_lifecycle(self.pattern_state):
            self.active = refresh_active_candidate(self, self.active, max(self.active.start_bar, b - 1))
            self.active.selection_score = self.refresh_selection_score(self.active)

        started_new_identity = False
        # Failure penalty: başarısız kırılımdan sonra 24 bar yeni formasyon arama
        in_penalty = (b - self.last_failed_bar) < self.failed_penalty_bars
        if new_pivot and not in_penalty:
            best = PatternCandidate()
            if len(self.high_side) >= 2 and len(self.low_side) >= 2:
                hstart = max(0, len(self.high_side) - self.search_pivots)
                lstart = max(0, len(self.low_side) - self.search_pivots)
                bull_cache = [self.find_pole_ctx(self.high_side.bars[i], self.high_side.prices[i], 1)
                              for i in range(hstart, len(self.high_side))]
                bear_cache = [self.find_pole_ctx(self.low_side.bars[i], self.low_side.prices[i], -1)
                              for i in range(lstart, len(self.low_side))]
                for hi_a in range(hstart, len(self.high_side) - 1):
                    bull_pole = bull_cache[hi_a - hstart]
                    for hi_b in range(hi_a + 1, len(self.high_side)):
                        for lo_a in range(lstart, len(self.low_side) - 1):
                            bear_pole = bear_cache[lo_a - lstart]
                            for lo_b in range(lo_a + 1, len(self.low_side)):
                                cand = build_candidate(self, hi_a, hi_b, lo_a, lo_b, bull_pole, bear_pole)
                                if cand.valid and not same_completed_structure(self, cand):
                                    cand.selection_score = selection_score(self, cand)
                                    if candidate_preferred(self, cand, best):
                                        best = cand
            if best.valid and not same_completed_structure(self, best):
                continuity = continuity_score(self, self.active, best) if self.active.valid else 0.0
                lifecycle_can_update = not f_is_break_lifecycle(self.pattern_state)
                identity_ok = self.active.valid and identity_compatible(self.active, best)
                if identity_ok and lifecycle_can_update and continuity >= 60.0:
                    preserved = self.active.identity
                    preserved_stable = getattr(self.active, "stable_id", None)
                    self.active = best
                    self.active.identity = preserved
                    self.active.stable_id = preserved_stable
                    reset_quality_snapshot(self.active)
                    self.lock_used_pivots(self.active)
                else:
                    margin = replacement_margin(self.pattern_state)
                    best_q = effective_raw_quality(best)
                    active_q = effective_raw_quality(self.active) if self.active.valid else 0.0
                    gap = quality_priority_gap(self.profile)
                    materially_better = self.active.valid and best_q >= active_q + gap
                    near_quality = self.active.valid and abs(best_q - active_q) < gap
                    context_wins = near_quality and best.selection_score >= self.active.selection_score + margin
                    replace_current = (not self.active.valid or f_is_terminal(self.pattern_state)
                                       or self.pattern_state == ST_NONE
                                       or (lifecycle_can_update and (materially_better or context_wins)))
                    if replace_current:
                        # Phase 1 — yeni formation doğumu: stable_id burada üretilir.
                        #
                        # `self.active` GEÇERSİZ ise motor hiç formation doğurmamıştır
                        # (taze motor / restart). Bu tek durumda diske yazılmış
                        # (stock,tf) anchor'u ile eşleştirme denenir; eşleşirse eski
                        # stable_id korunur (restart re-attach), eşleşme yoksa yeni
                        # UUID üretilir.
                        #
                        # `self.active` GEÇERLİ ise burada gerçekten YENİ bir formation
                        # kabul ediliyor yaşar (terminal olanın / daha zayıf olanın
                        # yerine geçiyor). Terminal olmuş eski formation'ın
                        # stable_id'si ASLA buraya taşınmaz — her zaman yeni üretilir.
                        # --- Faz 2.1: çoklu formasyon registry'si ---
                        # Registry (stock,tf) başına TEK slot yerine birden fazla
                        # kayıt taşır; böylece aynı pencere içindeki 2. formasyon
                        # doğru kimliğine ulaşır. Eşleşme DEĞİŞTİRİLMEMİŞ
                        # `identity_compatible` + `continuity_score` ile yapılır;
                        # eklenen tek şey bar-time alignment (pencere offset'i).
                        #
                        # NEDEN HER DOĞUMDA: `tam_yeniden=True` tam replay'de
                        # motor `self.active`'ini sıfırlamaz; önceki scan'den
                        # geçerli bir formation taşır. Eşleşmeyi yalnızca
                        # `not self.active.valid` anında denemek, replay'deki
                        # DOĞRUMU formasyonları da yeni UUID'ye düşürürdü.
                        # Aynı mı farklı mı olduğuna karar veren `continuity_score`
                        # olduğu için bu güvenlidir.
                        #
                        # Registry boş/bozuksa veya eşleşme yoksa Faz 1 davranışı
                        # AYNEN devrede kalır (anchor -> yeni UUID).
                        yeni_stable = _match_registry(self, best)
                        if not yeni_stable:
                            if not self.active.valid:
                                yeni_stable = _match_persisted_anchor(self, best)
                            if not yeni_stable:
                                yeni_stable = _new_stable_id()
                        if yeni_stable:
                            self._p2_kullanilan.add(yeni_stable)
                        self.next_pattern_identity += 1
                        self.active = best
                        self.active.identity = self.next_pattern_identity
                        self.active.stable_id = yeni_stable
                        # Faz 2.2: doğum kaydı (manager scan sonunda diske yazar).
                        self._p2_births.append(self.active)
                        reset_quality_snapshot(self.active)
                        self.lock_used_pivots(self.active)
                        _save_formation_anchor(self, self.active)
                        started_new_identity = True
                        self.pattern_state = ST_CANDIDATE
                        self.invalid_reason = "Yok"
                        self.break_candidate_bar = None
                        self.break_confirmed_bar = None
                        self.break_candidate_dir = 0
                        self.break_line_x1 = None
                        self.break_line_y1 = None
                        self.break_line_x2 = None
                        self.break_line_y2 = None
                        self.retest_success_bar = None
                        self._retest_seen = False

        # --- Bölüm 18: aktif adayın her-bar hafif güncellemesi ---
        has_pattern = self.active.valid
        if has_pattern:
            if f_is_break_lifecycle(self.pattern_state) and self.break_candidate_bar is not None:
                active_violation_end = max(self.active.start_bar, self.break_candidate_bar - 1)
            else:
                active_violation_end = max(self.active.start_bar, b - 1)
            self.active = refresh_active_candidate(self, self.active, active_violation_end)
            self.active.selection_score = self.refresh_selection_score(self.active)

        eff_q = effective_raw_quality(self.active) if has_pattern else None
        pattern_age = b - self.active.start_bar if has_pattern else 0
        near_upper = (abs(self.close[b] - self.active.upper_now) / max(self.tol, self.mintick)) if has_pattern else None
        near_lower = (abs(self.close[b] - self.active.lower_now) / max(self.tol, self.mintick)) if has_pattern else None
        strength_upper_boundary = self.active.upper_now if has_pattern else self.close[b]
        strength_lower_boundary = self.active.lower_now if has_pattern else self.close[b]
        (up_break, up_body, up_close, up_pen, up_exp, up_vol) = f_breakout_strength(
            self.open[b], self.high[b], self.low[b], self.close[b], self.volume[b], vol_sma_b,
            1, strength_upper_boundary, self.safe_atr, self.base_break_atr, self.mintick)
        (down_break, down_body, down_close, down_pen, down_exp, down_vol) = f_breakout_strength(
            self.open[b], self.high[b], self.low[b], self.close[b], self.volume[b], vol_sma_b,
            -1, strength_lower_boundary, self.safe_atr, self.base_break_atr, self.mintick)

        breakout_scan_eligible = has_pattern and not f_is_break_lifecycle(self.pattern_state)
        close_up_break_raw = breakout_scan_eligible and self.close[b] > self.active.upper_now + self.break_buffer
        close_down_break_raw = breakout_scan_eligible and self.close[b] < self.active.lower_now - self.break_buffer
        close_up_break = close_up_break_raw and (not self.use_breakout_quality_filter or up_break >= self.min_break_strength)
        close_down_break = close_down_break_raw and (not self.use_breakout_quality_filter or down_break >= self.min_break_strength)
        weak_filtered_up_break = close_up_break_raw and not close_up_break
        weak_filtered_down_break = close_down_break_raw and not close_down_break

        # Eşikler (Pine: bölüm 18)
        active_minimum_quality = (self.min_specialized_quality if f_is_specialized(self.active.pattern_type)
                                  else self.min_raw_quality) if has_pattern else self.min_raw_quality
        mature_quality_threshold = min(82.0, active_minimum_quality + 12.0)
        required_age = (max(6, self.min_age // 2) if has_pattern and f_is_specialized(self.active.pattern_type)
                        else self.min_age)
        defined_now = (has_pattern and b >= self.active.known_bar and pattern_age >= required_age
                       and self.active.upper_touches >= 2 and self.active.lower_touches >= 2
                       and eff_q >= active_minimum_quality)
        mature_now = (defined_now and eff_q >= mature_quality_threshold
                      and (f_is_flag(self.active.pattern_type) or self.active.contraction >= self.min_contraction))
        prep_now = mature_now and (near_upper <= 1.35 or near_lower <= 1.35)

        # Sert geometri bozulması + weak/invalid değerlendirmesi
        active_geometry_atr = max(self.active.geometry_atr if has_pattern and self.active.geometry_atr is not None
                                  else self.safe_atr, self.mintick * 10.0)
        hard_invalid_now = (has_pattern and not f_is_break_lifecycle(self.pattern_state)
                            and hard_geometry_invalid(self.active, active_geometry_atr,
                                                      self.parallel_slope_norm_tol, self.flat_slope_norm_tol,
                                                      self.min_contraction, self.mintick))
        weak_now = False
        invalid_now = False
        current_invalid_reason = "Yok"
        if has_pattern and not f_is_break_lifecycle(self.pattern_state):
            max_acc = MAX_ACCEPTED_VIOLATION.get(self.profile, 0.72)
            history_severely_degraded = (self.active.historical_close_violations >= 2
                                         or self.active.max_historical_violation > max_acc
                                         or self.active.historical_violation_penalty >= 62.0)
            history_weak = (history_severely_degraded or self.active.historical_close_violations >= 1
                            or self.active.historical_wick_violations >= 3
                            or self.active.historical_violation_penalty >= 28.0)
            history_weak_reason = ("Sınır ihlalleri arttı; kırılım davranışı izleniyor"
                                   if history_severely_degraded else "Geçmiş sınır ihlalleri kaliteyi düşürüyor")
            if f_is_flag(self.active.pattern_type):
                avg_slope_norm = ((self.active.upper_slope + self.active.lower_slope) * 0.5) / active_geometry_atr
                parallel_broken = (abs(self.active.upper_slope - self.active.lower_slope) / active_geometry_atr
                                   > self.parallel_slope_norm_tol * 1.8)
                same_dir_too_strong = (avg_slope_norm > self.flat_slope_norm_tol * 0.55 if self.active.pole_dir == 1
                                       else avg_slope_norm < -self.flat_slope_norm_tol * 0.55)
                invalid_now = hard_invalid_now
                weak_now = (not invalid_now and
                            (history_weak or self.active.correction_depth > 0.65 or self.active.duration_ratio > 2.7
                             or eff_q < self.min_specialized_quality))
                current_invalid_reason = ("Direğin büyük kısmı geri alındı" if self.active.correction_depth > 0.80 else
                                          "Konsolidasyon süresi aşırı uzadı" if self.active.duration_ratio > 4.0 else
                                          "Konsolidasyon direğe göre fazla geniş" if self.active.consolidation_height_ratio > 0.70 else
                                          "Paralel bayrak geometrisi bozuldu" if parallel_broken else
                                          "Kanal direkle aynı yönde güçlendi" if same_dir_too_strong else
                                          history_weak_reason if history_weak else
                                          "Bayrak kalitesi zayıflıyor" if weak_now else "Yok")
            elif f_is_pennant(self.active.pattern_type):
                invalid_now = hard_invalid_now
                weak_now = (not invalid_now and
                            (history_weak or self.active.correction_depth > 0.65 or self.active.duration_ratio > 2.7
                             or self.active.progress > 0.90 or eff_q < self.min_specialized_quality))
                current_invalid_reason = ("Direğin büyük kısmı geri alındı" if self.active.correction_depth > 0.80 else
                                          "Flama süresi aşırı uzadı" if self.active.duration_ratio > 4.0 else
                                          "Flama apex bölgesini geçti" if self.active.progress > 1.02 else
                                          "Flama genişliği geçersiz" if self.active.current_width <= self.mintick * 3.0 else
                                          "Flama yakınsaması bozuldu" if self.active.contraction < self.min_contraction * 0.55 else
                                          history_weak_reason if history_weak else
                                          "Flama kalitesi zayıflıyor" if weak_now else "Yok")
            else:
                invalid_now = hard_invalid_now
                weak_now = (not invalid_now and
                            (history_weak or self.active.progress > 0.90 or self.active.violation > 1.2
                             or self.active.contraction < self.min_contraction * 1.05))
                current_invalid_reason = ("Apex bölgesi geçildi" if self.active.progress > 1.02 else
                                          "Üst/alt sınır geometrisi geçersiz" if self.active.current_width <= self.mintick * 3.0 else
                                          "Daralma bozuldu" if self.active.contraction < self.min_contraction * 0.55 else
                                          history_weak_reason if history_weak else
                                          "Apex'e yaklaşıyor" if self.active.progress > 0.90 else
                                          "Çizgi ihlalleri artıyor" if self.active.violation > 1.2 else
                                          "Daralma zayıflıyor" if weak_now else "Yok")

        # Bekleyen direğin geçersizleşmesi
        if self.pending_pole.valid:
            pending_age = b - self.pending_pole.end_bar
            if self.pending_pole.direction == 1:
                pending_retrace = (self.pending_pole.end_price - self.low[b]) / max(self.pending_pole.magnitude, self.mintick)
            else:
                pending_retrace = (self.high[b] - self.pending_pole.end_price) / max(self.pending_pole.magnitude, self.mintick)
            pending_used = (has_pattern and self.active.has_pole
                            and self.active.pole_end_bar == self.pending_pole.end_bar
                            and self.active.pole_dir == self.pending_pole.direction)
            if not pending_used and (pending_age > self.max_consolidation_bars or pending_retrace > 0.80):
                self._emit("POLE_INVALID", "Direk geçersiz", self.pending_pole.direction,
                           self.pending_pole.quality, self.pending_pole.end_price)
                self.pending_pole.valid = False

        # --- Bölüm 19-20: yaşam döngüsü geçişleri ---
        next_state = self.pattern_state
        next_break_dir = self.break_candidate_dir
        prev_state = self.pattern_state

        if not has_pattern:
            next_state = ST_NONE
            self.invalid_reason = "Yeterli teyitli geometri yok"
        elif f_is_terminal(self.pattern_state):
            next_state = self.pattern_state
        elif self.pattern_state == ST_BREAK_ATTEMPT:
            next_state = self._break_attempt_or_candidate_step(b, is_attempt=True)
        elif self.pattern_state == ST_BREAK_CANDIDATE:
            next_state = self._break_attempt_or_candidate_step(b, is_attempt=False)
        elif self.pattern_state in (ST_BREAK_CONFIRMED, ST_RETEST_WAIT, ST_RETESTING):
            next_state = self._retest_step(b)
        elif self.pattern_state == ST_RETEST_OK:
            next_state = self._retest_ok_step(b)
        else:
            strong_closed_break_now = close_up_break or close_down_break
            weak_closed_break_now = weak_filtered_up_break or weak_filtered_down_break
            closed_boundary_break_now = strong_closed_break_now or weak_closed_break_now
            if closed_boundary_break_now and not hard_invalid_now:
                direction = 1 if close_up_break_raw else -1
                next_state = ST_BREAK_CANDIDATE if strong_closed_break_now else ST_BREAK_ATTEMPT
                next_break_dir = direction
                self.break_candidate_bar = b
                self.break_candidate_dir = direction
                if direction == 1:
                    self.break_line_x1, self.break_line_y1 = self.active.hb1, self.active.hp1
                    self.break_line_x2, self.break_line_y2 = self.active.hb2, self.active.hp2
                else:
                    self.break_line_x1, self.break_line_y1 = self.active.lb1, self.active.lp1
                    self.break_line_x2, self.break_line_y2 = self.active.lb2, self.active.lp2
                self.active = freeze_pattern_quality(self, self.active)
                self.active.break_strength = up_break if direction == 1 else down_break
                self.active.break_body_score = up_body if direction == 1 else down_body
                self.active.break_close_score = up_close if direction == 1 else down_close
                self.active.break_penetration_score = up_pen if direction == 1 else down_pen
                self.active.break_expansion_score = up_exp if direction == 1 else down_exp
                self.active.break_volume_score = up_vol if direction == 1 else down_vol
                self.invalid_reason = ("Yok" if strong_closed_break_now
                                       else "Sınır dışı kapanış var; kırılım gücü teyit bekliyor")
            elif invalid_now:
                next_state = ST_INVALID
                self.invalid_reason = current_invalid_reason
            elif self.pattern_state == ST_BREAK_TIMEOUT:
                reset_quality_snapshot(self.active)
                self.active.last_violation_processed_bar = max(self.active.start_bar, b)
                self.active.violation_scan_mode = "Atlandı"
                next_state = (ST_PREP if prep_now else ST_WEAK if weak_now else
                              ST_DEFINED if defined_now else ST_GEOMETRY)
            elif weak_now:
                next_state = ST_WEAK
                self.invalid_reason = current_invalid_reason
            elif prep_now:
                next_state = ST_PREP
            elif mature_now:
                next_state = (ST_MATURING if f_is_flag(self.active.pattern_type)
                              else ST_COMPRESSING if self.active.contraction >= 0.50 else ST_MATURING)
            elif defined_now:
                next_state = ST_DEFINED
            elif pattern_age >= max(5, required_age - 4):
                next_state = ST_GEOMETRY
            else:
                next_state = ST_CANDIDATE

        if next_state != prev_state:
            self.pattern_state_bar = b   # state bu barda değişti (tazelik ölçümü)
        self.pattern_state = next_state
        self.break_candidate_dir = next_break_dir

        # --- olaylar (Pine alertcondition karşılıkları; alert() çağrısı YOK) ---
        self._emit_state_events(prev_state, started_new_identity)
        self.last_pattern_state = self.pattern_state

    # ---------- lifecycle alt adımları ----------

    def _break_attempt_or_candidate_step(self, b: int, is_attempt: bool) -> str:
        active = self.active
        boundary = f_line_price(self.break_line_x1, self.break_line_y1, self.break_line_x2, self.break_line_y2, b)
        buf = effective_break_buffer(self, active)
        rtol = effective_retest_tolerance(self, active)
        projected_upper = active.upper_now
        projected_lower = active.lower_now
        d = self.break_candidate_dir
        same_side_close = (self.close[b] > boundary + buf) if d == 1 else (self.close[b] < boundary - buf)
        lifecycle_atr = (active.frozen_atr_at_break if active.quality_frozen and active.frozen_atr_at_break is not None
                         else self.safe_atr)
        (up_str, _, _, _, _, _) = f_breakout_strength(
            self.open[b], self.high[b], self.low[b], self.close[b], self.volume[b],
            self.vol_sma[b] if b < len(self.vol_sma) else None,
            1, boundary, lifecycle_atr, self.base_break_atr, self.mintick)
        (down_str, _, _, _, _, _) = f_breakout_strength(
            self.open[b], self.high[b], self.low[b], self.close[b], self.volume[b],
            self.vol_sma[b] if b < len(self.vol_sma) else None,
            -1, boundary, lifecycle_atr, self.base_break_atr, self.mintick)
        confirmation_strength = up_str if d == 1 else down_str
        strong_same_side = same_side_close and (not self.use_breakout_quality_filter
                                                or confirmation_strength >= max(25.0, self.min_break_strength - 6.0))
        hold_buffer = max(self.mintick, rtol * 0.12)
        if d == 1:
            attempt_retest = self.low[b] <= boundary + rtol and self.close[b] > boundary + hold_buffer
        else:
            attempt_retest = self.high[b] >= boundary - rtol and self.close[b] < boundary - hold_buffer
        back_inside = (self.close[b] < projected_upper - hold_buffer) if d == 1 else (self.close[b] > projected_lower + hold_buffer)
        age = b - self.break_candidate_bar
        if back_inside and b > self.break_candidate_bar:
            self.invalid_reason = "Kırılım denemesi formasyon içine döndü" if is_attempt else "Teyitsiz kırılım formasyon içine döndü"
            self.last_failed_bar = b
            return ST_BREAK_FAILED
        if b > self.break_candidate_bar and age <= self.confirm_window and (strong_same_side or attempt_retest):
            self.break_confirmed_bar = b
            active.break_confirmation_strength = confirmation_strength
            return ST_BREAK_CONFIRMED
        if age > self.confirm_window:
            self.invalid_reason = "Kırılım denemesi güçlenmedi" if is_attempt else "Kırılım teyit alamadı"
            return ST_BREAK_TIMEOUT
        return self.pattern_state

    def _retest_step(self, b: int) -> str:
        active = self.active
        boundary = f_line_price(self.break_line_x1, self.break_line_y1, self.break_line_x2, self.break_line_y2, b)
        rtol = effective_retest_tolerance(self, active)
        projected_upper = active.upper_now
        projected_lower = active.lower_now
        hold_buffer = max(self.mintick, rtol * 0.12)
        d = self.break_candidate_dir
        returned_inside = (self.close[b] < projected_upper - hold_buffer) if d == 1 else (self.close[b] > projected_lower + hold_buffer)
        if d == 1:
            retest_touch = self.low[b] <= boundary + rtol and self.high[b] >= boundary - rtol
            retest_held = retest_touch and self.close[b] > boundary + hold_buffer
        else:
            retest_touch = self.high[b] >= boundary - rtol and self.low[b] <= boundary + rtol
            retest_held = retest_touch and self.close[b] < boundary - hold_buffer
        confirmed_age = b - self.break_confirmed_bar
        if returned_inside:
            self.invalid_reason = "Kırılım sonrası formasyon alanına dönüldü"
            self.last_failed_bar = b
            return ST_BREAK_FAILED
        if retest_held:
            self.retest_success_bar = b
            self._retest_seen = True
            return ST_RETEST_OK
        if retest_touch:
            self._retest_seen = True
            return ST_RETESTING
        if confirmed_age > self.retest_window:
            self._capture_completed()
            return ST_COMPLETED
        return ST_RETEST_WAIT

    def _retest_ok_step(self, b: int) -> str:
        active = self.active
        boundary = f_line_price(self.break_line_x1, self.break_line_y1, self.break_line_x2, self.break_line_y2, b)
        rtol = effective_retest_tolerance(self, active)
        hold_buffer = max(self.mintick, rtol * 0.12)
        d = self.break_candidate_dir
        retained = (self.close[b] > boundary + hold_buffer) if d == 1 else (self.close[b] < boundary - hold_buffer)
        projected_upper = active.upper_now
        projected_lower = active.lower_now
        returned_inside = (self.close[b] < projected_upper - hold_buffer) if d == 1 else (self.close[b] > projected_lower + hold_buffer)
        retest_hold_age = b - self.retest_success_bar
        if returned_inside:
            self.invalid_reason = "Başarılı retest sonrası yapı içine dönüldü"
            self.last_failed_bar = b
            return ST_BREAK_FAILED
        if retained and retest_hold_age >= self.retest_hold_window:
            self._retest_seen = True
            self._capture_completed()
            return ST_COMPLETED
        if not retained:
            self.invalid_reason = "Retest sınır çevresinde yeniden izleniyor"
            self._retest_seen = True
            return ST_RETESTING
        self.invalid_reason = "Retest korunumu bekleniyor"
        return ST_RETEST_OK

    def _capture_completed(self) -> None:
        a = self.active
        self.completed_type = a.pattern_type
        self.completed_start_bar = a.start_bar
        self.completed_end_bar = a.end_bar
        self.completed_hb1, self.completed_hb2 = a.hb1, a.hb2
        self.completed_lb1, self.completed_lb2 = a.lb1, a.lb2
        self.completed_upper_at_end = f_line_price(a.hb1, a.hp1, a.hb2, a.hp2, a.end_bar)
        self.completed_lower_at_end = f_line_price(a.lb1, a.lp1, a.lb2, a.lp2, a.end_bar)
        self.completed_geometry_atr = max(a.geometry_atr if a.geometry_atr is not None else self.safe_atr,
                                          self.mintick * 10.0)

    # ---------- pivot kabul ----------

    def _confirm_pivots(self, b: int) -> Tuple[bool, bool]:
        """Pine bölüm 17 pivot üretimi: pivothigh/pivotlow teyidi + aynı-bar çift pivot çözümü."""
        n = len(self.close)
        src = b - self.pivot_len
        new_high = False
        new_low = False
        if src < self.pivot_len:
            return new_high, new_low
        ph = is_pivot_high(self.high, src, self.pivot_len, self.pivot_len, n)
        pl = is_pivot_low(self.low, src, self.pivot_len, self.pivot_len, n)
        same_bar_double = ph is not None and pl is not None
        if same_bar_double:
            src_atr = max(self.atr_at(src), self.mintick * 10.0)
            sel_type, _reason, _dh, _dl = choose_same_bar_pivot(
                self.high_side, self.low_side, ph, pl, src_atr,
                self.open[src], self.high[src], self.low[src], self.close[src],
                self.last_accepted_pivot_type, self.profile, self.mintick)
            if sel_type == 1:
                accepted, _app = self.high_side.add(ph, src, b, self.last_accepted_pivot_type == 1)
                if accepted:
                    if self.last_accepted_pivot_type == -1:
                        self.low_side.lock_previous_opposite()
                    self.last_accepted_pivot_type = 1
                    new_high = True
            elif sel_type == -1:
                accepted, _app = self.low_side.add(pl, src, b, self.last_accepted_pivot_type == -1)
                if accepted:
                    if self.last_accepted_pivot_type == 1:
                        self.high_side.lock_previous_opposite()
                    self.last_accepted_pivot_type = -1
                    new_low = True
        else:
            if ph is not None:
                accepted, _app = self.high_side.add(ph, src, b, self.last_accepted_pivot_type == 1)
                if accepted:
                    if self.last_accepted_pivot_type == -1:
                        self.low_side.lock_previous_opposite()
                    self.last_accepted_pivot_type = 1
                    new_high = True
            if pl is not None:
                accepted, _app = self.low_side.add(pl, src, b, self.last_accepted_pivot_type == -1)
                if accepted:
                    if self.last_accepted_pivot_type == 1:
                        self.high_side.lock_previous_opposite()
                    self.last_accepted_pivot_type = -1
                    new_low = True
        return new_high, new_low

    # ---------- olaylar ----------

    def _emit(self, event_type: str, name: str, direction: int, quality: Optional[float],
              price: Optional[float], **extra) -> None:
        ev = {
            "type": event_type,
            "name": name,
            "direction": direction,
            "quality": quality,
            "price": price,
            "bar": self.bar_index,
            "time": self.index_values[self.bar_index] if self.index_values is not None
                    and 0 <= self.bar_index < len(self.index_values) else None,
            "state": self.pattern_state,
            # Faz 2.2: olayin ait oldugu formation. `stable_id` dogumdan
            # terminal'e kadar ayni kalir; boylece history defteri olayi dogru
            # kayda baglar. Anahtar adlari DEGISTIRILMEDI, yalnizca eklendi.
            "stable_id": (self.active.stable_id
                          if getattr(self.active, "valid", False) else None),
        }
        ev.update(extra)
        self.events.append(ev)

    def _emit_state_events(self, prev_state: str, started_new_identity: bool) -> None:
        s = self.pattern_state
        a = self.active
        d = self.break_candidate_dir
        eff_q = effective_raw_quality(a) if a.valid else None
        price = self.close[self.bar_index] if 0 <= self.bar_index < len(self.close) else None

        def maybe(cond: bool, ev_type: str, name: str, direction: int = 0, q: Optional[float] = None):
            if cond:
                self._emit(ev_type, name, direction, q if q is not None else eff_q, price)
                # Faz 2.3: anlamlı state geçişinde geometry snapshot'ı yakala.
                # Matematik DEĞİŞTİRMEZ — mevcut candidate'ın halihazırda
                # hesaplanmış alanları okunur (schema.geometri_snapshot).
                self._p2_geometri_yakala()

        if not a.valid:
            return
        if started_new_identity:
            maybe(True, "NEW_PATTERN", "Yeni formasyon adayı", a.classic_dir)
        maybe(s == ST_DEFINED and prev_state != ST_DEFINED, "DEFINED", "Formasyon tanımlandı", a.classic_dir)
        maybe((s in (ST_MATURING, ST_COMPRESSING)) and prev_state not in (ST_MATURING, ST_COMPRESSING),
              "MATURE", "Formasyon olgunlaştı", a.classic_dir)
        maybe(s == ST_PREP and prev_state != ST_PREP, "PREP", "Kırılım hazırlığı", a.classic_dir)
        maybe(s == ST_BREAK_CANDIDATE and prev_state != ST_BREAK_CANDIDATE,
              "COUNTER_BREAK" if (a.classic_dir != 0 and d != a.classic_dir) else "BREAK_CANDIDATE",
              ("Karşı yönlü kırılım" if (a.classic_dir != 0 and d != a.classic_dir)
               else ("Kırılım adayı ↑" if d == 1 else "Kırılım adayı ↓")),
              d, a.break_strength)
        maybe(s == ST_BREAK_CONFIRMED and prev_state != ST_BREAK_CONFIRMED,
              "COUNTER_BREAK" if (a.classic_dir != 0 and d != a.classic_dir) else "BREAK_CONFIRMED",
              ("Karşı yönlü kırılım teyitli" if (a.classic_dir != 0 and d != a.classic_dir)
               else ("Kırılım teyitli ↑" if d == 1 else "Kırılım teyitli ↓")),
              d, a.break_confirmation_strength if a.break_confirmation_strength is not None else a.break_strength)
        maybe(s == ST_RETEST_OK and prev_state != ST_RETEST_OK, "RETEST_OK", "Retest başarılı", d)
        maybe(s == ST_COMPLETED and prev_state != ST_COMPLETED, "COMPLETED", "Formasyon tamamlandı", d)
        maybe(s == ST_BREAK_TIMEOUT and prev_state != ST_BREAK_TIMEOUT, "TIMEOUT", "Kırılım teyit alamadı", d)
        maybe(s == ST_BREAK_FAILED and prev_state != ST_BREAK_FAILED, "BREAK_FAILED", "Başarısız kırılım", d)
        maybe(s == ST_WEAK and prev_state != ST_WEAK, "WEAK", "Formasyon zayıfladı", a.classic_dir,
              self.invalid_reason if False else None)
        maybe(s == ST_INVALID and prev_state != ST_INVALID, "INVALID", "Formasyon geçersiz", a.classic_dir)

    def _p2_geometri_yakala(self) -> None:
        """Faz 2.3: anlamlı state geçişinde geometry snapshot'ı yakalar.

        NEDEN BURADA: lifecycle zaten "anlamlı aşama" kavramını kendi state
        makinesiyle tanımlıyor (`prev_state != state`). Yeni ve yapay bir
        eşik/scoring sistemi icat ETMEK YERİNE bu mevcut sinyal kullanılır;
        böylece snapshot'lar bar sayısıyla değil, gerçek anlamlı geçişlerle
        sınırlı kalır (per-bar persistence olmaz).

        Matematik DEĞİŞMEZ: `schema.geometri_snapshot` mevcut candidate'ın
        halihazırda hesaplanmış STATE alanlarını okur; hiçbir geometri yeniden
        hesaplanmaz.
        """
        a = self.active
        if not getattr(a, "valid", False) or not getattr(a, "stable_id", None):
            return
        bar_time = None
        if self.index_values is not None and 0 <= self.bar_index < len(self.index_values):
            bar_time = self.index_values[self.bar_index]
        bar_time = str(bar_time) if bar_time is not None else None

        from state import formation_schema as schema

        temel = {
            "stable_id": a.stable_id,
            "bar": self.bar_index,
            "bar_time": bar_time,
            "state": self.pattern_state,
        }
        # 1) Her anlamlı geçişte: o andaki geometri.
        self._p2_geo.append(dict(temel, tur="geometri",
                                 **schema.geometri_snapshot(a, bar_time=bar_time)))
        # 2) Kırılım teyidinde: kırılım anında dondurulmuş geometri.
        if self.pattern_state == ST_BREAK_CONFIRMED:
            self._p2_geo.append(dict(temel, tur="kirilim",
                                     **schema.kirilim_snapshot(a, bar_time=bar_time)))


# --- YÖNETİCİ (eski PatternLifecycleManager API'sini korur) ---

def _terminal_snapshotu(engine, snap: EngineSnapshot) -> Optional[Dict[str, Any]]:
    """Faz 2.3: terminal anındaki SON anlamlı geometry snapshot'ı.

    Terminal formation'ın son geometrisi history'de `tur="terminal"` ile
    saklanır. Matematik DEĞİŞTİRMEZ: mevcut candidate'ın halihazırda
    hesaplanmış alanları okunur. Kırılım sonrası terminal ise kırılım anında
    DONDURULMUŞ geometri (BREAKOUT alanları) daha anlamlıdır; değilse o anki
    geometry (STATE alanları) kullanılır.

    Bar zamanı MUTLAK olmalı: pencere-koordinat bar indeksleri yalnızca bu
    zamana göre yorumlanabilir (bkz. formation_history BAR-TIME ALIGNMENT).
    """
    aktif = getattr(snap, "active", None)
    if aktif is None or not getattr(aktif, "valid", False):
        return None
    idx = getattr(engine, "index_values", None)
    b = getattr(engine, "bar_index", None)
    if idx is None or b is None or not (0 <= b < len(idx)):
        return None
    try:
        from state import formation_schema as schema
        bar_time = str(idx[b])
        if snap.state in ("FORMASYON_TAMAMLANDI", "RETEST_BASARILI"):
            return schema.kirilim_snapshot(aktif, bar_time=bar_time)
        return schema.geometri_snapshot(aktif, bar_time=bar_time)
    except Exception:  # noqa: BLE001 - snapshot üretilemezse terminal yine yazılır
        return None


class PatternLifecycleManager:
    """
    Hisse+timeframe başına bir ArgentEngine tutar.
    update(key, df, candidate=None) -> (state, break_dir, log)  [eski imza korunur]
    scan(key, df) -> EngineSnapshot (main.py'nin yeni akışı için)
    """
    def __init__(self, profile: str = "Dengeli", mintick: float = 0.01):
        self.profile = profile
        self.mintick = mintick
        self.engines: Dict[str, ArgentEngine] = {}
        self.last_snapshots: Dict[str, EngineSnapshot] = {}

    def get_engine(self, key: str) -> ArgentEngine:
        if key not in self.engines:
            self.engines[key] = ArgentEngine(self.profile, self.mintick)
        # Phase 1: restart re-attach için motorun (stock,tf) anahtarını taşı.
        self.engines[key]._key = key
        return self.engines[key]

    def scan(self, key: str, df: pd.DataFrame, tam_yeniden: bool = False) -> EngineSnapshot:
        engine = self.get_engine(key)
        snap = engine.process(df, tam_yeniden=tam_yeniden)
        self.last_snapshots[key] = snap
        self._history_kaydet(key, engine, snap)
        return snap

    # ---------- Faz 2.1/2.2: history defteri yazımı ----------

    def _history_kaydet(self, key: str, engine, snap: EngineSnapshot) -> None:
        """Scan sonunda history defterini ANLAMLI olaylara göre günceller.

        Yazma tetikleyicileri (per-bar dump YOK):
          * doğum  -> engine._p2_births
          * olay   -> snap.events (state geçişleri)
          * geometri -> engine._p2_geo (anlamlı state geçişlerinde yakalanan)
          * terminal -> snap.state terminal ise

        Tek taramada tek save: defter bir kez yüklenir, tüm mutasyonlar
        uygulanır, en fazla bir kez yazılır.

        Bu fonksiyon MOTOR DAVRANIŞINI DEĞİŞTİRMEZ ve botu asla durdurmaz:
        herhangi bir hatta sessizce geri döner.
        """
        try:
            from state import formation_history as fh
            stock, tf = _parse_stock_tf(key)
            dogumlar = list(getattr(engine, "_p2_births", None) or [])
            olaylar = list(getattr(snap, "events", None) or [])
            geo = list(getattr(engine, "_p2_geo", None) or [])
            terminal = fh.terminal_durumu(snap.state)
            if not dogumlar and not olaylar and not terminal and not geo:
                return
            defter = fh.yukle(stock, tf)
            degisti = False
            for aday in dogumlar:
                if fh.dogum_ekle(defter, aday, engine) is not None:
                    degisti = True
            if olaylar and fh.olay_ekle(defter, olaylar):
                degisti = True
            # --- Faz 2.3: geometry evolution snapshot'ları ---
            # (tur, bar_time) dedup'ı sayesinde tam_yeniden replay'de ve kayan
            # pencerede AYNI fiziksel an için ikinci kayıt yazılmaz.
            for y in geo:
                sid = y.get("stable_id")
                if not sid:
                    continue
                if fh.snapshot_ekle(defter, sid, y.get("tur") or "geometri", y,
                                    ek={"state": y.get("state"),
                                        "bar": y.get("bar")}):
                    degisti = True
            if terminal:
                sid = (getattr(snap, "active", None).stable_id
                       if getattr(snap, "active", None) is not None
                       and getattr(snap.active, "valid", False) else None)
                # Faz 2.3: terminal geometry BİR KEZ yazılır. Terminal
                # formation'ın geometrisi donmuştur; tazelik penceresi
                # içinde her taramada yenisini yazmak gereksiz snapshot
                # çoğaltır ve MAX_SNAPSHOT altındaki gerçek geometry
                # evrimini dışarı iter.
                terminal_snap = None
                if sid:
                    rec_t = fh.kayit_getir(defter, sid)
                    if rec_t is not None and not any(
                            x.get("tur") == "terminal"
                            for x in rec_t.get("snapshotlar", [])):
                        terminal_snap = _terminal_snapshotu(engine, snap)
                if sid and fh.terminal_ekle(defter, sid, snap.state,
                                            snapshot=terminal_snap):
                    degisti = True
                elif sid:
                    # Terminal geçişi bu turda yakalanmasa bile (replay'de
                    # zaten terminal ise) durumu güncelle.
                    rec = fh.kayit_getir(defter, sid)
                    if rec is not None and rec.get("durum") != fh.DURUM_TERMINAL:
                        rec["durum"] = fh.DURUM_TERMINAL
                        rec["terminal_state"] = snap.state
                        rec["terminal_zamani"] = fh._simdi()
                        degisti = True
            if degisti:
                fh.kaydet(defter)
        except Exception:
            # History yazılamazsa bot çalışmaya devam eder (ölü kod değil,
            # bilinçli güvenlik sınırı).
            return

    def update(self, key: str, df: pd.DataFrame, candidate=None) -> Tuple[str, int, str]:
        """Eski 3'lü imza. `candidate` parametresi artık kullanılmaz — motor adayı kendisi bulur."""
        snap = self.scan(key, df)
        return snap.state, snap.break_dir, snap.log

    def get_snapshot(self, key: str) -> Optional[EngineSnapshot]:
        return self.last_snapshots.get(key)

