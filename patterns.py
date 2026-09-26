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
    Pine'daki f_choose_same_bar_pivot mantığı
    Neden? Dönüşümlü swing önceliği, ATR-normalize mesafe, mum gücü
    """
    # Bu fonksiyon pivot listelerini filtreler, aynı bar çakışmasını çözer
    # Şimdilik iskelet - detaylı implementasyon sonra
    # TODO: Pine'daki mantığı tam çevir
    return high_pivots, low_pivots

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

# === PATTERN TESPİTİ - İSKELET ===
# Tam implementasyon adım adım gelecek
# Şimdilik sadece yardımcılar ve pivot motoru var
# Sonraki adım: f_build_candidate (üçgen/kama/bayrak/flama)

def detect_patterns(df_1h: pd.DataFrame, df_2h: Optional[pd.DataFrame] = None, 
                   df_4h: Optional[pd.DataFrame] = None, df_1d: Optional[pd.DataFrame] = None,
                   stock_name: str = "", profile: str = "Dengeli") -> Optional[Dict]:
    """
    Ana tespit fonksiyonu - Pine'daki tüm mantığın Python karşılığı
    Şimdilik iskelet, detaylar adım adım eklenecek
    
    Döner:
    - pattern_name, timeframe, signal_type, critical_price, confidence, timestamp
    - veya None (formasyon yok)
    
    Neden bu kadar karmaşık? Çünkü Pine'da 1000+ satır, her filtre önemli
    """
    # TODO: Tam implementasyon
    # 1. ATR hesapla
    # 2. Pivot bul
    # 3. Pole bul
    # 4. Candidate build (tüm kombinasyonlar)
    # 5. Quality hesapla
    # 6. Selection score
    # 7. Lifecycle kontrol (breakout, retest)
    
    logger.debug(f"{stock_name} için pattern tespiti başlatıldı - {len(df_1h)} mum")
    
    # Şimdilik None dön, iskelet
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
