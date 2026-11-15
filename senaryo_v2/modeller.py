"""Gölge v2 veri modelleri ve replay-dayalı yapısal sabitler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TF_LISTESI: tuple[str, ...] = ("1d", "4h", "2h", "1h")
KESIM_TARIHI: str = "2026-04-01"

# Zaman dilimine göre taze ters EXTERNAL BOS / CHoCH penceresi (bar sayısı)
BOS_TAZELIK_PENCERE: dict[str, int] = {
    "1h": 10,
    "2h": 6,
    "4h": 4,
    "1d": 2,
}

# Varsayılan plan / yarış parametreleri (duyarlılık analizi ile ayrıca sınanır)
TAMPON_VARSAYILAN_ATR: float = 0.50
TAMPON_DUYARLILIK_LISTESI: tuple[float, ...] = (0.25, 0.50, 1.00)
UFUK_VARSAYILAN_BAR: int = 10
UFUK_DUYARLILIK_LISTESI: tuple[int, ...] = (10, 16)

# Sığ bağlam eşikleri (domain replay sabitlerinden türetilir)
RUNWAY_MIN_ATR: float = 0.75
SIKISMA_MIN_ATR: float = 0.50

# OB / FVG yapısal eşikleri (ARASTIRMA_SONUCLARI S03/S07/S15)
BLOK_MIN_HEIGHT_ATR: float = 0.50
BLOK_GUCLU_HEIGHT_ATR: float = 1.00
BLOK_ENGEL_MESAFE_ATR: float = 0.75
MOD2_MIN_RISK_ATR: float = 0.35

# VolumeParticipationConfig yerel eşikleriyle uyumlu katılım kapısı eşikleri
VP_MIN_RVOL: float = 0.75
VP_MIN_EFFICIENCY: float = 0.40
VP_MAX_TERS_BASINC: float = 0.13

# Çekirdek yapısal stop açıklığı eşiği (mikro-stop / sürtünme kırılması önlemi)
CEKIRDEK_MIN_RISK_ATR: float = 0.90

# Nedensel tez iptali & limit bekleme & 3-stop freni
TEZ_IPTAL_BAR: int = 3
MAX_BEKLEME_LIMIT: int = 3
FREN_ARDISIK_STOP: int = 3
FREN_SOGUMA_BAR: int = 5

# Veri sürekliliği karantinası (düzeltilmemiş bölünme / bedelli-bedelsiz / temettü
# veya durdurma sonrası açılış). BIST günlük fiyat marjı ±%10'dur; ardışık iki bar
# arasında bunu aşan bir açılış boşluğu normal işlemle oluşamaz. Böyle bir barı
# gören ATR/formasyon/MS durumu ve o barın üstünden taşınan işlem ölçülemez.
KOPUKLUK_ESIK_ORAN: float = 0.115
# Wilder ATR(14) şoku ~60 barda %3'ün altına iner; formasyon/MS pivotları da aynı
# pencerede yenilenir. Kopukluktan sonraki bu kadar bar "kirli bağlam" sayılır.
KOPUKLUK_KARANTINA_BAR: int = 60

# Market Structure motoru bir korunan seviyeyi "geçerli" diye bildirirken fiyat o seviyenin
# bu kadar ATR ötesinde kapanmışsa motorun durumu fiyatla çelişiyordur (bayat). Ardışık
# taban/tavan barlarında ya da kopukluk sonrasında swing oluşmadığı için kırılım olayı
# üretilemeyince görülür ve yüzlerce bar sürebilir. Karar girdisi DEĞİL; yalnız etiket.
MS_BAYAT_ESIK_ATR: float = 1.0


@dataclass(frozen=True, slots=True)
class BlokBand:
    """Bar i itibarıyla nedensel olarak canlı (available_index <= i < terminal_index) OB/FVG bandı."""

    family: str       # "OB" | "FVG"
    direction: str    # "bullish" | "bearish"
    lower: float
    upper: float
    available_index: int
    height_atr: float = 0.0
    touch_count_asof: int = 0


@dataclass(frozen=True, slots=True)
class BarDurum:
    """Tek bir kapalı bar (index i) için nedensel, as-of birleşik durum özeti."""

    i: int
    bar_close_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    atr_tf: float
    atr_1d: float | None
    is_kisa_1800: bool

    # Stabil Destek (S)
    s_level: float | None
    s_validity: str
    s_regime: str
    s_unchanged_days: int
    s_fixed: bool
    s_vertical: bool
    s_reclaim_kind: str | None
    s_momentum_kind: str | None
    s_vertical_attempt: str | None
    s_touch_count: int

    # Stabil Direnç (R)
    r_level: float | None
    r_validity: str
    r_regime: str
    r_unchanged_days: int
    r_fixed: bool
    r_vertical: bool
    r_return_kind: str | None
    r_momentum_kind: str | None
    r_vertical_attempt: str | None
    r_touch_count: int

    # Market Structure (as-of bar i)
    ms_bos_up_now: bool
    ms_bos_down_now: bool
    ms_fresh_dir: int             # +1 (taze UP), -1 (taze DOWN), 0 (yok)
    ms_unbroken_highs: tuple[float, ...]
    ms_unbroken_lows: tuple[float, ...]
    ms_down_broken_levels: tuple[float, ...]
    ms_up_broken_levels: tuple[float, ...]

    # Formasyon (as-of bar i)
    frm_aktif: bool
    frm_stable_id: str
    frm_state: str
    frm_prev_state: str
    frm_pattern_type: str
    frm_classic_dir: int
    frm_break_dir: int
    frm_upper_now: float | None
    frm_lower_now: float | None
    frm_broken_boundary: float | None
    frm_icerde: bool

    # Opsiyonel Bloklar (OB / FVG)
    blok_bull: tuple[BlokBand, ...]
    blok_bear: tuple[BlokBand, ...]

    # Market Structure ek yapısal alanları (PH/PL/WH/WL + bağlam durumu + S26)
    ms_ext_state: str = "STATE_NEUTRAL"
    ms_ext_dir: int = 0
    ms_bos_move_atr: float | None = None
    ms_protected_high: float | None = None
    ms_protected_low: float | None = None
    ms_weak_high: float | None = None
    ms_weak_low: float | None = None
    ms_protected_high_tc: int = 0
    ms_protected_low_tc: int = 0
    ms_protected_high_age: int = 0
    ms_protected_low_age: int = 0

    # Volume Participation (as-of bar i)
    vp_data_ready: bool = False
    vp_volume_usable: bool = False
    vp_rvol: float | None = None
    vp_rtv: float | None = None
    vp_pressure_5: float | None = None
    vp_directional_efficiency: float | None = None
    vp_effort_result_class: str = "NEUTRAL"
    vp_state: str = "PARTICIPATION_PENDING"
    vp_direction: int = 0

    # Formasyon ek metrikleri (FRM-02)
    frm_width_atr: float | None = None
    frm_contraction: float | None = None

    # Market Structure süreç alanları (işlem-içi izleme; hepsi bar i kapanışında as-of).
    # ms_olaylar etiketi: "<EXT|INT>:<BOS|CHOCH|TRANSITION_FAIL|SWEEP|FALSE_BREAK>:<+1|-1>".
    # Yön her zaman olayın İMA ETTİĞİ yöndür (tepe süpürmesi -1, dip süpürmesi +1,
    # başarısız yukarı kırılım -1). Giriş kapıları yalnız EXTERNAL BOS/CHoCH okur;
    # geri kalanı yalnız açık işlemin izlenmesi içindir.
    ms_olaylar: tuple[str, ...] = ()
    ms_int_state: str = "STATE_NEUTRAL"
    ms_int_dir: int = 0
    ms_ext_aday_dir: int = 0      # onay bekleyen (henüz BOS olmamış) dış kırılım adayı yönü
    ms_int_aday_dir: int = 0      # onay bekleyen iç kırılım adayı yönü
    ms_int_protected_high: float | None = None
    ms_int_protected_low: float | None = None

    # Veri sürekliliği: bu barın açılışı önceki kapanıştan KOPUKLUK_ESIK_ORAN'dan fazla kopuk.
    kopukluk: bool = False

    @property
    def ms_dis_bayat(self) -> bool:
        """Dış yapının korunan seviyesi kapanışın `MS_BAYAT_ESIK_ATR` ATR'den fazla gerisinde mi?

        Doğruysa `ms_ext_state` (ve ondan türeyen `ms_yapi_uyumlu`) bu barda güvenilmezdir:
        motor seviyeyi hâlâ koruyor sanıyor, fiyat çoktan ötesinde.
        """
        esik = MS_BAYAT_ESIK_ATR * self.atr_tf
        if self.ms_protected_low is not None and self.close < self.ms_protected_low - esik:
            return True
        return self.ms_protected_high is not None and self.close > self.ms_protected_high + esik


@dataclass(frozen=True, slots=True)
class SeriVerisi:
    """Bir (sembol, tf) çiftinin hizalanmış tüm nedensel bar durumları."""

    sembol: str
    tf: str
    barlar: tuple[BarDurum, ...]
    r_hatali: bool = False
    frm_hatali: bool = False
    ms_hatali: bool = False
    blok_hatali: bool = False
    vp_hatali: bool = False
    # Veri sürekliliği (karar girdisi DEĞİL; yalnız ölçüm kümesinden karantina etiketi):
    kopukluk_barlari: tuple[int, ...] = ()            # bu TF'de açılışı kopuk bar indeksleri
    kopukluk_gorunur_barlari: tuple[int, ...] = ()    # bu TF + günlük bağlam kopukluklarının göründüğü barlar
    kirli_araliklar: tuple[tuple[int, int], ...] = () # as-of bağlamın kirli olduğu [bas, bit] bar aralıkları

    @property
    def domain_hatali(self) -> bool:
        """Herhangi bir domain motoru hata verdiyse seri ölçüme alınmaz (fail-closed)."""
        return bool(self.r_hatali or self.frm_hatali or self.ms_hatali or self.blok_hatali or self.vp_hatali)

    def karantina_nedeni(self, bar_index: int, *, ileri_bar: int) -> str:
        """Olay barı için veri karantinası etiketi ("" = temiz).

        * `KOPUKLUK_GERI`  — olay barının as-of bağlamı (ATR, formasyon, MS, Stabil) bir
          fiyat kopukluğunu hâlâ taşıyor.
        * `KOPUKLUK_ILERI` — işlem penceresi (`bar_index` sonrası `ileri_bar` bar) içinde
          bir kopukluk var; sonuç stratejiye değil kurumsal işleme/durdurmaya aittir.

        Etiket işlemin nasıl bittiğine BAKMAZ (yalnız takvim konumuna bakar); böylece
        karantina sonuca göre seçim yapmaz.
        """
        geri = any(bas <= bar_index <= bit for bas, bit in self.kirli_araliklar)
        ileri = any(bar_index < x <= bar_index + ileri_bar for x in self.kopukluk_gorunur_barlari)
        if geri and ileri:
            return "KOPUKLUK_GERI+ILERI"
        if geri:
            return "KOPUKLUK_GERI"
        if ileri:
            return "KOPUKLUK_ILERI"
        return ""


@dataclass(frozen=True, slots=True)
class AdayOlay:
    """Ham aday olay + domain bazlı sığ kapı bayrakları (ablasyon için hiçbiri gizlice atılmaz)."""

    olay_id: str
    sembol: str
    tf: str
    bar_index: int
    bar_close_time: str
    donem: str                    # "kesif" (< KESIM_TARIHI) | "dogrulama" (>= KESIM_TARIHI)
    kohort: str                   # "A_stabil" | "B_formasyon"
    alt_kol: str                  # "A_sweep" | "A_multi_bar" | "A_return" | "A_momentum" | "B_kirilim" | "B_retest" | "B_sinir"
    tetik_adi: str                # ham alt olay adı (ör. intrabar_sweep_reclaim, KIRILIM_ADAYI, ...)
    yon: str                      # "long" | "short"
    giris_baz: float
    atr_tf: float
    atr_1d: float | None
    zemin_tavan: float            # yapısal taban (long) veya tavan (short) seviyesi
    is_kisa_1800: bool

    # 3 ana sığ kapı (G1, G2, G3) + 2 replay-doğrulanmış domain kapısı (G4 VP, G5 OB/FVG)
    g1_sr_koridor: bool
    g2_ms_bos: bool
    g3_frm_sikisma: bool

    # Teşhis detayları
    g1_dikey_bos: bool            # True => altı/üstü boş ihlali YOK (dikey proxy kapalı)
    g1_karsi_duvar_ok: bool       # True => karşı Stabil çizgisine runway >= RUNWAY_MIN_ATR
    runway_sr_atr: float | None
    frm_karsi_mesafe_atr: float | None
    sr_rejim_etiketi: str         # "S_REJ|R_REJ"
    ms_fresh_dir: int             # +1, -1, 0 (uyumlu / ters / yok teşhisi)
    touch_count: int
    frende: bool = False          # 3-ardışık stop freninde mi oluştu (nedensel)

    # Yeni domain denetimi ve öncelik alanları (varsayılanlı -> geriye uyumlu)
    sinyal_sinifi: str = "IKINCIL"     # "BIRINCIL" (B_kirilim: KIRILIM_ADAYI) | "IKINCIL" (retest/teyitli/sinir/stabil)
    kalite_katmani: str = "C_IKINCIL"  # "A_ARTI" | "A_CEKIRDEK" | "B_ADAY" | "C_IKINCIL"
    g4_vp_kalite: bool = True          # VP kullanılabilirse RVOL>=0.75 & eff>=0.40 & ters baskı yok
    g5_blok_temiz: bool = True         # Önde <0.75 ATR içinde taze+uzun (>=1.0 ATR) karşı OB/FVG yok
    ms_yapi_uyumlu: bool = False       # ms_fresh_dir == yon veya ms_ext_state yönle uyumlu
    cift_kirilim_stabil: bool = False  # B_kirilim doğrudan Stabil S/R duvarını kırıyorsa True
    vp_emilim_onayi: bool = False      # S10: A_stabil/destekte HIGH/VERY_HIGH_EFFORT_WEAK_RESULT
    vp_guclu_sonuc: bool = False       # Kırılımda STRONG_RESULT hacim itişi
    frm_pattern_type: str = ""
    frm_width_atr: float | None = None
    risk_baz_atr: float = 0.0
    ms_ext_state: str = "STATE_NEUTRAL"
    vp_volume_usable: bool = False
    vp_rvol: float | None = None
    vp_pressure_5: float | None = None
    vp_efficiency: float | None = None
    vp_effort_result_class: str = "NEUTRAL"
    opp_blok_engeli: bool = False

    @property
    def tum_kapilar_ok(self) -> bool:
        return self.g1_sr_koridor and self.g2_ms_bos and self.g3_frm_sikisma

    @property
    def tum_domain_kapilari_ok(self) -> bool:
        return self.tum_kapilar_ok and self.g4_vp_kalite and self.g5_blok_temiz


@dataclass(frozen=True, slots=True)
class PlanKartV2:
    """Seçilen giriş modu (Mod 0 / Mod 1 / Mod 2) ve tampon için plan kartı."""

    olay_id: str
    mod: str                      # "mod0" | "mod1" | "mod2"
    tampon_atr: float
    yon: str
    giris: float
    stop: float
    risk_atr: float
    hedef_yapisal: float | None
    r_yapisal: float | None
    hedef_kaynagi: str
    blok_kullanildi: bool
    blok_bilgisi: str             # "" | "OB:lo-hi" | "FVG:lo-hi"
    limit_fiyat: float | None = None
    karsi_aday_sayisi: int = 0


@dataclass(frozen=True, slots=True)
class YarisSonucuV2:
    """Hem yapısal hedef hem simetrik 1.5/2.0 ATR hedef, close & intrabar, tez iptali açık/kapalı."""

    olay_id: str
    mod: str
    tampon_atr: float
    ufuk_bar: int
    dolduruldu: bool              # Mod 0/1 için her zaman True; Mod 2 için limit dolumu
    dolum_bar_offset: int         # 0 (Mod 0/1) veya 1..3 (Mod 2)
    giris_gercek: float | None
    stop_gercek: float
    risk_gercek_atr: float

    # A. Simetrik 1.5 ATR hedef (intrabar OHLC, tez iptali açık & kapalı)
    pnl_15_intra_iptal_atr: float | None
    pnl_15_intra_iptal_r: float | None
    neden_15_intra_iptal: str
    bar_15_intra_iptal: int

    pnl_15_intra_ham_atr: float | None
    pnl_15_intra_ham_r: float | None
    neden_15_intra_ham: str

    # B. Simetrik 1.5 ATR hedef (close-only)
    pnl_15_close_iptal_atr: float | None
    neden_15_close_iptal: str

    # C. Simetrik 2.0 ATR hedef (intrabar OHLC, tez iptali açık & kapalı)
    pnl_20_intra_iptal_atr: float | None
    pnl_20_intra_iptal_r: float | None
    neden_20_intra_iptal: str

    pnl_20_intra_ham_atr: float | None
    pnl_20_intra_ham_r: float | None

    # D. Yapısal hedef yarışı (en yakın karşıt Stabil/MS seviyesi, varsa)
    pnl_yap_intra_iptal_atr: float | None
    pnl_yap_intra_iptal_r: float | None
    neden_yap_intra_iptal: str

    pnl_yap_intra_ham_atr: float | None
    pnl_yap_intra_ham_r: float | None
    neden_yap_intra_ham: str

    pnl_yap_close_iptal_atr: float | None
    pnl_yap_close_iptal_r: float | None
    neden_yap_close_iptal: str

    # E. Saf H-bar sonrası MFE/MAE & kapanış getirisi (tez iptali kapalı).
    # DİKKAT: bunlar stopsuz/hedefsiz TAM ufuk yoludur, çıkışta kesilmez; "işlem sırasında
    # ne görüldü" sorusu için `surec.mfe_r` / `surec.mae_r` (çıkışa kadar) kullanılır.
    mfe_atr: float | None
    mae_atr: float | None
    kapanis_h_atr: float | None
    sansurlu: bool
    sonuc_meta: dict[str, Any] | None = None

    # F. Birincil yarışın (2.0 ATR, intrabar, tez iptali açık) çıkış barı ve süreç özeti
    bar_20_intra_iptal: int = 0           # dolumdan itibaren çıkış barı (dolum barında çıkış = 0)
    risk_r_atr: float | None = None       # R paydası (ATR): Mod 0/1 gerçek risk, Mod 2 planlanan risk
    surec: Any | None = None              # senaryo_v2.surec.SurecOzeti (işlem-içi izleme özeti)
