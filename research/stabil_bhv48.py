"""48 Behavioral Questions (`STB-BHV-A01..H06`) evaluator for Stabil replay.

Strictly decoupled from engine execution: consumes causal 4H checkpoint frames
produced by `research.stabil_replay` and emits structured per-question answers
following `TANIM -> VERI -> KARSILASTIRMA -> TABLO -> KARSI ORNEK -> SINIR -> SONUC`.
Never applies the legacy S01-S32 decision gate or creates live trading rules.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from research.stabil_replay import (
    HORIZONS_4H,
    build_xu100_regime_lookup,
    replay_single_symbol,
    select_bist_equity_universe,
)


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    qid: str
    section: str
    title: str
    definition: str
    limitation_note: str
    uses_candidate_regime: bool
    builder: Callable[[pd.DataFrame], tuple[pd.DataFrame, int]]


def _enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add strictly causal backward-looking cohort columns once for all 48 questions."""
    work = df.copy()
    # Past 4 x 4H (~1 trading day) and 12 x 4H (~3 trading days) backward returns in ATR
    grp = work.groupby("symbol", sort=False)
    prev_c4 = grp["h4_close"].shift(4)
    prev_c12 = grp["h4_close"].shift(12)
    prev_s4 = grp["support_level"].shift(4)
    prev_valid1 = grp["validity"].shift(1)
    prev_reg1 = grp["candidate_regime"].shift(1)
    prev_sup1 = grp["support_level"].shift(1)

    atr = work["daily_atr"].replace(0.0, np.nan)
    work["past4_ret_atr"] = (work["h4_close"] - prev_c4) / atr
    work["past12_ret_atr"] = (work["h4_close"] - prev_c12) / atr
    work["past4_sup_chg_atr"] = (work["support_level"] - prev_s4) / atr
    work["prev_validity"] = prev_valid1.fillna("NO_SUPPORT")
    work["prev_regime"] = prev_reg1.fillna("UNAVAILABLE")
    work["prev_support"] = prev_sup1
    work["support_rebased_now"] = (
        work["support_ready"]
        & prev_sup1.notna()
        & ((work["support_level"] - prev_sup1).abs() > 0.01)
    )
    work["rebased_higher_now"] = work["support_rebased_now"] & (work["support_level"] > prev_sup1 + 0.01)
    work["rebased_lower_now"] = work["support_rebased_now"] & (work["support_level"] < prev_sup1 - 0.01)
    work["above_4h"] = work["support_ready"] & (work["h4_close"] >= work["support_level"])
    work["below_4h"] = work["support_ready"] & (work["h4_close"] < work["support_level"])
    work["touch_4h"] = (
        work["support_ready"]
        & (work["h4_low"] <= work["support_level"] + 0.05 * atr.fillna(0.0))
        & (work["h4_close"] >= work["support_level"])
    )
    prev_above1 = grp["above_4h"].shift(1, fill_value=False).astype(bool)
    work["just_moved_above_4h"] = work["above_4h"] & (~prev_above1) & prev_sup1.notna()
    work["just_broke_below_4h"] = work["below_4h"] & prev_above1 & prev_sup1.notna()
    return work


def _bucket_stats(sub: pd.DataFrame, bucket_name: str, unknown_excluded: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n_total = len(sub)
    sym_counts = sub["symbol"].value_counts() if n_total else pd.Series(dtype=int)
    sym_n = int(len(sym_counts))
    top1_share = float(sym_counts.iloc[0] / n_total) if n_total and sym_n >= 1 else 0.0
    top3_share = float(sym_counts.iloc[:3].sum() / n_total) if n_total and sym_n >= 1 else 0.0

    # Race distribution (24 x 4H window)
    race_vc = sub["next_race_24"].value_counts(normalize=True) if n_total and "next_race_24" in sub else pd.Series(dtype=float)
    sup_up_rate = float(race_vc.get("SUPPORT_UP_FIRST", 0.0))
    ret_dn_rate = float(race_vc.get("PRICE_RETURN_FIRST", 0.0))
    reclaim_rate = float(race_vc.get("PRICE_RECLAIM_FIRST", 0.0))
    sup_dn_rate = float(race_vc.get("SUPPORT_DOWN_FIRST", 0.0))

    # Split time in half for temporal stability check
    mid_ts = None
    if n_total >= 4:
        sorted_times = sub["cp_time"].sort_values()
        mid_ts = sorted_times.iloc[len(sorted_times) // 2]

    for h in HORIZONS_4H:
        if n_total == 0:
            rows.append(
                {
                    "bucket": bucket_name,
                    "horizon_4h": h,
                    "n_total": 0,
                    "n_full": 0,
                    "n_censored": 0,
                    "n_atr_valid": 0,
                    "n_unknown_excluded": unknown_excluded,
                    "symbols": 0,
                    "top1_sym_share": 0.0,
                    "top3_sym_share": 0.0,
                    "mean_ret_atr": math.nan,
                    "median_ret_atr": math.nan,
                    "eq_sym_mean_ret_atr": math.nan,
                    "mean_mfe_atr": math.nan,
                    "median_mfe_atr": math.nan,
                    "mean_mae_atr": math.nan,
                    "median_mae_atr": math.nan,
                    "pos_close_rate": math.nan,
                    "up_1atr_first_rate": math.nan,
                    "down_1atr_first_rate": math.nan,
                    "ambig_1atr_rate": math.nan,
                    "early_half_med_ret": math.nan,
                    "late_half_med_ret": math.nan,
                    "race_sup_up_24": sup_up_rate,
                    "race_price_ret_24": ret_dn_rate,
                    "race_reclaim_24": reclaim_rate,
                    "race_sup_dn_24": sup_dn_rate,
                }
            )
            continue

        cens = sub[f"censored_{h}"].astype(bool)
        n_cens = int(cens.sum())
        full = sub[~cens]
        n_full = len(full)
        valid = full[full[f"ret_atr_{h}"].notna()]
        n_valid = len(valid)

        if n_valid == 0:
            rows.append(
                {
                    "bucket": bucket_name,
                    "horizon_4h": h,
                    "n_total": n_total,
                    "n_full": n_full,
                    "n_censored": n_cens,
                    "n_atr_valid": 0,
                    "n_unknown_excluded": unknown_excluded,
                    "symbols": sym_n,
                    "top1_sym_share": round(top1_share, 4),
                    "top3_sym_share": round(top3_share, 4),
                    "mean_ret_atr": math.nan,
                    "median_ret_atr": math.nan,
                    "eq_sym_mean_ret_atr": math.nan,
                    "mean_mfe_atr": math.nan,
                    "median_mfe_atr": math.nan,
                    "mean_mae_atr": math.nan,
                    "median_mae_atr": math.nan,
                    "pos_close_rate": math.nan,
                    "up_1atr_first_rate": math.nan,
                    "down_1atr_first_rate": math.nan,
                    "ambig_1atr_rate": math.nan,
                    "early_half_med_ret": math.nan,
                    "late_half_med_ret": math.nan,
                    "race_sup_up_24": round(sup_up_rate, 4),
                    "race_price_ret_24": round(ret_dn_rate, 4),
                    "race_reclaim_24": round(reclaim_rate, 4),
                    "race_sup_dn_24": round(sup_dn_rate, 4),
                }
            )
            continue

        ret = valid[f"ret_atr_{h}"].to_numpy(dtype=float)
        mfe = valid[f"mfe_atr_{h}"].to_numpy(dtype=float)
        mae = valid[f"mae_atr_{h}"].to_numpy(dtype=float)
        f1 = valid[f"first_1atr_{h}"]
        eq_sym = float(valid.groupby("symbol")[f"ret_atr_{h}"].mean().mean())

        early_med = math.nan
        late_med = math.nan
        if mid_ts is not None:
            e_sub = valid[valid["cp_time"] <= mid_ts][f"ret_atr_{h}"]
            l_sub = valid[valid["cp_time"] > mid_ts][f"ret_atr_{h}"]
            if len(e_sub) >= 2:
                early_med = float(e_sub.median())
            if len(l_sub) >= 2:
                late_med = float(l_sub.median())

        rows.append(
            {
                "bucket": bucket_name,
                "horizon_4h": h,
                "n_total": n_total,
                "n_full": n_full,
                "n_censored": n_cens,
                "n_atr_valid": n_valid,
                "n_unknown_excluded": unknown_excluded,
                "symbols": sym_n,
                "top1_sym_share": round(top1_share, 4),
                "top3_sym_share": round(top3_share, 4),
                "mean_ret_atr": round(float(np.mean(ret)), 4),
                "median_ret_atr": round(float(np.median(ret)), 4),
                "eq_sym_mean_ret_atr": round(eq_sym, 4),
                "mean_mfe_atr": round(float(np.mean(mfe)), 4),
                "median_mfe_atr": round(float(np.median(mfe)), 4),
                "mean_mae_atr": round(float(np.mean(mae)), 4),
                "median_mae_atr": round(float(np.median(mae)), 4),
                "pos_close_rate": round(float(np.mean(ret > 0.0)), 4),
                "up_1atr_first_rate": round(float((f1 == "UP_FIRST").mean()), 4),
                "down_1atr_first_rate": round(float((f1 == "DOWN_FIRST").mean()), 4),
                "ambig_1atr_rate": round(float((f1 == "AMBIGUOUS_SAME_BAR").mean()), 4),
                "early_half_med_ret": round(early_med, 4) if math.isfinite(early_med) else math.nan,
                "late_half_med_ret": round(late_med, 4) if math.isfinite(late_med) else math.nan,
                "race_sup_up_24": round(sup_up_rate, 4),
                "race_price_ret_24": round(ret_dn_rate, 4),
                "race_reclaim_24": round(reclaim_rate, 4),
                "race_sup_dn_24": round(sup_dn_rate, 4),
            }
        )
    return rows


def _extract_counterexamples(cohort: pd.DataFrame, max_items: int = 3) -> list[str]:
    """Select concrete counterexamples against each bucket's median 8x4H sign."""
    if cohort.empty or "ret_atr_8" not in cohort:
        return ["Tam 8x4H ufuklu karşı örnek bulunamadı."]
    valid = cohort[(~cohort["censored_8"].astype(bool)) & cohort["ret_atr_8"].notna()].copy()
    if valid.empty:
        return ["Tam 8x4H ufuklu karşı örnek bulunamadı."]
    examples: list[str] = []
    for b_name, grp in valid.groupby("_bucket", sort=False):
        med = float(grp["ret_atr_8"].median())
        if med >= 0:
            worst = grp.sort_values("ret_atr_8", ascending=True).head(1)
        else:
            worst = grp.sort_values("ret_atr_8", ascending=False).head(1)
        for _, r in worst.iterrows():
            ts_txt = str(r["cp_time"])[:16]
            examples.append(
                f"{r['symbol']} ({ts_txt}, kova={b_name}): 8x4H korunan={r['ret_atr_8']:+.2f} ATR "
                f"(MFE={r['mfe_atr_8']:.2f} / MAE={r['mae_atr_8']:.2f} ATR)"
            )
            if len(examples) >= max_items:
                return examples
    return examples or ["Belirgin karşı örnek yok."]


def _build_question_specs() -> list[QuestionSpec]:
    specs: list[QuestionSpec] = []

    def add(
        qid: str,
        sec: str,
        title: str,
        defn: str,
        limit_note: str,
        uses_cand: bool,
        fn: Callable[[pd.DataFrame], tuple[pd.DataFrame, int]],
    ) -> None:
        specs.append(QuestionSpec(qid, sec, title, defn, limit_note, uses_cand, fn))

    # --- SECTION A: Uzaklaşma ve takip ---
    def a01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["above_4h"] & df["dist_atr_4h"].notna() & (df["dist_atr_4h"] >= 1.0)].copy()
        c["_bucket"] = np.where(
            c["dist_atr_4h"] < 2.0,
            "1.0-2.0_ATR_uzak",
            np.where(c["dist_atr_4h"] < 3.5, "2.0-3.5_ATR_uzak", "3.5+_ATR_uzak"),
        )
        return c, 0

    add(
        "STB-BHV-A01", "A",
        "Fiyat uzaklaşınca önce destek mi yukarı güncelleniyor, fiyat mı eski desteğe dönüyor?",
        "Destek üstünde >=1.0 günlük ATR uzaklaşmış 4H kapanışlarında 24x4H içinde ilk yarış sonucu ve ileri getiriler.",
        "Aynı checkpoint'te çakışan olaylar ve 24x4H sağdan sansür ayrı tutulur; örtüşen checkpoint'ler bağımsız işlem değildir.",
        False, a01,
    )

    def a02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["above_4h"] & df["dist_atr_4h"].between(1.5, 3.0) & df["past12_ret_atr"].notna()].copy()
        c["_bucket"] = np.where(c["past12_ret_atr"] >= 1.2, "hizli_uzaklasma", "yavas_uzaklasma")
        return c, 0

    add(
        "STB-BHV-A02", "A",
        "Aynı uzaklığa hızlı veya yavaş çıkmak bu iki yolun oranını değiştiriyor mu?",
        "1.5-3.0 ATR benzer destek uzaklığında son 12x4H hareketi >=1.2 ATR (hızlı) ile <1.2 ATR (yavaş) çıkış karşılaştırması.",
        "Mesafe bandı sabitlenmiştir; yine de rejim ve sembol yoğunlaşması kontrol edilmelidir.",
        False, a02,
    )

    def a03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["rebased_higher_now"] & df["above_4h"]].copy()
        unk = int((c["prev_rise_gain_atr"].isna()).sum())
        c = c[c["prev_rise_gain_atr"].notna()]
        c["_bucket"] = np.where(c["prev_rise_gain_atr"] >= 2.0, "buyuk_geride_kalan_artis", "ilimli_geride_kalan_artis")
        return c, unk

    add(
        "STB-BHV-A03", "A",
        "Destek takibe başladığında yükselişin ne kadarı geride, ne kadarı ileride?",
        "Desteğin yukarı taşındığı (REBASED_HIGHER) ilk bilinen 4H kapanışında geride kalan ATR kazancı ile ileri ufuk getirisi.",
        "Pivot teyidi 4 günlük sağ bar beklediği için giriş anı teyit kapanışıdır, pivot dibine geri taşınmaz.",
        False, a03,
    )

    def a04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & (df["dist_atr_4h"] >= 1.0)]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"] & (base["bars_since_support"] >= 0)].copy()
        c["_bucket"] = np.where(
            c["bars_since_support"] <= 5, "bekleme_0_5g",
            np.where(c["bars_since_support"] <= 15, "bekleme_6_15g", "bekleme_16g_ustu"),
        )
        return c, unk

    add(
        "STB-BHV-A04", "A",
        "Destek takip etmeden bekleme uzadıkça fiyatın geri dönüş riski artıyor mu?",
        "Yalnız o ana kadar bilinen destek yaşına (0-5g, 6-15g, 16g+) göre yukarıda bekleyen fiyatın MAE ve geri dönüş oranı.",
        "Arşiv başındaki ilk yaşı bilinmeyen epizotlar UNKNOWN olarak dışlanmıştır; gelecekte güncellenmeyecekler baştan seçilmez.",
        False, a04,
    )

    def a05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[
            df["above_4h"]
            & df["price_delta_4h_atr"].notna()
            & ((df["price_delta_4h_atr"] - df["support_delta_4h_atr"]) < -0.05)
        ].copy()
        c["_bucket"] = np.where(
            c["support_delta_4h_atr"] > 0.05,
            "destek_yukari_yakaliyor",
            "fiyat_asagi_cekiliyor",
        )
        return c, 0

    add(
        "STB-BHV-A05", "A",
        "Mesafe küçülürken fiyat mı geri geliyor, destek mi fiyatı yakalıyor?",
        "Fiyat-destek mesafesinin daraldığı 4H kapanışlarında daralmanın kaynağını destek yükselişi vs fiyat geri çekilmesi olarak ayırır.",
        "Aynı CONTRACTING etiketi altında iki mekanizma farklı frekansta görülür; örnek sayıları dengesiz olabilir.",
        False, a05,
    )

    def a06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["rebased_higher_now"] & df["above_4h"] & df["dist_atr_4h"].notna()].copy()
        c["_bucket"] = np.where(c["dist_atr_4h"] <= 1.2, "destek_fiyati_yakaladi", "destek_uzakta_kaldi")
        return c, 0

    add(
        "STB-BHV-A06", "A",
        "Destek fiyatı yakalayınca devam mı geliyor, hareket tükenmiş mi oluyor?",
        "Yukarı destek güncellemesinde fiyatın yeni desteğe yakın (<=1.2 ATR) yakalandığı durumlar ile hala uzakta olduğu durumların MFE ve kapanış korunması.",
        "Yol içi MFE ile kapanışta korunan getiri ayrı okunmalıdır.",
        False, a06,
    )

    # --- SECTION B: Yükseliş sonrası yataylaşma (Candidate Regime Dependent) ---
    def b01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"]]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"] & c_in(base["candidate_regime"], ["STEPPING_UP", "NEWLY_FLATTENED_AFTER_RISE", "LONG_HORIZONTAL"])].copy()
        c["_bucket"] = c["candidate_regime"]
        return c, unk

    def c_in(s: pd.Series, vals: list[str]) -> pd.Series:
        return s.isin(vals)

    add(
        "STB-BHV-B01", "B",
        "Yukarı takip sonrası yataylaşmanın ardından devam, bekleme ve kırılma nasıl dağılıyor?",
        "Aday eşlemeye göre yukarı basamak (STEPPING_UP), yükseliş sonrası yeni yataylaşma ve uzun yatay kalış kova karşılaştırması.",
        "DİKKAT: Aday dikey/yatay eşlemesi gerçek grafik örneği üzerinde kullanıcıyla teyit edilene kadar bu ölçüm aday/proxy niteliğindedir.",
        True, b01,
    )

    def b02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & (df["candidate_regime"] == "NEWLY_FLATTENED_AFTER_RISE")]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"]].copy()
        c["_bucket"] = np.where(c["prev_rise_bars"] >= 20, "uzun_yukselis_sonrasi_yeni_yatay", "kisa_yukselis_sonrasi_yeni_yatay")
        return c, unk

    add(
        "STB-BHV-B02", "B",
        "Yeni yataydan önce yükseliş uzun sürmüşse kırılma daha sık veya sert mi?",
        "Yeni yataylaşmış (aday eşleme: 9-23 günlük yaş) destekte önceki yükseliş süresinin >=20 gün vs <20 gün karşılaştırması.",
        "Aday yataylaşma eşlemesi kullanıcı grafik onayı beklemektedir; önceki yükseliş süresi yatay yaşından ayrı tutulmuştur.",
        True, b02,
    )

    def b03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & (df["candidate_regime"] == "NEWLY_FLATTENED_AFTER_RISE") & df["prev_rise_gain_atr"].notna()]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"] & (base["prev_rise_bars"] >= 12)].copy()
        c["_bucket"] = np.where(c["prev_rise_gain_atr"] >= 3.0, "yuksek_siddetli_onceki_artis", "ilimli_onceki_artis")
        return c, unk

    add(
        "STB-BHV-B03", "B",
        "Önceki yükselişin şiddeti ve hızı, süreden bağımsız ek bilgi taşıyor mu?",
        "Benzer önceki yükseliş süresinde (>=12 gün) yeni yataylaşan destekte ATR kazanç şiddeti >=3.0 vs <3.0 karşılaştırması.",
        "Aday yataylaşma eşlemesi kullanıcı grafik onayı beklemektedir.",
        True, b03,
    )

    def b04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & df["dist_atr_4h"].between(0.0, 2.5)]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"] & c_in(base["candidate_regime"], ["NEWLY_FLATTENED_AFTER_RISE", "LONG_HORIZONTAL"])].copy()
        c["_bucket"] = c["candidate_regime"]
        return c, unk

    add(
        "STB-BHV-B04", "B",
        "Uzun yatay seviyelerde bir sonraki ani aşağı kırılma gerçekten daha az mı?",
        "Benzer destek mesafesinde (0-2.5 ATR) yeni yataylaşmış seviye ile >=24 gün uzun yatay seviyenin aşağı MAE ve -1 ATR kırılma oranı.",
        "Sağ kalım etkisi ve aday yataylaşma eşlemesi birlikte dikkate alınmalıdır; kullanıcı grafik teyidi beklemektedir.",
        True, b04,
    )

    def b05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["just_broke_below_4h"]]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"] & c_in(base["prev_regime"], ["NEWLY_FLATTENED_AFTER_RISE", "LONG_HORIZONTAL", "STEPPING_UP"])].copy()
        c["_bucket"] = c["prev_regime"]
        return c, unk

    add(
        "STB-BHV-B05", "B",
        "Yeni yatayda kırılma sıklığı mı, kırılınca şiddet mi artıyor?",
        "4H kapanışın destek altına ilk indiği anda kırılan desteğin önceki aday rejimine göre koşullu hasar (MAE/korunan zarar).",
        "Koşulsuz sıklık B04'te, kırılma anındaki koşullu şiddet burada ayrı raporlanır; aday eşleme kullanıcı teyidi bekler.",
        True, b05,
    )

    def b06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & df["episode_known"] & (df["bars_since_support"].between(1, 12))]
        c = base[base["past12_ret_atr"].notna()].copy()
        c["_bucket"] = np.where(
            c["bars_since_support"] <= 4,
            "pivot_onay_penceresi_1_4g",
            np.where(c["past12_ret_atr"].abs() <= 0.8, "sakinlesen_fiyat_5_12g", "hareketli_fiyat_5_12g"),
        )
        return c, int((~df["episode_known"]).sum())

    add(
        "STB-BHV-B06", "B",
        "Yataylaşma fiyat sakinleşmesini mi, pivot teyit gecikmesini mi yansıtıyor?",
        "İlk 1-4 günlük doğal pivot teyit penceresi ile 5-12 günlük pencerede sakinleşen vs hareketli kalan fiyatın ayrımı.",
        "Native günlük pivot L=4 sağ bar onayına sahiptir; görsel yataylaşma tanımı kullanıcı grafik teyidiyle kesinleşecektir.",
        True, b06,
    )

    # --- SECTION C: Temas ve tepki dizileri ---
    def c01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & (df["progression"] == "REBASED_HIGHER")]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"]].copy()
        c["_bucket"] = np.where(c["touch_4h"] & (c["touch_seq"] <= 1), "ilk_temas_ani", "temassiz_devam")
        return c, unk

    add(
        "STB-BHV-C01", "C",
        "Yukarı takip sonrası ilk temas, temas olmadan devamdan nasıl farklı?",
        "Yukarı taşınmış destekte ilk temasın gerçekleştiği 4H kapanışları ile temassız üstte devam eden kapanışların ileri dağılımı.",
        "Temas yalnız gerçekleştiği anda çapalanır; gelecekte temas edecek olanlar önceden ayrılmaz.",
        False, c01,
    )

    def c02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["touch_4h"]]
        unk = int((base["touch_seq"] < 0).sum())
        c = base[base["touch_seq"] >= 1].copy()
        c["_bucket"] = np.where(c["touch_seq"] == 1, "birinci_temas", np.where(c["touch_seq"] == 2, "ikinci_temas", "uc_ve_uzeri_temas"))
        return c, unk

    add(
        "STB-BHV-C02", "C",
        "İlk ve sonraki bağımsız temaslar aynı tutunmayı mı üretiyor?",
        "Aralarında en az 0.35 ATR ayrılma şartıyla sayılan 1., 2. ve 3+ bağımsız destek temaslarının karşılaştırması.",
        "Arşiv başındaki ilk epizot temas sayıları UNKNOWN olarak dışlanmıştır.",
        False, c02,
    )

    def c03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["touch_4h"] & df["past4_ret_atr"].notna()].copy()
        c["_bucket"] = np.where(c["past4_ret_atr"] <= -1.0, "sert_duserek_temas", "yavas_yaklasarak_temas")
        return c, 0

    add(
        "STB-BHV-C03", "C",
        "Yavaş yaklaşmakla sert düşerek desteğe gelmek farklı mı?",
        "Desteğe temas anında son 4x4H düşüşü >=1.0 ATR (sert geliş) ile <1.0 ATR (sakin yaklaşma) olan temasların tutunma farkı.",
        "Sert geliş aynı zamanda yüksek kısa vadeli oynaklık taşıyabilir; MAE birlikte okunmalıdır.",
        False, c03,
    )

    def c04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["touch_4h"]]
        unk = int((base["failed_bounces"] < 0).sum())
        c = base[base["failed_bounces"] >= 0].copy()
        c["_bucket"] = np.where(c["failed_bounces"] == 0, "onceki_basarisiz_tepki_yok", "onceki_basarisiz_tepki_var")
        return c, unk

    add(
        "STB-BHV-C04", "C",
        "Temaslardan sonra uzaklaşamamak kırılma riskini biriktiriyor mu?",
        "Yalnız geçmişte tamamlanmış cılız tepkiler (<0.75 ATR) biriktikten sonraki yeni temaslar ile ilk temiz temasların karşılaştırması.",
        "Yalnız olay öncesinde tamamlanmış tepkiler sayılır.",
        False, c04,
    )

    def c05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["touch_4h"] & df["last_bounce_atr"].notna() & df["prev_bounce_atr"].notna()].copy()
        c["_bucket"] = np.where(c["last_bounce_atr"] < c["prev_bounce_atr"] * 0.85, "kuculen_tepkiler", "korunan_veya_buyuyen_tepkiler")
        return c, 0

    add(
        "STB-BHV-C05", "C",
        "Tepkilerin giderek küçülmesi, temas sayısından daha açıklayıcı mı?",
        "En az iki tamamlanmış tepki görmüş desteklerde son tepkinin bir öncekine göre %15+ küçüldüğü durumlar ile korunduğu durumlar.",
        "En az iki tamamlanmış tepki şartı örneklem hacmini doğal olarak daraltır.",
        False, c05,
    )

    def c06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["touch_4h"] & df["last_bounce_atr"].notna() & (df["last_bounce_atr"] >= 1.2) & (df["bars_since_support"] >= 0)].copy()
        c["_bucket"] = np.where(c["bars_since_support"] <= 10, "hizli_yeniden_test", "gec_yeniden_test")
        return c, 0

    add(
        "STB-BHV-C06", "C",
        "Güçlü ilk tepkiye rağmen hızlı yeniden test kazancı geri verdiriyor mu?",
        "Önceki tamamlanmış tepkisi >=1.2 ATR olan güçlü desteklerde erken (<=10g) vs geç (>10g) yeniden testlerin sonucu.",
        "Destek yaşı bilinen epizotlarla sınırlıdır.",
        False, c06,
    )

    # --- SECTION D: Kırılma boyutu ve biçimi ---
    def d01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["below_4h"] & df["breach_depth_max_atr"].notna()].copy()
        c["_bucket"] = np.where(
            c["breach_depth_max_atr"] <= 0.5, "kucuk_kirilma_0_0.5_ATR",
            np.where(c["breach_depth_max_atr"] <= 1.2, "orta_kirilma_0.5_1.2_ATR", "derin_kirilma_1.2+_ATR"),
        )
        return c, 0

    add(
        "STB-BHV-D01", "D",
        "Küçük ve derin aşağı kırılmalarda geri alım ihtimali farklı mı?",
        "Destek altındaki 4H kapanışlarında o ana kadar gözlenen azami ihlal derinliğine göre 24x4H geri alım oranı ve ileri getiri.",
        "Geri almayan ve sansürlü olaylar tabanda dahildir; yalnız başarılı geri alımlar seçilmemiştir.",
        False, d01,
    )

    def d02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["reclaimed_4h_now"] & df["reclaimed_prev_depth_atr"].notna()].copy()
        c["_bucket"] = np.where(
            c["reclaimed_prev_depth_atr"] <= 0.5, "kucuk_kirilmadan_geri_alim",
            np.where(c["reclaimed_prev_depth_atr"] <= 1.2, "orta_kirilmadan_geri_alim", "derin_kirilmadan_geri_alim"),
        )
        return c, 0

    add(
        "STB-BHV-D02", "D",
        "Geri alımdan sonra küçük ve derin kırılmaların kalan tepkisi farklı mı?",
        "Sabit desteğin 4H kapanışla geri alındığı ilk anda, geride bırakılan kırılma derinliğine göre geri alım SONRASI kalan hareket.",
        "Dipten desteğe kadar harcanan yol bu ölçüme katılmaz; yalnız geri alım kapanışından sonraki hareket ölçülür.",
        False, d02,
    )

    def d03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["below_4h"] & df["breach_depth_max_atr"].between(0.5, 1.8) & df["breach_drop_1bar_atr"].notna()].copy()
        c["_bucket"] = np.where(c["breach_drop_1bar_atr"] >= 0.6, "tek_mumda_sert_kirilma", "kademeli_suzulen_kirilma")
        return c, 0

    add(
        "STB-BHV-D03", "D",
        "Aynı derinliğe tek mumda ve yavaş düşerek gelmek farklı mı?",
        "Benzer ihlal derinliğinde (0.5-1.8 ATR) ilk kırılma mumunda >=0.6 ATR sert düşüşle inenler ile kademeli inenlerin karşılaştırması.",
        "Derinlik bandı sabit tutulmuştur.",
        False, d03,
    )

    def d04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["below_4h"]].copy()
        c["_bucket"] = np.where(c["breach_floor_seen"] | (c["h4_close"] < c["support_floor"]), "floor_alti_ihlal", "yalniz_ana_destek_alti")
        return c, 0

    add(
        "STB-BHV-D04", "D",
        "Ana seviye ile native tolerans sınırının kaybı geri dönüşü ayırıyor mu?",
        "Yalnız ana destek altında kalan (BREACHED) durumlar ile 0.35 ATR native floor altına da inenlerin geri alım ve getiri farkı.",
        "Floor grafikte çizilmez; burada yalnız native motorun iç durumu olarak test edilmektedir.",
        False, d04,
    )

    def d05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["just_broke_below_4h"]].copy()
        c["_bucket"] = np.where(c["breach_gap_open"], "bosluklu_gap_kirilma", "seans_ici_normal_kirilma")
        return c, 0

    add(
        "STB-BHV-D05", "D",
        "Gap ve seans içi kırılma benzer derinlikte farklı mı?",
        "Destek altına ilk geçişte >=0.15 ATR aşağı boşluklu açılışla kırılanlar ile seans içi normal kırılanların karşılaştırması.",
        "4H kova açılışı BIST seans/kova sınırına göredir.",
        False, d05,
    )

    def d06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["reclaimed_4h_now"] & df["reclaimed_prev_depth_atr"].notna() & df["daily_atr"].notna()].copy()
        spent = c["reclaimed_prev_depth_atr"] + c["dist_atr_4h"].clip(lower=0.0)
        c["_bucket"] = np.where(spent >= 1.2, "geri_alima_kadar_buyuk_yol_tuketildi", "geri_alima_yakin_donduruldu")
        return c, 0

    add(
        "STB-BHV-D06", "D",
        "Geri alıma kadar hareketin çoğu zaten tüketiliyor mu?",
        "İhlal dibinden geri alım kapanışına kadar harcanan yol >=1.2 ATR olanlar ile <1.2 ATR olanların geri alım sonrası kalan getirisi.",
        "Harcanan yol ile kalan ileri getiri birbirine karıştırılmadan ayrı tutulmuştur.",
        False, d06,
    )

    # --- SECTION E: Sabit desteğin geri alınması ---
    def e01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[
            df["support_ready"]
            & (~df["support_rebased_now"])
            & ((df["below_4h"] & (df["h4_high"] >= df["support_level"] - 0.1 * df["daily_atr"].fillna(0.0))) | df["reclaimed_4h_now"])
        ].copy()
        c["_bucket"] = np.where(c["reclaimed_4h_now"], "ustte_kapanis_basarili", "fitil_veya_yakin_red")
        return c, 0

    add(
        "STB-BHV-E01", "E",
        "Destek sabitken ilk deneme ne sıklıkla üstte kapanışa dönüşüyor?",
        "Sabit destek altındayken desteğe uzanan denemelerin üstte kapanışla sonuçlananları vs fitil/red kalanlarının ileri davranışı.",
        "Yalnız kapanmış 4H mum sonundaki durum bilinir.",
        False, e01,
    )

    def e02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["below_4h"] & (~df["support_rebased_now"])]
        unk = int((base["breach_attempts"] < 0).sum())
        c = base[base["breach_attempts"] >= 1].copy()
        c["_bucket"] = np.where(c["breach_attempts"] == 1, "ilk_basarisiz_deneme_sonrasi", "coklu_basarisiz_deneme_sonrasi")
        return c, unk

    add(
        "STB-BHV-E02", "E",
        "Başarısız denemeden sonra önce destek mi aşağı iner, fiyat mı yeniden dener?",
        "Sabit desteği geçemeyen denemelerden sonra 24x4H yarışında desteğin aşağı taşınması (SUPPORT_DOWN_FIRST) vs geri alım (PRICE_RECLAIM_FIRST).",
        "Başlangıcı arşiv öncesinde kalan kırılma epizotları UNKNOWN olarak dışlanmıştır.",
        False, e02,
    )

    def e03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["reclaimed_4h_now"]]
        unk = int((base["reclaimed_prev_attempts"] < 0).sum())
        c = base[base["reclaimed_prev_attempts"] >= 0].copy()
        c["_bucket"] = np.where(c["reclaimed_prev_attempts"] == 0, "ilk_denemede_geri_alim", "birden_cok_deneme_sonrasi_geri_alim")
        return c, unk

    add(
        "STB-BHV-E03", "E",
        "İlk ve birkaçıncı denemede geri alım aynı tepkiyi mi veriyor?",
        "Öncesinde başarısız fitil denemesi olmadan doğrudan geri alınan destekler ile başarısız denemeler sonrası geri alınanların karşılaştırması.",
        "Deneme sayısı yalnız başlangıcı bilinen kırılma epizotlarında ölçülür.",
        False, e03,
    )

    def e04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["reclaimed_4h_now"] & (df["reclaimed_prev_bars_4h"] >= 1)].copy()
        c["_bucket"] = np.where(
            c["reclaimed_prev_bars_4h"] <= 4, "kisa_altta_kalma_1_4_4h",
            np.where(c["reclaimed_prev_bars_4h"] <= 12, "orta_altta_kalma_5_12_4h", "uzun_altta_kalma_13+_4h"),
        )
        return c, 0

    add(
        "STB-BHV-E04", "E",
        "Altta kalma uzarsa sabit seviyenin geri alım tepkisi güçleniyor mu?",
        "Sabit desteğin geri alındığı anda altta geçirilen 4H bar sayısına (1-4, 5-12, 13+) göre geri alım sonrası tepki.",
        "Bu tablo geri alım koşuluna bağlıdır; altta kalma uzadıkça hiç geri alamama oranı D01/E02 ile birlikte okunmalıdır.",
        False, e04,
    )

    def e05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["reclaimed_4h_now"] & df["daily_atr"].notna()].copy()
        candle_gain = (c["h4_close"] - c["h4_open"]) / c["daily_atr"]
        c["_bucket"] = np.where(candle_gain >= 0.5, "guclu_geri_alim_mumu", "ilimli_geri_alim_mumu")
        return c, 0

    add(
        "STB-BHV-E05", "E",
        "Güçlü geri alım mumu bilgi mi taşıyor, kalan tepkiyi mi tüketiyor?",
        "Geri alım 4H mumunun gövdesi >=0.5 günlük ATR olan güçlü geri alımlar ile daha küçük gövdeli geri alımların SONRAKİ ufuk getirisi.",
        "Olay mumunun kendi kazancı ileri getiriye dahil değildir.",
        False, e05,
    )

    def e06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        reclaim_Direct = df[df["reclaimed_4h_now"]].copy()
        reclaim_Direct["_bucket"] = "dogrudan_geri_alim_kapanisi"
        retest_hold = df[df["touch_4h"] & (df["bars_above_support"].between(1, 5)) & (df["prior_lost_supports"] >= 0)].copy()
        # Filter to recent reclaim episodes via native reclaim_count or recent move above
        retest_hold = df[df["touch_4h"] & (df["bars_above_support"].between(1, 3))].copy()
        retest_hold["_bucket"] = "ustte_kapanis_sonrasi_yeniden_test_tutunmasi"
        c = pd.concat([reclaim_Direct, retest_hold], ignore_index=True)
        return c, 0

    add(
        "STB-BHV-E06", "E",
        "Geri alım sonrası yeniden testte tutunmayı beklemek faydalı mı?",
        "Doğrudan geri alım kapanışında ölçüm ile üstte 1-3 gün içinde gelen yeniden test tutunmasını beklemenin getiri/örneklem takası.",
        "Yeniden test beklemek hiç test vermeden giden hareketleri dışarıda bırakır (örneklem farkına dikkat).",
        False, e06,
    )

    # --- SECTION F: Aşağı takip ve yeniden yerleşme ---
    def f01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[
            df["support_ready"]
            & (df["past4_ret_atr"].notna() & (df["past4_ret_atr"] > 0.3))
            & c_in(df["candidate_regime"], ["STEPPING_DOWN", "HORIZONTAL_AFTER_DROP"])
        ].copy()
        c["_bucket"] = c["candidate_regime"]
        return c, 0

    add(
        "STB-BHV-F01", "F",
        "Hareketli/dikey bölümde yukarı deneme, yataylaşma sonrasından daha mı çok geri dönüyor?",
        "Aşağı basamak/iniş (STEPPING_DOWN) evresindeki yukarı tepki denemeleri ile ek gecikmesiz yataylaşma (HORIZONTAL_AFTER_DROP) sonrası denemeler.",
        "DİKKAT: Kullanıcının 'altı boş' hipotezinin aday eşlemesidir; gerçek grafik örneği üzerinde kullanıcı teyidi alınana kadar kesinleşmiş ölçüm sayılmaz.",
        True, f01,
    )

    def f02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["just_moved_above_4h"]].copy()
        c["_bucket"] = np.where(
            c["rebased_lower_now"] & (c["h4_close"] < c["prev_support"]),
            "destek_asagi_inerek_ustte_kaldi",
            np.where(
                (~c["rebased_lower_now"]) & (c["h4_close"] >= c["support_level"]),
                "fiyat_yukselerek_eski_destegi_asti",
                "hem_fiyat_hem_destek_degisti",
            ),
        )
        return c, 0

    add(
        "STB-BHV-F02", "F",
        "Üstte görünmeyi fiyat mı, desteğin aşağı taşınması mı oluşturuyor?",
        "Fiyatın destek üstüne geçtiği ilk 4H kapanışını: (1) eski desteği fiyatın aşması vs (2) desteğin fiyatın altına inmesi olarak ayırır.",
        "Bu ayrım tamamen native seviye değişiminden ve kapanış fiyatından nedensel olarak hesaplanır.",
        False, f02,
    )

    def f03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[
            df["support_ready"]
            & (df["prev_regime"] == "STEPPING_DOWN")
            & (df["candidate_regime"] != "STEPPING_DOWN")
        ].copy()
        # Also include first bar after downward rebase to compare above vs below at stabilization
        c2 = df[df["rebased_lower_now"]].copy()
        c2["_bucket"] = np.where(c2["above_4h"], "asagi_basamak_aninda_ustte", "asagi_basamak_aninda_altta")
        return c2, 0

    add(
        "STB-BHV-F03", "F",
        "Kesin yataylaşma anında üstte veya altta olmak sonucu değiştiriyor mu?",
        "Yeni aşağı basamak onaylandığı (4 sağ bar teyitli) anda 4H kapanışın yeni seviyenin üstünde vs altında olmasının ileri sonucu.",
        "Görsel yataylaşma teyidi kullanıcı grafik onayı beklemektedir; burada ek bar gecikmesi eklenmeden native onay anı ölçülmüştür.",
        True, f03,
    )

    def f04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["rebased_lower_now"] & df["prev_support_level"].notna() & df["daily_atr"].notna()].copy()
        step_sz = (c["prev_support_level"] - c["support_level"]) / c["daily_atr"]
        c["_bucket"] = np.where(step_sz >= 2.0, "tek_buyuk_asagi_basamak", "kucuk_kademeli_asagi_basamak")
        return c, 0

    add(
        "STB-BHV-F04", "F",
        "Tek büyük aşağı basamak ile birçok küçük basamaktan sonra toparlanma farklı mı?",
        "Desteğin aşağı taşındığı anda basamak boyutu >=2.0 ATR (tek büyük basamak) ile <2.0 ATR (küçük basamak) sonrası hareket.",
        "Toplam geçmiş düşüş büyüklüğü hisseden hisseye değişebilir.",
        False, f04,
    )

    def f05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["above_4h"] & (df["candidate_regime"] == "HORIZONTAL_AFTER_DROP")].copy()
        c["_bucket"] = np.where(c["bars_since_support"] == 1, "hemen_ilk_gun_giris", "yeni_dip_yapmadan_3_6g_sonra")
        c = c[(c["bars_since_support"] == 1) | (c["bars_since_support"].between(3, 6))]
        return c, 0

    add(
        "STB-BHV-F05", "F",
        "Yataylaşma sonrası yeni dip yapmamak ek bilgi katıyor mu?",
        "Aşağı basamak sonrası ilk tutunma gününde girmek ile 3-6 gün yeni dip yapmadan bekleyip girmek arasındaki getiri ve kaçan hareket farkı.",
        "Zorunlu teyit kuralı değildir; aday eşleme kullanıcı grafik teyidi beklemektedir.",
        True, f05,
    )

    def f06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["rebased_lower_now"]].copy()
        c["_bucket"] = np.where(c["prior_lost_supports"] >= 2, "ikinci_veya_sonraki_asagi_kayma", "ilk_asagi_yerlesme")
        return c, 0

    add(
        "STB-BHV-F06", "F",
        "Yerleşip tekrar aşağı hareketlenmek tek yerleşmeden farklı mı?",
        "İlk kez aşağı yerleşen destek ile öncesinde >=2 kez destek kaybedip tekrar aşağı kayan yapıların karşılaştırması.",
        "Yalnız olay anına kadar gözlenmiş geçmiş kayıplar kullanılır; aday rejim teyidi kullanıcı onayı bekler.",
        True, f06,
    )

    # --- SECTION G: Yol bağımlılığı ve karşı örnekler ---
    def g01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["above_4h"] & df["dist_atr_4h"].between(0.0, 1.0)].copy()
        c["_bucket"] = np.where(
            c["reclaimed_4h_now"],
            "asagidan_eski_destegi_geri_alarak",
            np.where(
                c["progression"] == "REBASED_LOWER",
                "asagi_basamakla_yerleserek",
                "yukaridan_cekilerek_veya_yukari_basamakla",
            ),
        )
        return c, 0

    add(
        "STB-BHV-G01", "G",
        "Aynı güncel konuma farklı yollardan gelmek fiyatı ayırıyor mu?",
        "Destek üstünde 0-1.0 ATR aynı güncel konumdayken bu konuma: geri alımla, aşağı basamakla veya yukarıdan gelişin karşılaştırması.",
        "Tek satırlık statik 'destek üstünde' etiketinin arkasındaki yol farkını sınar.",
        False, g01,
    )

    def g02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["above_4h"] & df["dist_atr_4h"].between(0.0, 1.2)]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"]].copy()
        c["_bucket"] = np.where(c["bars_since_support"] <= 3, "yeni_teyitli_destek_0_3g", "eski_yasli_destek_15g_ustu")
        c = c[(c["bars_since_support"] <= 3) | (c["bars_since_support"] >= 15)]
        return c, unk

    add(
        "STB-BHV-G02", "G",
        "Aynı fiyat civarındaki eski ve yeni teyit edilen destek farklı mı?",
        "Desteğe 0-1.2 ATR yakınlıkta yeni teyit edilmiş (0-3g) destek ile >=15 günlük eski desteğin ileri davranış farkı.",
        "Yaşı bilinmeyen ilk arşiv epizotları dışlanmıştır.",
        False, g02,
    )

    def g03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[
            df["above_4h"]
            & (df["progression"] == "REBASED_LOWER")
            & df["prev_support_level"].notna()
            & (df["h4_close"] < df["prev_support_level"])
        ].copy()
        mid = (c["support_level"] + c["prev_support_level"]) * 0.5
        c["_bucket"] = np.where(c["h4_close"] >= mid, "eski_ust_destege_yakin", "yeni_alt_destege_yakin")
        return c, 0

    add(
        "STB-BHV-G03", "G",
        "Eski ve yeni destek arasında gidip gelince hangi seviye açıklayıcı?",
        "Destek aşağı taşındıktan sonra yeni alt destek ile kırılan eski üst destek koridorunda kalan fiyatın alt/üst yarı davranışı.",
        "Her iki seviye de checkpoint anında nedensel olarak bilinmektedir.",
        False, g03,
    )

    def g04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        base = df[df["support_rebased_now"]]
        unk = int((~base["episode_known"]).sum())
        c = base[base["episode_known"]].copy()
        c["_bucket"] = np.where(c["prior_lost_supports"] == 0, "gecmiste_kayip_yok", "gecmiste_en_az_1_kayip_var")
        return c, unk

    add(
        "STB-BHV-G04", "G",
        "Önceki başarısız destekler yeni desteğin sonucunu etkiliyor mu?",
        "Yeni destek teyidinde arşiv içinde daha önce SUPPORT_LOST yaşamamış olanlar ile yaşamış olanların karşılaştırması.",
        "Arşiv öncesi dönem sıfır sayılmaz; ilk epizotlar dışlanmıştır.",
        False, g04,
    )

    def g05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["support_ready"] & df["daily_atr"].notna()].copy()
        rng_atr = (c["h4_high"] - c["h4_low"]) / c["daily_atr"]
        c["_bucket"] = np.where(rng_atr >= 0.65, "yuksek_iki_yonlu_savrulma", "normal_dar_mum_araligi")
        return c, 0

    add(
        "STB-BHV-G05", "G",
        "İki yönlü savrulma artınca yön avantajı kayboluyor mu?",
        "4H mum aralığı >=0.65 günlük ATR olan yüksek savrulmalı anlar ile daha sakin anlarda MFE/MAE simetrisi ve korunan kapanış.",
        "Yalnız yukarı MFE değil, MAE ve aynı mumda çift eşik belirsizliği birlikte okunur.",
        False, g05,
    )

    def g06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["reclaimed_4h_now"] | df["touch_4h"]].copy()
        c["_bucket"] = np.where(
            c["h4_bull_disp"] & c["h4_volume_pass"],
            "4h_alici_ve_hacim_kaniti_var",
            "4h_alici_kaniti_yok_veya_hacim_zayif",
        )
        return c, 0

    add(
        "STB-BHV-G06", "G",
        "Hacim/4H alıcı kanıtı hangi yolda ek bilgi veya gecikme getiriyor?",
        "Destek teması ve geri alım anlarında native H4 bull_displacement + hacim onayı olanlar ile olmayanların karşılaştırması.",
        "Eksik hacim olumlu teyit sayılmaz.",
        False, g06,
    )

    # --- SECTION H: Kontrol ve sağlamlık ---
    def h01(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["past12_ret_atr"].notna() & (df["past12_ret_atr"] <= -1.2)].copy()
        c["_bucket"] = np.where(
            c["touch_4h"] | c["reclaimed_4h_now"],
            "stabil_temas_veya_geri_alim_var",
            "benzer_dusus_stabil_olayi_yok",
        )
        return c, 0

    add(
        "STB-BHV-H01", "H",
        "Benzer fiyat düşüşlerinden sonra Stabil olayı olmadan da aynı tepki var mı?",
        "Son 12x4H içinde <=-1.2 ATR benzer düşüş yaşamış barlarda Stabil temas/geri alımı olanlar ile olmayan kontrol grubunun tepkisi.",
        "Basit düşüş eşleştirmesidir; tam saat/oynaklık ikiz eşleştirmesi ek incelik sağlayabilir.",
        False, h01,
    )

    def h02(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        s_touch = df[df["touch_4h"]].copy()
        s_touch["_bucket"] = "stabil_destek_temasi"
        c_roll = df[df["ctrl_near_roll20_low"] & (~df["touch_4h"])].copy()
        c_roll["_bucket"] = "basit_20g_dip_kontrol_temasi"
        c = pd.concat([s_touch, c_roll], ignore_index=True)
        return c, 0

    add(
        "STB-BHV-H02", "H",
        "Basit/gecikmeli referans seviyeleri aynı ayrımı yapıyor mu?",
        "Stabil günlük pivot destek teması ile önceden sabitlenmiş basit 20-günlük dip yakınlığının ileri getiri ve MAE karşılaştırması.",
        "Kontrol seviyesi sonuçlara bakılmadan 20-günlük dip olarak sabitlenmiştir.",
        False, h02,
    )

    def h03(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[(df["touch_4h"] | df["reclaimed_4h_now"]) & (df["xu100_regime"].isin(["XU100_ABOVE_EMA34", "XU100_BELOW_EMA34"]))].copy()
        c["_bucket"] = c["xu100_regime"]
        return c, 0

    add(
        "STB-BHV-H03", "H",
        "Aynı yol farklı piyasa rejimlerinde korunuyor mu?",
        "Destek teması ve geri alım olaylarının o anda nedensel olarak bilinen XU100 > EMA34 vs XU100 < EMA34 endeks rejimindeki davranışı.",
        "XU100 EMA34 genel piyasa yönü için sade ve nedensel bir vekildir.",
        False, h03,
    )

    def h04(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        c = df[df["support_ready"]].copy()
        c["_bucket"] = np.where(c["above_4h"], "destek_ustunde_tum_evren", "destek_altinda_tum_evren")
        return c, 0

    add(
        "STB-BHV-H04", "H",
        "Sonucu birkaç hisse/gün/aşırı hareket mi sürüklüyor?",
        "Tüm evrende ortalama vs medyan vs eşit-sembol ortalaması, ilk-yarı/ikinci-yarı medyanları ve top-1/top-3 sembol yoğunlaşması.",
        "Ortalama ile medyan/eşit-sembol ortalaması ayrıştığında uç hareket etkisi var demektir.",
        False, h04,
    )

    def h05(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        grp = df.groupby("symbol", sort=False)
        recl_prev = grp["reclaimed_4h_now"].shift(1, fill_value=False).astype(bool)
        imm = df[df["reclaimed_4h_now"]].copy()
        imm["_bucket"] = "ilk_4h_kapanisinda_giris"
        wait1 = df[recl_prev & df["above_4h"]].copy()
        wait1["_bucket"] = "izleyen_ikinci_4h_kapanisinda_giris"
        c = pd.concat([imm, wait1], ignore_index=True)
        return c, 0

    add(
        "STB-BHV-H05", "H",
        "İlk izleyen 4H kapanışını beklemek farkı yok ediyor mu?",
        "Geri alımın ilk 4H kapanışında ölçüm ile bir sonraki 4H kapanışında hala üstteyse ölçüm arasındaki gecikme maliyeti.",
        "Saatlik ara fiyatlarla sahte native teyit üretilmez; gerçek 4H kapanışları kıyaslanır.",
        False, h05,
    )

    def h06(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        syms = sorted(df["symbol"].unique())
        half = max(1, len(syms) // 2)
        first_syms = set(syms[:half])
        c = df[df["touch_4h"] | df["reclaimed_4h_now"]].copy()
        c["_bucket"] = np.where(c["symbol"].isin(first_syms), "alfabetik_ilk_yari_semboller", "alfabetik_ikinci_yari_semboller")
        return c, 0

    add(
        "STB-BHV-H06", "H",
        "Ayrımlar yeni dönem/sembol ve komşu eşiklerde korunuyor mu?",
        "Sembol evreninin iki bağımsız alt kümesi ve tablodaki erken/geç dönem yarı medyanları arasında yön ve büyüklük tutarlılığı.",
        "Aynı arşivde görülmüş 100 sembol tam kör gelecek testi değildir; canlı kural öncesi ileri tarihli doğrulama gerekir.",
        False, h06,
    )

    return specs


def _classify_conclusion(
    spec: QuestionSpec,
    bucket_rows: list[dict[str, Any]],
    *,
    user_confirmed_regime: bool,
) -> tuple[str, str]:
    """Choose only from the permitted descriptive conclusions in `STABIL_DAVRANIS_SORULARI.md`."""
    h8 = [r for r in bucket_rows if r["horizon_4h"] == 8]
    valid_buckets = [r for r in h8 if r["n_atr_valid"] >= 20 and math.isfinite(r["median_ret_atr"])]

    if spec.uses_candidate_regime and not user_confirmed_regime:
        if not valid_buckets:
            return "örnek yetersiz", "Aday eşleme altında yeterli tam ufuklu örnek oluşmadı; ayrıca dikey/yatay eşlemesi ayrı doğrulama şerhi taşımaktadır."
        meds = [r["median_ret_atr"] for r in valid_buckets]
        maes = [r["median_mae_atr"] for r in valid_buckets]
        spread = max(meds) - min(meds) if len(meds) >= 2 else 0.0
        mae_spread = max(maes) - min(maes) if len(maes) >= 2 else 0.0
        bucket_brief = ", ".join(
            f"{r['bucket']}: med={r['median_ret_atr']:+.3f} / MAE={r['median_mae_atr']:.3f} ATR (n={r['n_atr_valid']})"
            for r in valid_buckets
        )
        return (
            "ayrı doğrulama gerekli",
            f"Aday dikey/yatay eşlemesi altında 8x4H medyan farkı {spread:.3f} ATR, MAE farkı {mae_spread:.3f} ATR "
            f"[{bucket_brief}]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.",
        )

    if len(valid_buckets) == 0:
        return "örnek yetersiz", "8x4H tam ufukta en az 20 geçerli ATR gözlemi olan kova oluşmadı."
    if len(valid_buckets) == 1:
        b = valid_buckets[0]
        return (
            "örnek yetersiz",
            f"Yalnız tek kovada ({b['bucket']}, n={b['n_atr_valid']}) yeterli örnek var; karşılaştırmalı ayrım kurulamadı.",
        )

    # Check period stability across buckets
    sign_flips = 0
    for r in valid_buckets:
        e_m, l_m = r["early_half_med_ret"], r["late_half_med_ret"]
        if math.isfinite(e_m) and math.isfinite(l_m) and (e_m * l_m < -0.005):
            sign_flips += 1

    meds = [r["median_ret_atr"] for r in valid_buckets]
    mfes = [r["median_mfe_atr"] for r in valid_buckets]
    maes = [r["median_mae_atr"] for r in valid_buckets]
    race_spread = max(r["race_sup_up_24"] for r in valid_buckets) - min(r["race_sup_up_24"] for r in valid_buckets)
    med_spread = max(meds) - min(meds)
    risk_spread = max(maes) - min(maes)

    if sign_flips >= len(valid_buckets) and med_spread >= 0.08:
        return (
            "dönemlere göre değişiyor",
            f"8x4H kova medyan farkı {med_spread:.3f} ATR olsa da erken ve geç dönem yarılarında işaret değişimi gözlendi.",
        )
    if med_spread >= 0.10 or risk_spread >= 0.12 or race_spread >= 0.08:
        return (
            "betimsel ayrım",
            f"Kovalar arasında 8x4H medyan korunan getiri farkı {med_spread:.3f} ATR, MAE farkı {risk_spread:.3f} ATR düzeyinde ayrıştı.",
        )
    return (
        "belirgin ayrım yok",
        f"Kovalar arasında 8x4H medyan korunan getiri farkı ({med_spread:.3f} ATR) ve MAE farkı ({risk_spread:.3f} ATR) sınırlı kaldı.",
    )


def evaluate_all_48_questions(
    checkpoints_df: pd.DataFrame,
    *,
    user_confirmed_regime: bool = False,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Evaluate `STB-BHV-A01..H06` on the combined causal checkpoint DataFrame."""
    enriched = _enrich_features(checkpoints_df)
    specs = _build_question_specs()
    results: list[dict[str, Any]] = []
    all_table_rows: list[dict[str, Any]] = []

    for spec in specs:
        cohort, unk_excluded = spec.builder(enriched)
        bucket_names = sorted(cohort["_bucket"].dropna().unique().tolist()) if not cohort.empty else []
        q_rows: list[dict[str, Any]] = []
        if not bucket_names:
            q_rows.extend(_bucket_stats(cohort, "BOS_KOHORT", unk_excluded))
        else:
            for b_name in bucket_names:
                sub = cohort[cohort["_bucket"] == b_name]
                q_rows.extend(_bucket_stats(sub, str(b_name), unk_excluded))

        for r in q_rows:
            all_table_rows.append(
                {
                    "question_id": spec.qid,
                    "section": spec.section,
                    "uses_candidate_regime": spec.uses_candidate_regime,
                    "regime_user_confirmed": user_confirmed_regime,
                    **r,
                }
            )

        verdict, summary_sentence = _classify_conclusion(
            spec,
            q_rows,
            user_confirmed_regime=user_confirmed_regime,
        )
        counterexamples = _extract_counterexamples(cohort)

        total_n = sum(r["n_total"] for r in q_rows if r["horizon_4h"] == 8)
        full8_n = sum(r["n_full"] for r in q_rows if r["horizon_4h"] == 8)
        cens8_n = sum(r["n_censored"] for r in q_rows if r["horizon_4h"] == 8)
        atr8_n = sum(r["n_atr_valid"] for r in q_rows if r["horizon_4h"] == 8)

        results.append(
            {
                "question_id": spec.qid,
                "section": spec.section,
                "title": spec.title,
                "definition": spec.definition,
                "uses_candidate_regime": spec.uses_candidate_regime,
                "regime_mapping_status": (
                    "USER_CONFIRMED"
                    if (not spec.uses_candidate_regime or user_confirmed_regime)
                    else "PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION"
                ),
                "data_summary": {
                    "n_total": int(total_n),
                    "n_full_8x4h": int(full8_n),
                    "n_censored_8x4h": int(cens8_n),
                    "n_atr_valid_8x4h": int(atr8_n),
                    "n_unknown_excluded": int(unk_excluded),
                    "buckets": bucket_names,
                },
                "table_rows": q_rows,
                "counterexamples": counterexamples,
                "limitation": spec.limitation_note,
                "verdict": verdict,
                "conclusion_text": summary_sentence,
            }
        )

    return results, pd.DataFrame(all_table_rows)


def render_markdown_report(
    results: Sequence[dict[str, Any]],
    *,
    symbols: Sequence[str],
    elapsed_sec: float,
    user_confirmed_regime: bool,
) -> str:
    """Render full 48-question report in `TANIM -> VERI -> KARSILASTIRMA -> TABLO -> KARSI ORNEK -> SINIR -> SONUC` format."""
    lines: list[str] = [
        "# Stabil — 48 Davranış Sorusu (`STB-BHV-A01..H06`) Nedensel Replay Raporu",
        "",
        f"- **Sembol sayısı:** {len(symbols)} BIST hissesi (`{symbols[0]}` .. `{symbols[-1]}`)" if symbols else "- **Sembol sayısı:** 0",
        f"- **Toplam çalışma süresi:** {elapsed_sec:.2f} sn (tek geçişli O(N) native tarihçe)",
        "- **Kaynak matematik:** `domain_engines/05_stabil.txt` (`StabilTrendEngine` + `StabilSupportLifecycleEngine`, değiştirilmemiş eşikler)",
        "- **Checkpoint birimi:** Kapanmış `4H` mum kapanışları (`daily_close <= h4_close`, tamamlanmış takvim haftası `weekly_close <= h4_close`)",
        "- **Ufuklar:** `1, 4, 8, 10, 12, 16` × `4H` mum; sabit başlangıç günlük ATR birimi",
        f"- **Dikey/Yatay eşleme durumu:** {'Kullanıcı grafik teyitli' if user_confirmed_regime else 'ADAY EŞLEME (gerçek grafik örneği üzerinde kullanıcı teyidi bekleniyor; B01-B06 ve F01/F03/F05/F06 kesinleşmiş ölçüm sayılmaz)'}",
        "- **Karar kapısı notu:** Eski `S01–S32` otomatik karar kapısı uygulanmamıştır; hiçbir sonuç otomatik canlı alarm kuralı üretmez.",
        "",
        "## Genel Dağılım Özeti",
        "",
    ]
    verdict_counts: dict[str, int] = {}
    for item in results:
        v = item["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    for k, cnt in sorted(verdict_counts.items()):
        lines.append(f"- **{k}:** {cnt} soru")
    lines.append("")

    for item in results:
        qid = item["question_id"]
        lines.append(f"## {qid} — {item['title']}")
        lines.append("")
        ds = item["data_summary"]
        lines.append(f"- **TANIM:** {item['definition']}")
        lines.append(
            f"- **VERİ:** Toplam checkpoint/olay `n={ds['n_total']}`, 8×4H tam ufuk `n={ds['n_full_8x4h']}`, "
            f"sağdan sansürlü `n={ds['n_censored_8x4h']}`, ATR geçerli `n={ds['n_atr_valid_8x4h']}`, "
            f"`UNKNOWN` başlangıç nedeniyle dışlanan `n={ds['n_unknown_excluded']}`. "
            f"Eşleme durumu: `{item['regime_mapping_status']}`."
        )
        h8_rows = [r for r in item["table_rows"] if r["horizon_4h"] == 8]
        comp_parts = []
        for r in h8_rows:
            comp_parts.append(
                f"`{r['bucket']}` (8×4H n={r['n_atr_valid']}, med={r['median_ret_atr']:.3f} ATR, "
                f"ort={r['mean_ret_atr']:.3f} ATR, MFE_med={r['median_mfe_atr']:.3f}, MAE_med={r['median_mae_atr']:.3f}, "
                f"top1_sembol={r['top1_sym_share']*100:.1f}%)"
                if r["n_atr_valid"] > 0 and math.isfinite(r["median_ret_atr"])
                else f"`{r['bucket']}` (8×4H geçerli n={r['n_atr_valid']})"
            )
        lines.append("- **KARŞILAŞTIRMA (8×4H referans kesiti):** " + (" vs ".join(comp_parts) if comp_parts else "Veri yok"))
        lines.append("")
        lines.append("| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in item["table_rows"]:
            if r["n_atr_valid"] > 0 and math.isfinite(r["median_ret_atr"]):
                e_txt = f"{r['early_half_med_ret']:.3f}" if math.isfinite(r["early_half_med_ret"]) else "—"
                l_txt = f"{r['late_half_med_ret']:.3f}" if math.isfinite(r["late_half_med_ret"]) else "—"
                lines.append(
                    f"| `{r['bucket']}` | {r['horizon_4h']} | {r['n_atr_valid']} / {r['n_full']} / {r['n_censored']} | "
                    f"{r['symbols']} ({r['top1_sym_share']*100:.1f}%) | "
                    f"{r['mean_ret_atr']:+.3f} / {r['median_ret_atr']:+.3f} | {r['eq_sym_mean_ret_atr']:+.3f} | "
                    f"{r['median_mfe_atr']:.3f} / {r['median_mae_atr']:.3f} | "
                    f"{r['up_1atr_first_rate']*100:.1f}% / {r['down_1atr_first_rate']*100:.1f}% / {r['ambig_1atr_rate']*100:.1f}% | "
                    f"{e_txt} / {l_txt} |"
                )
            else:
                lines.append(
                    f"| `{r['bucket']}` | {r['horizon_4h']} | {r['n_atr_valid']} / {r['n_full']} / {r['n_censored']} | "
                    f"{r['symbols']} ({r['top1_sym_share']*100:.1f}%) | — | — | — | — | — |"
                )
        lines.append("")
        lines.append("- **KARŞI ÖRNEK:** " + " · ".join(item["counterexamples"]))
        lines.append(f"- **SINIR:** {item['limitation']}")
        lines.append(f"- **SONUÇ (`{item['verdict']}`):** {item['conclusion_text']}")
        lines.append("")

    return "\n".join(lines)


def run_benchmark_or_batch(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stabil single-pass 48 behavioral questions runner.")
    parser.add_argument("--benchmark-symbol", type=str, default="", help="Run 1-symbol benchmark and print timeout plan.")
    parser.add_argument("--universe", type=int, default=100, help="Number of BIST equities for full batch.")
    parser.add_argument("--output-dir", type=str, default="", help="Directory to write report/CSV/JSON artifacts.")
    parser.add_argument("--user-confirmed-regime", action="store_true", help="Mark candidate vertical/horizontal mapping as confirmed.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    t0 = time.perf_counter()
    xu_lookup = build_xu100_regime_lookup()

    if args.benchmark_symbol:
        sym = args.benchmark_symbol.strip().upper()
        res = replay_single_symbol(
            sym,
            xu100_lookup=xu_lookup,
            user_confirmed_regime=args.user_confirmed_regime,
        )
        t_eval0 = time.perf_counter()
        q_results, q_table = evaluate_all_48_questions(
            res.checkpoint_df,
            user_confirmed_regime=args.user_confirmed_regime,
        )
        eval_sec = time.perf_counter() - t_eval0
        total_1sym = time.perf_counter() - t0
        est_100 = res.elapsed_sec * 100.0 + eval_sec * 25.0
        rec_timeout = int(math.ceil(max(180.0, est_100 * 3.0) / 30.0) * 30)
        summary = {
            "benchmark_symbol": sym,
            "daily_bars": res.daily_bars,
            "weekly_bars": res.weekly_bars,
            "h4_bars": res.h4_bars,
            "first_seen_events": int(len(res.first_seen_events_df)),
            "replay_symbol_sec": round(res.elapsed_sec, 4),
            "bhv48_eval_sec": round(eval_sec, 4),
            "total_benchmark_sec": round(total_1sym, 4),
            "question_count": len(q_results),
            "table_row_count": int(len(q_table)),
            "estimated_100_symbols_sec": round(est_100, 1),
            "recommended_timeout_sec": rec_timeout,
            "recommended_kill_grace_sec": 30,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    symbols = select_bist_equity_universe(args.universe)
    cp_frames: list[pd.DataFrame] = []
    ev_frames: list[pd.DataFrame] = []
    per_symbol_manifest: list[dict[str, Any]] = []

    for idx, sym in enumerate(symbols, 1):
        res = replay_single_symbol(
            sym,
            xu100_lookup=xu_lookup,
            user_confirmed_regime=args.user_confirmed_regime,
        )
        cp_frames.append(res.checkpoint_df)
        if not res.first_seen_events_df.empty:
            ev_frames.append(res.first_seen_events_df)
        per_symbol_manifest.append(
            {
                "symbol": sym,
                "daily_bars": res.daily_bars,
                "weekly_bars": res.weekly_bars,
                "h4_bars": res.h4_bars,
                "first_seen_events": int(len(res.first_seen_events_df)),
                "elapsed_sec": round(res.elapsed_sec, 4),
            }
        )
        if idx % 10 == 0 or idx == len(symbols):
            print(f"[{idx}/{len(symbols)}] {sym} tamamlandı ({time.perf_counter() - t0:.1f}s)", flush=True)

    full_cp = pd.concat(cp_frames, ignore_index=True) if cp_frames else pd.DataFrame()
    q_results, q_table = evaluate_all_48_questions(
        full_cp,
        user_confirmed_regime=args.user_confirmed_regime,
    )
    elapsed_all = time.perf_counter() - t0

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md_text = render_markdown_report(
            q_results,
            symbols=symbols,
            elapsed_sec=elapsed_all,
            user_confirmed_regime=args.user_confirmed_regime,
        )
        (out_dir / "STABIL_DAVRANIS_48_YANITLARI.md").write_text(md_text, encoding="utf-8")
        q_table.to_csv(out_dir / "STABIL_DAVRANIS_48_TABLO.csv", index=False)
        manifest = {
            "generated_at": "2026-11-01",
            "symbol_count": len(symbols),
            "symbols": symbols,
            "total_checkpoints_4h": int(len(full_cp)),
            "total_first_seen_events": int(sum(m["first_seen_events"] for m in per_symbol_manifest)),
            "question_count": len(q_results),
            "table_row_count": int(len(q_table)),
            "elapsed_sec": round(elapsed_all, 3),
            "user_confirmed_regime": bool(args.user_confirmed_regime),
            "source_reference": "domain_engines/05_stabil.txt",
            "per_symbol": per_symbol_manifest,
            "verdict_summary": {
                v: sum(1 for r in q_results if r["verdict"] == v)
                for v in sorted({r["verdict"] for r in q_results})
            },
        }
        (out_dir / "STABIL_DAVRANIS_48_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "STABIL_DAVRANIS_48_SONUCLAR.json").write_text(
            json.dumps(q_results, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_benchmark_or_batch())
