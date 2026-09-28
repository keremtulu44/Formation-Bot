# --- SABİTLER ---
# Pine: Bölüm 3 (STATE SABİTLERİ) + f_is_* yardımcıları + tip haritası
# EXPORT contract (f_export_* kodları) bilerek çevrilmedi — kullanıcı isteği.

# State sabitleri - Pine ile birebir aynı stringler
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

# Formasyon tipi -> integer (Pine'daki f_export_pattern_type eşleşmeleri;
# export yapılmıyor ama Python tarafında raporlama için tutuluyor)
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


def f_classic_direction(pattern: str) -> int:
    """Pine: f_classic_direction — formasyonun klasik devam yönü."""
    if pattern in ("Yükselen Üçgen", "Alçalan Kama", "Boğa Bayrağı", "Boğa Flaması"):
        return 1
    if pattern in ("Alçalan Üçgen", "Yükselen Kama", "Ayı Bayrağı", "Ayı Flaması"):
        return -1
    return 0


def f_is_specialized(pattern: str) -> bool:
    """Pine: f_is_specialized — bayrak/flama ailesi (direk zorunlu)."""
    return pattern in ("Boğa Bayrağı", "Ayı Bayrağı", "Boğa Flaması", "Ayı Flaması")


def f_is_flag(pattern: str) -> bool:
    """Pine: f_is_flag."""
    return pattern in ("Boğa Bayrağı", "Ayı Bayrağı")


def f_is_pennant(pattern: str) -> bool:
    """Pine: f_is_pennant."""
    return pattern in ("Boğa Flaması", "Ayı Flaması")


def f_is_break_lifecycle(state_value: str) -> bool:
    """Pine: f_is_break_lifecycle — kırılım alt yaşam döngüsündeki stateler."""
    return state_value in (
        ST_BREAK_ATTEMPT, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED,
        ST_RETEST_WAIT, ST_RETESTING, ST_RETEST_OK,
        ST_BREAK_TIMEOUT, ST_COMPLETED, ST_BREAK_FAILED,
    )


def f_is_terminal(state_value: str) -> bool:
    """Pine: f_is_terminal — son state'ler."""
    return state_value in (ST_COMPLETED, ST_BREAK_FAILED, ST_INVALID)


def f_is_dead_state(state_value: str) -> bool:
    """
    Formasyon "ölü" mü? (canlı takip edilecek bir formasyon kalmadı)

    f_is_terminal'e ek olarak KIRILIM_TEYIT_ALAMADI (ST_BREAK_TIMEOUT) da burada:
    kırılım teyit alamadı, formasyon ya zayıfladı ya yeni aday bekliyor.

    Neden lazım? Motor deterministik tekrar (tam_yeniden=True) ile tüm pencereyi her
    taramada baştan oynatır. Terminal state'e ulaşmış formasyonlar `self.active`'te
    valid kalmaya devam eder (replacement-margin mantığı için gerekli) ve
    _snapshot'ta "canlı formasyon" olarak raporlanırdı. Sonuç: günler önce
    tamamlanmış/başarısız formasyonlar için her taramada "🏁 TAMAMLANDI" mesajı
    (ölçüm: 80 formasyondan 44'ü terminal -> alert akışının %55'i çöptü).
    """
    return state_value in (ST_COMPLETED, ST_BREAK_FAILED, ST_INVALID, ST_BREAK_TIMEOUT, ST_NONE)
