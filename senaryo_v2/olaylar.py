"""Gölge v2 aday olay çıkarımı ve tüm domain kapıları (G1..G5 + sinyal önceliği).

Her aday olay **kesinlikle düşürülmez**:
- `BIRINCIL`: Formasyon taze kırılım adayı (`B_kirilim: KIRILIM_ADAYI`)
- `IKINCIL` (düşük öncelikli / ayrıştırılmış):
  * `B_retest` (`RETEST_BASARILI`) — FRM-13 ve ampirik bulguya göre devamlılığı zayıf
  * Gecikmiş `KIRILIM_TEYITLI` (zayıf deneme sonrası 1-3 bar geç gelen onay)
  * `B_sinir` (formasyon içi sınır dönüşü)
  * `A_stabil` (yalnız başına yatay ok; S10 emilim onayı ayrı etiketlenir)
"""

from __future__ import annotations

import math

from patterns.constants import (
    ST_BREAK_CANDIDATE,
    ST_BREAK_CONFIRMED,
    ST_COMPRESSING,
    ST_DEFINED,
    ST_MATURING,
    ST_PREP,
    ST_RETEST_OK,
)

from .modeller import (
    BLOK_ENGEL_MESAFE_ATR,
    BLOK_GUCLU_HEIGHT_ATR,
    CEKIRDEK_MIN_RISK_ATR,
    KESIM_TARIHI,
    RUNWAY_MIN_ATR,
    SIKISMA_MIN_ATR,
    TAMPON_VARSAYILAN_ATR,
    VP_MAX_TERS_BASINC,
    VP_MIN_EFFICIENCY,
    VP_MIN_RVOL,
    AdayOlay,
    BarDurum,
    SeriVerisi,
)

_GUCLU_LONG_DIKEY = frozenset({
    "intrabar_sweep_reclaim",
    "long_base_breakout",
    "upward_rebase_momentum",
})
_GUCLU_SHORT_DIKEY = frozenset({
    "close_return_below",
    "intrabar_sweep_rejection",
    "long_ceiling_breakdown",
    "downward_rebase_momentum",
})
_FRM_KIRILIM_ST = frozenset({ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED})
_FRM_SINIR_ST = frozenset({ST_DEFINED, ST_MATURING, ST_COMPRESSING, ST_PREP})

_VP_WEAK_ABSORB = frozenset({"HIGH_EFFORT_WEAK_RESULT", "VERY_HIGH_EFFORT_WEAK_RESULT"})
_VP_STRONG_RESULT = frozenset({"RISING_EFFORT_STRONG_RESULT", "HIGH_EFFORT_STRONG_RESULT"})


def _stabil_runway_atr(b: BarDurum, yon: str) -> float | None:
    if b.atr_tf <= 0:
        return None
    if yon == "long":
        if (
            b.r_level is not None
            and b.r_validity in ("ACTIVE", "BREACHED")
            and b.r_level > b.close - 0.10 * b.atr_tf
        ):
            return max(0.0, (b.r_level - b.close) / b.atr_tf)
        return None
    if (
        b.s_level is not None
        and b.s_validity in ("ACTIVE", "BREACHED")
        and b.s_level < b.close + 0.10 * b.atr_tf
    ):
        return max(0.0, (b.close - b.s_level) / b.atr_tf)
    return None


def _frm_karsi_mesafe_atr(b: BarDurum, yon: str) -> float | None:
    if not b.frm_icerde or b.atr_tf <= 0:
        return None
    if yon == "long" and b.frm_upper_now is not None:
        return (b.frm_upper_now - b.close) / b.atr_tf
    if yon == "short" and b.frm_lower_now is not None:
        return (b.close - b.frm_lower_now) / b.atr_tf
    return None


def _vp_kapisi_ve_bayraklar(b: BarDurum, yon: str) -> tuple[bool, bool, bool]:
    """(g4_vp_kalite, vp_emilim_onayi, vp_guclu_sonuc) döndürür.

    S32 & Endeks kuralı: `vp_data_ready` veya `vp_volume_usable` False ise fail-open (True).
    """
    usable = bool(b.vp_data_ready and b.vp_volume_usable)
    if not usable:
        return True, False, False

    emilim = b.vp_effort_result_class in _VP_WEAK_ABSORB
    guclu = b.vp_effort_result_class in _VP_STRONG_RESULT
    yon_int = 1 if yon == "long" else -1

    rvol_ok = b.vp_rvol is None or b.vp_rvol >= VP_MIN_RVOL
    eff_ok = b.vp_directional_efficiency is None or b.vp_directional_efficiency >= VP_MIN_EFFICIENCY
    p5_ok = b.vp_pressure_5 is None or (b.vp_pressure_5 * yon_int) > -VP_MAX_TERS_BASINC
    return bool(rvol_ok and eff_ok and p5_ok), emilim, guclu


def _blok_temiz_mi(b: BarDurum, yon: str) -> bool:
    """S03/S07: Önde < 0.75 ATR içinde taze (tc==0) ve güçlü (>=1.0 ATR) karşı OB/FVG yoksa True."""
    if b.atr_tf <= 0:
        return True
    atr = b.atr_tf
    if yon == "long":
        for z in b.blok_bear:
            h_atr = z.height_atr if z.height_atr > 0 else (z.upper - z.lower) / atr
            if (
                h_atr >= BLOK_GUCLU_HEIGHT_ATR
                and z.touch_count_asof == 0
                and (b.close - 0.20 * atr) <= z.lower <= (b.close + BLOK_ENGEL_MESAFE_ATR * atr)
            ):
                return False
        return True
    for z in b.blok_bull:
        h_atr = z.height_atr if z.height_atr > 0 else (z.upper - z.lower) / atr
        if (
            h_atr >= BLOK_GUCLU_HEIGHT_ATR
            and z.touch_count_asof == 0
            and (b.close - BLOK_ENGEL_MESAFE_ATR * atr) <= z.upper <= (b.close + 0.20 * atr)
        ):
            return False
    return True


def _ms_yapi_uyumlu_mu(b: BarDurum, yon: str) -> bool:
    yon_int = 1 if yon == "long" else -1
    if b.ms_fresh_dir == yon_int:
        return True
    if yon == "long":
        return b.ms_ext_state in ("STATE_BULLISH", "STATE_TRANSITION_UP")
    return b.ms_ext_state in ("STATE_BEARISH", "STATE_TRANSITION_DOWN")


def _olay_olustur(
    *,
    seri: SeriVerisi,
    b: BarDurum,
    kohort: str,
    alt_kol: str,
    tetik_adi: str,
    yon: str,
    zemin_tavan: float,
    g1_dikey_bos: bool,
    g1_karsi_duvar_ok: bool,
    g1_duvar_engeli_aktif: bool,
    runway_sr_atr: float | None,
    frm_karsi_mesafe_atr: float | None,
    g3_frm_sikisma: bool,
    touch_count: int,
    frm_width_atr: float | None = None,
) -> AdayOlay:
    donem = "kesif" if b.bar_close_time[:10] < KESIM_TARIHI else "dogrulama"
    yon_int = 1 if yon == "long" else -1

    # G1: B_kirilim doğrudan Stabil S/R duvarını kırıyorsa engel değildir (cift_kirilim_stabil).
    g1 = bool(g1_dikey_bos and (g1_karsi_duvar_ok or not g1_duvar_engeli_aktif))
    g2 = (b.ms_fresh_dir != -1) if yon == "long" else (b.ms_fresh_dir != 1)
    g4_vp, vp_emilim, vp_guclu = _vp_kapisi_ve_bayraklar(b, yon)
    g5_blok = _blok_temiz_mi(b, yon)
    ms_uyum = _ms_yapi_uyumlu_mu(b, yon)

    stop_baz = (
        float(zemin_tavan) - TAMPON_VARSAYILAN_ATR * b.atr_tf
        if yon == "long"
        else float(zemin_tavan) + TAMPON_VARSAYILAN_ATR * b.atr_tf
    )
    risk_baz_atr = round(abs(b.close - stop_baz) / b.atr_tf, 4) if b.atr_tf > 0 else 0.0

    # Öncelik sınıflandırması: yalnızca B_kirilim + KIRILIM_ADAYI BIRINCIL'dir.
    is_birincil = (alt_kol == "B_kirilim" and tetik_adi == ST_BREAK_CANDIDATE)
    sinyal_sinifi = "BIRINCIL" if is_birincil else "IKINCIL"
    cift_kirilim = bool(alt_kol == "B_kirilim" and not g1_karsi_duvar_ok)

    if is_birincil and g2 and b.ms_fresh_dir == yon_int and g4_vp and g5_blok:
        kalite_katmani = "A_ARTI"
    elif is_birincil and g2 and ms_uyum and g4_vp and g5_blok and risk_baz_atr >= CEKIRDEK_MIN_RISK_ATR:
        kalite_katmani = "A_CEKIRDEK"
    elif is_birincil:
        kalite_katmani = "B_ADAY"
    else:
        kalite_katmani = "C_IKINCIL"

    return AdayOlay(
        olay_id=f"{seri.sembol}:{seri.tf}:{b.i}:{alt_kol}:{yon}",
        sembol=seri.sembol,
        tf=seri.tf,
        bar_index=b.i,
        bar_close_time=b.bar_close_time,
        donem=donem,
        kohort=kohort,
        alt_kol=alt_kol,
        tetik_adi=tetik_adi,
        yon=yon,
        giris_baz=b.close,
        atr_tf=b.atr_tf,
        atr_1d=b.atr_1d,
        zemin_tavan=float(zemin_tavan),
        is_kisa_1800=b.is_kisa_1800,
        g1_sr_koridor=g1,
        g2_ms_bos=g2,
        g3_frm_sikisma=bool(g3_frm_sikisma),
        g1_dikey_bos=bool(g1_dikey_bos),
        g1_karsi_duvar_ok=bool(g1_karsi_duvar_ok),
        runway_sr_atr=runway_sr_atr,
        frm_karsi_mesafe_atr=frm_karsi_mesafe_atr,
        sr_rejim_etiketi=f"{b.s_regime}|{b.r_regime}",
        ms_fresh_dir=b.ms_fresh_dir,
        touch_count=int(touch_count),
        sinyal_sinifi=sinyal_sinifi,
        kalite_katmani=kalite_katmani,
        g4_vp_kalite=g4_vp,
        g5_blok_temiz=g5_blok,
        ms_yapi_uyumlu=ms_uyum,
        cift_kirilim_stabil=cift_kirilim,
        vp_emilim_onayi=vp_emilim,
        vp_guclu_sonuc=vp_guclu,
        frm_pattern_type=b.frm_pattern_type,
        frm_width_atr=frm_width_atr if frm_width_atr is not None else b.frm_width_atr,
        risk_baz_atr=risk_baz_atr,
        ms_ext_state=b.ms_ext_state,
        vp_volume_usable=bool(b.vp_data_ready and b.vp_volume_usable),
        vp_rvol=b.vp_rvol,
        vp_pressure_5=b.vp_pressure_5,
        vp_efficiency=b.vp_directional_efficiency,
        vp_effort_result_class=b.vp_effort_result_class,
        opp_blok_engeli=not g5_blok,
    )


def aday_olaylari_cikar(seri: SeriVerisi, *, min_warmup_bar: int = 20) -> tuple[AdayOlay, ...]:
    """Serideki tüm Kohort A (Stabil) ve Kohort B (Formasyon) aday olaylarını çıkarır."""
    olaylar: list[AdayOlay] = []
    kirilim_ids: set[str] = set()
    retest_ids: set[str] = set()
    sinir_son_bar: dict[tuple[str, str], int] = {}

    for b in seri.barlar:
        if b.i < min_warmup_bar:
            continue

        # ------------------------------------------------------------------
        # KOHORT A — Stabil S (Long) ve Stabil R (Short) -> IKINCIL
        # ------------------------------------------------------------------
        if b.s_level is not None and math.isfinite(b.s_level) and b.s_level > 0:
            long_tetik: str | None = None
            long_alt: str | None = None
            if b.s_reclaim_kind == "intrabar_sweep_reclaim":
                long_tetik = b.s_reclaim_kind
                long_alt = "A_sweep"
            elif b.s_reclaim_kind == "multi_bar_recovery":
                long_tetik = b.s_reclaim_kind
                long_alt = "A_multi_bar"
            elif b.s_momentum_kind is not None:
                long_tetik = b.s_momentum_kind
                long_alt = "A_momentum"
            elif b.s_vertical and b.s_vertical_attempt in _GUCLU_LONG_DIKEY:
                long_tetik = b.s_vertical_attempt
                long_alt = "A_sweep" if long_tetik == "intrabar_sweep_reclaim" else "A_momentum"

            if long_tetik is not None and long_alt is not None and b.close > b.s_level:
                runway = _stabil_runway_atr(b, "long")
                frm_dist = _frm_karsi_mesafe_atr(b, "long")
                olaylar.append(
                    _olay_olustur(
                        seri=seri,
                        b=b,
                        kohort="A_stabil",
                        alt_kol=long_alt,
                        tetik_adi=long_tetik,
                        yon="long",
                        zemin_tavan=b.s_level,
                        g1_dikey_bos=not b.s_vertical,
                        g1_karsi_duvar_ok=(runway is None or runway >= RUNWAY_MIN_ATR),
                        g1_duvar_engeli_aktif=True,
                        runway_sr_atr=runway,
                        frm_karsi_mesafe_atr=frm_dist,
                        g3_frm_sikisma=(frm_dist is None or frm_dist >= SIKISMA_MIN_ATR),
                        touch_count=b.s_touch_count,
                    )
                )

        if b.r_level is not None and math.isfinite(b.r_level) and b.r_level > 0:
            short_tetik: str | None = None
            short_alt: str | None = None
            if b.r_return_kind == "close_return_below":
                short_tetik = b.r_return_kind
                short_alt = "A_return"
            elif b.r_return_kind == "intrabar_sweep_rejection":
                short_tetik = b.r_return_kind
                short_alt = "A_sweep"
            elif b.r_momentum_kind is not None:
                short_tetik = b.r_momentum_kind
                short_alt = "A_momentum"
            elif b.r_vertical and b.r_vertical_attempt in _GUCLU_SHORT_DIKEY:
                short_tetik = b.r_vertical_attempt
                if short_tetik == "close_return_below":
                    short_alt = "A_return"
                elif short_tetik == "intrabar_sweep_rejection":
                    short_alt = "A_sweep"
                else:
                    short_alt = "A_momentum"

            if short_tetik is not None and short_alt is not None and b.close < b.r_level:
                runway = _stabil_runway_atr(b, "short")
                frm_dist = _frm_karsi_mesafe_atr(b, "short")
                olaylar.append(
                    _olay_olustur(
                        seri=seri,
                        b=b,
                        kohort="A_stabil",
                        alt_kol=short_alt,
                        tetik_adi=short_tetik,
                        yon="short",
                        zemin_tavan=b.r_level,
                        g1_dikey_bos=not b.r_vertical,
                        g1_karsi_duvar_ok=(runway is None or runway >= RUNWAY_MIN_ATR),
                        g1_duvar_engeli_aktif=True,
                        runway_sr_atr=runway,
                        frm_karsi_mesafe_atr=frm_dist,
                        g3_frm_sikisma=(frm_dist is None or frm_dist >= SIKISMA_MIN_ATR),
                        touch_count=b.r_touch_count,
                    )
                )

        # ------------------------------------------------------------------
        # KOHORT B — Formasyon Kırılım (BIRINCIL: KIRILIM_ADAYI) / Retest & Sınır (IKINCIL)
        # ------------------------------------------------------------------
        if b.frm_aktif and b.frm_stable_id:
            frm_w = (
                round((b.frm_upper_now - b.frm_lower_now) / b.atr_tf, 4)
                if (b.frm_upper_now is not None and b.frm_lower_now is not None and b.atr_tf > 0)
                else b.frm_width_atr
            )

            # 1) Kırılım (KIRILIM_ADAYI = BIRINCIL; gecikmiş KIRILIM_TEYITLI = IKINCIL)
            if (
                b.frm_state in _FRM_KIRILIM_ST
                and b.frm_stable_id not in kirilim_ids
                and b.frm_break_dir in (-1, 1)
            ):
                yon = "long" if b.frm_break_dir == 1 else "short"
                sinir = b.frm_broken_boundary
                if sinir is None:
                    sinir = b.frm_upper_now if yon == "long" else b.frm_lower_now
                if sinir is not None and math.isfinite(sinir) and sinir > 0:
                    if (yon == "long" and b.close > sinir) or (yon == "short" and b.close < sinir):
                        kirilim_ids.add(b.frm_stable_id)
                        runway = _stabil_runway_atr(b, yon)
                        olaylar.append(
                            _olay_olustur(
                                seri=seri,
                                b=b,
                                kohort="B_formasyon",
                                alt_kol="B_kirilim",
                                tetik_adi=b.frm_state,
                                yon=yon,
                                zemin_tavan=sinir,
                                g1_dikey_bos=True,
                                g1_karsi_duvar_ok=(runway is None or runway >= RUNWAY_MIN_ATR),
                                g1_duvar_engeli_aktif=False,
                                runway_sr_atr=runway,
                                frm_karsi_mesafe_atr=frm_w,
                                g3_frm_sikisma=True,
                                touch_count=0,
                                frm_width_atr=frm_w,
                            )
                        )

            # 2) Retest Başarılı — DÜŞÜRÜLMÜŞ ÖNCELİK (IKINCIL; yalnızca ablasyon/karşılaştırma için etiketlenir)
            if (
                b.frm_state == ST_RETEST_OK
                and b.frm_prev_state != ST_RETEST_OK
                and b.frm_stable_id not in retest_ids
                and b.frm_break_dir in (-1, 1)
            ):
                yon = "long" if b.frm_break_dir == 1 else "short"
                sinir = b.frm_broken_boundary
                if sinir is None:
                    sinir = b.frm_upper_now if yon == "long" else b.frm_lower_now
                if sinir is not None and math.isfinite(sinir) and sinir > 0:
                    if (yon == "long" and b.close > sinir) or (yon == "short" and b.close < sinir):
                        retest_ids.add(b.frm_stable_id)
                        runway = _stabil_runway_atr(b, yon)
                        olaylar.append(
                            _olay_olustur(
                                seri=seri,
                                b=b,
                                kohort="B_formasyon",
                                alt_kol="B_retest",
                                tetik_adi=b.frm_state,
                                yon=yon,
                                zemin_tavan=sinir,
                                g1_dikey_bos=True,
                                g1_karsi_duvar_ok=(runway is None or runway >= RUNWAY_MIN_ATR),
                                g1_duvar_engeli_aktif=True,
                                runway_sr_atr=runway,
                                frm_karsi_mesafe_atr=frm_w,
                                g3_frm_sikisma=True,
                                touch_count=0,
                                frm_width_atr=frm_w,
                            )
                        )

            # 3) Aktif formasyon içi sınır tepkisi (IKINCIL)
            if (
                b.frm_icerde
                and b.frm_state in _FRM_SINIR_ST
                and b.frm_lower_now is not None
                and b.frm_upper_now is not None
                and b.atr_tf > 0
            ):
                if (
                    b.low <= b.frm_lower_now + 0.15 * b.atr_tf
                    and b.close > b.frm_lower_now
                    and (b.close - b.open) >= 0.25 * b.atr_tf
                    and (b.i - sinir_son_bar.get((b.frm_stable_id, "long"), -999)) >= 3
                ):
                    sinir_son_bar[(b.frm_stable_id, "long")] = b.i
                    runway = _stabil_runway_atr(b, "long")
                    ic_bosluk = (b.frm_upper_now - b.close) / b.atr_tf
                    duvar_ok = (runway is None or runway >= RUNWAY_MIN_ATR) and (ic_bosluk >= RUNWAY_MIN_ATR)
                    olaylar.append(
                        _olay_olustur(
                            seri=seri,
                            b=b,
                            kohort="B_formasyon",
                            alt_kol="B_sinir",
                            tetik_adi="FRM_ALT_SINIR",
                            yon="long",
                            zemin_tavan=b.frm_lower_now,
                            g1_dikey_bos=True,
                            g1_karsi_duvar_ok=duvar_ok,
                            g1_duvar_engeli_aktif=True,
                            runway_sr_atr=runway,
                            frm_karsi_mesafe_atr=ic_bosluk,
                            g3_frm_sikisma=True,
                            touch_count=0,
                            frm_width_atr=frm_w,
                        )
                    )

                if (
                    b.high >= b.frm_upper_now - 0.15 * b.atr_tf
                    and b.close < b.frm_upper_now
                    and (b.open - b.close) >= 0.25 * b.atr_tf
                    and (b.i - sinir_son_bar.get((b.frm_stable_id, "short"), -999)) >= 3
                ):
                    sinir_son_bar[(b.frm_stable_id, "short")] = b.i
                    runway = _stabil_runway_atr(b, "short")
                    ic_bosluk = (b.close - b.frm_lower_now) / b.atr_tf
                    duvar_ok = (runway is None or runway >= RUNWAY_MIN_ATR) and (ic_bosluk >= RUNWAY_MIN_ATR)
                    olaylar.append(
                        _olay_olustur(
                            seri=seri,
                            b=b,
                            kohort="B_formasyon",
                            alt_kol="B_sinir",
                            tetik_adi="FRM_UST_SINIR",
                            yon="short",
                            zemin_tavan=b.frm_upper_now,
                            g1_dikey_bos=True,
                            g1_karsi_duvar_ok=duvar_ok,
                            g1_duvar_engeli_aktif=True,
                            runway_sr_atr=runway,
                            frm_karsi_mesafe_atr=ic_bosluk,
                            g3_frm_sikisma=True,
                            touch_count=0,
                            frm_width_atr=frm_w,
                        )
                    )

    return tuple(olaylar)
