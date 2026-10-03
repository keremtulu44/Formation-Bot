# --- FAZ 2.0: FIELD & EVENT CONTRACT (alan ve olay sözleşmesi) ---
#
# Bu modül "veri modeli tasarımı" DEĞİL, "sözleşme ayrıştırmadır".
# Alan modeli zaten motora gömülüdür: `PatternCandidate` tam 85 alan taşır.
# Faz 2'nin yapması gereken yeni bir model icat etmek değil, mevcut alanları
# "history persistence açısından" doğru sınıfa ayırmaktır.
#
# Üç ana sınıf + bir alt sınıf:
#
#   IDENTITY  — Doğumda sabit. Formasyonun *kimliğini* ve *doğum snapshot*'ını
#               belirler. Aynı formation yeniden algılandığında aynı kalmalıdır.
#               Pencere kaydığında (bar indeksi 1 birim ötelenir) bu alanlar
#               fiziksel olarak AYNI kalır; yalnızca pencere-koordinatları kayar.
#               -> Bar-time alignment bu yüzden zorunludur.
#   STATE     — Zaman içinde değişir (üst/alt sınır, genişlik, dokunuş sayısı,
#               kalite bileşenleri). Per-bar dump edilmez; yalnızca ANLAMLI
#               anlarda (birth / geometry snapshot / breakout / terminal) saklanır.
#   BREAKOUT  — `freeze_pattern_quality` anında dondurulan 20 alan. Bu turda
#               SADECE sınıflandırılır (kontrat); serileştirilmesi Faz 2.4'ün işidir.
#   TRANSIENT — Motor içinde türetilir, önbelleğe alınır veya her bar yeniden
#               hesaplanır. History'ye ASLA yazılmaz.
#
# KRİTİK KURAL (Faz 2'nin tüm taahhüdü):
#   Bu modül SAF SERİLEŞTİRİCİDİR. Matematik çalıştırmaz, formasyon
#   hesaplamasını değiştirmez, threshold'lara dokunmaz, motor davranışını
#   değiştirmez. Yalnızca `PatternCandidate` -> JSON-safe dict dönüşümü yapar.
#
# MODÜL YERİ NEDEN `state/`:
#   `patterns/` saf matematik katmanıdır ve hiçbir zaman `state/`'e bağımlı
#   olmamalıdır. Ters yön (state -> patterns) serbesttir. Böylece kontrat,
#   persistence tarafında yaşar ve tek yerde tanımlanır.

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "IDENTITY_FIELDS",
    "STATE_FIELDS",
    "BREAKOUT_FIELDS",
    "TRANSIENT_FIELDS",
    "ALL_FIELDS",
    "PERSISTED_TODAY",
    "INCELENMELI",
    "SINIFLAR",
    "bir_snapshot",
    "alan_sinifi",
    "json_guvenli",
]


# =====================================================================
# 1) ALAN SINIFLANDIRMASI — 85 alanın tamamı, belirsiz hiçbiri kalmadan
# =====================================================================
#
# `raw_quality` bilerek İKİ sınıfta geçer:
#   - IDENTITY olarak doğumdaki değer (birth snapshot)
#   - STATE olarak anlık değer (geometry snapshot)
# Bu bir hata değil, bilinçli tasarım: aynı alan iki farklı anlama gelir.

# --- Doğumda sabit: kimlik + doğum geometrisi + direk (pole) ---
IDENTITY_FIELDS: frozenset = frozenset({
    "stable_id",
    "pattern_type",
    "family",
    "classic_dir",
    "specialized_variant",
    # doğum geometrisi
    "start_bar",
    "end_bar",
    "known_bar",
    "apex_bar",
    "hb1", "hp1", "hb2", "hp2",
    "lb1", "lp1", "lb2", "lp2",
    "upper_slope",
    "lower_slope",
    "start_width",
    "geometry_atr",
    # doğumdaki kalite anlık görüntüsü
    "raw_quality",
    # direk (pole) — doğumun parçası
    "has_pole",
    "pole_dir",
    "pole_start_bar",
    "pole_start_price",
    "pole_end_bar",
    "pole_end_price",
    "pole_duration",
    "pole_magnitude",
    "pole_efficiency",
    "pole_quality",
})

# --- Zaman içinde değişir: geometri + kalite bileşenleri ---
STATE_FIELDS: frozenset = frozenset({
    "upper_now",
    "lower_now",
    "current_width",
    "contraction",
    "progress",
    "upper_touches",
    "lower_touches",
    "violation",
    "raw_quality",
    "geometry_score",
    "slope_shape_score",
    "touch_score",
    "contraction_score",
    "maturity_score",
    "correction_depth",
    "duration_ratio",
    "consolidation_efficiency",
    "consolidation_height_ratio",
})

# --- Kırılım anında dondurulan alanlar (Faz 2.4'te serileştirilecek) ---
BREAKOUT_FIELDS: frozenset = frozenset({
    "quality_frozen",
    "frozen_raw_quality",
    "frozen_upper_boundary_at_break",
    "frozen_lower_boundary_at_break",
    "frozen_break_buffer",
    "frozen_retest_tolerance",
    "frozen_atr_at_break",
    "frozen_classic_dir",
    "frozen_pattern_type",
    "break_snapshot_bar",
    "break_snapshot_price",
    "break_snapshot_direction",
    "break_snapshot_quality",
    "break_strength",
    "break_body_score",
    "break_close_score",
    "break_penetration_score",
    "break_expansion_score",
    "break_volume_score",
    "break_confirmation_strength",
})

# --- Motor içi türetilmiş / önbellek / pencere-bağımlı: ASLA persist edilmez ---
#
# `identity` motor-içi sayaçtır (Faz 1 kararı): `stable_id` ile aynı şey
# DEĞİLDİR ve ikisi asla karıştırılmamalıdır. Engine-internal olarak kalır.
TRANSIENT_FIELDS: frozenset = frozenset({
    "valid",
    "identity",
    "selection_score",
    # artan/incremental ihlal taramasının taşıdığı önbellek durumu:
    # her bar yeniden hesaplanır, snapshot'ta anlamı yoktur.
    "historical_upper_close_violations",
    "historical_lower_close_violations",
    "historical_upper_wick_violations",
    "historical_lower_wick_violations",
    "historical_close_violations",
    "historical_wick_violations",
    "max_historical_violation",
    "historical_violation_penalty",
    "historical_scanned_bars",
    "violation_history_truncated",
    "last_violation_processed_bar",
    "violation_geometry_key",
    "violation_scan_mode",
})

SINIFLAR = ("IDENTITY", "STATE", "BREAKOUT", "TRANSIENT")

# Tüm sınıflandırılmış alanlar (birleşim). `raw_quality` iki sınıfta geçtiği
# için union boyutu 84'tür; toplam tekil alan 85'tir.
ALL_FIELDS: frozenset = (IDENTITY_FIELDS | STATE_FIELDS
                         | BREAKOUT_FIELDS | TRANSIENT_FIELDS)


# =====================================================================
# 2) BUGÜN PERSIST EDİLENLER vs INCELENMELI
# =====================================================================
#
# İsteğe bağlı: "Bugün persist edilmeyen ama persistence gerektiren alanlar
# varsa incelemek üzere ayrıca işaretlenmeli (tahmin yapma)."
#
# Burada TAHMİN yapılmaz; liste disk üzerinde ölçülür:
#   - state/formation_identity.py anchor  : 14 candidate alanı yazar
#   - main.py formasyon_kaydi             : 9 candidate alanı yazar
#   - karne.py kayıtları                  : stable_id + pattern_type + kalite
# Birleşim aşağıdadır. Kontrat testi bu listenin gerçekten bugünkü
# davranışla örtüştüğünü doğrular (bkz. test_formation_history.py).
PERSISTED_TODAY: frozenset = frozenset({
    # formation_identity.py
    "stable_id", "family", "classic_dir", "pattern_type",
    "start_bar", "apex_bar",
    "hb1", "hb2", "hp1", "hp2",
    "lb1", "lb2", "lp1", "lp2",
    # main.py formasyon_kaydi
    "raw_quality",          # 'quality' anahtarı
    "upper_now", "lower_now",
    "break_strength", "contraction",
    "upper_touches", "lower_touches",
})

# Sınıflandırılmış (yani history'ye girmeye değer) ama bugün diske yazılmayan.
# Bunlar Faz 2.2/Faz 2.3'te ilk snapshot'larda taşınacaktır. Kesin karar
# gerektiren alanlar için burası "incelenmeli" listesi olarak hizmet eder.
INCELENMELI: frozenset = ((IDENTITY_FIELDS | STATE_FIELDS | BREAKOUT_FIELDS)
                          - PERSISTED_TODAY)


# =====================================================================
# 3) SERİLEŞTİRME
# =====================================================================

def alan_sinifi(alan: str) -> Optional[str]:
    """Bir alanın history sınıfını döndürür. Sınıflandırılmamışsa None."""
    if alan in TRANSIENT_FIELDS:
        return "TRANSIENT"
    if alan in IDENTITY_FIELDS:
        return "IDENTITY"
    if alan in STATE_FIELDS:
        return "STATE"
    if alan in BREAKOUT_FIELDS:
        return "BREAKOUT"
    return None


def json_guvenli(deger: Any) -> Any:
    """NumPy/Timestamp/Pandas tiplerini JSON-safe değere indirger.

    Sözleşmenin can alıcı noktası: bir alanı serileştirmek imkansızsa
    snapshot'ı DÜŞÜRMEK değil, None'a çevirmektir. Eksik alan veya tuhaf
    tip asla exception üretmez (history botu asla durdurmaz).
    """
    if deger is None:
        return None
    if isinstance(deger, bool):
        return deger
    if isinstance(deger, (int, float, str)):
        return deger
    # numpy scalar -> python
    if hasattr(deger, "item"):
        try:
            return json_guvenli(deger.item())
        except Exception:
            return None
    # pandas Timestamp / datetime -> ISO string
    iso = getattr(deger, "isoformat", None)
    if callable(iso):
        try:
            return str(iso())
        except Exception:
            return None
    return str(deger)


def bir_snapshot(
    candidate: Any,
    alanlar: Iterable[str],
    *,
    bar_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Mevcut candidate bilgisinden tek bir snapshot üretir.

    Parametreler
    ------------
    candidate : PatternCandidate (veya stable_id vb. taşıyan benzeri nesne)
    alanlar   : bu snapshot için çıkarılacak alan adları
    bar_time  : opsiyonel; snapshot'ın bağlı olduğu mutlak bar zamanı.
                Snapshot'larda her zaman bulunmalıdır çünkü pencere-koordinat
                bar indeksleri yalnızca bu zamana göre yorumlanabilir.

    Döndürür
    --------
    {"bar_time": str|None, "alanlar": {...}} — JSON-safe, None-tolerant.

    Not: `alanlar` içindeki bir alan candidate'da yoksa sessizce None yazılır.
    Bu bilinçlidir: kontrat, alan listesini sabit tutar; değer varlığına
    göre şekil değiştirmez.
    """
    cikan: Dict[str, Any] = {}
    for alan in alanlar:
        if alan not in ALL_FIELDS:
            # Sınıflandırılmamış alan: kontrat dışıdır, atlanır.
            continue
        cikan[alan] = json_guvenli(getattr(candidate, alan, None))
    return {"bar_time": bar_time, "alanlar": cikan}


def dogum_snapshot(candidate: Any, bar_time: Optional[str] = None) -> Dict[str, Any]:
    """Doğum snapshot'ı: IDENTITY alanları (doğumda sabit olanlar)."""
    return bir_snapshot(candidate, sorted(IDENTITY_FIELDS), bar_time=bar_time)


def geometri_snapshot(candidate: Any, bar_time: Optional[str] = None) -> Dict[str, Any]:
    """Geometri/kalite snapshot'ı: STATE alanları (zaman içinde değişenler)."""
    return bir_snapshot(candidate, sorted(STATE_FIELDS), bar_time=bar_time)


def kirilim_snapshot(candidate: Any, bar_time: Optional[str] = None) -> Dict[str, Any]:
    """Kırılım snapshot'ı: BREAKOUT (dondurulmuş) alanlar."""
    return bir_snapshot(candidate, sorted(BREAKOUT_FIELDS), bar_time=bar_time)


def alan_listesi(*snapshotlar: Dict[str, Any]) -> List[str]:
    """Birkaç snapshot'ın alanlarını tek, sıralı, tekrarsız listede birleştirir."""
    toplam = set()
    for snap in snapshotlar:
        toplam.update((snap or {}).get("alanlar", {}).keys())
    return sorted(toplam)
