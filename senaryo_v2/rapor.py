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


# ---------------------------------------------------------------------------
# Küme tanımına duyarlılık + işlem-içi süreç görünürlüğü
# ---------------------------------------------------------------------------
ZAMAN_KUMELERI: tuple[str, ...] = ("sembol", "gun", "hafta", "ay")


def zaman_kumesi_saglamligi(
    df: pd.DataFrame,
    deger_col: str,
    *,
    zaman_col: str = "bar_close_time",
    sembol_col: str = "sembol",
    B: int = 1000,
) -> dict[str, Any]:
    """Aynı ortalamanın %95 GA'sını dört küme tanımıyla verir: sembol, gün, hafta, ay.

    Sembol kümesi, aynı gün birlikte hareket eden hisseleri bağımsız sayar. Piyasa geneli
    bir günün/haftanın etkisi bütün sembollere birden yayıldığı için tek başına sembol
    kümesi belirsizliği olduğundan dar gösterebilir; kabul kararı en dar değil en geniş
    aralığa dayanmalıdır. `en_kotu_alt` dört alt sınırın en küçüğüdür.

    Tek kümeli bir tanım belirsizlik ölçemez: aralığı `None` kalır ve o durumda
    `hepsinde_pozitif` False döner (ölçülemeyen dayanıklılık, dayanıklılık sayılmaz).
    """
    bos = {"n": 0, "ort": None, "kumeler": {}, "en_kotu_alt": None, "hepsinde_pozitif": False}
    if df.empty or deger_col not in df.columns or zaman_col not in df.columns:
        return bos
    sub = df[[sembol_col, zaman_col, deger_col]].dropna()
    if sub.empty:
        return bos
    gun = sub[zaman_col].astype(str).str[:10]
    tarih = pd.to_datetime(gun, errors="coerce")
    iso = tarih.dt.isocalendar()
    calisma = pd.DataFrame(
        {
            "sembol": sub[sembol_col].to_numpy(),
            "gun": gun.to_numpy(),
            "hafta": (iso["year"].astype(str) + "-H" + iso["week"].astype(str).str.zfill(2)).to_numpy(),
            "ay": gun.str[:7].to_numpy(),
            deger_col: sub[deger_col].to_numpy(dtype=float),
        }
    )
    kumeler: dict[str, Any] = {}
    for kume in ZAMAN_KUMELERI:
        oz = kume_bootstrap_ozet(calisma, deger_col, sembol_col=kume, B=B)
        olculebilir = oz["sembol_n"] >= 2
        kumeler[kume] = {
            "kume_n": oz["sembol_n"],
            "ci95_alt": oz["ci95_alt"] if olculebilir else None,
            "ci95_ust": oz["ci95_ust"] if olculebilir else None,
        }
    altlar = [k["ci95_alt"] for k in kumeler.values() if k["ci95_alt"] is not None]
    return {
        "n": int(len(calisma)),
        "ort": round(float(calisma[deger_col].mean()), 4),
        "kumeler": kumeler,
        "en_kotu_alt": min(altlar) if altlar else None,
        "hepsinde_pozitif": len(altlar) == len(ZAMAN_KUMELERI) and min(altlar) > 0,
    }


def surec_izini_coz(iz: Any) -> list[tuple[int, tuple[str, ...]]]:
    """`"1:FRM_TEYIT,VP_LEHTE_BASKI|3:SEVIYE_ICI"` -> [(1, (...)), (3, (...))]."""
    if not isinstance(iz, str) or not iz:
        return []
    cozulen: list[tuple[int, tuple[str, ...]]] = []
    for parca in iz.split("|"):
        k, _, etiketler = parca.partition(":")
        if etiketler:
            cozulen.append((int(k), tuple(etiketler.split(","))))
    return cozulen


def surec_ozeti_uret(
    df: pd.DataFrame,
    *,
    deger_col: str = "net15_20_r",
    neden_col: str = "neden_20_intra_iptal",
) -> dict[str, Any]:
    """Birincil yarışın işlem-içi süreç kayıtlarından BETİMLEYİCİ özet üretir.

    Bu tablo "işlem açıkken ne görüldü" sorusunu yanıtlar; bir çıkış kuralının değerini
    ÖLÇMEZ. Etiketlerin nihai sonuçla ilişkisi sonuç-koşulludur (erken stop olan işlem
    etiketi görmeye fırsat bulamaz); kural değeri yalnız eşleşmiş replay ile ölçülür
    (`research/golge_v2_surec_olcum.py`).
    """
    if df.empty or "surec_gozlem_n" not in df.columns:
        return {}
    sub = df[df["surec_gozlem_n"].notna() & df[deger_col].notna()].copy()
    if sub.empty:
        return {}
    n = int(len(sub))
    gozlem = sub["surec_gozlem_n"].astype(float)
    stoplar = sub[sub[neden_col].astype(str).str.startswith("STOP")]

    cikis: list[dict[str, Any]] = []
    for neden, grp in sub.groupby(neden_col, sort=True):
        cikis.append(
            {
                "neden": str(neden),
                "n": int(len(grp)),
                "ort_net_r": round(float(grp[deger_col].mean()), 4),
                "ort_gozlem": round(float(grp["surec_gozlem_n"].mean()), 2),
                "ort_mfe_r": round(float(grp["surec_mfe_r"].mean()), 4),
                "ort_mae_r": round(float(grp["surec_mae_r"].mean()), 4),
            }
        )

    tez: list[dict[str, Any]] = []
    for durum, grp in sub.groupby(sub["surec_tez_son"].fillna("").replace("", "GOZLEM_YOK"), sort=True):
        tez.append(
            {
                "tez_son": str(durum),
                "n": int(len(grp)),
                "pay": round(len(grp) / n, 4),
                "ort_net_r": round(float(grp[deger_col].mean()), 4),
                "stop_orani": round(float(grp[neden_col].astype(str).str.startswith("STOP").mean()), 4),
            }
        )

    sayac: dict[str, int] = {}
    ilk_bar: dict[str, list[int]] = {}
    for iz in sub["surec_izi"]:
        gorulen: dict[str, int] = {}
        for k, etiketler in surec_izini_coz(iz):
            for e in etiketler:
                gorulen.setdefault(e, k)
        for e, k in gorulen.items():
            sayac[e] = sayac.get(e, 0) + 1
            ilk_bar.setdefault(e, []).append(k)
    etiketler_ozet = [
        {
            "etiket": e,
            "islem_n": c,
            "pay": round(c / n, 4),
            "medyan_ilk_bar": float(np.median(ilk_bar[e])),
        }
        for e, c in sorted(sayac.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    return {
        "n": n,
        "ort_gozlem": round(float(gozlem.mean()), 2),
        "gozlemsiz_n": int((gozlem == 0).sum()),
        "gozlemsiz_pay": round(float((gozlem == 0).mean()), 4),
        "stop_n": int(len(stoplar)),
        # Stop olan işlemler stoptan ÖNCE ne kadar kâr gördü? (stopu taşıma fikrinin tavanı)
        "stop_once_yarim_r_gordu": round(float((stoplar["surec_mfe_r"] >= 0.5).mean()), 4) if len(stoplar) else None,
        "stop_once_bir_r_gordu": round(float((stoplar["surec_mfe_r"] >= 1.0).mean()), 4) if len(stoplar) else None,
        "cikis_nedeni": cikis,
        "tez_son": tez,
        "etiketler": etiketler_ozet,
    }
