"""Gölge v2 küme-bootstrap (sembol bazlı) istatistikleri, ablasyon ve kesit tabloları."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def kume_bootstrap_ozet(
    df: pd.DataFrame,
    deger_col: str,
    *,
    sembol_col: str = "sembol",
    B: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Sembol kümesi bazlı (cluster bootstrap) %95 GA ve özet metrikler."""
    if df.empty or deger_col not in df.columns:
        return {
            "n": 0,
            "sembol_n": 0,
            "ort": None,
            "medyan": None,
            "sembol_esit_ort": None,
            "pozitif_oran": None,
            "ci95_alt": None,
            "ci95_ust": None,
        }
    sub = df[[sembol_col, deger_col]].dropna()
    if sub.empty:
        return {
            "n": 0,
            "sembol_n": 0,
            "ort": None,
            "medyan": None,
            "sembol_esit_ort": None,
            "pozitif_oran": None,
            "ci95_alt": None,
            "ci95_ust": None,
        }

    vals = sub[deger_col].to_numpy(dtype=float)
    n = int(len(vals))
    ort = float(np.mean(vals))
    medyan = float(np.median(vals))
    poz = float(np.mean(vals > 0.0))

    gruplar = [grp[deger_col].to_numpy(dtype=float) for _, grp in sub.groupby(sembol_col, sort=True)]
    k = len(gruplar)
    sembol_ort_list = np.array([float(np.mean(g)) for g in gruplar], dtype=float)
    sembol_esit_ort = float(np.mean(sembol_ort_list))

    if k < 2:
        return {
            "n": n,
            "sembol_n": k,
            "ort": round(ort, 4),
            "medyan": round(medyan, 4),
            "sembol_esit_ort": round(sembol_esit_ort, 4),
            "pozitif_oran": round(poz, 4),
            "ci95_alt": round(ort, 4),
            "ci95_ust": round(ort, 4),
        }

    rng = np.random.default_rng(seed)
    sums = np.array([float(np.sum(g)) for g in gruplar], dtype=float)
    counts = np.array([len(g) for g in gruplar], dtype=float)

    idx_mat = rng.integers(0, k, size=(B, k))
    boot_sum = sums[idx_mat].sum(axis=1)
    boot_cnt = counts[idx_mat].sum(axis=1)
    boot_means = boot_sum / np.maximum(boot_cnt, 1.0)
    ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])

    return {
        "n": n,
        "sembol_n": k,
        "ort": round(ort, 4),
        "medyan": round(medyan, 4),
        "sembol_esit_ort": round(sembol_esit_ort, 4),
        "pozitif_oran": round(poz, 4),
        "ci95_alt": round(float(ci_lo), 4),
        "ci95_ust": round(float(ci_hi), 4),
    }


def ablasyon_tablosu_uret(
    df: pd.DataFrame,
    *,
    deger_col: str = "pnl_15_intra_iptal_r",
    B: int = 1000,
) -> list[dict[str, Any]]:
    """Sığ kapılar üzerinde izole A/B ablasyon tablosu (dönem x kapı)."""
    if df.empty:
        return []
    kapi_maskeleri = [
        ("G0_Ham", pd.Series(True, index=df.index)),
        ("G1_SR_Koridor", df["g1_sr_koridor"].astype(bool)),
        ("G2_MS_BOS", df["g2_ms_bos"].astype(bool)),
        ("G3_Frm_Sikisma", df["g3_frm_sikisma"].astype(bool)),
        (
            "G123_Tumu",
            df["g1_sr_koridor"].astype(bool)
            & df["g2_ms_bos"].astype(bool)
            & df["g3_frm_sikisma"].astype(bool),
        ),
    ]
    if "g4_vp_kalite" in df.columns and "g5_blok_temiz" in df.columns:
        kapi_maskeleri.extend([
            ("G4_VP_Kalite", df["g4_vp_kalite"].astype(bool)),
            ("G5_Blok_Temiz", df["g5_blok_temiz"].astype(bool)),
            (
                "G12345_Tumu",
                df["g1_sr_koridor"].astype(bool)
                & df["g2_ms_bos"].astype(bool)
                & df["g3_frm_sikisma"].astype(bool)
                & df["g4_vp_kalite"].astype(bool)
                & df["g5_blok_temiz"].astype(bool),
            ),
        ])

    satirlar: list[dict[str, Any]] = []
    for donem in ("tumu", "kesif", "dogrulama"):
        d_sub = df if donem == "tumu" else df[df["donem"] == donem]
        for kapi_adi, mask in kapi_maskeleri:
            k_sub = d_sub[mask.loc[d_sub.index]]
            oz = kume_bootstrap_ozet(k_sub, deger_col, B=B)
            oz["donem"] = donem
            oz["kapi"] = kapi_adi
            oz["kalma_oran"] = round(len(k_sub) / max(len(d_sub), 1), 4)
            satirlar.append(oz)
    return satirlar


def domain_ablasyonu_uret(
    df: pd.DataFrame,
    *,
    deger_col: str = "pnl_20_intra_iptal_r",
    B: int = 800,
) -> list[dict[str, Any]]:
    """Domain-doğrulamalı kademeli merdiven (birincil kırılım vs düşürülmüş ikinciller)."""
    if df.empty:
        return []
    birincil = df["sinyal_sinifi"] == "BIRINCIL"
    d2 = birincil & df["g2_ms_bos"].astype(bool)
    d3 = d2 & df["g5_blok_temiz"].astype(bool)
    d4 = d3 & df["g4_vp_kalite"].astype(bool)
    d5 = d4 & df["ms_yapi_uyumlu"].astype(bool)
    d6 = df["kalite_katmani"].isin(["A_ARTI", "A_CEKIRDEK"])
    d7 = df["kalite_katmani"] == "A_ARTI"

    maskeler = [
        ("D0_Tum_Olaylar", pd.Series(True, index=df.index)),
        ("D1_Birincil_KirilimAdayi", birincil),
        ("D2_TersBOS_Yok", d2),
        ("D3_Blok_Temiz", d3),
        ("D4_VP_Kalite", d4),
        ("D5_MS_Yapi_Uyumlu", d5),
        ("D6_A_Cekirdek_Veya_Arti", d6),
        ("D7_A_Arti_UyumluBOS", d7),
        ("Ikincil_Retest", df["alt_kol"] == "B_retest"),
        ("Ikincil_GecTeyitli", (df["alt_kol"] == "B_kirilim") & (df["tetik_adi"] == "KIRILIM_TEYITLI")),
        ("Ikincil_Stabil_Tumu", df["kohort"] == "A_stabil"),
        ("Ikincil_Stabil_Emilim", (df["kohort"] == "A_stabil") & df["vp_emilim_onayi"].astype(bool)),
    ]
    satirlar: list[dict[str, Any]] = []
    for donem in ("tumu", "kesif", "dogrulama"):
        d_sub = df if donem == "tumu" else df[df["donem"] == donem]
        for kat_adi, mask in maskeler:
            k_sub = d_sub[mask.loc[d_sub.index]]
            oz = kume_bootstrap_ozet(k_sub, deger_col, B=B)
            oz["donem"] = donem
            oz["katman"] = kat_adi
            oz["pay"] = round(len(k_sub) / max(len(d_sub), 1), 4)
            satirlar.append(oz)
    return satirlar


def kesit_ozeti_uret(
    df: pd.DataFrame,
    grup_kolonlari: list[str],
    *,
    deger_col: str = "pnl_15_intra_iptal_r",
    B: int = 500,
) -> list[dict[str, Any]]:
    """Verilen boyutlara göre (tf, kohort, alt_kol, yon, donem) bootstrap özeti."""
    if df.empty:
        return []
    satirlar: list[dict[str, Any]] = []
    for anahtar, grp in df.groupby(grup_kolonlari, sort=True):
        if not isinstance(anahtar, tuple):
            anahtar = (anahtar,)
        oz = kume_bootstrap_ozet(grp, deger_col, B=B)
        for col, val in zip(grup_kolonlari, anahtar):
            oz[col] = val
        satirlar.append(oz)
    return satirlar


def tez_iptali_karsilastir(df: pd.DataFrame) -> dict[str, Any]:
    """Aynı dolmuş işlemlerde 1-3 bar ters BOS tez iptali AÇIK vs KAPALI farkı."""
    if df.empty:
        return {}
    out: dict[str, Any] = {}
    for donem in ("tumu", "kesif", "dogrulama"):
        sub = df if donem == "tumu" else df[df["donem"] == donem]
        if sub.empty:
            continue
        iptal_etti = (sub["neden_15_intra_iptal"] == "TEZ_IPTAL_BOS")
        fark = sub["pnl_15_intra_iptal_r"] - sub["pnl_15_intra_ham_r"]
        out[donem] = {
            "n": int(len(sub)),
            "iptal_sayisi": int(iptal_etti.sum()),
            "iptal_orani": round(float(iptal_etti.mean()), 4),
            "ort_iptal_acik_r": round(float(sub["pnl_15_intra_iptal_r"].mean()), 4),
            "ort_iptal_kapali_r": round(float(sub["pnl_15_intra_ham_r"].mean()), 4),
            "net_fark_r": round(float(fark.mean()), 4),
            "iptal_edilenlerde_fark_r": (
                round(float(fark[iptal_etti].mean()), 4) if int(iptal_etti.sum()) > 0 else None
            ),
        }
    return out
