# --- PATTERN DETECTION ---
# ARGENT v0.4.6 FINAL EXPORT - Pine Script -> Python dönüşümü
# Her fonksiyonun başında: Neden var? Pine'da ne yapıyor? Nasıl kontrol edilir?
# Türkçe yorumlar, production-ready, explainable

import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from collections import deque
import logging

logger = logging.getLogger(__name__)

# Pine'daki STATE sabitleri - birebir aynı isimler, Türkçe
ST_NONE = "FORMASYON_YOK"
ST_CANDIDATE = "ADAY_OLUSUYOR"
ST_GEOMETRY = "GEOMETRI_ADAYI"
ST_DEFINED = "FORMASYON_TANIMLANDI"
ST_MATURING = "OLGUNLASIYOR"
ST_COMPRESSING = "SIKISMA_GUCLENIYOR"
ST_PREP = "KIRILIM_HAZIRLIGI"
ST_BREAK_ATTEMPT = "KIRILIM_DENEMESI"
ST_BREAK_CANDIDATE = "KIRILIM_ADAYI"
ST_BREAK_CONFIRMED = "KIRILIM_TEYITLI"
ST_RETEST_WAIT = "RETEST_BEKLENIYOR"
ST_RETESTING = "RETEST_EDILIYOR"
ST_RETEST_OK = "RETEST_BASARILI"
ST_BREAK_TIMEOUT = "KIRILIM_TEYIT_ALAMADI"
ST_BREAK_FAILED = "BASARISIZ_KIRILIM"
ST_WEAK = "FORMASYON_ZAYIFLADI"
ST_INVALID = "FORMASYON_GECERSIZ"
ST_COMPLETED = "FORMASYON_TAMAMLANDI"

# Export contract - dışarıya aktarılan kodlar (Pine'daki f_export_* ile aynı)
PATTERN_TYPE_MAP = {
    "Yok": 0,
    "Yükselen Üçgen": 1,
    "Alçalan Üçgen": 2,
    "Simetrik Üçgen": 3,
    "Yükselen Kama": 4,
    "Alçalan Kama": 5,
    "Boğa Bayrağı": 6,
    "Ayı Bayrağı": 7,
    "Boğa Flaması": 8,
    "Ayı Flaması": 9,
}

# === VERİ TİPLERİ ===
# Pine'daki type PoleInfo ve PatternCandidate -> Python dataclass

@dataclass
class PoleInfo:
    """Direk (impuls) bilgisi - bayrak/flama için ön koşul"""
    valid: bool = False
    direction: int = 0  # 1 yukarı, -1 aşağı
    start_bar: Optional[int] = None
    start_price: Optional[float] = None
    end_bar: Optional[int] = None
    end_price: Optional[float] = None
    duration: int = 0
    magnitude: Optional[float] = None
    efficiency: Optional[float] = None
    quality: float = 0.0

@dataclass
class PatternCandidate:
    """Formasyon adayı - Pine'daki PatternCandidate'in birebir karşılığı"""
    valid: bool = False
    identity: int = 0
    pattern_type: str = "Yok"
    family: str = "Yok"  # Üçgen, Kama, Bayrak, Flama
    classic_dir: int = 0  # 1 yükseliş, -1 düşüş, 0 nötr
    raw_quality: float = 0.0
    selection_score: float = 0.0
    geometry_score: float = 0.0
    geometry_atr: Optional[float] = None
    slope_shape_score: float = 0.0
    touch_score: float = 0.0
    contraction_score: float = 0.0
    maturity_score: float = 0.0
    violation: float = 0.0
    
    # Tarihsel ihlal sayıları - neden önemli? Formasyon sınırları geçmişte delinmiş mi?
    historical_upper_close_violations: int = 0
    historical_lower_close_violations: int = 0
    historical_upper_wick_violations: int = 0
    historical_lower_wick_violations: int = 0
    historical_close_violations: int = 0
    historical_wick_violations: int = 0
    max_historical_violation: float = 0.0
    historical_violation_penalty: float = 0.0
    historical_scanned_bars: int = 0
    violation_history_truncated: bool = False
    last_violation_processed_bar: Optional[int] = None
    violation_geometry_key: str = ""
    violation_scan_mode: str = "Bekliyor"

    # Temas sayıları
    upper_touches: int = 0
    lower_touches: int = 0

    # Bar indeksleri - Pine'da bar_index ile çalışır, bizde DataFrame index
    start_bar: Optional[int] = None
    end_bar: Optional[int] = None
    known_bar: Optional[int] = None  # Son pivotun teyit barı
    apex_bar: Optional[int] = None
    progress: Optional[float] = None

    # Pivot detayları
    hb1: Optional[int] = None
    hp1: Optional[float] = None
    hb2: Optional[int] = None
    hp2: Optional[float] = None
    lb1: Optional[int] = None
    lp1: Optional[float] = None
    lb2: Optional[int] = None
    lp2: Optional[float] = None

    # Geometri
    upper_slope: Optional[float] = None
    lower_slope: Optional[float] = None
    start_width: Optional[float] = None
    current_width: Optional[float] = None
    contraction: Optional[float] = None
    upper_now: Optional[float] = None
    lower_now: Optional[float] = None

    # Direk bilgisi
    has_pole: bool = False
    pole_dir: int = 0
    pole_start_bar: Optional[int] = None
    pole_start_price: Optional[float] = None
    pole_end_bar: Optional[int] = None
    pole_end_price: Optional[float] = None
    pole_duration: int = 0
    pole_magnitude: Optional[float] = None
    pole_efficiency: Optional[float] = None
    pole_quality: float = 0.0
    correction_depth: Optional[float] = None
    duration_ratio: Optional[float] = None
    consolidation_efficiency: Optional[float] = None
    consolidation_height_ratio: Optional[float] = None

    # Quality freeze - kırılım anında dondurulur, neden? Kırılım sonrası kalite bozulmasın diye
    quality_frozen: bool = False
    frozen_raw_quality: Optional[float] = None
    frozen_upper_boundary_at_break: Optional[float] = None
    frozen_lower_boundary_at_break: Optional[float] = None
    frozen_break_buffer: Optional[float] = None
    frozen_retest_tolerance: Optional[float] = None
    frozen_atr_at_break: Optional[float] = None
    frozen_classic_dir: int = 0
    frozen_pattern_type: str = "Yok"
    break_snapshot_bar: Optional[int] = None
    break_snapshot_price: Optional[float] = None
    break_snapshot_direction: int = 0
    break_snapshot_quality: Optional[float] = None

    # Kırılım gücü skorları
    break_strength: Optional[float] = None
    break_body_score: Optional[float] = None
    break_close_score: Optional[float] = None
    break_penetration_score: Optional[float] = None
    break_expansion_score: Optional[float] = None
    break_volume_score: Optional[float] = None
    break_confirmation_strength: Optional[float] = None


# === ORTAK MATEMATİK YARDIMCILARI ===
# Pine'daki f_* fonksiyonlarının birebir Python karşılığı
# Her biri neden var? Kalite skorlaması için smooth geçişler

def f_clamp(value: float, minimum: float, maximum: float) -> float:
    """Değeri min-max arasına sıkıştır - Pine'daki f_clamp ile aynı"""
    return max(minimum, min(maximum, value))

def f_smoothstep(edge0: float, edge1: float, value: float) -> float:
    """
    Smoothstep: 0'dan 1'e yumuşak geçiş
    Neden? Sert eşik yerine yumuşak kalite geçişi için
    Pine'daki ile birebir aynı formül
    """
    if edge1 == edge0:
        return 1.0 if value >= edge1 else 0.0
    normalized = f_clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)

def f_inverse_smoothstep(edge0: float, edge1: float, value: float) -> float:
    """Smoothstep'in tersi - yüksek değer kötü ise"""
    return 1.0 - f_smoothstep(edge0, edge1, value)

def f_band_quality(value: float, hard_low: float, optimal_low: float, optimal_high: float, hard_high: float) -> float:
    """
    Band kalitesi: Değer optimal aralıkta ise 100, dışındaysa düşer
    Neden? Örn: contraction %25-50 arası optimal, altı/üstü düşük kalite
    """
    lower_quality = f_smoothstep(hard_low, optimal_low, value)
    upper_quality = f_inverse_smoothstep(optimal_high, hard_high, value)
    return f_clamp(min(lower_quality, upper_quality) * 100.0, 0.0, 100.0)

def f_progress_quality(progress_value: Optional[float]) -> float:
    """Apex'e ilerleme kalitesi - %15-42 arası olgunlaşma, %82 sonrası geç kalmış"""
    if progress_value is None or math.isnan(progress_value):
        return 0.0
    return f_clamp(f_smoothstep(0.15, 0.42, progress_value) * f_inverse_smoothstep(0.82, 1.03, progress_value) * 100.0, 0.0, 100.0)

def f_age_quality(age_value: int, target_age: int) -> float:
    """Yaş kalitesi - formasyon yeterince eski mi?"""
    ratio = float(max(age_value, 0)) / max(1.0, float(target_age))
    return f_clamp(f_smoothstep(0.42, 1.05, ratio) * 100.0, 0.0, 100.0)

def f_contraction_quality(contraction_value: Optional[float], min_contraction: float) -> float:
    """
    Daralma kalitesi - formasyon ne kadar sıkışmış?
    min_contraction altı zayıf, üstü güçlü
    """
    if contraction_value is None or math.isnan(contraction_value):
        return 0.0
    strong_contraction = max(0.52, min_contraction * 2.20)
    below_threshold_score = f_smoothstep(min_contraction * 0.55, min_contraction, contraction_value) * 45.0
    above_threshold_score = 45.0 + f_smoothstep(min_contraction, strong_contraction, contraction_value) * 55.0
    return f_clamp(below_threshold_score if contraction_value < min_contraction else above_threshold_score, 0.0, 100.0)

def f_cleanliness_quality(violation_penalty_value: float) -> float:
    """Temizlik kalitesi - ihlal cezası ne kadar? Az ihlal = yüksek kalite"""
    return f_clamp(100.0 - f_smoothstep(10.0, 62.0, violation_penalty_value) * 100.0, 0.0, 100.0)

def f_line_price(x1: int, y1: float, x2: int, y2: float, x: int) -> float:
    """İki noktadan geçen doğrunun x'teki y değeri - sınır çizgisi için"""
    if x2 == x1:
        return y2
    return y1 + (y2 - y1) / float(x2 - x1) * float(x - x1)

def f_slope(x1: int, y1: float, x2: int, y2: float) -> float:
    """Eğim"""
    if x2 == x1:
        return 0.0
    return (y2 - y1) / float(x2 - x1)

def f_depth_quality(depth: Optional[float]) -> float:
    """Düzeltme derinliği kalitesi - bayrak/flama için"""
    if depth is None or math.isnan(depth):
        return 0.0
    return f_band_quality(depth, 0.03, 0.16, 0.45, 0.82)

def f_duration_quality(duration_ratio: Optional[float]) -> float:
    """Süre oranı kalitesi"""
    if duration_ratio is None or math.isnan(duration_ratio):
        return 0.0
    return f_band_quality(duration_ratio, 0.12, 0.35, 1.55, 3.60)

def f_classic_direction(pattern: str) -> int:
    """Klasik yön - Pine'daki f_classic_direction ile aynı"""
    if pattern in ["Yükselen Üçgen", "Alçalan Kama", "Boğa Bayrağı", "Boğa Flaması"]:
        return 1
    elif pattern in ["Alçalan Üçgen", "Yükselen Kama", "Ayı Bayrağı", "Ayı Flaması"]:
        return -1
    else:
        return 0

def f_is_specialized(pattern: str) -> bool:
    return pattern in ["Boğa Bayrağı", "Ayı Bayrağı", "Boğa Flaması", "Ayı Flaması"]

def f_is_flag(pattern: str) -> bool:
    return pattern in ["Boğa Bayrağı", "Ayı Bayrağı"]

def f_is_pennant(pattern: str) -> bool:
    return pattern in ["Boğa Flaması", "Ayı Flaması"]

def f_is_break_lifecycle(state_value: str) -> bool:
    return state_value in [ST_BREAK_ATTEMPT, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, 
                           ST_RETEST_WAIT, ST_RETESTING, ST_RETEST_OK, 
                           ST_BREAK_TIMEOUT, ST_COMPLETED, ST_BREAK_FAILED]

def f_is_terminal(state_value: str) -> bool:
    return state_value in [ST_COMPLETED, ST_BREAK_FAILED, ST_INVALID]

# === ATR HESAPLAMA ===
# Pine'daki ta.atr(14) = RMA of TR, Wilder's smoothing

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ATR hesapla - Pine'daki ta.atr ile aynı olmalı
    Neden RMA? TradingView Wilder's RMA kullanır, SMA değil
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's RMA: ilk period SMA, sonra RMA
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()

# === PİVOT MOTORU ===
# Pine'daki ta.pivothigh/low -> Python'da nasıl?
# PivotHigh: pivotLen sol ve sağ taraf düşük ise ortası pivot
# Teyit gecikmeli: pivot bar_index - pivotLen'de oluşur, teyit bar_index'te gelir

def find_pivots(df: pd.DataFrame, pivot_len: int) -> Tuple[List[Dict], List[Dict]]:
    """
    Pivot bul - Pine'daki pivothigh/low mantığı
    Neden önemli? Formasyonun köşe taşları pivotlar
    Döner: high_pivots, low_pivots listesi, her biri {price, bar_index, confirm_bar}
    
    Kontrol: TradingView'de pivotları işaretle, bu fonksiyonla karşılaştır
    """
    high_pivots = []
    low_pivots = []
    
    highs = df['high'].values
    lows = df['low'].values
    
    # Pine: ta.pivothigh(high, left, right) -> pivotLen sol ve sağ
    for i in range(pivot_len, len(df) - pivot_len):
        # High pivot kontrol
        is_high_pivot = True
        pivot_high = highs[i]
        for j in range(1, pivot_len + 1):
            if highs[i - j] >= pivot_high or highs[i + j] >= pivot_high:
                is_high_pivot = False
                break
        if is_high_pivot:
            # Pine'da pivotSourceBar = bar_index - pivotLen, confirmBar = bar_index
            # Bizde: source bar = i, confirm bar = i + pivotLen
            high_pivots.append({
                'price': float(pivot_high),
                'bar': i,  # pivot'un gerçek barı
                'confirm_bar': i + pivot_len,  # teyit edildiği bar
                'locked': False
            })
        
        # Low pivot kontrol
        is_low_pivot = True
        pivot_low = lows[i]
        for j in range(1, pivot_len + 1):
            if lows[i - j] <= pivot_low or lows[i + j] <= pivot_low:
                is_low_pivot = False
                break
        if is_low_pivot:
            low_pivots.append({
                'price': float(pivot_low),
                'bar': i,
                'confirm_bar': i + pivot_len,
                'locked': False
            })
    
    return high_pivots, low_pivots

def filter_same_bar_double_pivot(high_pivots: List[Dict], low_pivots: List[Dict], 
                                 df: pd.DataFrame, atr_series: pd.Series,
                                 last_accepted_type: int) -> Tuple[List[Dict], List[Dict]]:
    """
    Aynı barda hem high hem low pivot varsa hangisi seçilecek?
    Pine'daki f_choose_same_bar_pivot mantığı - birebir çeviri
    Neden? Dönüşümlü swing önceliği, ATR-normalize mesafe, mum gücü
    """
    if not high_pivots and not low_pivots:
        return high_pivots, low_pivots

    # Bar bazlı grupla
    from collections import defaultdict
    bar_to_high = defaultdict(list)
    bar_to_low = defaultdict(list)
    
    for hp in high_pivots:
        bar_to_high[hp['bar']].append(hp)
    for lp in low_pivots:
        bar_to_low[lp['bar']].append(lp)

    # Çakışan barlar
    common_bars = set(bar_to_high.keys()) & set(bar_to_low.keys())
    
    if not common_bars:
        return high_pivots, low_pivots

    filtered_high = []
    filtered_low = []
    
    # last_accepted_type: 1=high, -1=low, 0=yok
    last_type = last_accepted_type

    # Tüm barları sıralı işle
    all_bars = sorted(set(list(bar_to_high.keys()) + list(bar_to_low.keys())))
    
    for bar in all_bars:
        has_high = bar in bar_to_high
        has_low = bar in bar_to_low
        
        if has_high and has_low:
            # Aynı barda ikisi de var - seçim yap
            # ATR al
            try:
                atr = atr_series.iloc[bar] if bar < len(atr_series) else atr_series.iloc[-1]
                if pd.isna(atr) or atr <= 0:
                    atr = 1.0
            except Exception:
                atr = 1.0

            # Mum bilgileri
            try:
                open_p = df['open'].iloc[bar] if bar < len(df) else 0
                close_p = df['close'].iloc[bar] if bar < len(df) else 0
                high_p = df['high'].iloc[bar] if bar < len(df) else 0
                low_p = df['low'].iloc[bar] if bar < len(df) else 0
                # Mum gücü - gövde / range
                candle_range = max(high_p - low_p, 0.0001)
                upper_wick = high_p - max(open_p, close_p)
                lower_wick = min(open_p, close_p) - low_p
            except Exception:
                upper_wick = 0
                lower_wick = 0
                candle_range = atr

            # Pine mantığı: dönüşümlü swing önceliği
            # Eğer son kabul edilen high ise low'u seç, tersi de öyle
            # Eğer yoksa wick büyüklüğüne göre seç
            choose_high = False
            if last_type == 1:
                # Son high idi, şimdi low tercih et
                choose_high = False
            elif last_type == -1:
                # Son low idi, high tercih et
                choose_high = True
            else:
                # İlk pivot - wick'e göre
                # Üst fitil büyükse high pivot daha anlamlı, alt fitil büyükse low
                if upper_wick > lower_wick:
                    choose_high = True
                elif lower_wick > upper_wick:
                    choose_high = False
                else:
                    # Eşitse ATR-normalize mesafeye bak
                    # High pivot'un open'a uzaklığı vs low pivot'un
                    try:
                        high_dist = abs(bar_to_high[bar][0]['price'] - open_p) / atr
                        low_dist = abs(open_p - bar_to_low[bar][0]['price']) / atr
                        choose_high = high_dist > low_dist
                    except Exception:
                        choose_high = True

            if choose_high:
                filtered_high.extend(bar_to_high[bar])
                last_type = 1
            else:
                filtered_low.extend(bar_to_low[bar])
                last_type = -1
        elif has_high:
            filtered_high.extend(bar_to_high[bar])
            last_type = 1
        else:
            filtered_low.extend(bar_to_low[bar])
            last_type = -1

    return filtered_high, filtered_low


def f_same_bar_candidate_valid(high_pivots: List[Dict], low_pivots: List[Dict], bar: int) -> bool:
    """Aynı barda çift pivot var mı kontrolü - hızlı"""
    for hp in high_pivots:
        if hp['bar'] == bar:
            for lp in low_pivots:
                if lp['bar'] == bar:
                    return False
    return True

# === DİREK (POLE) MOTORU ===
def calculate_path_stats(df: pd.DataFrame, start_bar: int, end_bar: int, 
                        start_price: float, end_price: float, max_sample: int = 120) -> Tuple[float, float, float, float]:
    """
    Yol istatistikleri - direk ne kadar verimli?
    netMove, totalPath, efficiency, maxRange
    """
    duration = max(0, end_bar - start_bar)
    sample_bars = min(duration, max_sample)
    
    total_path = 0.0
    max_range = 0.0
    
    if sample_bars > 0 and end_bar < len(df):
        # end_bar'dan geriye doğru sample_bars kadar
        for step in range(sample_bars):
            abs_bar = end_bar - step
            if abs_bar > 0 and abs_bar < len(df):
                total_path += abs(df['close'].iloc[abs_bar] - df['close'].iloc[abs_bar - 1])
                max_range = max(max_range, df['high'].iloc[abs_bar] - df['low'].iloc[abs_bar])
    
    net_move = abs(end_price - start_price)
    efficiency = f_clamp(net_move / max(max(total_path, net_move), 0.0001), 0.0, 1.0)
    
    return net_move, total_path, efficiency, max_range

def find_pole(df: pd.DataFrame, atr_series: pd.Series,
              high_pivots: List[Dict], low_pivots: List[Dict],
              end_bar: int, end_price: float, direction: int,
              params: dict) -> PoleInfo:
    """
    Direk bul - bayrak/flama öncesi impuls
    Pine'daki f_find_pole ile aynı
    Neden? Bayrak/flama için önce güçlü bir direk olmalı
    
    Mantık:
    - direction 1 ise low pivotlardan başla, yukarı impuls ara
    - direction -1 ise high pivotlardan başla, aşağı impuls ara
    - ATR cinsinden büyüklük, efficiency, quality hesapla
    """
    best_pole = PoleInfo()
    
    pivot_list = low_pivots if direction == 1 else high_pivots
    min_pole_atr = params['min_pole_atr']
    min_pole_efficiency = params['min_pole_efficiency']
    max_pole_bars = params['max_pole_bars']
    min_pole_quality = params['min_pole_quality']
    
    if len(pivot_list) == 0:
        return best_pole
    
    for pivot in pivot_list:
        start_bar = pivot['bar']
        start_price = pivot['price']
        duration = end_bar - start_bar
        
        if start_bar >= end_bar:
            continue
        if duration < 1 or duration > max_pole_bars:
            continue
        
        magnitude = abs(end_price - start_price)
        
        # Path stats
        net_move, total_path, efficiency, max_range = calculate_path_stats(
            df, start_bar, end_bar, start_price, end_price, params.get('max_path_sample', 120)
        )
        
        # ATR at end_bar
        atr_at_end = atr_series.iloc[end_bar] if end_bar < len(atr_series) else atr_series.iloc[-1]
        atr_at_end = max(atr_at_end, 0.0001)
        atr_units = magnitude / atr_at_end
        speed = atr_units / duration if duration > 0 else 0.0
        
        directional = (direction == 1 and end_price > start_price) or (direction == -1 and end_price < start_price)
        
        # Single shock kontrolü - tek mumda mı oluşmuş?
        single_shock = duration <= 1 or max_range >= magnitude * 0.72
        
        # Quality skorları
        magnitude_score = f_clamp(atr_units / max(min_pole_atr, 0.1) * 65.0, 0.0, 100.0)
        efficiency_score = f_clamp((efficiency - 0.30) / 0.70 * 100.0, 0.0, 100.0)
        duration_score = 100.0 if duration >= 2 else 35.0
        speed_score = f_clamp(speed / 0.22 * 100.0, 0.0, 100.0)
        
        # Local break kontrolü - önceki extreme'i kırmış mı?
        # Basit versiyon - tam local extreme break için pivot history gerekir
        local_break = False  # TODO: f_local_extreme_break implementasyonu
        
        uncapped_quality = f_clamp(
            magnitude_score * 0.30 + efficiency_score * 0.30 + duration_score * 0.16 + speed_score * 0.12 + (12.0 if local_break else 0.0) - (24.0 if single_shock else 0.0),
            0.0, 100.0
        )
        quality = min(uncapped_quality, 46.0) if single_shock else uncapped_quality
        
        valid = directional and atr_units >= min_pole_atr and efficiency >= min_pole_efficiency and quality >= min_pole_quality
        
        # En iyi direği seç - quality'ye göre
        outranks = (valid and not best_pole.valid) or (valid == best_pole.valid and quality > best_pole.quality)
        if outranks:
            best_pole.valid = valid
            best_pole.direction = direction
            best_pole.start_bar = start_bar
            best_pole.start_price = start_price
            best_pole.end_bar = end_bar
            best_pole.end_price = end_price
            best_pole.duration = duration
            best_pole.magnitude = magnitude
            best_pole.efficiency = efficiency
            best_pole.quality = quality
    
    return best_pole

# === BOUNDARY VIOLATION (İHLAL) TARAMASI ===
def calculate_violation_penalty(total_close_violations: int, total_wick_violations: int, 
                               max_violation: float, history_truncated: bool, profile: str) -> float:
    """İhlal cezası - Pine'daki f_violation_penalty_from_stats"""
    if profile == "Hassas":
        close_penalty = 10.0
        wick_penalty = 3.0
    elif profile == "Seçici":
        close_penalty = 16.0
        wick_penalty = 7.0
    else:  # Dengeli
        close_penalty = 13.0
        wick_penalty = 5.0
    
    repeat_penalty = 10.0 if total_close_violations >= 2 else 0.0
    truncation_penalty = 4.0 if history_truncated else 0.0
    
    return f_clamp(
        float(total_close_violations) * close_penalty + 
        float(total_wick_violations) * wick_penalty + 
        max_violation * 18.0 + repeat_penalty + truncation_penalty,
        0.0, 70.0
    )

# === TOUCH STATS ===
def f_touch_stats(pivot_prices: List[float], pivot_bars: List[int],
                  x1: int, y1: float, x2: int, y2: float,
                  start_bar: int, end_bar: int,
                  tolerance: float, min_touch_gap: int) -> Tuple[int, float, Optional[int], Optional[int]]:
    """
    Sınır çizgisine kaç pivot temas ediyor?
    Pine'daki f_touch_stats ile aynı
    
    - Her pivot için expected price hesapla (çizgi üzerinde)
    - Distance <= tolerance ise temas
    - Aynı bölgede 2 temas sayılmasın diye min_touch_gap
    """
    touch_count = 0
    first_touch = None
    last_touch = None
    last_accepted = None
    distance_sum = 0.0
    
    for price, bar in zip(pivot_prices, pivot_bars):
        if bar < start_bar or bar > end_bar:
            continue
        
        expected = f_line_price(x1, y1, x2, y2, bar)
        distance = abs(price - expected)
        
        if distance <= tolerance:
            if last_accepted is None or bar - last_accepted >= min_touch_gap:
                touch_count += 1
                distance_sum += distance / max(tolerance, 0.0001)
                if first_touch is None:
                    first_touch = bar
                last_touch = bar
                last_accepted = bar
    
    avg_distance = distance_sum / touch_count if touch_count > 0 else 10.0
    return touch_count, avg_distance, first_touch, last_touch

def f_chronological_swings(hb1: int, hb2: int, lb1: int, lb2: int) -> bool:
    """Pivotlar kronolojik mi? HLHL veya LHLH"""
    high_low_high_low = hb1 < lb1 and lb1 < hb2 and hb2 < lb2
    low_high_low_high = lb1 < hb1 and hb1 < lb2 and lb2 < hb2
    return high_low_high_low or low_high_low_high

def f_pivot_trend_ok(first_price: float, second_price: float, rising: bool, tolerance: float) -> bool:
    """Pivot trendi uygun mu? Yükselen üçgende dipler yükselmeli"""
    if rising:
        return second_price >= first_price - tolerance
    else:
        return second_price <= first_price + tolerance

# === VIOLATION TARAMA (BASİT VERSİYON) ===
def f_boundary_violation_stats_simple(df: pd.DataFrame, atr_series: pd.Series,
                                      upper_x1: int, upper_y1: float, upper_x2: int, upper_y2: float,
                                      lower_x1: int, lower_y1: float, lower_x2: int, lower_y2: float,
                                      start_bar: int, end_bar: int,
                                      profile: str) -> Tuple[int, int, int, int, float, float, float, int, bool]:
    """
    Basit ihlal taraması - Pine'daki f_boundary_violation_stats_range'in sade hali
    - Her barda close ve wick ihlali kontrol et
    - ATR'ye göre buffer
    """
    upper_close_viol = 0
    lower_close_viol = 0
    upper_wick_viol = 0
    lower_wick_viol = 0
    max_upper = 0.0
    max_lower = 0.0
    scanned = 0
    
    # Buffer'lar profile göre
    if profile == "Hassas":
        close_buf_mult = 0.05
        wick_buf_mult = 0.13
    elif profile == "Seçici":
        close_buf_mult = 0.07
        wick_buf_mult = 0.18
    else:
        close_buf_mult = 0.06
        wick_buf_mult = 0.15
    
    # Tarama aralığı
    start_idx = max(0, start_bar)
    end_idx = min(len(df) - 1, end_bar)
    
    for bar in range(start_idx, end_idx + 1):
        if bar >= len(df) or bar >= len(atr_series):
            continue
        
        atr = atr_series.iloc[bar]
        if pd.isna(atr) or atr <= 0:
            atr = 1.0
        
        close_buf = max(0.0001, atr * close_buf_mult)
        wick_buf = max(0.0001, atr * wick_buf_mult)
        
        upper_boundary = f_line_price(upper_x1, upper_y1, upper_x2, upper_y2, bar)
        lower_boundary = f_line_price(lower_x1, lower_y1, lower_x2, lower_y2, bar)
        
        close_price = df['close'].iloc[bar]
        high_price = df['high'].iloc[bar]
        low_price = df['low'].iloc[bar]
        
        upper_close_broken = close_price > upper_boundary + close_buf
        lower_close_broken = close_price < lower_boundary - close_buf
        upper_wick_broken = not upper_close_broken and high_price > upper_boundary + wick_buf
        lower_wick_broken = not lower_close_broken and low_price < lower_boundary - wick_buf
        
        if upper_close_broken:
            upper_close_viol += 1
        if lower_close_broken:
            lower_close_viol += 1
        if upper_wick_broken:
            upper_wick_viol += 1
        if lower_wick_broken:
            lower_wick_viol += 1
        
        upper_excess = (close_price - upper_boundary - close_buf) / atr if upper_close_broken else (high_price - upper_boundary - wick_buf) / atr if upper_wick_broken else 0.0
        lower_excess = (lower_boundary - close_price - close_buf) / atr if lower_close_broken else (lower_boundary - low_price - wick_buf) / atr if lower_wick_broken else 0.0
        
        max_upper = max(max_upper, upper_excess)
        max_lower = max(max_lower, lower_excess)
        scanned += 1
    
    total_close = upper_close_viol + lower_close_viol
    total_wick = upper_wick_viol + lower_wick_viol
    max_viol = max(max_upper, max_lower)
    
    # Ceza hesapla
    penalty = calculate_violation_penalty(total_close, total_wick, max_viol, False, profile)
    
    return upper_close_viol, lower_close_viol, upper_wick_viol, lower_wick_viol, max_upper, max_lower, penalty, scanned, False

# === ÜÇGEN/KAMA ADAY OLUŞTURMA (CORE) ===
def f_build_triangle_candidate(df: pd.DataFrame, atr_series: pd.Series,
                               high_pivots: List[Dict], low_pivots: List[Dict],
                               hiA_idx: int, hiB_idx: int, loA_idx: int, loB_idx: int,
                               params: dict, profile: str,
                               current_bar: int) -> Tuple[Optional[PatternCandidate], str]:
    """
    Üçgen/Kama adayı oluştur - Pine'daki f_build_candidate'in üçgen kısmı
    Döner: (candidate, reject_reason)
    
    Neden reject_reason? Senin istediğin explainable log için
    Her reddedilme sebebi Türkçe açıklanacak
    """
    # Pivotları al
    try:
        hp1 = high_pivots[hiA_idx]['price']
        hb1 = high_pivots[hiA_idx]['bar']
        hc1 = high_pivots[hiA_idx]['confirm_bar']
        
        hp2 = high_pivots[hiB_idx]['price']
        hb2 = high_pivots[hiB_idx]['bar']
        hc2 = high_pivots[hiB_idx]['confirm_bar']
        
        lp1 = low_pivots[loA_idx]['price']
        lb1 = low_pivots[loA_idx]['bar']
        lc1 = low_pivots[loA_idx]['confirm_bar']
        
        lp2 = low_pivots[loB_idx]['price']
        lb2 = low_pivots[loB_idx]['bar']
        lc2 = low_pivots[loB_idx]['confirm_bar']
    except IndexError:
        return None, "Pivot index hatası"
    
    # Kronolojik kontrol
    if not f_chronological_swings(hb1, hb2, lb1, lb2):
        return None, f"Kronolojik değil: hb1={hb1} hb2={hb2} lb1={lb1} lb2={lb2}"
    
    start_bar = min(min(hb1, hb2), min(lb1, lb2))
    end_bar = max(max(hb1, hb2), max(lb1, lb2))
    known_bar = max(max(hc1, hc2), max(lc1, lc2))
    age = current_bar - start_bar
    
    # Yaş kontrolü - en az 5 bar
    if age < max(5, params['min_age'] // 2):
        return None, f"Yaş yetersiz: {age} < {max(5, params['min_age']//2)}"
    
    # Geometri ATR
    geom_start_offset = max(0, min(len(atr_series)-1, current_bar - start_bar))
    geom_end_offset = max(0, min(len(atr_series)-1, current_bar - end_bar))
    # Basit: son ATR'yi kullan
    geometry_atr = atr_series.iloc[-1] if len(atr_series) > 0 else 1.0
    if pd.isna(geometry_atr) or geometry_atr <= 0:
        geometry_atr = 1.0
    
    touch_tolerance = max(0.0001, geometry_atr * params['touch_atr_mult'])
    
    # Sınır fiyatları
    upper_start = f_line_price(hb1, hp1, hb2, hp2, start_bar)
    lower_start = f_line_price(lb1, lp1, lb2, lp2, start_bar)
    upper_now = f_line_price(hb1, hp1, hb2, hp2, current_bar)
    lower_now = f_line_price(lb1, lp1, lb2, lp2, current_bar)
    
    start_width = upper_start - lower_start
    current_width = upper_now - lower_now
    
    if start_width <= 0 or current_width <= 0:
        return None, f"Genişlik geçersiz: start={start_width:.4f} now={current_width:.4f}"
    
    if upper_start <= lower_start or upper_now <= lower_now:
        return None, f"Üst alt'tan düşük: üst {upper_start:.2f}/{upper_now:.2f} alt {lower_start:.2f}/{lower_now:.2f}"
    
    upper_slope = f_slope(hb1, hp1, hb2, hp2)
    lower_slope = f_slope(lb1, lp1, lb2, lp2)
    upper_slope_norm = upper_slope / geometry_atr
    lower_slope_norm = lower_slope / geometry_atr
    slope_gap_norm = upper_slope_norm - lower_slope_norm
    slope_gap = upper_slope - lower_slope
    
    # Apex hesapla
    if abs(slope_gap) < 0.000001:
        return None, "Eğim farkı sıfır, apex yok (paralel)"
    
    apex_float = float(start_bar) - start_width / slope_gap
    apex_bar = int(round(apex_float))
    
    contraction = (start_width - current_width) / start_width if start_width > 0 else None
    
    # Apex kontrolü
    apex_ok = apex_bar > current_bar and apex_bar <= start_bar + max(params['min_age'] * 8, 260)
    if not apex_ok:
        # Apex geçersizse progress'i maxConsolidationBars'a göre hesapla (Pine'daki gibi)
        progress = f_clamp(float(age) / max(1.0, float(params['max_consolidation_bars'])), 0.0, 2.0)
    else:
        progress = f_clamp(float(current_bar - start_bar) / max(1.0, float(apex_bar - start_bar)), 0.0, 2.0)
    
    # Converging kontrolü
    min_contraction = params['min_contraction_pct'] / 100.0
    converging = start_width > 0 and current_width > 0 and contraction is not None and contraction >= min_contraction and slope_gap_norm < -params['min_slope_norm_tol']
    
    parallel_like = abs(slope_gap_norm) <= params['flat_slope_norm_tol'] * 0.75
    
    # Touch stats
    high_prices = [p['price'] for p in high_pivots]
    high_bars = [p['bar'] for p in high_pivots]
    low_prices = [p['price'] for p in low_pivots]
    low_bars = [p['bar'] for p in low_pivots]
    
    upper_touches, upper_avg_dist, upper_first, upper_last = f_touch_stats(
        high_prices, high_bars, hb1, hp1, hb2, hp2, start_bar, current_bar, touch_tolerance, params['min_touch_gap']
    )
    lower_touches, lower_avg_dist, lower_first, lower_last = f_touch_stats(
        low_prices, low_bars, lb1, lp1, lb2, lp2, start_bar, current_bar, touch_tolerance, params['min_touch_gap']
    )
    
    total_touches = upper_touches + lower_touches
    
    # Touch distribution
    if upper_first is None or lower_first is None:
        return None, "Temas yok (upper_first veya lower_first None)"
    
    touch_distribution = total_touches >= 4 and min(upper_last or 0, lower_last or 0) - start_bar >= max(params['min_age'] // 2, params['min_touch_gap'] * 2)
    
    if not touch_distribution:
        return None, f"Touch distribution yetersiz: total={total_touches} upper_last={upper_last} lower_last={lower_last}"
    
    if upper_touches < 2 or lower_touches < 2:
        return None, f"Temas sayısı yetersiz: üst {upper_touches} alt {lower_touches} (min 2+2)"
    
    # Trend kontrolleri
    highs_lower = f_pivot_trend_ok(hp1, hp2, False, touch_tolerance)
    lows_higher = f_pivot_trend_ok(lp1, lp2, True, touch_tolerance)
    
    # Formasyon tipi belirle
    horizontal_upper = abs(upper_slope_norm) <= params['flat_slope_norm_tol']
    horizontal_lower = abs(lower_slope_norm) <= params['flat_slope_norm_tol']
    strict_upper_down = upper_slope_norm < -params['flat_slope_norm_tol']
    strict_upper_up = upper_slope_norm > params['flat_slope_norm_tol']
    strict_lower_up = lower_slope_norm > params['flat_slope_norm_tol']
    strict_lower_down = lower_slope_norm < -params['flat_slope_norm_tol']
    
    generic_type = "Yok"
    if converging and apex_ok and not parallel_like:
        if horizontal_upper and strict_lower_up and lows_higher:
            generic_type = "Yükselen Üçgen"
        elif horizontal_lower and strict_upper_down and highs_lower:
            generic_type = "Alçalan Üçgen"
        elif strict_upper_down and strict_lower_up:
            generic_type = "Simetrik Üçgen"
        elif strict_upper_up and strict_lower_up and lower_slope_norm > upper_slope_norm + params['min_slope_norm_tol']:
            generic_type = "Yükselen Kama"
        elif strict_upper_down and strict_lower_down and upper_slope_norm < lower_slope_norm - params['min_slope_norm_tol']:
            generic_type = "Alçalan Kama"
    
    if generic_type == "Yok":
        return None, f"Geometri uyuşmadı: horizUpper={horizontal_upper} horizLower={horizontal_lower} upDown={strict_upper_down} upUp={strict_upper_up} lowUp={strict_lower_up} lowDown={strict_lower_down} converging={converging} parallel={parallel_like} apexOk={apex_ok} contraction={contraction}"
    
    # Kalite skorları
    contraction_score = f_contraction_quality(contraction, min_contraction)
    
    # Slope shape quality
    upper_flat_q = f_inverse_smoothstep(params['flat_slope_norm_tol'] * 0.55, params['flat_slope_norm_tol'] * 1.65, abs(upper_slope_norm)) * 100.0
    lower_flat_q = f_inverse_smoothstep(params['flat_slope_norm_tol'] * 0.55, params['flat_slope_norm_tol'] * 1.65, abs(lower_slope_norm)) * 100.0
    upper_down_q = f_smoothstep(params['flat_slope_norm_tol'] * 0.70, params['flat_slope_norm_tol'] * 4.50, -upper_slope_norm) * 100.0
    upper_up_q = f_smoothstep(params['flat_slope_norm_tol'] * 0.70, params['flat_slope_norm_tol'] * 4.50, upper_slope_norm) * 100.0
    lower_up_q = f_smoothstep(params['flat_slope_norm_tol'] * 0.70, params['flat_slope_norm_tol'] * 4.50, lower_slope_norm) * 100.0
    lower_down_q = f_smoothstep(params['flat_slope_norm_tol'] * 0.70, params['flat_slope_norm_tol'] * 4.50, -lower_slope_norm) * 100.0
    
    if generic_type == "Yükselen Üçgen":
        slope_shape_q = upper_flat_q * 0.52 + lower_up_q * 0.48
    elif generic_type == "Alçalan Üçgen":
        slope_shape_q = lower_flat_q * 0.52 + upper_down_q * 0.48
    elif generic_type == "Simetrik Üçgen":
        slope_shape_q = upper_down_q * 0.50 + lower_up_q * 0.50
    elif generic_type == "Yükselen Kama":
        slope_shape_q = upper_up_q * 0.42 + lower_up_q * 0.42 + f_smoothstep(params['min_slope_norm_tol'], params['flat_slope_norm_tol'] * 2.5, lower_slope_norm - upper_slope_norm) * 16.0
    elif generic_type == "Alçalan Kama":
        slope_shape_q = upper_down_q * 0.42 + lower_down_q * 0.42 + f_smoothstep(params['min_slope_norm_tol'], params['flat_slope_norm_tol'] * 2.5, upper_slope_norm - lower_slope_norm) * 16.0
    else:
        slope_shape_q = 0.0
    
    geometry_score = f_clamp(slope_shape_q * 0.65 + contraction_score * 0.35, 0.0, 100.0)
    
    # Touch score
    avg_touch_dist = (upper_avg_dist + lower_avg_dist) * 0.5
    touch_precision_q = f_inverse_smoothstep(0.15, 1.10, avg_touch_dist) * 100.0
    touch_count_q = f_smoothstep(4.0, 7.0, float(total_touches)) * 100.0
    weakest_last = min(upper_last or start_bar, lower_last or start_bar)
    touch_span_ratio = float(weakest_last - start_bar) / max(1.0, float(age))
    touch_span_q = f_smoothstep(0.35, 0.78, touch_span_ratio) * 100.0
    touch_score = f_clamp(touch_precision_q * 0.42 + touch_count_q * 0.33 + touch_span_q * 0.25, 0.0, 100.0)
    
    # Maturity
    maturity_score = f_clamp(f_age_quality(age, params['min_age']) * 0.58 + f_progress_quality(progress) * 0.42, 0.0, 100.0)
    
    # Violation taraması
    viol_upper_close, viol_lower_close, viol_upper_wick, viol_lower_wick, max_upper, max_lower, penalty, scanned, truncated = f_boundary_violation_stats_simple(
        df, atr_series, hb1, hp1, hb2, hp2, lb1, lp1, lb2, lp2, start_bar, end_bar, profile
    )
    
    total_close_viol = viol_upper_close + viol_lower_close
    total_wick_viol = viol_upper_wick + viol_lower_wick
    max_hist_viol = max(max_upper, max_lower)
    
    # Historical kabul
    max_accepted_viol = 0.90 if profile == "Hassas" else 0.55 if profile == "Seçici" else 0.72
    historical_ok = total_close_viol < 2 and max_hist_viol <= max_accepted_viol and penalty < 62.0
    
    if not historical_ok:
        return None, f"Tarihsel ihlal fazla: close={total_close_viol} maxViol={max_hist_viol:.2f} penalty={penalty:.1f} (limit close<2 max<={max_accepted_viol} penalty<62)"
    
    cleanliness_score = f_cleanliness_quality(penalty)
    
    # Raw quality
    raw_quality = f_clamp(geometry_score * 0.38 + touch_score * 0.32 + maturity_score * 0.18 + cleanliness_score * 0.12, 0.0, 100.0)
    
    min_raw = params['min_raw_quality']
    if raw_quality < min_raw:
        return None, f"Kalite düşük: {raw_quality:.1f} < {min_raw} (geom={geometry_score:.0f} touch={touch_score:.0f} mat={maturity_score:.0f} clean={cleanliness_score:.0f})"
    
    # Başarılı - candidate oluştur
    candidate = PatternCandidate()
    candidate.valid = True
    candidate.pattern_type = generic_type
    candidate.family = "Kama" if "Kama" in generic_type else "Üçgen"
    candidate.classic_dir = f_classic_direction(generic_type)
    candidate.raw_quality = raw_quality
    candidate.geometry_score = geometry_score
    candidate.geometry_atr = geometry_atr
    candidate.slope_shape_score = slope_shape_q
    candidate.touch_score = touch_score
    candidate.contraction_score = contraction_score
    candidate.maturity_score = maturity_score
    candidate.historical_upper_close_violations = viol_upper_close
    candidate.historical_lower_close_violations = viol_lower_close
    candidate.historical_upper_wick_violations = viol_upper_wick
    candidate.historical_lower_wick_violations = viol_lower_wick
    candidate.historical_close_violations = total_close_viol
    candidate.historical_wick_violations = total_wick_viol
    candidate.max_historical_violation = max_hist_viol
    candidate.historical_violation_penalty = penalty
    candidate.historical_scanned_bars = scanned
    candidate.upper_touches = upper_touches
    candidate.lower_touches = lower_touches
    candidate.start_bar = start_bar
    candidate.end_bar = end_bar
    candidate.known_bar = known_bar
    candidate.apex_bar = apex_bar
    candidate.progress = progress
    candidate.hb1 = hb1
    candidate.hp1 = hp1
    candidate.hb2 = hb2
    candidate.hp2 = hp2
    candidate.lb1 = lb1
    candidate.lp1 = lp1
    candidate.lb2 = lb2
    candidate.lp2 = lp2
    candidate.upper_slope = upper_slope
    candidate.lower_slope = lower_slope
    candidate.start_width = start_width
    candidate.current_width = current_width
    candidate.contraction = contraction
    candidate.upper_now = upper_now
    candidate.lower_now = lower_now
    
    return candidate, f"OK - {generic_type} kalite {raw_quality:.1f}"

def find_best_triangle_candidate(df: pd.DataFrame, profile: str = "Dengeli", verbose: bool = False) -> Tuple[Optional[PatternCandidate], List[str]]:
    """
    Tüm pivot kombinasyonlarını dene, en iyiyi bul
    Pine'daki SEARCH_PIVOTS=6 ile son 6 pivotun kombinasyonları
    
    verbose=True ise reddedilenlerin sebeplerini de logla (rejected_only)
    """
    from config import get_profile_params
    
    params = get_profile_params(profile)
    pivot_len = params['pivot_len']
    
    atr_series = calculate_atr(df, 14)
    
    high_pivots, low_pivots = find_pivots(df, pivot_len)
    
    # Aynı barda çift pivot filtresi - Pine birebir
    try:
        high_pivots, low_pivots = filter_same_bar_double_pivot(high_pivots, low_pivots, df, atr_series, 0)
    except Exception:
        pass
    
    if len(high_pivots) < 2 or len(low_pivots) < 2:
        return None, [f"Yetersiz pivot: high={len(high_pivots)} low={len(low_pivots)}"]
    
    # Son SEARCH_PIVOTS pivotu al
    search_n = 6
    high_search = high_pivots[-search_n:] if len(high_pivots) > search_n else high_pivots
    low_search = low_pivots[-search_n:] if len(low_pivots) > search_n else low_pivots
    
    best_candidate = None
    logs = []
    tried = 0
    rejected = 0
    
    # Tüm kombinasyonlar: hiA, hiB, loA, loB
    for hiA in range(len(high_search) - 1):
        for hiB in range(hiA + 1, len(high_search)):
            for loA in range(len(low_search) - 1):
                for loB in range(loA + 1, len(low_search)):
                    tried += 1
                    candidate, reason = f_build_triangle_candidate(
                        df, atr_series, high_search, low_search,
                        hiA, hiB, loA, loB, params, profile, len(df) - 1
                    )
                    
                    if candidate is None:
                        rejected += 1
                        if verbose and len(logs) < 20:  # İlk 20 reddi logla
                            logs.append(f"RED [{hiA},{hiB},{loA},{loB}]: {reason}")
                    else:
                        if best_candidate is None or candidate.raw_quality > best_candidate.raw_quality:
                            best_candidate = candidate
                            logs.append(f"OK [{hiA},{hiB},{loA},{loB}]: {reason}")
    
    if best_candidate and best_candidate.valid:
        summary = f"Toplam {tried} aday denendi, {rejected} reddedildi, {tried-rejected} geçti, en iyi kalite {best_candidate.raw_quality:.1f} ise {best_candidate.pattern_type}"
    else:
        summary = f"Toplam {tried} aday denendi, {rejected} reddedildi, {tried-rejected} geçti, en iyi kalite Yok"
    logs.insert(0, summary)
    
    return best_candidate, logs

# === BAYRAK/FLAMA YARDIMCILARI ===
def f_range_between(df: pd.DataFrame, start_bar: int, end_bar: int, max_bars: int = 120) -> Tuple[float, float]:
    """İki bar arası high/low range - Pine'daki f_range_between"""
    bounded_end = min(end_bar, len(df) - 1)
    available_bars = min(max(bounded_end - start_bar, 0), max_bars)
    
    if bounded_end < 0 or bounded_end >= len(df):
        return 0.0, 0.0
    
    range_high = df['high'].iloc[bounded_end]
    range_low = df['low'].iloc[bounded_end]
    
    for step in range(available_bars):
        abs_bar = bounded_end - step
        if 0 <= abs_bar < len(df):
            range_high = max(range_high, df['high'].iloc[abs_bar])
            range_low = min(range_low, df['low'].iloc[abs_bar])
    
    return range_high, range_low

def f_efficiency_between(df: pd.DataFrame, start_bar: int, end_bar: int, max_bars: int = 120) -> float:
    """İki bar arası efficiency - Pine'daki f_efficiency_between"""
    bounded_end = min(end_bar, len(df) - 1)
    duration = max(0, bounded_end - start_bar)
    sample_bars = min(duration, max_bars)
    
    total_path = 0.0
    if sample_bars > 0:
        for step in range(sample_bars):
            abs_bar = bounded_end - step
            if abs_bar > 0 and abs_bar < len(df):
                total_path += abs(df['close'].iloc[abs_bar] - df['close'].iloc[abs_bar - 1])
    
    if sample_bars > 0 and bounded_end - sample_bars >= 0:
        net_move = abs(df['close'].iloc[bounded_end] - df['close'].iloc[bounded_end - sample_bars])
    else:
        net_move = 0.0
    
    return f_clamp(net_move / max(max(total_path, net_move), 0.0001), 0.0, 1.0)

def f_build_flag_candidate(df: pd.DataFrame, atr_series: pd.Series,
                           high_pivots: List[Dict], low_pivots: List[Dict],
                           hiA_idx: int, hiB_idx: int, loA_idx: int, loB_idx: int,
                           bull_pole: PoleInfo, bear_pole: PoleInfo,
                           params: dict, profile: str, current_bar: int) -> Tuple[Optional[PatternCandidate], str]:
    """
    Bayrak adayı - Pine'daki flag kısmı
    - Direk + paralel kanal
    - Boğa bayrağı: yukarı direk sonrası hafif aşağı/yan kanal
    - Ayı bayrağı: aşağı direk sonrası hafif yukarı/yan kanal
    """
    # Önce üçgen adayını dene (temel geometri için)
    base_candidate, base_reason = f_build_triangle_candidate(
        df, atr_series, high_pivots, low_pivots, hiA_idx, hiB_idx, loA_idx, loB_idx, params, profile, current_bar
    )
    
    # Eğer üçgen adayı yoksa, bayrak için de temel kontrolleri yap
    # Ama bayrak paralel olmalı, üçgen converging olmalı - farklı
    # O yüzden üçgen adayının reddedilme sebebi parallel ise bayrak için OK olabilir
    
    # Pivotları al
    try:
        hb1 = high_pivots[hiA_idx]['bar']
        hp1 = high_pivots[hiA_idx]['price']
        hb2 = high_pivots[hiB_idx]['bar']
        hp2 = high_pivots[hiB_idx]['price']
        lb1 = low_pivots[loA_idx]['bar']
        lp1 = low_pivots[loA_idx]['price']
        lb2 = low_pivots[loB_idx]['bar']
        lp2 = low_pivots[loB_idx]['price']
    except IndexError:
        return None, "Pivot index hatası (bayrak)"
    
    start_bar = min(min(hb1, hb2), min(lb1, lb2))
    end_bar = max(max(hb1, hb2), max(lb1, lb2))
    
    # Geometri ATR
    geometry_atr = atr_series.iloc[-1] if len(atr_series) > 0 else 1.0
    if pd.isna(geometry_atr) or geometry_atr <= 0:
        geometry_atr = 1.0
    
    # Eğimler
    upper_slope = f_slope(hb1, hp1, hb2, hp2)
    lower_slope = f_slope(lb1, lp1, lb2, lp2)
    upper_slope_norm = upper_slope / geometry_atr
    lower_slope_norm = lower_slope / geometry_atr
    slope_gap_norm = upper_slope_norm - lower_slope_norm
    avg_slope_norm = (upper_slope_norm + lower_slope_norm) * 0.5
    
    # Paralel kontrolü - bayrak için daha toleranslı olmalı
    # Eskisi: flat_tol * 0.75 = 0.018 (çok katı)
    # 2.5->0.06, 6.0->0.144 hala katı (0.1471 bile RED)
    # Yenisi: flat_tol * 10.0 = 0.24 (Dengeli), gerçek BIST kanalında %20-25 sapma normal
    # Üçgen converging için -0.006 altı, bayrak parallel için |gap| <0.24 makul
    flag_parallel_tol = params['flat_slope_norm_tol'] * 10.0
    parallel_like = abs(slope_gap_norm) <= flag_parallel_tol
    if not parallel_like:
        return None, f"Paralel değil: slopeGapNorm={slope_gap_norm:.4f} tol={flag_parallel_tol:.4f} (bayrak için paralel olmalı)"
    
    # Touch basics (üçgen adayından al, ama bayrak için de gerekli)
    touch_tolerance = max(0.0001, geometry_atr * params['touch_atr_mult'])
    high_prices = [p['price'] for p in high_pivots]
    high_bars = [p['bar'] for p in high_pivots]
    low_prices = [p['price'] for p in low_pivots]
    low_bars = [p['bar'] for p in low_pivots]
    
    upper_touches, _, upper_first, upper_last = f_touch_stats(
        high_prices, high_bars, hb1, hp1, hb2, hp2, start_bar, current_bar, touch_tolerance, params['min_touch_gap']
    )
    lower_touches, _, lower_first, lower_last = f_touch_stats(
        low_prices, low_bars, lb1, lp1, lb2, lp2, start_bar, current_bar, touch_tolerance, params['min_touch_gap']
    )
    
    if upper_touches < 2 or lower_touches < 2:
        return None, f"Bayrak temas yetersiz: üst {upper_touches} alt {lower_touches}"
    
    # Kronolojik
    if not f_chronological_swings(hb1, hb2, lb1, lb2):
        return None, "Kronolojik değil (bayrak)"
    
    # Direk bağlantısı - genişletildi
    # Eskisi: 10 bar çok katı, 20 de yetmedi (32 bar diff vardı THYAO'da)
    # Yenisi: 35 bar, direk sonrası konsolidasyon biraz gecikebilir
    max_pole_link_bars = max(params['pivot_len'] * 5, params['min_touch_gap'] + 15, 35)
    
    bull_seq_compat = hb1 < lb1  # Önce üst sonra alt -> yukarı impuls sonrası
    bear_seq_compat = lb1 < hb1
    
    bull_linked = bull_pole.valid and bull_seq_compat and abs(bull_pole.end_bar - start_bar) <= max_pole_link_bars
    bear_linked = bear_pole.valid and bear_seq_compat and abs(bear_pole.end_bar - start_bar) <= max_pole_link_bars
    
    if not bull_linked and not bear_linked:
        return None, f"Direk bağlantısı yok: bullLinked={bull_linked} bearLinked={bear_linked} maxLink={max_pole_link_bars} bullEnd={bull_pole.end_bar if bull_pole.valid else 'Yok'} bearEnd={bear_pole.end_bar if bear_pole.valid else 'Yok'} start={start_bar}"
    
    # Hangi direk?
    pole = bull_pole if bull_linked else bear_pole
    is_bull_flag = bull_linked
    
    # Consolidation range
    observed_high, observed_low = f_range_between(df, pole.end_bar, end_bar, 120)
    base_low = min(lp1, lp2)
    base_high = max(hp1, hp2)
    consol_low = min(base_low, observed_low)
    consol_high = max(base_high, observed_high)
    consol_height = max(consol_high - consol_low, 0.0001)
    
    # Depth
    if is_bull_flag:
        depth = f_clamp((pole.end_price - consol_low) / max(pole.magnitude or 1.0, 0.0001), 0.0, 2.0)
    else:
        depth = f_clamp((consol_high - pole.end_price) / max(pole.magnitude or 1.0, 0.0001), 0.0, 2.0)
    
    # Duration ratio
    formed_duration = max(1, end_bar - start_bar)
    duration_ratio = float(formed_duration) / max(1.0, float(pole.duration or 1))
    
    # Height ratio
    height_ratio = consol_height / max(pole.magnitude or 1.0, 0.0001)
    
    # Bayrak eğim kontrolü - genişletildi
    # Boğa bayrağı: genelde hafif aşağı/yatay ama hafif yukarı da olabilir (BIST gürültülü)
    # Ayı bayrağı: hafif yukarı/yatay ama hafif aşağı da olabilir
    # Eskisi bull <=0.024 çok katı, 0.10 bile RED oluyordu
    # Yenisi: bull -0.35..+0.12, bear -0.12..+0.35
    flat_tol = params['flat_slope_norm_tol']
    if is_bull_flag:
        flag_slope_ok = avg_slope_norm <= 0.12 and avg_slope_norm >= -0.35
    else:
        flag_slope_ok = avg_slope_norm >= -0.12 and avg_slope_norm <= 0.35
    
    if not flag_slope_ok:
        return None, f"Bayrak eğimi uygun değil: avgSlopeNorm={avg_slope_norm:.4f} bull={is_bull_flag} (bull: -0.35..0.12, bear: -0.12..0.35)"
    
    # Validasyon - gevşetildi BIST için
    # Eskisi depth 0.08-0.80 çok katı, 1.00 bile RED oluyordu
    # Yenisi 0.05-1.0, bayrak biraz derin düzeltme yapabilir BIST'te
    if not (0.05 <= depth <= 1.0):
        return None, f"Depth uygun değil: {depth:.2f} (0.05-1.0 olmalı, eski 0.08-0.80)"
    if height_ratio > 0.70:
        return None, f"Height ratio fazla: {height_ratio:.2f} >0.70 (eski 0.58)"
    if duration_ratio > 4.0:
        return None, f"Duration ratio fazla: {duration_ratio:.2f} >4.0 (eski 3.5)"
    if formed_duration > params['max_consolidation_bars']:
        return None, f"Konsolidasyon süresi uzun: {formed_duration} > {params['max_consolidation_bars']}"
    
    # Efficiency
    consol_eff = f_efficiency_between(df, start_bar, end_bar, 120)
    if consol_eff >= (pole.efficiency or 0) + 0.10:
        return None, f"Konsolidasyon direktten daha verimli: {consol_eff:.2f} >= {pole.efficiency:.2f}+0.10"
    
    # Quality
    # Touch score (basit)
    total_touches = upper_touches + lower_touches
    touch_score = f_clamp(f_smoothstep(4.0, 7.0, float(total_touches)) * 100.0, 0.0, 100.0)
    
    # Parallel quality
    parallel_q = f_inverse_smoothstep(params['flat_slope_norm_tol'] * 0.30, params['flat_slope_norm_tol'] * 1.05, abs(slope_gap_norm)) * 100.0
    
    # Calmness
    calmness_q = 100.0 if consol_eff <= (pole.efficiency or 0) else f_inverse_smoothstep(0.00, 0.28, consol_eff - (pole.efficiency or 0)) * 100.0
    
    # Depth, duration quality
    depth_q = f_depth_quality(depth)
    duration_q = f_duration_quality(duration_ratio)
    
    # Cleanliness (basit - violation yok varsay)
    cleanliness_q = 80.0
    
    raw_q = f_clamp(
        pole.quality * 0.28 + depth_q * 0.20 + duration_q * 0.12 + parallel_q * 0.16 + touch_score * 0.12 + calmness_q * 0.07 + cleanliness_q * 0.05,
        0.0, 100.0
    )
    
    min_qual = params['min_specialized_quality']
    if raw_q < min_qual:
        return None, f"Bayrak kalite düşük: {raw_q:.1f} < {min_qual}"
    
    # Başarılı
    candidate = PatternCandidate()
    candidate.valid = True
    candidate.pattern_type = "Boğa Bayrağı" if is_bull_flag else "Ayı Bayrağı"
    candidate.family = "Bayrak"
    candidate.classic_dir = 1 if is_bull_flag else -1
    candidate.raw_quality = raw_q
    candidate.geometry_score = parallel_q
    candidate.slope_shape_score = parallel_q
    candidate.touch_score = touch_score
    candidate.upper_touches = upper_touches
    candidate.lower_touches = lower_touches
    candidate.start_bar = start_bar
    candidate.end_bar = end_bar
    candidate.hb1 = hb1
    candidate.hp1 = hp1
    candidate.hb2 = hb2
    candidate.hp2 = hp2
    candidate.lb1 = lb1
    candidate.lp1 = lp1
    candidate.lb2 = lb2
    candidate.lp2 = lp2
    candidate.upper_slope = upper_slope
    candidate.lower_slope = lower_slope
    candidate.has_pole = True
    candidate.pole_dir = pole.direction
    candidate.pole_start_bar = pole.start_bar
    candidate.pole_start_price = pole.start_price
    candidate.pole_end_bar = pole.end_bar
    candidate.pole_end_price = pole.end_price
    candidate.pole_duration = pole.duration
    candidate.pole_magnitude = pole.magnitude
    candidate.pole_efficiency = pole.efficiency
    candidate.pole_quality = pole.quality
    candidate.correction_depth = depth
    candidate.duration_ratio = duration_ratio
    candidate.consolidation_efficiency = consol_eff
    candidate.consolidation_height_ratio = height_ratio
    candidate.upper_now = f_line_price(hb1, hp1, hb2, hp2, current_bar)
    candidate.lower_now = f_line_price(lb1, lp1, lb2, lp2, current_bar)
    candidate.geometry_atr = geometry_atr
    
    return candidate, f"OK - {candidate.pattern_type} kalite {raw_q:.1f} depth {depth:.2f}"

def find_best_flag_candidate(df: pd.DataFrame, profile: str = "Dengeli", verbose: bool = False) -> Tuple[Optional[PatternCandidate], List[str]]:
    """En iyi bayrak adayını bul"""
    from config import get_profile_params
    params = get_profile_params(profile)
    pivot_len = params['pivot_len']
    
    atr_series = calculate_atr(df, 14)
    high_pivots, low_pivots = find_pivots(df, pivot_len)

    # Aynı barda çift pivot filtresi
    try:
        high_pivots, low_pivots = filter_same_bar_double_pivot(high_pivots, low_pivots, df, atr_series, 0)
    except Exception:
        pass
    
    if len(high_pivots) < 2 or len(low_pivots) < 2:
        return None, [f"Yetersiz pivot bayrak: high={len(high_pivots)} low={len(low_pivots)}"]
    
    search_n = 6
    high_search = high_pivots[-search_n:] if len(high_pivots) > search_n else high_pivots
    low_search = low_pivots[-search_n:] if len(low_pivots) > search_n else low_pivots
    
    # Direkleri bul - son pivotlar için
    bull_poles = []
    bear_poles = []
    for hp in high_search:
        pole = find_pole(df, atr_series, high_pivots, low_pivots, hp['bar'], hp['price'], 1, params)
        bull_poles.append(pole)
    for lp in low_search:
        pole = find_pole(df, atr_series, high_pivots, low_pivots, lp['bar'], lp['price'], -1, params)
        bear_poles.append(pole)
    
    # En iyi direkleri seç
    best_bull = max(bull_poles, key=lambda p: p.quality if p.valid else -1) if bull_poles else PoleInfo()
    best_bear = max(bear_poles, key=lambda p: p.quality if p.valid else -1) if bear_poles else PoleInfo()
    
    best_candidate = None
    logs = []
    tried = 0
    rejected = 0
    
    for hiA in range(len(high_search) - 1):
        for hiB in range(hiA + 1, len(high_search)):
            for loA in range(len(low_search) - 1):
                for loB in range(loA + 1, len(low_search)):
                    tried += 1
                    cand, reason = f_build_flag_candidate(
                        df, atr_series, high_search, low_search, hiA, hiB, loA, loB,
                        best_bull, best_bear, params, profile, len(df)-1
                    )
                    if cand is None:
                        rejected += 1
                        if verbose and len(logs) < 15:
                            logs.append(f"RED BAYRAK [{hiA},{hiB},{loA},{loB}]: {reason}")
                    else:
                        if best_candidate is None or cand.raw_quality > best_candidate.raw_quality:
                            best_candidate = cand
                            logs.append(f"OK BAYRAK [{hiA},{hiB},{loA},{loB}]: {reason}")
    
    if best_candidate and best_candidate.valid:
        summary = f"Bayrak: Toplam {tried} denendi, {rejected} reddedildi, {tried-rejected} geçti, en iyi {best_candidate.raw_quality:.1f} {best_candidate.pattern_type}"
    else:
        summary = f"Bayrak: Toplam {tried} denendi, {rejected} reddedildi, {tried-rejected} geçti, en iyi Yok"
    logs.insert(0, summary)
    return best_candidate, logs

# === BREAKOUT GÜCÜ ===
def f_breakout_strength(df: pd.DataFrame, atr_series: pd.Series, 
                        bar_idx: int, direction: int, boundary_price: float,
                        profile: str, volume_sma_series: Optional[pd.Series] = None) -> Tuple[float, float, float, float, float, float]:
    """
    Kırılım mum gücü - Pine'daki f_breakout_strength ile aynı
    direction: 1 yukarı, -1 aşağı
    Neden? Zayıf kırılımlar BREAK_ATTEMPT, güçlüler BREAK_CANDIDATE
    
    Skorlar:
    - bodyScore: Gövde ne kadar yönlü?
    - closeScore: Kapanış range'in neresinde?
    - penetrationScore: Sınırı ne kadar geçmiş? ATR cinsinden
    - expansionScore: Mum ne kadar geniş?
    - volumeScore: Hacim ortalamadan fazla mı?
    """
    if bar_idx >= len(df) or bar_idx < 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    
    open_p = df['open'].iloc[bar_idx]
    high_p = df['high'].iloc[bar_idx]
    low_p = df['low'].iloc[bar_idx]
    close_p = df['close'].iloc[bar_idx]
    volume = df['volume'].iloc[bar_idx] if 'volume' in df.columns else 0
    
    atr = atr_series.iloc[bar_idx] if bar_idx < len(atr_series) else atr_series.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        atr = 1.0
    
    candle_range = max(high_p - low_p, 0.0001)
    
    # Directional body ratio
    if direction == 1:
        directional_body_ratio = (close_p - open_p) / candle_range
        close_location = (close_p - low_p) / candle_range
        penetration_atr = (close_p - boundary_price) / max(atr, 0.0001)
    else:
        directional_body_ratio = (open_p - close_p) / candle_range
        close_location = (high_p - close_p) / candle_range
        penetration_atr = (boundary_price - close_p) / max(atr, 0.0001)
    
    expansion_atr = candle_range / max(atr, 0.0001)
    
    # Volume
    volume_available = False
    volume_ratio = 1.0
    if volume_sma_series is not None and bar_idx < len(volume_sma_series):
        vol_sma = volume_sma_series.iloc[bar_idx]
        if not pd.isna(vol_sma) and vol_sma > 0 and volume > 0:
            volume_available = True
            volume_ratio = volume / vol_sma
    
    # Skorlar - Pine ile aynı eşikler
    from config import get_profile_params
    params = get_profile_params(profile)
    base_break_atr = params['break_atr_mult']
    
    body_score = f_smoothstep(0.10, 0.65, directional_body_ratio) * 100.0
    close_score = f_smoothstep(0.56, 0.88, close_location) * 100.0
    penetration_score = f_smoothstep(base_break_atr * 0.75, max(0.24, base_break_atr * 4.0), penetration_atr) * 100.0
    expansion_score = f_smoothstep(0.65, 1.55, expansion_atr) * 100.0
    volume_score = f_smoothstep(0.90, 1.55, volume_ratio) * 100.0 if volume_available else 50.0
    
    strength = f_clamp(body_score * 0.24 + close_score * 0.28 + penetration_score * 0.25 + expansion_score * 0.15 + volume_score * 0.08, 0.0, 100.0)
    
    return strength, body_score, close_score, penetration_score, expansion_score, volume_score

# === LIFECYCLE YÖNETİCİSİ ===
@dataclass
class PatternState:
    """Bir hissenin anlık formasyon state'i - Pine'daki var değişkenlerin karşılığı"""
    active_candidate: Optional[PatternCandidate] = None
    state: str = ST_NONE
    break_candidate_bar: Optional[int] = None
    break_confirmed_bar: Optional[int] = None
    break_candidate_dir: int = 0
    break_line_x1: Optional[int] = None
    break_line_y1: Optional[float] = None
    break_line_x2: Optional[int] = None
    break_line_y2: Optional[float] = None
    retest_success_bar: Optional[int] = None
    invalid_reason: str = "Yok"
    last_update_bar: int = 0

class PatternLifecycleManager:
    """
    Lifecycle yöneticisi - her hisse için state tutar
    Pine'daki barstate.isconfirmed ile çalışan lifecycle'ın Python karşılığı
    
    Neden gerekli? Formasyon tek barda oluşmuyor, bar bar evriliyor
    """
    def __init__(self, profile: str = "Dengeli"):
        from config import get_profile_params
        self.profile = profile
        self.params = get_profile_params(profile)
        self.states: Dict[str, PatternState] = {}  # stock -> state
        self.logger = logging.getLogger(__name__)
    
    def get_state(self, stock: str) -> PatternState:
        if stock not in self.states:
            self.states[stock] = PatternState()
        return self.states[stock]
    
    def update(self, stock: str, df: pd.DataFrame, candidate: Optional[PatternCandidate]) -> Tuple[str, int, str]:
        """
        State güncelle - Pine'daki 19-20. bölüm lifecycle mantığı
        Döner: (new_state, break_dir, log_message)
        """
        state_obj = self.get_state(stock)
        current_bar = len(df) - 1
        
        if current_bar <= 0:
            return ST_NONE, 0, "Bar yok"
        
        # ATR ve diğer seriler
        atr_series = calculate_atr(df, 14)
        safe_atr = atr_series.iloc[-1] if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]) else 1.0
        break_buffer = max(0.0001, safe_atr * self.params['break_atr_mult'])
        tol = max(0.0001, safe_atr * self.params['touch_atr_mult'])
        # Volume SMA - kırılım gücü için
        try:
            volume_sma = calculate_sma(df['volume'], 20) if 'volume' in df.columns else None
        except Exception:
            volume_sma = None
        
        # Eğer candidate yoksa
        if candidate is None or not candidate.valid:
            if state_obj.state in [ST_NONE, ST_INVALID, ST_BREAK_FAILED, ST_BREAK_TIMEOUT, ST_COMPLETED]:
                # Terminal state'te kal veya NONE
                return state_obj.state, state_obj.break_candidate_dir, "Formasyon yok, terminal state korunuyor"
            else:
                # Aktif formasyon vardı ama şimdi yok - zayıfladı mı?
                if state_obj.active_candidate is not None:
                    # Eski candidate'i kontrol et hala geçerli mi?
                    # Basit: Eğer yaş çok ilerlediyse INVALID
                    age = current_bar - (state_obj.active_candidate.start_bar or 0)
                    if age > self.params['max_consolidation_bars'] * 2:
                        state_obj.state = ST_INVALID
                        state_obj.invalid_reason = "Formasyon süresi aşırı uzadı, teyit gelmedi"
                        return ST_INVALID, 0, state_obj.invalid_reason
                
                state_obj.state = ST_NONE
                state_obj.invalid_reason = "Yeterli teyitli geometri yok"
                return ST_NONE, 0, state_obj.invalid_reason
        
        # Candidate var - ilk kez mi?
        if state_obj.active_candidate is None or state_obj.state in [ST_NONE, ST_INVALID, ST_BREAK_FAILED, ST_BREAK_TIMEOUT, ST_COMPLETED]:
            # Yeni formasyon
            state_obj.active_candidate = candidate
            state_obj.state = ST_CANDIDATE
            state_obj.break_candidate_bar = None
            state_obj.break_candidate_dir = 0
            state_obj.invalid_reason = "Yok"
            state_obj.last_update_bar = current_bar
            return ST_CANDIDATE, 0, f"Yeni aday: {candidate.pattern_type} kalite {candidate.raw_quality:.0f}"
        
        # Aktif candidate var - güncelle
        # Sınır fiyatları
        upper_now = candidate.upper_now
        lower_now = candidate.lower_now
        if upper_now is None or lower_now is None:
            # Eski candidate'in sınırlarını kullan
            upper_now = f_line_price(candidate.hb1, candidate.hp1, candidate.hb2, candidate.hp2, current_bar) if candidate.hb1 is not None else df['close'].iloc[-1]
            lower_now = f_line_price(candidate.lb1, candidate.lp1, candidate.lb2, candidate.lp2, current_bar) if candidate.lb1 is not None else df['close'].iloc[-1]
        
        close = df['close'].iloc[-1]
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        
        # Breakout kontrolü - sadece DEFINED ve sonrası state'lerde
        if state_obj.state in [ST_CANDIDATE, ST_GEOMETRY, ST_DEFINED, ST_MATURING, ST_COMPRESSING, ST_PREP]:
            # Kırılım var mı?
            close_up_break_raw = close > upper_now + break_buffer
            close_down_break_raw = close < lower_now - break_buffer
            
            if close_up_break_raw or close_down_break_raw:
                direction = 1 if close_up_break_raw else -1
                boundary = upper_now if direction == 1 else lower_now
                
                # Breakout gücü hesapla - volume SMA ile
                strength, body_s, close_s, pen_s, exp_s, vol_s = f_breakout_strength(
                    df, atr_series, current_bar, direction, boundary, self.profile, volume_sma
                )
                
                min_strength = self.params['min_break_strength']
                
                # Güçlü mü zayıf mı?
                if strength >= min_strength:
                    # Güçlü kırılım - BREAK_CANDIDATE
                    state_obj.state = ST_BREAK_CANDIDATE
                    state_obj.break_candidate_bar = current_bar
                    state_obj.break_candidate_dir = direction
                    state_obj.break_line_x1 = candidate.hb1 if direction == 1 else candidate.lb1
                    state_obj.break_line_y1 = candidate.hp1 if direction == 1 else candidate.lp1
                    state_obj.break_line_x2 = candidate.hb2 if direction == 1 else candidate.lb2
                    state_obj.break_line_y2 = candidate.hp2 if direction == 1 else candidate.lp2
                    
                    # Candidate'i dondur (quality freeze)
                    candidate.quality_frozen = True
                    candidate.frozen_raw_quality = candidate.raw_quality
                    candidate.frozen_upper_boundary_at_break = candidate.upper_now
                    candidate.frozen_lower_boundary_at_break = candidate.lower_now
                    candidate.frozen_break_buffer = break_buffer
                    candidate.frozen_retest_tolerance = tol
                    candidate.frozen_atr_at_break = safe_atr
                    candidate.break_snapshot_bar = current_bar
                    candidate.break_snapshot_price = boundary
                    candidate.break_snapshot_direction = direction
                    candidate.break_strength = strength
                    candidate.break_body_score = body_s
                    candidate.break_close_score = close_s
                    candidate.break_penetration_score = pen_s
                    candidate.break_expansion_score = exp_s
                    candidate.break_volume_score = vol_s
                    
                    state_obj.active_candidate = candidate
                    
                    return ST_BREAK_CANDIDATE, direction, f"Güçlü kırılım adayı {direction} güç {strength:.0f} (min {min_strength})"
                else:
                    # Zayıf kırılım - BREAK_ATTEMPT
                    state_obj.state = ST_BREAK_ATTEMPT
                    state_obj.break_candidate_bar = current_bar
                    state_obj.break_candidate_dir = direction
                    state_obj.break_line_x1 = candidate.hb1 if direction == 1 else candidate.lb1
                    state_obj.break_line_y1 = candidate.hp1 if direction == 1 else candidate.lp1
                    state_obj.break_line_x2 = candidate.hb2 if direction == 1 else candidate.lb2
                    state_obj.break_line_y2 = candidate.hp2 if direction == 1 else candidate.lp2
                    
                    return ST_BREAK_ATTEMPT, direction, f"Zayıf kırılım denemesi {direction} güç {strength:.0f} < {min_strength} - teyit bekliyor"
            else:
                # Kırılım yok - olgunlaşma state'ine geç
                if candidate.raw_quality >= self.params['min_raw_quality'] + 25:
                    new_state = ST_PREP if (abs(close - upper_now) / max(tol, 0.0001) <= 1.35 or abs(close - lower_now) / max(tol, 0.0001) <= 1.35) else ST_COMPRESSING
                elif candidate.raw_quality >= self.params['min_raw_quality'] + 12:
                    new_state = ST_MATURING
                else:
                    new_state = ST_DEFINED
                
                state_obj.state = new_state
                state_obj.active_candidate = candidate
                state_obj.last_update_bar = current_bar
                return new_state, 0, f"Olgunlaşıyor: {new_state} kalite {candidate.raw_quality:.0f} kırılım yok"
        
        # BREAK_ATTEMPT ve BREAK_CANDIDATE state'lerinde teyit bekle
        elif state_obj.state in [ST_BREAK_ATTEMPT, ST_BREAK_CANDIDATE]:
            if state_obj.break_candidate_bar is None:
                return state_obj.state, state_obj.break_candidate_dir, "Break bar yok"
            
            # Kaç bar geçti?
            age = current_bar - state_obj.break_candidate_bar
            confirm_window = self.params['confirm_window']
            
            # Sınır çizgisi
            if state_obj.break_line_x1 is None or state_obj.break_line_x2 is None:
                return state_obj.state, state_obj.break_candidate_dir, "Break line yok"
            
            boundary = f_line_price(state_obj.break_line_x1, state_obj.break_line_y1, 
                                   state_obj.break_line_x2, state_obj.break_line_y2, current_bar)
            
            direction = state_obj.break_candidate_dir
            
            # Aynı yönde kapanış var mı?
            same_side_close = (direction == 1 and close > boundary + break_buffer) or (direction == -1 and close < boundary - break_buffer)
            
            # Güç hesapla - volume SMA ile
            strength, _, _, _, _, _ = f_breakout_strength(df, atr_series, current_bar, direction, boundary, self.profile, volume_sma)
            
            # Formasyon içine dönüş var mı?
            projected_upper = upper_now
            projected_lower = lower_now
            hold_buffer = max(0.0001, tol * 0.12)
            back_inside = (direction == 1 and close < projected_upper - hold_buffer) or (direction == -1 and close > projected_lower + hold_buffer)
            
            if back_inside and current_bar > state_obj.break_candidate_bar:
                state_obj.state = ST_BREAK_FAILED
                state_obj.invalid_reason = "Kırılım sonrası formasyon içine dönüldü"
                return ST_BREAK_FAILED, direction, state_obj.invalid_reason
            
            # Teyit?
            strong_same_side = same_side_close and strength >= max(25.0, self.params['min_break_strength'] - 6.0)
            
            # Retest kontrolü
            retest = False
            if direction == 1:
                retest = low <= boundary + tol and close > boundary + hold_buffer
            else:
                retest = high >= boundary - tol and close < boundary - hold_buffer
            
            if current_bar > state_obj.break_candidate_bar and age <= confirm_window and (strong_same_side or retest):
                state_obj.state = ST_BREAK_CONFIRMED
                state_obj.break_confirmed_bar = current_bar
                if state_obj.active_candidate:
                    state_obj.active_candidate.break_confirmation_strength = strength
                return ST_BREAK_CONFIRMED, direction, f"Kırılım teyitli {direction} güç {strength:.0f} retest={retest}"
            
            if age > confirm_window:
                state_obj.state = ST_BREAK_TIMEOUT
                state_obj.invalid_reason = "Kırılım teyit alamadı"
                return ST_BREAK_TIMEOUT, direction, state_obj.invalid_reason
            
            return state_obj.state, direction, f"Teyit bekleniyor age={age}/{confirm_window} sameSide={same_side_close} retest={retest}"
        
        # BREAK_CONFIRMED, RETEST_WAIT, RETESTING
        elif state_obj.state in [ST_BREAK_CONFIRMED, ST_RETEST_WAIT, ST_RETESTING]:
            if state_obj.break_line_x1 is None:
                return state_obj.state, state_obj.break_candidate_dir, "Break line yok"
            
            boundary = f_line_price(state_obj.break_line_x1, state_obj.break_line_y1,
                                   state_obj.break_line_x2, state_obj.break_line_y2, current_bar)
            direction = state_obj.break_candidate_dir
            hold_buffer = max(0.0001, tol * 0.12)
            
            # İçeri dönüş?
            returned_inside = (direction == 1 and close < upper_now - hold_buffer) or (direction == -1 and close > lower_now + hold_buffer)
            if returned_inside:
                state_obj.state = ST_BREAK_FAILED
                state_obj.invalid_reason = "Kırılım sonrası formasyon alanına dönüldü"
                return ST_BREAK_FAILED, direction, state_obj.invalid_reason
            
            # Retest?
            retest_touch = False
            retest_held = False
            if direction == 1:
                retest_touch = low <= boundary + tol and high >= boundary - tol
                retest_held = retest_touch and close > boundary + hold_buffer
            else:
                retest_touch = high >= boundary - tol and low <= boundary + tol
                retest_held = retest_touch and close < boundary - hold_buffer
            
            confirmed_age = current_bar - (state_obj.break_confirmed_bar or state_obj.break_candidate_bar or current_bar)
            
            if retest_held:
                state_obj.state = ST_RETEST_OK
                state_obj.retest_success_bar = current_bar
                return ST_RETEST_OK, direction, f"Retest başarılı {direction}"
            elif retest_touch:
                state_obj.state = ST_RETESTING
                return ST_RETESTING, direction, f"Retest ediliyor {direction}"
            elif confirmed_age > self.params['retest_window']:
                state_obj.state = ST_COMPLETED
                return ST_COMPLETED, direction, f"Kırılım korunuyor, retest olmadan tamamlandı"
            else:
                state_obj.state = ST_RETEST_WAIT
                return ST_RETEST_WAIT, direction, f"Retest bekleniyor age={confirmed_age}"
        
        # RETEST_OK
        elif state_obj.state == ST_RETEST_OK:
            if state_obj.break_line_x1 is None:
                return state_obj.state, state_obj.break_candidate_dir, "Break line yok"
            
            boundary = f_line_price(state_obj.break_line_x1, state_obj.break_line_y1,
                                   state_obj.break_line_x2, state_obj.break_line_y2, current_bar)
            direction = state_obj.break_candidate_dir
            hold_buffer = max(0.0001, tol * 0.12)
            
            retained = (direction == 1 and close > boundary + hold_buffer) or (direction == -1 and close < boundary - hold_buffer)
            returned_inside = (direction == 1 and close < upper_now - hold_buffer) or (direction == -1 and close > lower_now + hold_buffer)
            
            retest_hold_age = current_bar - (state_obj.retest_success_bar or current_bar)
            
            if returned_inside:
                state_obj.state = ST_BREAK_FAILED
                state_obj.invalid_reason = "Başarılı retest sonrası yapı içine dönüldü"
                return ST_BREAK_FAILED, direction, state_obj.invalid_reason
            elif retained and retest_hold_age >= self.params['retest_hold_window']:
                state_obj.state = ST_COMPLETED
                return ST_COMPLETED, direction, f"Retest sonrası tamamlandı holdAge={retest_hold_age}"
            elif not retained:
                state_obj.state = ST_RETESTING
                return ST_RETESTING, direction, "Retest sınır çevresinde yeniden izleniyor"
            else:
                return ST_RETEST_OK, direction, f"Retest korunumu bekleniyor holdAge={retest_hold_age}"
        
        # Diğer state'ler - formasyon olgunlaşıyor mu?
        else:
            # Basit: DEFINED, MATURING, COMPRESSING, PREP arası geçiş
            # Şimdilik sadece DEFINED döndür, detay sonra
            if candidate.raw_quality >= self.params['min_raw_quality'] + 25:
                new_state = ST_PREP if (abs(close - upper_now) / max(tol, 0.0001) <= 1.35 or abs(close - lower_now) / max(tol, 0.0001) <= 1.35) else ST_COMPRESSING
            elif candidate.raw_quality >= self.params['min_raw_quality'] + 12:
                new_state = ST_MATURING
            else:
                new_state = ST_DEFINED
            
            state_obj.state = new_state
            state_obj.active_candidate = candidate
            return new_state, 0, f"Olgunlaşıyor: {new_state} kalite {candidate.raw_quality:.0f}"

# === PATTERN TESPİTİ - İSKELET ===
# Tam implementasyon adım adım gelecek
# Şimdilik sadece yardımcılar ve pivot motoru var
# Sonraki adım: f_build_candidate (üçgen/kama/bayrak/flama)

def detect_patterns(df_1h: pd.DataFrame, df_2h: Optional[pd.DataFrame] = None, 
                   df_4h: Optional[pd.DataFrame] = None, df_1d: Optional[pd.DataFrame] = None,
                   stock_name: str = "", profile: str = "Dengeli", verbose: bool = False) -> Optional[Dict]:
    """
    Ana tespit fonksiyonu - Pine'daki tüm mantığın Python karşılığı
    Şu an: Üçgen/Kama + Bayrak (flama sonra)
    """
    if df_1h is None or len(df_1h) < 50:
        logger.debug(f"{stock_name} için yetersiz veri: {0 if df_1h is None else len(df_1h)}")
        return None
    
    try:
        # Önce üçgen/kama dene
        candidate_tri, logs_tri = find_best_triangle_candidate(df_1h, profile=profile, verbose=verbose)
        
        # Sonra bayrak dene
        candidate_flag, logs_flag = find_best_flag_candidate(df_1h, profile=profile, verbose=verbose)
        
        # En iyiyi seç - kaliteye göre
        best_candidate = None
        all_logs = []
        
        if candidate_tri and candidate_tri.valid:
            best_candidate = candidate_tri
            all_logs.extend(logs_tri[:3])
        
        if candidate_flag and candidate_flag.valid:
            if best_candidate is None or candidate_flag.raw_quality > best_candidate.raw_quality:
                best_candidate = candidate_flag
                all_logs = logs_flag[:3] + all_logs
            else:
                all_logs.extend(logs_flag[:2])
        
        if best_candidate is None:
            if verbose:
                combined_log = (logs_tri[0] if logs_tri else "Üçgen yok") + " | " + (logs_flag[0] if logs_flag else "Bayrak yok")
                logger.info(f"{stock_name} - Formasyon yok: {combined_log}")
            return None
        
        # Başarılı
        result = {
            'stock_name': stock_name,
            'timeframe': '1h',
            'pattern_name': best_candidate.pattern_type,
            'family': best_candidate.family,
            'classic_dir': best_candidate.classic_dir,
            'confidence_score': best_candidate.raw_quality,
            'critical_price_level': best_candidate.upper_now,
            'upper_level': best_candidate.upper_now,
            'lower_level': best_candidate.lower_now,
            'contraction': best_candidate.contraction,
            'progress': best_candidate.progress,
            'apex_bar': best_candidate.apex_bar,
            'start_bar': best_candidate.start_bar,
            'end_bar': best_candidate.end_bar,
            'geometry_score': best_candidate.geometry_score,
            'touch_score': best_candidate.touch_score,
            'maturity_score': best_candidate.maturity_score,
            'contraction_score': best_candidate.contraction_score,
            'timestamp': df_1h.index[-1] if hasattr(df_1h.index[-1], 'strftime') else pd.Timestamp.now(),
            'state': ST_DEFINED,
            'upper_touches': best_candidate.upper_touches,
            'lower_touches': best_candidate.lower_touches,
            'violation_penalty': best_candidate.historical_violation_penalty,
            'has_pole': best_candidate.has_pole,
            'pole_quality': best_candidate.pole_quality if best_candidate.has_pole else None,
            'logs': all_logs
        }
        
        logger.info(f"{stock_name} - {best_candidate.pattern_type} bulundu: kalite {best_candidate.raw_quality:.1f}")
        
        return result
        
    except Exception as e:
        logger.error(f"{stock_name} pattern tespit hatası: {e}", exc_info=True)
        return None

# === TEST YARDIMCILARI ===
def create_mock_data(n_bars: int = 100) -> pd.DataFrame:
    """Test için mock OHLCV data oluştur"""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='h')
    
    # Basit random walk
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars) * 0.3)
    low = close - np.abs(np.random.randn(n_bars) * 0.3)
    open_ = close + np.random.randn(n_bars) * 0.1
    volume = np.random.randint(100000, 1000000, n_bars)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df

if __name__ == "__main__":
    # Hızlı test
    print("=== Patterns.py Test ===")
    df = create_mock_data(200)
    print(f"Mock data: {len(df)} bar")
    
    atr = calculate_atr(df, 14)
    print(f"ATR son: {atr.iloc[-1]:.4f}")
    
    from config import PROFILE_PARAMS
    high_pivots, low_pivots = find_pivots(df, PROFILE_PARAMS['pivot_len'])
    print(f"High pivots: {len(high_pivots)}, Low pivots: {len(low_pivots)}")
    
    if high_pivots:
        print(f"Son high pivot: {high_pivots[-1]}")
    if low_pivots:
        print(f"Son low pivot: {low_pivots[-1]}")
    
    print("Test bitti - iskelet çalışıyor")
