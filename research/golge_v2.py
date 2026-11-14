"""Gölge v2 araştırma koşucusu — tüm BIST evreni × 4 TF × simetrik Long/Short domain ablasyonu.

Canlı ürüne ve v1 `senaryo/` motoruna dokunmaz. Çıktıları `docs/arastirma/sonuclar/golge_v2/`
altına yazar.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
import math
from pathlib import Path
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd

from config import sembol_turu
from senaryo_v2.adaptor import hazirla_gunluk_baglam, seriyi_hazirla
from senaryo_v2.modeller import TF_LISTESI, TAMPON_VARSAYILAN_ATR, UFUK_VARSAYILAN_BAR, AdayOlay
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.rapor import (
    ablasyon_tablosu_uret,
    domain_ablasyonu_uret,
    kesit_ozeti_uret,
    kume_bootstrap_ozet,
    tez_iptali_karsilastir,
)
from senaryo_v2.yaris import fren_etiketle, yarisi_yurut

KOK = Path(__file__).resolve().parents[1]
VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_v2"
EVREN_DOSYA = KOK / "docs/arastirma/sonuclar/golge_zincir/evren176_semboller.txt"


def _evren_oku(evren: str, limit: int | None) -> list[str]:
    tum = [s.strip() for s in EVREN_DOSYA.read_text(encoding="utf-8").splitlines() if s.strip() and s.strip() != "BRENT"]
    if evren == "hisse174":
        tum = [s for s in tum if sembol_turu(s) == "hisse"]
    if limit is not None:
        tum = tum[: int(limit)]
    return tum


def _satir_birlestir(
    olay: AdayOlay,
    plan: Any,
    sonuc: Any,
    *,
    frende: bool,
    varlik_turu: str,
) -> dict[str, Any]:
    meta = sonuc.sonuc_meta or {}
    giris_ref = sonuc.giris_gercek if sonuc.giris_gercek is not None else olay.giris_baz
    risk_px = max(float(sonuc.risk_gercek_atr) * float(olay.atr_tf), 1e-6)
    cost15_r = (0.0030 * float(giris_ref)) / risk_px if sonuc.dolduruldu else None
    cost25_r = (0.0050 * float(giris_ref)) / risk_px if sonuc.dolduruldu else None

    def _net(pnl_r: float | None, cost_r: float | None) -> float | None:
        if pnl_r is None or cost_r is None or not math.isfinite(pnl_r):
            return None
        return round(float(pnl_r) - float(cost_r), 4)

    return {
        "olay_id": olay.olay_id,
        "sembol": olay.sembol,
        "varlik_turu": varlik_turu,
        "tf": olay.tf,
        "bar_index": olay.bar_index,
        "bar_close_time": olay.bar_close_time,
        "donem": olay.donem,
        "kohort": olay.kohort,
        "alt_kol": olay.alt_kol,
        "tetik_adi": olay.tetik_adi,
        "sinyal_sinifi": olay.sinyal_sinifi,
        "kalite_katmani": olay.kalite_katmani,
        "yon": olay.yon,
        "giris_baz": olay.giris_baz,
        "atr_tf": olay.atr_tf,
        "atr_1d": olay.atr_1d,
        "atr_oran": (round(olay.atr_tf / olay.atr_1d, 4) if olay.atr_1d and olay.atr_1d > 0 else None),
        "zemin_tavan": olay.zemin_tavan,
        "is_kisa_1800": olay.is_kisa_1800,
        "g1_sr_koridor": olay.g1_sr_koridor,
        "g2_ms_bos": olay.g2_ms_bos,
        "g3_frm_sikisma": olay.g3_frm_sikisma,
        "g4_vp_kalite": olay.g4_vp_kalite,
        "g5_blok_temiz": olay.g5_blok_temiz,
        "tum_kapilar_ok": olay.tum_kapilar_ok,
        "tum_domain_kapilari_ok": olay.tum_domain_kapilari_ok,
        "g1_dikey_bos": olay.g1_dikey_bos,
        "g1_karsi_duvar_ok": olay.g1_karsi_duvar_ok,
        "cift_kirilim_stabil": olay.cift_kirilim_stabil,
        "ms_yapi_uyumlu": olay.ms_yapi_uyumlu,
        "vp_emilim_onayi": olay.vp_emilim_onayi,
        "vp_guclu_sonuc": olay.vp_guclu_sonuc,
        "opp_blok_engeli": olay.opp_blok_engeli,
        "frm_pattern_type": olay.frm_pattern_type,
        "frm_width_atr": olay.frm_width_atr,
        "risk_baz_atr": olay.risk_baz_atr,
        "ms_ext_state": olay.ms_ext_state,
        "vp_volume_usable": olay.vp_volume_usable,
        "vp_rvol": round(olay.vp_rvol, 4) if olay.vp_rvol is not None else None,
        "vp_pressure_5": round(olay.vp_pressure_5, 4) if olay.vp_pressure_5 is not None else None,
        "vp_efficiency": round(olay.vp_efficiency, 4) if olay.vp_efficiency is not None else None,
        "vp_effort_result_class": olay.vp_effort_result_class,
        "runway_sr_atr": round(olay.runway_sr_atr, 4) if olay.runway_sr_atr is not None else None,
        "frm_karsi_mesafe_atr": round(olay.frm_karsi_mesafe_atr, 4) if olay.frm_karsi_mesafe_atr is not None else None,
        "sr_rejim_etiketi": olay.sr_rejim_etiketi,
        "ms_fresh_dir": olay.ms_fresh_dir,
        "touch_count": olay.touch_count,
        "frende": frende,
        "mod": plan.mod,
        "tampon_atr": plan.tampon_atr,
        "ufuk_bar": sonuc.ufuk_bar,
        "stop": plan.stop,
        "risk_atr": plan.risk_atr,
        "hedef_yapisal": plan.hedef_yapisal,
        "r_yapisal": plan.r_yapisal,
        "hedef_kaynagi": plan.hedef_kaynagi,
        "blok_kullanildi": plan.blok_kullanildi,
        "mod2_uygun": bool(meta.get("mod2_uygun", plan.mod == "mod2" and plan.limit_fiyat is not None)),
        "dolduruldu": sonuc.dolduruldu,
        "dolum_bar_offset": sonuc.dolum_bar_offset,
        "giris_gercek": sonuc.giris_gercek,
        "risk_gercek_atr": sonuc.risk_gercek_atr,
        "pnl_15_intra_iptal_atr": sonuc.pnl_15_intra_iptal_atr,
        "pnl_15_intra_iptal_r": sonuc.pnl_15_intra_iptal_r,
        "net15_15_r": _net(sonuc.pnl_15_intra_iptal_r, cost15_r),
        "neden_15_intra_iptal": sonuc.neden_15_intra_iptal,
        "bar_15_intra_iptal": sonuc.bar_15_intra_iptal,
        "pnl_15_intra_ham_atr": sonuc.pnl_15_intra_ham_atr,
        "pnl_15_intra_ham_r": sonuc.pnl_15_intra_ham_r,
        "neden_15_intra_ham": sonuc.neden_15_intra_ham,
        "pnl_15_close_iptal_atr": sonuc.pnl_15_close_iptal_atr,
        "neden_15_close_iptal": sonuc.neden_15_close_iptal,
        "pnl_20_intra_iptal_atr": sonuc.pnl_20_intra_iptal_atr,
        "pnl_20_intra_iptal_r": sonuc.pnl_20_intra_iptal_r,
        "net15_20_r": _net(sonuc.pnl_20_intra_iptal_r, cost15_r),
        "net25_20_r": _net(sonuc.pnl_20_intra_iptal_r, cost25_r),
        "neden_20_intra_iptal": sonuc.neden_20_intra_iptal,
        "pnl_20_intra_ham_atr": sonuc.pnl_20_intra_ham_atr,
        "pnl_20_intra_ham_r": sonuc.pnl_20_intra_ham_r,
        "pnl_yap_intra_iptal_atr": sonuc.pnl_yap_intra_iptal_atr,
        "pnl_yap_intra_iptal_r": sonuc.pnl_yap_intra_iptal_r,
        "neden_yap_intra_iptal": sonuc.neden_yap_intra_iptal,
        "pnl_yap_intra_ham_atr": sonuc.pnl_yap_intra_ham_atr,
        "pnl_yap_intra_ham_r": sonuc.pnl_yap_intra_ham_r,
        "neden_yap_intra_ham": sonuc.neden_yap_intra_ham,
        "pnl_yap_close_iptal_atr": sonuc.pnl_yap_close_iptal_atr,
        "pnl_yap_close_iptal_r": sonuc.pnl_yap_close_iptal_r,
        "neden_yap_close_iptal": sonuc.neden_yap_close_iptal,
        "mfe_atr": sonuc.mfe_atr,
        "mae_atr": sonuc.mae_atr,
        "kapanis_h_atr": sonuc.kapanis_h_atr,
        "sansurlu": sonuc.sansurlu,
    }


def _sembol_is_isle(sembol: str, *, tfs: tuple[str, ...] = TF_LISTESI) -> dict[str, Any]:
    t0 = time.perf_counter()
    varlik_turu = sembol_turu(sembol)
    gunluk_baglam = hazirla_gunluk_baglam(sembol)
    mod_satirlari: dict[str, list[dict[str, Any]]] = {"mod0": [], "mod1": [], "mod2": []}
    duyar_satirlari: list[dict[str, Any]] = []
    hatalar: list[dict[str, Any]] = []

    duyar_konfig = (
        (0.25, 10),
        (1.00, 10),
        (0.50, 16),
    )

    for tf in tfs:
        seri = seriyi_hazirla(sembol, tf, gunluk_baglam=gunluk_baglam, bloklari_yukle=True)
        if seri.r_hatali or seri.ms_hatali or seri.frm_hatali or seri.blok_hatali or seri.vp_hatali:
            hatalar.append({
                "sembol": sembol,
                "tf": tf,
                "r_hatali": seri.r_hatali,
                "ms_hatali": seri.ms_hatali,
                "frm_hatali": seri.frm_hatali,
                "blok_hatali": seri.blok_hatali,
                "vp_hatali": seri.vp_hatali,
            })
        olaylar = list(aday_olaylari_cikar(seri))
        if not olaylar:
            continue

        # 3 ana mod (varsayılan tampon=0.50 ATR_TF, ufuk=10 bar)
        for mod in ("mod0", "mod1", "mod2"):
            planlar = {
                o.olay_id: plan_karti_olustur(
                    o,
                    seri.barlar[o.bar_index],
                    mod=mod,
                    tampon_atr=TAMPON_VARSAYILAN_ATR,
                )
                for o in olaylar
            }
            sonuclar = {
                o.olay_id: yarisi_yurut(seri, o, planlar[o.olay_id], ufuk_bar=UFUK_VARSAYILAN_BAR)
                for o in olaylar
            }
            fren_map = fren_etiketle(olaylar, sonuclar, yalniz_kapilar_acik=True)
            for o in olaylar:
                mod_satirlari[mod].append(
                    _satir_birlestir(
                        o,
                        planlar[o.olay_id],
                        sonuclar[o.olay_id],
                        frende=fren_map.get(o.olay_id, False),
                        varlik_turu=varlik_turu,
                    )
                )

        # Duyarlılık ızgarası (mod0 üzerinden tampon & ufuk değişimi)
        for tamp, ufk in duyar_konfig:
            for o in olaylar:
                pl = plan_karti_olustur(o, seri.barlar[o.bar_index], mod="mod0", tampon_atr=tamp)
                sn = yarisi_yurut(seri, o, pl, ufuk_bar=ufk)
                duyar_satirlari.append({
                    "olay_id": o.olay_id,
                    "sembol": o.sembol,
                    "varlik_turu": varlik_turu,
                    "tf": o.tf,
                    "donem": o.donem,
                    "kohort": o.kohort,
                    "alt_kol": o.alt_kol,
                    "sinyal_sinifi": o.sinyal_sinifi,
                    "kalite_katmani": o.kalite_katmani,
                    "yon": o.yon,
                    "tum_kapilar_ok": o.tum_kapilar_ok,
                    "tum_domain_kapilari_ok": o.tum_domain_kapilari_ok,
                    "tampon_atr": tamp,
                    "ufuk_bar": ufk,
                    "pnl_15_intra_iptal_r": sn.pnl_15_intra_iptal_r,
                    "pnl_20_intra_iptal_r": sn.pnl_20_intra_iptal_r,
                    "pnl_15_intra_iptal_atr": sn.pnl_15_intra_iptal_atr,
                    "pnl_yap_intra_iptal_r": sn.pnl_yap_intra_iptal_r,
                    "sansurlu": sn.sansurlu,
                })

    return {
        "sembol": sembol,
        "elapsed": round(time.perf_counter() - t0, 2),
        "mod0": mod_satirlari["mod0"],
        "mod1": mod_satirlari["mod1"],
        "mod2": mod_satirlari["mod2"],
        "duyarlilik": duyar_satirlari,
        "hatalar": hatalar,
    }


def _rapor_olustur(
    df0: pd.DataFrame,
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    df_duy: pd.DataFrame,
    hatalar: list[dict[str, Any]],
    cikti_dir: Path,
    sure_sn: float,
    sembol_sayisi: int,
) -> dict[str, Any]:
    cikti_dir.mkdir(parents=True, exist_ok=True)
    df0.to_csv(cikti_dir / "mod0_baz.csv.gz", index=False, compression="gzip")
    df1.to_csv(cikti_dir / "mod1_blok_stop.csv.gz", index=False, compression="gzip")
    df2.to_csv(cikti_dir / "mod2_blok_limit.csv.gz", index=False, compression="gzip")
    df_duy.to_csv(cikti_dir / "duyarlilik.csv.gz", index=False, compression="gzip")

    df0_tam = df0[~df0["sansurlu"]].copy()
    df0_hisse = df0_tam[df0_tam["varlik_turu"] == "hisse"].copy()
    df0_4h1d = df0_tam[df0_tam["tf"].isin(["4h", "1d"])].copy()

    # 1. Domain-Denetimli Kademe Merdiveni (Tüm TFs & 4h+1d brüt/net)
    dom_merdiven_tumu_20r = domain_ablasyonu_uret(df0_tam, deger_col="pnl_20_intra_iptal_r", B=800)
    dom_merdiven_4h1d_20r = domain_ablasyonu_uret(df0_4h1d, deger_col="pnl_20_intra_iptal_r", B=800)
    dom_merdiven_4h1d_net15 = domain_ablasyonu_uret(df0_4h1d, deger_col="net15_20_r", B=800)

    # 2. Klasik + Genişletilmiş Sığ Kapı Ablasyonu (1.5 ATR R)
    ab_tumu_r = ablasyon_tablosu_uret(df0_tam, deger_col="pnl_15_intra_iptal_r", B=1000)
    ab_hisse_r = ablasyon_tablosu_uret(df0_hisse, deger_col="pnl_15_intra_iptal_r", B=1000)
    ab_long_r = ablasyon_tablosu_uret(df0_tam[df0_tam["yon"] == "long"], deger_col="pnl_15_intra_iptal_r", B=800)
    ab_short_r = ablasyon_tablosu_uret(df0_tam[df0_tam["yon"] == "short"], deger_col="pnl_15_intra_iptal_r", B=800)
    ab_tumu_atr = ablasyon_tablosu_uret(df0_tam, deger_col="pnl_15_intra_iptal_atr", B=1000)
    ab_yap_r = ablasyon_tablosu_uret(df0_tam[df0_tam["pnl_yap_intra_iptal_r"].notna()], deger_col="pnl_yap_intra_iptal_r", B=1000)
    ab_kohort_a = ablasyon_tablosu_uret(df0_tam[df0_tam["kohort"] == "A_stabil"], deger_col="pnl_15_intra_iptal_r", B=800)
    ab_kohort_b = ablasyon_tablosu_uret(df0_tam[df0_tam["kohort"] == "B_formasyon"], deger_col="pnl_15_intra_iptal_r", B=800)

    # 3. Kalite Katmanları × (TF, Yön, Sinyal Sınıfı)
    df0_birincil = df0_tam[df0_tam["sinyal_sinifi"] == "BIRINCIL"].copy()
    df0_cekirdek = df0_tam[df0_tam["kalite_katmani"].isin(["A_ARTI", "A_CEKIRDEK"])].copy()
    kesit_kalite_katmani = kesit_ozeti_uret(df0_tam, ["donem", "kalite_katmani", "tf"], deger_col="net15_20_r", B=500)
    kesit_kalite_yon = kesit_ozeti_uret(df0_4h1d, ["donem", "kalite_katmani", "yon"], deger_col="net15_20_r", B=500)
    kesit_alt_kol = kesit_ozeti_uret(df0_tam, ["donem", "sinyal_sinifi", "alt_kol", "yon"], deger_col="pnl_20_intra_iptal_r", B=500)
    kesit_tf_yon = kesit_ozeti_uret(df0_birincil[df0_birincil["tum_domain_kapilari_ok"]], ["donem", "tf", "yon"], deger_col="net15_20_r", B=500)
    kesit_hisse_vs_endeks = kesit_ozeti_uret(df0_4h1d[df0_4h1d["sinyal_sinifi"] == "BIRINCIL"], ["donem", "varlik_turu"], deger_col="net15_20_r", B=500)

    # 4. Tez İptali & Close vs Intrabar
    df0_ok = df0_tam[df0_tam["tum_domain_kapilari_ok"]].copy()
    tez_iptal_ham = tez_iptali_karsilastir(df0_tam)
    tez_iptal_ok = tez_iptali_karsilastir(df0_birincil[df0_birincil["tum_domain_kapilari_ok"]])

    close_vs_intra = {}
    for donem in ("tumu", "kesif", "dogrulama"):
        sub = df0_ok if donem == "tumu" else df0_ok[df0_ok["donem"] == donem]
        if not sub.empty:
            close_vs_intra[donem] = {
                "n": int(len(sub)),
                "ort_intra_15_atr": round(float(sub["pnl_15_intra_iptal_atr"].mean()), 4),
                "ort_close_15_atr": round(float(sub["pnl_15_close_iptal_atr"].mean()), 4),
                "fark_intra_eksi_close_atr": round(float((sub["pnl_15_intra_iptal_atr"] - sub["pnl_15_close_iptal_atr"]).mean()), 4),
            }

    # 5. Mod 0 vs Mod 1 vs Mod 2 (birincil + tum_domain_kapilari_ok kümesinde!)
    bir_ok_ids = set(df0_birincil[df0_birincil["tum_domain_kapilari_ok"]]["olay_id"])
    df0_m = df0_tam[df0_tam["olay_id"].isin(bir_ok_ids)].copy()
    df1_m = df1[(~df1["sansurlu"]) & (df1["olay_id"].isin(bir_ok_ids))].copy()
    df2_m = df2[df2["olay_id"].isin(bir_ok_ids)].copy()
    df2_uygun = df2_m[df2_m["mod2_uygun"]].copy()
    df2_dolan = df2_uygun[df2_uygun["dolduruldu"] & (~df2_uygun["sansurlu"])].copy()
    mod0_es_kume = df0_m[df0_m["olay_id"].isin(set(df2_uygun["olay_id"]))].copy()

    mod_kiyas = {
        "mod0_birincil_ok": kume_bootstrap_ozet(df0_m, "pnl_20_intra_iptal_r", B=500),
        "mod1_birincil_ok": kume_bootstrap_ozet(df1_m, "pnl_20_intra_iptal_r", B=500),
        "mod1_blok_degisen_alt": {
            "n_degisen": int(df1_m["blok_kullanildi"].sum()),
            "mod0_ayni_kume": kume_bootstrap_ozet(
                df0_m[df0_m["olay_id"].isin(set(df1_m[df1_m["blok_kullanildi"]]["olay_id"]))],
                "pnl_20_intra_iptal_r",
                B=500,
            ),
            "mod1_ayni_kume": kume_bootstrap_ozet(
                df1_m[df1_m["blok_kullanildi"]],
                "pnl_20_intra_iptal_r",
                B=500,
            ),
        },
        "mod2_limit": {
            "uygun_aday_n": int(len(df2_uygun)),
            "dolan_n": int(len(df2_dolan)),
            "dolmayan_n": int((~df2_uygun["dolduruldu"]).sum()),
            "dolum_orani": round(float(df2_uygun["dolduruldu"].mean()), 4) if len(df2_uygun) else 0.0,
            "mod2_dolan_sadece_r": kume_bootstrap_ozet(df2_dolan, "pnl_20_intra_iptal_r", B=500),
            "mod0_ayni_uygun_kume_r": kume_bootstrap_ozet(mod0_es_kume, "pnl_20_intra_iptal_r", B=500),
            "mod0_dolmayan_kacirilan_r": kume_bootstrap_ozet(
                df0_m[df0_m["olay_id"].isin(set(df2_uygun[~df2_uygun["dolduruldu"]]["olay_id"]))],
                "pnl_20_intra_iptal_r",
                B=500,
            ),
        },
    }

    # 6. 3-Stop Freni & 4h 18:00 kısa kova
    fren_kiyas = {
        "frensiz_birincil": kume_bootstrap_ozet(df0_m, "pnl_20_intra_iptal_r", B=500),
        "fren_uygulanmis_birincil": kume_bootstrap_ozet(df0_m[~df0_m["frende"]], "pnl_20_intra_iptal_r", B=500),
        "frende_elenenler": kume_bootstrap_ozet(df0_m[df0_m["frende"]], "pnl_20_intra_iptal_r", B=500),
    }

    h4_ok = df0_m[df0_m["tf"] == "4h"]
    kisa_1800_kiyas = {
        "4h_normal_kova": kume_bootstrap_ozet(h4_ok[~h4_ok["is_kisa_1800"]], "pnl_20_intra_iptal_r", B=500),
        "4h_1800_kisa_kova": kume_bootstrap_ozet(h4_ok[h4_ok["is_kisa_1800"]], "pnl_20_intra_iptal_r", B=500),
    }

    # 7. Duyarlılık özeti
    duy_tam = df_duy[(~df_duy["sansurlu"]) & (df_duy["sinyal_sinifi"] == "BIRINCIL") & (df_duy["tum_domain_kapilari_ok"])].copy()
    duy_ozet = []
    for (tamp, ufk), grp in [((0.50, 10), df0_m)] + list(duy_tam.groupby(["tampon_atr", "ufuk_bar"], sort=True)):
        for donem in ("kesif", "dogrulama"):
            sub = grp[grp["donem"] == donem]
            oz = kume_bootstrap_ozet(sub, "pnl_20_intra_iptal_r", B=400)
            oz["tampon_atr"] = float(tamp)
            oz["ufuk_bar"] = int(ufk)
            oz["donem"] = donem
            duy_ozet.append(oz)

    # 8. Karar (D6 A_Cekirdek_Veya_Arti 4h+1d Net15 ve D7 A_Arti üzerinden dürüst değerlendirme)
    dog_d6_net = next((x for x in dom_merdiven_4h1d_net15 if x["donem"] == "dogrulama" and x["katman"] == "D6_A_Cekirdek_Veya_Arti"), {})
    dog_d7_net = next((x for x in dom_merdiven_4h1d_net15 if x["donem"] == "dogrulama" and x["katman"] == "D7_A_Arti_UyumluBOS"), {})
    dog_d0_net = next((x for x in dom_merdiven_4h1d_net15 if x["donem"] == "dogrulama" and x["katman"] == "D0_Tum_Olaylar"), {})
    if (
        dog_d6_net.get("ci95_alt") is not None and dog_d6_net["ci95_alt"] > 0
        and dog_d7_net.get("ci95_alt") is not None and dog_d7_net["ci95_alt"] > 0
    ):
        karar = "GECTI_4H_1D_CEKIRDEK"
    elif dog_d6_net.get("ort") is not None and dog_d0_net.get("ort") is not None and dog_d6_net["ort"] > dog_d0_net["ort"] and dog_d6_net["ort"] > 0:
        karar = "KISMI_IYILESME"
    else:
        karar = "GECMEDI"

    ozet = {
        "meta": {
            "sembol_sayisi": sembol_sayisi,
            "sure_sn": round(sure_sn, 1),
            "hata_serisi_sayisi": len(hatalar),
            "toplam_ham_olay": int(len(df0)),
            "sansursuz_olay": int(len(df0_tam)),
            "birincil_olay": int(len(df0_birincil)),
            "cekirdek_veya_arti_olay": int(len(df0_cekirdek)),
            "karar": karar,
        },
        "domain_merdiven_tumu_20r": dom_merdiven_tumu_20r,
        "domain_merdiven_4h1d_20r": dom_merdiven_4h1d_20r,
        "domain_merdiven_4h1d_net15": dom_merdiven_4h1d_net15,
        "ablasyon_15r": ab_tumu_r,
        "ablasyon_hisse_15r": ab_hisse_r,
        "ablasyon_long_15r": ab_long_r,
        "ablasyon_short_15r": ab_short_r,
        "ablasyon_15atr": ab_tumu_atr,
        "ablasyon_yapisal_r": ab_yap_r,
        "ablasyon_kohort_a": ab_kohort_a,
        "ablasyon_kohort_b": ab_kohort_b,
        "kesit_kalite_katmani": kesit_kalite_katmani,
        "kesit_kalite_yon": kesit_kalite_yon,
        "kesit_tf_yon": kesit_tf_yon,
        "kesit_alt_kol": kesit_alt_kol,
        "kesit_hisse_vs_endeks": kesit_hisse_vs_endeks,
        "tez_iptali_ham": tez_iptal_ham,
        "tez_iptali_ok": tez_iptal_ok,
        "close_vs_intrabar": close_vs_intra,
        "mod_kiyas": mod_kiyas,
        "fren_kiyas": fren_kiyas,
        "kisa_1800_kiyas": kisa_1800_kiyas,
        "duyarlilik": duy_ozet,
    }
    (cikti_dir / "ozet_rapor.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    return ozet


def _markdown_ozet_yaz(ozet: dict[str, Any], cikti_dir: Path) -> None:
    m = ozet["meta"]
    lines = [
        "# Gölge v2 Domain-Denetimli Plan & Kalite Merdiveni Raporu",
        "",
        f"- **Evren:** {m['sembol_sayisi']} sembol (`BRENT` hariç tüm BIST arşivi)",
        f"- **Toplam Ham Olay:** `{m['toplam_ham_olay']}` (sansürsüz `{m['sansursuz_olay']}`, birincil `KIRILIM_ADAYI`: `{m['birincil_olay']}`, çekirdek/A+: `{m['cekirdek_veya_arti_olay']}`)",
        f"- **Hata / Veri Uyarısı Olan Seri:** `{m['hata_serisi_sayisi']}`",
        f"- **Kabul Kapısı Kararı:** **`{m['karar']}`**",
        "",
        "## 1. Domain Merdiveni (`4h + 1d`, `2.0 ATR` Hedef, `Net15` = `30 bps` Gidiş-Dönüş Masraf Düşülmüş R)",
        "",
        "| Dönem | Katman | N | Pay | Net15 Ort R | Pozitif % | Küme %95 GA |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in ozet["domain_merdiven_4h1d_net15"]:
        lines.append(
            f"| {r['donem']} | {r['katman']} | {r['n']} | {r['pay']:.1%} | "
            f"{r['ort']} | {r['pozitif_oran']:.1%} | [{r['ci95_alt']}, {r['ci95_ust']}] |"
            if r["ort"] is not None
            else f"| {r['donem']} | {r['katman']} | 0 | 0% | - | - | - |"
        )

    lines += [
        "",
        "## 2. Kalite Katmanı × Zaman Dilimi (Tüm TF'ler, `Net15` R)",
        "",
        "| Dönem | Katman | TF | N | Net15 Ort R | Pozitif % | Küme %95 GA |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for r in ozet["kesit_kalite_katmani"]:
        lines.append(
            f"| {r['donem']} | {r['kalite_katmani']} | {r['tf']} | {r['n']} | "
            f"{r['ort']} | {r['pozitif_oran']:.1%} | [{r['ci95_alt']}, {r['ci95_ust']}] |"
        )

    lines += [
        "",
        "## 3. Birincil vs İkincil Alt Kol Karşılaştırması (`2.0 ATR` Brüt R)",
        "",
        "| Dönem | Sınıf | Alt Kol | Yön | N | Brüt Ort R | Pozitif % | Küme %95 GA |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for r in ozet["kesit_alt_kol"]:
        lines.append(
            f"| {r['donem']} | {r['sinyal_sinifi']} | {r['alt_kol']} | {r['yon']} | {r['n']} | "
            f"{r['ort']} | {r['pozitif_oran']:.1%} | [{r['ci95_alt']}, {r['ci95_ust']}] |"
        )

    lines += [
        "",
        "## 4. Kalite Katmanı × Yön (`4h + 1d`, `Net15` R)",
        "",
        "| Dönem | Katman | Yön | N | Net15 Ort R | Pozitif % | Küme %95 GA |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for r in ozet["kesit_kalite_yon"]:
        lines.append(
            f"| {r['donem']} | {r['kalite_katmani']} | {r['yon']} | {r['n']} | "
            f"{r['ort']} | {r['pozitif_oran']:.1%} | [{r['ci95_alt']}, {r['ci95_ust']}] |"
        )

    mk = ozet["mod_kiyas"]
    m2 = mk["mod2_limit"]
    lines += [
        "",
        "## 5. Mod 0 vs Mod 1 vs Mod 2 (Birincil + Tüm Domain Kapıları Açık, `2.0 ATR` Brüt R)",
        "",
        f"- **Mod 0 (Bloksuz baz):** N={mk['mod0_birincil_ok']['n']}, Ort R={mk['mod0_birincil_ok']['ort']} `[{mk['mod0_birincil_ok']['ci95_alt']}, {mk['mod0_birincil_ok']['ci95_ust']}]`",
        f"- **Mod 1 (Blok kenarına stop):** N={mk['mod1_birincil_ok']['n']}, Ort R={mk['mod1_birincil_ok']['ort']} `[{mk['mod1_birincil_ok']['ci95_alt']}, {mk['mod1_birincil_ok']['ci95_ust']}]` (değişen N={mk['mod1_blok_degisen_alt']['n_degisen']})",
        f"- **Mod 2 (Min risk >=0.35 ATR & >=0.50 ATR blok):** Uygun={m2['uygun_aday_n']}, Dolan={m2['dolan_n']} (`{m2['dolum_orani']:.1%}`), Ort R={m2['mod2_dolan_sadece_r']['ort']} vs Mod 0 eş küme={m2['mod0_ayni_uygun_kume_r']['ort']}",
    ]

    lines += [
        "",
        "## 6. Duyarlılık (`tampon` & `H`, Birincil + Tüm Domain Kapıları, `2.0 ATR` Brüt R)",
        "",
        "| Tampon | H | Dönem | N | Ort R | Küme %95 GA |",
        "|---:|---:|---|---:|---:|---|",
    ]
    for r in ozet["duyarlilik"]:
        lines.append(f"| {r['tampon_atr']} | {r['ufuk_bar']} | {r['donem']} | {r['n']} | {r['ort']} | [{r['ci95_alt']}, {r['ci95_ust']}] |")

    (cikti_dir / "RAPOR_GOLGE_V2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sembol_onbellekli_isle(sembol: str, cache_dir: Path | None, *, tfs: tuple[str, ...]) -> dict[str, Any]:
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cpath = cache_dir / f"{sembol}.pkl.gz"
        if cpath.exists():
            with gzip.open(cpath, "rb") as f:
                return pickle.load(f)
        res = _sembol_is_isle(sembol, tfs=tfs)
        with gzip.open(cpath, "wb") as f:
            pickle.dump(res, f, protocol=pickle.HIGHEST_PROTOCOL)
        return res
    return _sembol_is_isle(sembol, tfs=tfs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 araştırma çalıştırıcısı")
    ap.add_argument("--evren", choices=("evren176", "hisse174"), default="evren176")
    ap.add_argument("--tfs", nargs="+", default=list(TF_LISTESI))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--sadece-hesapla", action="store_true", help="Yalnız önbelleği doldurur, toplu rapor yazmaz")
    ap.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    args = ap.parse_args(argv)

    tfs = tuple(args.tfs)
    tum_semboller = _evren_oku(args.evren, args.limit)
    secili = tum_semboller[args.start : args.end]
    t0 = time.perf_counter()
    mod0_all: list[dict[str, Any]] = []
    mod1_all: list[dict[str, Any]] = []
    mod2_all: list[dict[str, Any]] = []
    duy_all: list[dict[str, Any]] = []
    hatalar: list[dict[str, Any]] = []

    if args.workers <= 1:
        for i, sym in enumerate(secili, 1):
            res = _sembol_onbellekli_isle(sym, args.cache_dir, tfs=tfs)
            if not args.sadece_hesapla:
                mod0_all.extend(res["mod0"])
                mod1_all.extend(res["mod1"])
                mod2_all.extend(res["mod2"])
                duy_all.extend(res["duyarlilik"])
                hatalar.extend(res["hatalar"])
            if i % 10 == 0 or i == len(secili):
                print(f"[{i}/{len(secili)}] {sym} ({res['elapsed']}s)", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_sembol_onbellekli_isle, sym, args.cache_dir, tfs=tfs): sym for sym in secili}
            done = 0
            for fut in as_completed(futs):
                done += 1
                res = fut.result()
                if not args.sadece_hesapla:
                    mod0_all.extend(res["mod0"])
                    mod1_all.extend(res["mod1"])
                    mod2_all.extend(res["mod2"])
                    duy_all.extend(res["duyarlilik"])
                    hatalar.extend(res["hatalar"])
                if done % 10 == 0 or done == len(secili):
                    print(f"[{done}/{len(secili)}] {res['sembol']} ({res['elapsed']}s)", flush=True)

    sure_sn = time.perf_counter() - t0
    if args.sadece_hesapla:
        print(f"Onbellek tamamlandi: {len(secili)} sembol ({sure_sn:.1f}s)", flush=True)
        return 0

    df0 = pd.DataFrame(mod0_all)
    df1 = pd.DataFrame(mod1_all)
    df2 = pd.DataFrame(mod2_all)
    df_duy = pd.DataFrame(duy_all)
    ozet = _rapor_olustur(df0, df1, df2, df_duy, hatalar, args.cikti, sure_sn, len(secili))
    _markdown_ozet_yaz(ozet, args.cikti)
    print(f"Tamamlandi ({sure_sn:.1f}s) -> {args.cikti} | Karar: {ozet['meta']['karar']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
