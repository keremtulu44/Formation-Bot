# --- PİVOT MOTORU ---
# Pine: Bölüm 7 (f_add_pivot, f_choose_same_bar_pivot, kilitler) + Bölüm 17 pivot üretimi.
# Eski Python'daki stub `filter_same_bar_double_pivot` (TODO) artık birebir çevrildi (Teşhis A5).

from typing import Dict, List, Optional, Tuple

import pandas as pd


class PivotSide:
    """
    Bir yönün pivot dizileri: fiyat / kaynak bar / teyit barı / kilit.
    Pine'daki var array<float> highPrices + highBars + highConfirmBars + highLocked dörtlüsü.
    """
    def __init__(self, max_pivots: int = 24):
        self.max_pivots = max_pivots
        self.prices: List[float] = []
        self.bars: List[int] = []
        self.confirm_bars: List[int] = []
        self.locked: List[bool] = []

    def __len__(self) -> int:
        return len(self.prices)

    def last_price(self) -> Optional[float]:
        return self.prices[-1] if self.prices else None

    def add(self, price: float, source_bar: int, confirm_bar: int, same_open_type: bool) -> Tuple[bool, bool]:
        """Pine: f_add_pivot — aynı tip pivotta daha ekstrem değer mevcut (kilitsiz) pivoru GÜNCELLER."""
        accepted = False
        appended = False
        count = len(self.prices)
        if count > 0:
            last_price = self.prices[-1]
            last_locked = self.locked[-1]
            stronger_extreme = price > last_price  # is_high ve is_low için aynı: ekstrem = "daha büyük üst" ya da "daha küçük alt"
            # DİKKAT: Pine'da strongerExtreme isHigh ? price > last : price < last.
            if same_open_type:
                if not last_locked and stronger_extreme:
                    self.prices[-1] = price
                    self.bars[-1] = source_bar
                    self.confirm_bars[-1] = confirm_bar
                    accepted = True
                elif last_locked and stronger_extreme:
                    self.prices.append(price)
                    self.bars.append(source_bar)
                    self.confirm_bars.append(confirm_bar)
                    self.locked.append(False)
                    accepted = True
                    appended = True
            else:
                self.prices.append(price)
                self.bars.append(source_bar)
                self.confirm_bars.append(confirm_bar)
                self.locked.append(False)
                accepted = True
                appended = True
        else:
            self.prices.append(price)
            self.bars.append(source_bar)
            self.confirm_bars.append(confirm_bar)
            self.locked.append(False)
            accepted = True
            appended = True
        while len(self.prices) > self.max_pivots:
            self.prices.pop(0)
            self.bars.pop(0)
            self.confirm_bars.pop(0)
            self.locked.pop(0)
        return accepted, appended

    def is_locked_by_bar(self, source_bar: int) -> bool:
        """Pine: f_is_pivot_locked."""
        for i, bar in enumerate(self.bars):
            if bar == source_bar:
                return self.locked[i]
        return False

    def lock_by_bar(self, source_bar: int) -> int:
        """Pine: f_lock_pivot_by_bar."""
        newly = 0
        for i, bar in enumerate(self.bars):
            if bar == source_bar and not self.locked[i]:
                self.locked[i] = True
                newly += 1
        return newly

    def lock_previous_opposite(self) -> int:
        """Pine: f_lock_previous_opposite_pivot — dizinin son elemanını kilitler."""
        if len(self.locked) > 0 and not self.locked[-1]:
            self.locked[-1] = True
            return 1
        return 0


def is_pivot_high(high: list, center: int, left: int, right: int, series_len: int) -> Optional[float]:
    """ta.pivothigh karşılığı: merkez, iki yandaki TÜM barlardan sıkı biçimde yüksekse fiyat döner."""
    if center - left < 0 or center + right >= series_len:
        return None
    pivot = high[center]
    for j in range(1, left + 1):
        if high[center - j] >= pivot:
            return None
    for j in range(1, right + 1):
        if high[center + j] >= pivot:
            return None
    return pivot


def is_pivot_low(low: list, center: int, left: int, right: int, series_len: int) -> Optional[float]:
    """ta.pivotlow karşılığı."""
    if center - left < 0 or center + right >= series_len:
        return None
    pivot = low[center]
    for j in range(1, left + 1):
        if low[center - j] <= pivot:
            return None
    for j in range(1, right + 1):
        if low[center + j] <= pivot:
            return None
    return pivot


def same_bar_candidate_valid(side: PivotSide, is_high: bool, candidate_price: float,
                             source_atr: float, last_accepted_type: int,
                             minimum_move_atr: float, mintick: float) -> bool:
    """Pine: f_same_bar_candidate_valid."""
    candidate_type = 1 if is_high else -1
    valid = True
    if last_accepted_type == candidate_type and len(side) > 0:
        last_price = side.prices[-1]
        last_locked = side.locked[-1]
        # Ekstrem karşılaştırma: high için daha yüksek, low için daha düşük
        stronger_extreme = candidate_price > last_price if is_high else candidate_price < last_price
        minimum_same_type_move = max(mintick * 2.0, source_atr * 0.03) if last_locked else mintick
        valid = stronger_extreme and abs(candidate_price - last_price) >= minimum_same_type_move
    elif last_accepted_type == -candidate_type:
        reference_price = side.last_price()
        minimum_move = max(mintick * 2.0, source_atr * minimum_move_atr)
        valid = reference_price is not None and abs(candidate_price - reference_price) >= minimum_move
    return valid


MIN_MOVE_ATR = {"Hassas": 0.08, "Seçici": 0.16, "Dengeli": 0.12}


def choose_same_bar_pivot(high_side: PivotSide, low_side: PivotSide,
                          high_candidate: float, low_candidate: float,
                          source_atr: float, source_open: float, source_high: float,
                          source_low: float, source_close: float,
                          last_accepted_type: int, profile: str, mintick: float) -> Tuple[int, str, float, float]:
    """Pine: f_choose_same_bar_pivot — aynı barda çift pivot çözümü (dönüşümlü öncelik + ATR mesafe + mum gücü)."""
    min_move_atr = MIN_MOVE_ATR.get(profile, 0.12)
    high_valid = same_bar_candidate_valid(high_side, True, high_candidate, source_atr, last_accepted_type, min_move_atr, mintick)
    low_valid = same_bar_candidate_valid(low_side, False, low_candidate, source_atr, last_accepted_type, min_move_atr, mintick)

    if last_accepted_type == 1:
        reference_price = high_side.last_price()
    elif last_accepted_type == -1:
        reference_price = low_side.last_price()
    else:
        reference_price = (source_high + source_low) * 0.5

    def norm_dist(candidate: float, ref: Optional[float]) -> float:
        if ref is None:
            return 0.0
        return abs(candidate - ref) / max(source_atr, mintick * 10.0)

    high_distance_atr = norm_dist(high_candidate, reference_price)
    low_distance_atr = norm_dist(low_candidate, reference_price)

    selected_type = 0
    reason = "İki aday da kabul şartını sağlamadı"
    if high_valid and not low_valid:
        selected_type = 1
        reason = "Yalnız High adayı kabul edilebilir"
    elif low_valid and not high_valid:
        selected_type = -1
        reason = "Yalnız Low adayı kabul edilebilir"
    elif high_valid and low_valid:
        if last_accepted_type == 1:
            selected_type = -1
            reason = "Dönüşümlü swing önceliği: Low"
        elif last_accepted_type == -1:
            selected_type = 1
            reason = "Dönüşümlü swing önceliği: High"
        else:
            distance_difference = high_distance_atr - low_distance_atr
            equality_tolerance = {"Hassas": 0.05, "Seçici": 0.10}.get(profile, 0.075)
            if abs(distance_difference) > equality_tolerance:
                selected_type = 1 if distance_difference > 0.0 else -1
                reason = "Daha büyük ATR-normalize High hareketi" if selected_type == 1 else "Daha büyük ATR-normalize Low hareketi"
            else:
                candle_range = max(source_high - source_low, mintick)
                body_strength = abs(source_close - source_open) / candle_range
                if body_strength >= 0.35 and source_close > source_open:
                    selected_type = 1
                    reason = "Yakın mesafe; güçlü yükseliş mumu"
                elif body_strength >= 0.35 and source_close < source_open:
                    selected_type = -1
                    reason = "Yakın mesafe; güçlü düşüş mumu"
                else:
                    high_close_distance = abs(high_candidate - source_close)
                    low_close_distance = abs(source_close - low_candidate)
                    selected_type = 1 if high_close_distance >= low_close_distance else -1
                    reason = "Nötr mum; deterministik High seçimi" if selected_type == 1 else "Nötr mum; deterministik Low seçimi"
    return selected_type, reason, high_distance_atr, low_distance_atr


# --- ESKİ (BATCH) ARAYÜZ ---
# Eski diagnostic'ler dict-listeleri kullanıyor; korundu.

def find_pivots(df: pd.DataFrame, pivot_len: int) -> Tuple[List[Dict], List[Dict]]:
    """Eski batch pivot araması (test uyumluluğu için). Motor PivotSide kullanır."""
    high_pivots: List[Dict] = []
    low_pivots: List[Dict] = []
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    n = len(df)
    for i in range(pivot_len, n - pivot_len):
        if is_pivot_high(highs, i, pivot_len, pivot_len, n) is not None:
            high_pivots.append({
                "price": float(highs[i]),
                "bar": i,
                "confirm_bar": i + pivot_len,
                "locked": False,
            })
        if is_pivot_low(lows, i, pivot_len, pivot_len, n) is not None:
            low_pivots.append({
                "price": float(lows[i]),
                "bar": i,
                "confirm_bar": i + pivot_len,
                "locked": False,
            })
    return high_pivots, low_pivots


def side_from_legacy(pivot_dicts: List[Dict], max_pivots: int = 24) -> PivotSide:
    """Dict-listesini PivotSide'a çevir (legacy shim için)."""
    side = PivotSide(max_pivots=max(max_pivots, len(pivot_dicts)))
    for p in pivot_dicts:
        side.prices.append(float(p["price"]))
        side.bars.append(int(p["bar"]))
        side.confirm_bars.append(int(p.get("confirm_bar", p["bar"])))
        side.locked.append(bool(p.get("locked", False)))
    return side
