"""Gölge v2 çekirdek birim testleri — simetri, muhafazakar çıkış, domain kapıları, Mod 1/2, fren."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from patterns.constants import ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK
from senaryo_v2.modeller import BarDurum, BlokBand, SeriVerisi
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.rapor import domain_ablasyonu_uret, kume_bootstrap_ozet
from senaryo_v2.yaris import fren_etiketle, yarisi_yurut


def _bar(
    i: int,
    *,
    o: float = 100.0,
    h: float = 101.0,
    l: float = 99.0,
    c: float = 100.5,
    atr: float = 2.0,
    s_level: float | None = 98.0,
    r_level: float | None = 110.0,
    s_vertical: bool = False,
    r_vertical: bool = False,
    s_reclaim_kind: str | None = None,
    r_return_kind: str | None = None,
    ms_bos_up_now: bool = False,
    ms_bos_down_now: bool = False,
    ms_fresh_dir: int = 0,
    ms_ext_state: str = "STATE_NEUTRAL",
    frm_aktif: bool | None = None,
    frm_stable_id: str = "",
    frm_state: str = "YOK",
    frm_prev_state: str = "YOK",
    frm_break_dir: int = 0,
    frm_broken_boundary: float | None = None,
    frm_icerde: bool = False,
    frm_upper_now: float | None = None,
    frm_lower_now: float | None = None,
    blok_bull: tuple[BlokBand, ...] = (),
    blok_bear: tuple[BlokBand, ...] = (),
    vp_data_ready: bool = False,
    vp_volume_usable: bool = False,
    vp_rvol: float | None = None,
    vp_pressure_5: float | None = None,
    vp_directional_efficiency: float | None = None,
    vp_effort_result_class: str = "NEUTRAL",
) -> BarDurum:
    return BarDurum(
        i=i,
        bar_close_time=f"2026-03-{(i % 28) + 1:02d}T13:30:00+03:00",
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1000.0,
        atr_tf=atr,
        atr_1d=atr * 2.0,
        is_kisa_1800=False,
        s_level=s_level,
        s_validity="ACTIVE" if s_level else "NO_SUPPORT",
        s_regime="HORIZONTAL_BASE",
        s_unchanged_days=15,
        s_fixed=True,
        s_vertical=s_vertical,
        s_reclaim_kind=s_reclaim_kind,
        s_momentum_kind=None,
        s_vertical_attempt=None,
        s_touch_count=1,
        r_level=r_level,
        r_validity="ACTIVE" if r_level else "NO_RESISTANCE",
        r_regime="HORIZONTAL_CEILING",
        r_unchanged_days=15,
        r_fixed=True,
        r_vertical=r_vertical,
        r_return_kind=r_return_kind,
        r_momentum_kind=None,
        r_vertical_attempt=None,
        r_touch_count=1,
        ms_bos_up_now=ms_bos_up_now,
        ms_bos_down_now=ms_bos_down_now,
        ms_fresh_dir=ms_fresh_dir,
        ms_unbroken_highs=(105.0,),
        ms_unbroken_lows=(95.0,),
        ms_down_broken_levels=(),
        ms_up_broken_levels=(),
        frm_aktif=frm_icerde if frm_aktif is None else frm_aktif,
        frm_stable_id=frm_stable_id or ("frm_test" if frm_icerde else ""),
        frm_state="SIKISMA_GUCLENIYOR" if frm_icerde and frm_state == "YOK" else frm_state,
        frm_prev_state="OLGUNLASIYOR" if frm_icerde and frm_prev_state == "YOK" else frm_prev_state,
        frm_pattern_type="Yukselen Ucgen" if (frm_icerde or frm_aktif) else "",
        frm_classic_dir=1 if (frm_icerde or frm_aktif) else 0,
        frm_break_dir=frm_break_dir,
        frm_upper_now=frm_upper_now,
        frm_lower_now=frm_lower_now,
        frm_broken_boundary=frm_broken_boundary,
        frm_icerde=frm_icerde,
        blok_bull=blok_bull,
        blok_bear=blok_bear,
        ms_ext_state=ms_ext_state,
        vp_data_ready=vp_data_ready,
        vp_volume_usable=vp_volume_usable,
        vp_rvol=vp_rvol,
        vp_pressure_5=vp_pressure_5,
        vp_directional_efficiency=vp_directional_efficiency,
        vp_effort_result_class=vp_effort_result_class,
    )


def test_sig_kapilar_ayri_ayri_etiketlenir_ve_atmaz():
    barlar = [_bar(k) for k in range(20)]
    barlar.append(_bar(20, c=100.0, s_level=98.0, s_vertical=True, s_reclaim_kind=None))
    b20 = barlar[-1]
    barlar[-1] = replace(b20, s_vertical_attempt="intrabar_sweep_reclaim")
    barlar.append(_bar(21, c=100.0, s_level=98.0, ms_fresh_dir=-1, s_reclaim_kind="intrabar_sweep_reclaim"))
    barlar.append(
        _bar(
            22,
            c=100.0,
            s_level=98.0,
            s_reclaim_kind="intrabar_sweep_reclaim",
            frm_icerde=True,
            frm_lower_now=98.5,
            frm_upper_now=100.6,
        )
    )
    barlar.append(_bar(23, c=100.0, r_level=102.0, s_level=94.0, r_return_kind="intrabar_sweep_rejection"))

    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olaylar = aday_olaylari_cikar(seri, min_warmup_bar=20)
    assert len(olaylar) == 4

    o20, o21, o22, o23 = olaylar
    assert o20.yon == "long" and not o20.g1_sr_koridor and o20.g2_ms_bos and o20.g3_frm_sikisma
    assert o21.yon == "long" and o21.g1_sr_koridor and not o21.g2_ms_bos and o21.g3_frm_sikisma
    assert o22.yon == "long" and o22.g1_sr_koridor and o22.g2_ms_bos and not o22.g3_frm_sikisma
    assert o23.yon == "short" and o23.tum_kapilar_ok
    assert all(o.sinyal_sinifi == "IKINCIL" for o in olaylar)


def test_retest_ve_gecikmis_teyitli_dusurulur_kirilim_adayi_birincil_kalir():
    barlar = [_bar(k) for k in range(20)]
    # bar 20: Formasyon A KIRILIM_ADAYI (Long), Stabil R hemen tepede (100.5) -> G1 bloklamamalı, cift_kirilim_stabil=True!
    barlar.append(
        _bar(
            20,
            c=100.2,
            r_level=100.5,
            atr=2.0,
            ms_fresh_dir=1,
            ms_ext_state="STATE_BULLISH",
            frm_aktif=True,
            frm_stable_id="frm_A",
            frm_state=ST_BREAK_CANDIDATE,
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
        )
    )
    # bar 21: Formasyon A RETEST_BASARILI -> IKINCIL (C_IKINCIL)
    barlar.append(
        _bar(
            21,
            c=99.5,
            atr=2.0,
            ms_fresh_dir=1,
            frm_aktif=True,
            frm_stable_id="frm_A",
            frm_state=ST_RETEST_OK,
            frm_prev_state="RETEST_EDILIYOR",
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
        )
    )
    # bar 22: Formasyon B gecikmiş KIRILIM_TEYITLI (ilk kırılım barı) -> IKINCIL (C_IKINCIL)
    barlar.append(
        _bar(
            22,
            c=101.0,
            atr=2.0,
            ms_fresh_dir=1,
            frm_aktif=True,
            frm_stable_id="frm_B",
            frm_state=ST_BREAK_CONFIRMED,
            frm_prev_state="KIRILIM_DENEMESI",
            frm_break_dir=1,
            frm_broken_boundary=100.0,
            frm_upper_now=100.0,
            frm_lower_now=97.0,
        )
    )

    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olaylar = aday_olaylari_cikar(seri, min_warmup_bar=20)
    assert len(olaylar) == 3

    o_aday, o_retest, o_teyit = olaylar
    assert o_aday.alt_kol == "B_kirilim"
    assert o_aday.sinyal_sinifi == "BIRINCIL"
    assert o_aday.kalite_katmani == "A_ARTI"
    assert o_aday.g1_sr_koridor is True
    assert o_aday.cift_kirilim_stabil is True

    assert o_retest.alt_kol == "B_retest"
    assert o_retest.sinyal_sinifi == "IKINCIL"
    assert o_retest.kalite_katmani == "C_IKINCIL"

    assert o_teyit.alt_kol == "B_kirilim" and o_teyit.tetik_adi == ST_BREAK_CONFIRMED
    assert o_teyit.sinyal_sinifi == "IKINCIL"
    assert o_teyit.kalite_katmani == "C_IKINCIL"


def test_vp_ve_blok_kapilari_replay_kurallarina_uyar():
    barlar = [_bar(k) for k in range(20)]
    # bar 20: VP usable=False (endeks veya 09:30 sıfır hacim) -> g4_vp_kalite fail-open True
    barlar.append(
        _bar(
            20,
            c=100.0,
            atr=2.0,
            ms_ext_state="STATE_BULLISH",
            frm_aktif=True,
            frm_stable_id="f1",
            frm_state=ST_BREAK_CANDIDATE,
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
            vp_data_ready=True,
            vp_volume_usable=False,
            vp_rvol=0.1,
        )
    )
    # bar 21: VP usable=True & rvol=0.50 (< 0.75) -> g4_vp_kalite False
    barlar.append(
        _bar(
            21,
            c=100.0,
            atr=2.0,
            ms_ext_state="STATE_BULLISH",
            frm_aktif=True,
            frm_stable_id="f2",
            frm_state=ST_BREAK_CANDIDATE,
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
            vp_data_ready=True,
            vp_volume_usable=True,
            vp_rvol=0.50,
            vp_directional_efficiency=0.70,
            vp_pressure_5=0.20,
        )
    )
    # bar 22: Önde taze (tc=0), uzun (height_atr=1.2) karşı OB <0.75 ATR içinde -> g5_blok_temiz False
    engel_band = BlokBand(family="OB", direction="bearish", lower=101.0, upper=103.4, available_index=15, height_atr=1.2, touch_count_asof=0)
    barlar.append(
        _bar(
            22,
            c=100.0,
            atr=2.0,
            ms_ext_state="STATE_BULLISH",
            frm_aktif=True,
            frm_stable_id="f3",
            frm_state=ST_BREAK_CANDIDATE,
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
            vp_data_ready=True,
            vp_volume_usable=True,
            vp_rvol=1.40,
            vp_directional_efficiency=0.65,
            vp_pressure_5=0.25,
            blok_bear=(engel_band,),
        )
    )
    # bar 23: Küçük (height=0.3 ATR) veya dokunulmuş (tc=1) karşı OB -> engel DEĞİL (S03/S07), A_CEKIRDEK!
    gurultu_band = BlokBand(family="OB", direction="bearish", lower=101.0, upper=101.6, available_index=15, height_atr=0.3, touch_count_asof=0)
    barlar.append(
        _bar(
            23,
            c=100.0,
            atr=2.0,
            ms_ext_state="STATE_BULLISH",
            frm_aktif=True,
            frm_stable_id="f4",
            frm_state=ST_BREAK_CANDIDATE,
            frm_break_dir=1,
            frm_broken_boundary=99.0,
            frm_upper_now=99.0,
            frm_lower_now=96.0,
            vp_data_ready=True,
            vp_volume_usable=True,
            vp_rvol=1.40,
            vp_directional_efficiency=0.65,
            vp_pressure_5=0.25,
            blok_bear=(gurultu_band,),
        )
    )

    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    o_endeks, o_dusuk_hacim, o_blok_engelli, o_temiz = aday_olaylari_cikar(seri, min_warmup_bar=20)
    assert o_endeks.g4_vp_kalite is True
    assert o_dusuk_hacim.g4_vp_kalite is False
    assert o_blok_engelli.g5_blok_temiz is False and o_blok_engelli.opp_blok_engeli is True
    assert o_temiz.g4_vp_kalite is True and o_temiz.g5_blok_temiz is True
    assert o_temiz.kalite_katmani == "A_CEKIRDEK"


def test_muhafazakar_intrabar_stop_esitlikte_hedefe_baskin_gelir():
    barlar = [_bar(k) for k in range(21)]
    barlar[20] = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    barlar.append(_bar(21, o=100.0, h=104.0, l=97.5, c=101.0))
    barlar.extend(_bar(k) for k in range(22, 32))

    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan = plan_karti_olustur(olay, barlar[20], mod="mod0", tampon_atr=0.50)
    assert plan.stop == pytest.approx(98.0)

    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)
    assert sonuc.neden_15_intra_iptal == "STOP"
    assert sonuc.pnl_15_intra_iptal_atr == pytest.approx(-1.0)
    assert sonuc.neden_15_close_iptal == "ZAMAN_STOPU"


def test_gap_acilis_stopu_daha_kotu_fiyattan_kesilir():
    barlar = [_bar(k) for k in range(21)]
    barlar[20] = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    barlar.append(_bar(21, o=96.0, h=97.0, l=95.5, c=96.5))
    barlar.extend(_bar(k) for k in range(22, 32))
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan = plan_karti_olustur(olay, barlar[20], mod="mod0", tampon_atr=0.50)
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)
    assert sonuc.neden_15_intra_iptal == "STOP_GAP"
    assert sonuc.pnl_15_intra_iptal_atr == pytest.approx(-2.0)


def test_nedensel_1_3_bar_ters_bos_tez_iptali_ve_4_bar_siniri():
    barlar = [_bar(k) for k in range(35)]
    barlar[20] = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    barlar[22] = _bar(22, o=100.0, h=100.2, l=99.0, c=99.2, ms_bos_down_now=True)
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan = plan_karti_olustur(olay, barlar[20], mod="mod0", tampon_atr=0.50)
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)
    assert sonuc.neden_15_intra_iptal == "TEZ_IPTAL_BOS"
    assert sonuc.pnl_15_intra_iptal_atr == pytest.approx(-0.4)
    assert sonuc.neden_15_intra_ham == "ZAMAN_STOPU"

    barlar2 = [_bar(k) for k in range(35)]
    barlar2[20] = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    barlar2[24] = _bar(24, o=100.0, h=100.2, l=99.0, c=99.2, ms_bos_down_now=True)
    seri2 = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar2))
    sonuc2 = yarisi_yurut(seri2, olay, plan, ufuk_bar=10)
    assert sonuc2.neden_15_intra_iptal == "ZAMAN_STOPU"


def test_mod2_dolmayan_dolum_bari_ve_min_risk_korumasi():
    # 1) Geçerli (>=0.50 ATR height, >=0.35 ATR risk) FVG limiti 3 bar dolmaz -> LIMIT_DOLMADI
    band = BlokBand(family="FVG", direction="bullish", lower=98.2, upper=99.5, available_index=18, height_atr=0.65, touch_count_asof=0)
    barlar = [_bar(k, l=99.8) for k in range(35)]
    barlar[20] = _bar(
        20,
        c=100.0,
        s_level=99.0,
        atr=2.0,
        s_reclaim_kind="intrabar_sweep_reclaim",
        blok_bull=(band,),
    )
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan2 = plan_karti_olustur(olay, barlar[20], mod="mod2", tampon_atr=0.50)
    assert plan2.blok_kullanildi and plan2.limit_fiyat == pytest.approx(99.5)
    assert plan2.risk_atr >= 0.35

    sonuc_bos = yarisi_yurut(seri, olay, plan2, ufuk_bar=10)
    assert not sonuc_bos.dolduruldu
    assert sonuc_bos.neden_15_intra_iptal == "LIMIT_DOLMADI"

    # 2) Dolum barında hem limit hem stop değerse kar yazılmaz -> STOP_DOLUM_BARI
    barlar[21] = _bar(21, o=100.0, h=104.0, l=97.0, c=103.5)
    seri_hit = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    sonuc_hit = yarisi_yurut(seri_hit, olay, plan2, ufuk_bar=10)
    assert sonuc_hit.dolduruldu
    assert sonuc_hit.neden_15_intra_iptal == "STOP_DOLUM_BARI"
    assert sonuc_hit.pnl_15_intra_iptal_atr < 0

    # 3) Stop üstüne çok yakın (<0.35 ATR risk) mikro bant (DMSAS artifaktı) Mod 2'de seçilmez!
    mikro_band = BlokBand(family="OB", direction="bullish", lower=97.0, upper=98.1, available_index=18, height_atr=0.55, touch_count_asof=0)
    bar_mikro = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim", blok_bull=(mikro_band,))
    plan_mikro = plan_karti_olustur(olay, bar_mikro, mod="mod2", tampon_atr=0.50)
    assert not plan_mikro.blok_kullanildi and plan_mikro.limit_fiyat is None


def test_nedensel_3_stop_freni_yalniz_kapanmis_stoplari_sayar():
    barlar = [_bar(k) for k in range(60)]
    for idx in (20, 22, 24, 26, 27, 40):
        barlar[idx] = _bar(idx, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    for s_idx in (21, 23, 25):
        barlar[s_idx] = _bar(s_idx, o=99.5, h=100.0, l=97.0, c=97.5)
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olaylar = list(aday_olaylari_cikar(seri, min_warmup_bar=20))
    sonuclar = {}
    for o in olaylar:
        p = plan_karti_olustur(o, barlar[o.bar_index], mod="mod0", tampon_atr=0.50)
        sonuclar[o.olay_id] = yarisi_yurut(seri, o, p, ufuk_bar=10)

    fren = fren_etiketle(olaylar, sonuclar)
    by_idx = {o.bar_index: fren[o.olay_id] for o in olaylar}
    assert by_idx[20] is False
    assert by_idx[22] is False
    assert by_idx[24] is False
    assert by_idx[26] is True
    assert by_idx[27] is True
    assert by_idx[40] is False


def test_kume_bootstrap_ve_domain_ablasyonu_deterministik():
    df = pd.DataFrame({
        "sembol": ["A", "A", "B", "B", "C", "C", "D", "D"],
        "donem": ["kesif", "dogrulama"] * 4,
        "sinyal_sinifi": ["BIRINCIL"] * 6 + ["IKINCIL"] * 2,
        "kalite_katmani": ["A_ARTI", "A_CEKIRDEK", "B_ADAY", "A_ARTI", "A_CEKIRDEK", "B_ADAY", "C_IKINCIL", "C_IKINCIL"],
        "alt_kol": ["B_kirilim"] * 6 + ["B_retest", "B_retest"],
        "tetik_adi": ["KIRILIM_ADAYI"] * 6 + ["RETEST_BASARILI", "RETEST_BASARILI"],
        "kohort": ["B_formasyon"] * 8,
        "g2_ms_bos": [True] * 8,
        "g4_vp_kalite": [True] * 8,
        "g5_blok_temiz": [True] * 8,
        "ms_yapi_uyumlu": [True, True, False, True, True, False, False, False],
        "vp_emilim_onayi": [False] * 8,
        "pnl_15_intra_iptal_r": [1.0, 0.5, 0.8, 0.4, -0.2, 1.2, 0.3, 0.7],
        "pnl_20_intra_iptal_r": [1.2, 0.6, 0.9, 0.5, -0.3, 1.4, -0.5, -0.4],
    })
    r1 = kume_bootstrap_ozet(df, "pnl_15_intra_iptal_r", B=200, seed=42)
    r2 = kume_bootstrap_ozet(df, "pnl_15_intra_iptal_r", B=200, seed=42)
    assert r1 == r2
    assert r1["sembol_n"] == 4
    assert r1["n"] == 8
    assert r1["ci95_alt"] <= r1["ort"] <= r1["ci95_ust"]

    merdiven = domain_ablasyonu_uret(df, deger_col="pnl_20_intra_iptal_r", B=100)
    retest_tumu = next(x for x in merdiven if x["donem"] == "tumu" and x["katman"] == "Ikincil_Retest")
    assert retest_tumu["n"] == 2 and retest_tumu["ort"] == pytest.approx(-0.45)
