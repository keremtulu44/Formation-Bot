"""100 BIST hissesi üzerinde 'Üstüne Çıkış (Geri Alım / Reclaim)' süreci,
grafik minik işareti adayları ve Telegram kartı durum etiketlerinin derin analizi.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd

from research.stabil_replay import (
    build_xu100_regime_lookup,
    replay_single_symbol,
    select_bist_equity_universe,
)


def _enrich(all_cp: pd.DataFrame) -> pd.DataFrame:
    df = all_cp.copy()
    rng = (df["h4_high"] - df["h4_low"]).to_numpy(dtype=float)
    close_pos = np.where(
        rng > 1e-12,
        (df["h4_close"].to_numpy(dtype=float) - df["h4_low"].to_numpy(dtype=float)) / rng,
        0.5,
    )
    df["h4_close_pos"] = close_pos

    atr = df["daily_atr"].to_numpy(dtype=float)
    body_atr = np.where(
        atr > 1e-12,
        (df["h4_close"].to_numpy(dtype=float) - df["h4_open"].to_numpy(dtype=float)) / atr,
        np.nan,
    )
    df["h4_body_atr"] = body_atr

    grp = df.groupby("symbol", sort=False)
    df["prev_support_age"] = grp["bars_since_support"].shift(1).fillna(0).astype(int)
    df["prev_support_level_1"] = grp["support_level"].shift(1)
    df["prev_dist_atr_1"] = grp["dist_atr_4h"].shift(1)
    df["next_dist_atr_1"] = grp["dist_atr_4h"].shift(-1)
    df["next_still_above"] = df["next_dist_atr_1"] >= 0.0

    # Gerçek sabit/aynı destek geri alımı: önceki 4H kapanış destek altında, şimdiki >= 0 ve destek aşağı kaymamış
    df["true_reclaim"] = (
        df["reclaimed_4h_now"].astype(bool)
        & (df["support_delta_4h_atr"].fillna(0.0).abs() <= 1e-6)
    )
    # Güçlü mum tanımı (gövde >= 0.45 günlük ATR veya (gövde >= 0.30 ATR ve 4H bull disp))
    df["strong_body"] = (df["h4_body_atr"] >= 0.45) | (
        (df["h4_body_atr"] >= 0.30) & df["h4_bull_disp"].astype(bool)
    )
    df["clean_close"] = df["h4_close_pos"] >= 0.65
    return df


def _summarize_buckets(
    sub: pd.DataFrame,
    bucket_col: str,
    horizons: tuple[int, ...] = (4, 8, 16),
) -> list[dict[str, Any]]:
    if sub.empty:
        return []
    mid_ts = sub["cp_time"].quantile(0.5)
    rows: list[dict[str, Any]] = []
    for bval, grp in sub.groupby(bucket_col, sort=True):
        if bval is None or (isinstance(bval, float) and math.isnan(bval)) or str(bval) == "":
            continue
        n_events = int(len(grp))
        n_syms = int(grp["symbol"].nunique())
        per_sym_freq = round(n_events / 100.0, 2)
        hold_next = (
            float(grp["next_still_above"].mean())
            if grp["next_dist_atr_1"].notna().any()
            else float("nan")
        )
        race_valid = grp["next_race_24"].dropna()
        sup_dn_24 = float((race_valid == "SUPPORT_DOWN_FIRST").mean()) if len(race_valid) else 0.0
        sup_up_24 = float((race_valid == "SUPPORT_UP_FIRST").mean()) if len(race_valid) else 0.0
        recl_24 = float((race_valid == "PRICE_RECLAIM_FIRST").mean()) if len(race_valid) else 0.0

        h_stats: dict[str, Any] = {}
        for h in horizons:
            valid = grp[(~grp[f"censored_{h}"]) & grp[f"ret_atr_{h}"].notna()]
            if valid.empty:
                h_stats[str(h)] = {"n": 0}
                continue
            rets = valid[f"ret_atr_{h}"].to_numpy(dtype=float)
            mfes = valid[f"mfe_atr_{h}"].to_numpy(dtype=float)
            maes = valid[f"mae_atr_{h}"].to_numpy(dtype=float)
            eq_sym = float(valid.groupby("symbol")[f"ret_atr_{h}"].mean().mean())
            f1 = valid[f"first_1atr_{h}"]
            up1 = float((f1 == "UP_FIRST").mean())
            dn1 = float((f1 == "DOWN_FIRST").mean())
            early = valid[valid["cp_time"] <= mid_ts][f"ret_atr_{h}"]
            late = valid[valid["cp_time"] > mid_ts][f"ret_atr_{h}"]
            h_stats[str(h)] = {
                "n": int(len(valid)),
                "med": round(float(np.median(rets)), 3),
                "mean": round(float(np.mean(rets)), 3),
                "eq_sym": round(eq_sym, 3),
                "mfe_med": round(float(np.median(mfes)), 3),
                "mae_med": round(float(np.median(maes)), 3),
                "pos_pct": round(float((rets > 0).mean() * 100.0), 1),
                "up1_pct": round(up1 * 100.0, 1),
                "dn1_pct": round(dn1 * 100.0, 1),
                "early_med": round(float(early.median()), 3) if len(early) else None,
                "late_med": round(float(late.median()), 3) if len(late) else None,
            }

        rows.append(
            {
                "bucket": str(bval),
                "n_events": n_events,
                "symbols": n_syms,
                "events_per_symbol": per_sym_freq,
                "hold_next_4h_pct": round(hold_next * 100.0, 1) if math.isfinite(hold_next) else None,
                "race_sup_up_pct": round(sup_up_24 * 100.0, 1),
                "race_reclaim_pct": round(recl_24 * 100.0, 1),
                "race_sup_dn_pct": round(sup_dn_24 * 100.0, 1),
                "horizons": h_stats,
            }
        )
    return rows


def evaluate_16_questions(df: pd.DataFrame) -> list[dict[str, Any]]:
    ready = df[df["support_ready"]].copy()
    rcl = ready[ready["true_reclaim"]].copy()
    out: list[dict[str, Any]] = []

    def add_q(qid: str, title: str, sub: pd.DataFrame, col: str, note: str = "") -> None:
        out.append(
            {
                "qid": qid,
                "title": title,
                "note": note,
                "total_n": int(len(sub)),
                "buckets": _summarize_buckets(sub, col),
            }
        )

    # RCL-01: Sarkma Derinliği x Mum Gücü Matrisi
    s = rcl[rcl["reclaimed_prev_depth_atr"].notna()].copy()
    depth_cat = np.where(
        s["reclaimed_prev_depth_atr"] <= 0.5,
        "1_sig_0_0.5ATR",
        np.where(s["reclaimed_prev_depth_atr"] <= 1.2, "2_orta_0.5_1.2ATR", "3_derin_1.2+ATR"),
    )
    pwr_cat = np.where(s["strong_body"], "guclu_mum", "ciliz_mum")
    s["b"] = pd.Series(depth_cat, index=s.index) + "__" + pd.Series(pwr_cat, index=s.index)
    add_q("RCL-01", "Sarkma derinliği × çıkış mumunun gücü birlikte nasıl çalışıyor?", s, "b")

    # RCL-02: Native 0.35 ATR Floor İhlali x Mum Gücü
    s = rcl.copy()
    fl_cat = np.where(s["reclaimed_prev_floor_seen"].astype(bool), "floor_altindan_donus", "floor_ustunde_sig_sarkma")
    pwr_cat = np.where(s["strong_body"], "guclu_mum", "ciliz_mum")
    s["b"] = pd.Series(fl_cat, index=s.index) + "__" + pd.Series(pwr_cat, index=s.index)
    add_q("RCL-02", "0.35 ATR tolerans (floor) üstünde kalıp dönen mi, altına sarkıp (silkeleyip) güçlü dönen mi?", s, "b")

    # RCL-03: Altta Kalma Süresi x Güçlü Çıkış
    s = rcl[rcl["strong_body"]].copy()
    bars = s["reclaimed_prev_bars_4h"].to_numpy(dtype=int)
    s["b"] = np.where(
        bars <= 2,
        "1_hizli_tuzak_1_2_mum",
        np.where(bars <= 6, "2_kisa_3_6_mum", np.where(bars <= 14, "3_orta_7_14_mum", "4_uzun_15+_mum")),
    )
    add_q("RCL-03", "Güçlü geri alımda altta kaç 4H mum kaldığı (hızlı tuzak vs altta yatma) sonucu değiştiriyor mu?", s, "b")

    # RCL-04: Çıkış Mumunun Kapanış Kalitesi (Üst Fitil Reddi vs Tepeye Yakın Kapanış)
    s = rcl.copy()
    cp_pos = s["h4_close_pos"].to_numpy(dtype=float)
    s["b"] = np.where(
        cp_pos >= 0.70,
        "1_tepeye_yakin_kapanis_70%+",
        np.where(cp_pos >= 0.45, "2_orta_kapanis_45_70%", "3_ustten_fitil_yemis_<45%"),
    )
    add_q("RCL-04", "Geri alım mumunun en tepeye yakın kapanması ile üstte fitil bırakması arasındaki fark nedir?", s, "b")

    # RCL-05: Hacim + Gövde Gücü Kombinasyonu
    s = rcl.copy()
    vol = s["h4_volume_pass"].astype(bool)
    sb = s["strong_body"].astype(bool)
    s["b"] = np.where(
        sb & vol,
        "1_guclu_govde_VE_hacimli",
        np.where(sb & (~vol), "2_guclu_govde_hacim_normal", np.where((~sb) & vol, "3_ciliz_govde_ama_hacimli", "4_ciliz_ve_hacimsiz")),
    )
    add_q("RCL-05", "Geri alım mumunda gövde gücü ile hacim (RVOL) birleştiğinde ne oluyor?", s, "b")

    # RCL-06: Çizgi Üstüne Ne Kadar Payla Kapanış Yaptığı
    s = rcl.copy()
    d = s["dist_atr_4h"].to_numpy(dtype=float)
    s["b"] = np.where(
        d < 0.12,
        "1_kil_payi_ustte_0_0.12ATR",
        np.where(d <= 0.50, "2_temiz_kopus_0.12_0.50ATR", "3_cok_uzamis_0.50+ATR"),
    )
    add_q("RCL-06", "Çizginin kıl payı üstünde kapanmak mı, temiz kopuş mu, aşırı uzamak mı?", s, "b")

    # RCL-07: Geri Alınan Çizginin Önceki Yaşı / Düzlüğü
    s = rcl[rcl["episode_known"]].copy()
    age = s["prev_support_age"].to_numpy(dtype=int)
    age_cat = np.where(age >= 16, "uzun_duz_16g+", np.where(age >= 6, "orta_6_15g", "taze_0_5g"))
    pwr_cat = np.where(s["strong_body"], "guclu_mum", "ciliz_mum")
    s["b"] = pd.Series(age_cat, index=s.index) + "__" + pd.Series(pwr_cat, index=s.index)
    add_q("RCL-07", "Öncesinde uzun süredir düz (16g+) olan desteğin geri alınması tepkiyi katlıyor mu?", s, "b")

    # RCL-08: İlk Denemede V-Çıkış vs Altta Birden Çok Deneme Sonrası Kopuş
    s = rcl[rcl["episode_known"] & rcl["strong_body"]].copy()
    s["b"] = np.where(
        s["reclaimed_prev_attempts"] <= 1,
        "1_ilk_denemede_V_kopus",
        "2_basarisiz_denemeler_sonrasi_kopus",
    )
    add_q("RCL-08", "Güçlü geri alımda ilk denemede V-çıkış mı daha iyi, birkaç yoklama sonrası kopuş mu?", s, "b")

    # RCL-09: Kırılmanın Başlangıç Şekli (Sert Panik Kırılması vs Süzülerek Kırılma)
    s = rcl[rcl["strong_body"] & rcl["reclaimed_prev_drop_1bar_atr"].notna()].copy()
    s["b"] = np.where(
        s["reclaimed_prev_drop_1bar_atr"] >= 0.50,
        "1_sert_panik_kirilmasi_sonrasi",
        "2_yumusak_suzulme_sonrasi",
    )
    add_q("RCL-09", "Sert panik mumla kırılıp güçlü geri alınanlar mı daha iyi gidiyor, süzülerek kırılanlar mı?", s, "b")

    # RCL-10: Ertesi 4H Mumda Üstte Kalıcılık (Sahte Geri Alım Filtresi)
    s = rcl[rcl["next_dist_atr_1"].notna()].copy()
    s["b"] = np.where(s["next_still_above"], "1_ertesi_mumda_ustte_kaldi", "2_hemen_ertesi_mumda_alta_dustu")
    add_q("RCL-10", "Geri alımdan hemen sonraki mumda tekrar alta düşen 'sahte çıkışların' oranı ve etkisi nedir?", s, "b")

    # RCL-11: Günlük / Haftalık Stabil Trend Uyumu x Güçlü Geri Alım
    s = rcl[rcl["strong_body"]].copy()
    up_macro = (s["weekly_state"] == "UP") | (s["daily_trend_state"] == "UP")
    s["b"] = np.where(up_macro, "1_ust_trend_YUKARI_uyumlu", "2_ust_trend_ZAYIF_veya_DUSUS")
    add_q("RCL-11", "Güçlü geri alım olurken günlük/haftalık ana trend yukarıysa fark yaratıyor mu?", s, "b")

    # RCL-12: Endeks (XU100) Rejimi x Güçlü Geri Alım
    s = rcl[rcl["strong_body"] & s["xu100_regime"].isin(["XU100_ABOVE_EMA34", "XU100_BELOW_EMA34"])].copy()
    s["b"] = s["xu100_regime"]
    add_q("RCL-12", "Güçlü geri alım hem endeks güçlü (XU100>EMA34) hem zayıfken çalışıyor mu?", s, "b")

    # RCL-13: GRAFİK MİNİK İŞARETİ — 5 Aday Tanımın Sıklık ve Kalite Yarışı
    cand_rows = []
    defs = [
        ("Aday_1_tum_geri_alimlar", rcl.index),
        ("Aday_2_guclu_govdeli_geri_alim", rcl[rcl["strong_body"]].index),
        ("Aday_3_guclu_govde_VE_tepeye_yakin_kapanis", rcl[rcl["strong_body"] & rcl["clean_close"]].index),
        (
            "Aday_4_guclu_govde_VE_hacim_onayli",
            rcl[rcl["strong_body"] & rcl["h4_volume_pass"].astype(bool)].index,
        ),
        (
            "Aday_5_makul_sarkma_<=1.2ATR_guclu_hacimli_temiz",
            rcl[
                (rcl["reclaimed_prev_depth_atr"] <= 1.2)
                & rcl["strong_body"]
                & rcl["clean_close"]
                & rcl["h4_volume_pass"].astype(bool)
            ].index,
        ),
    ]
    for label, idx in defs:
        part = ready.loc[idx].copy()
        part["b"] = label
        cand_rows.append(part)
    s = pd.concat(cand_rows, ignore_index=True)
    add_q(
        "RCL-13",
        "Grafiğe konacak 'minik geri alım işareti' için 5 aday tanımın sıklık ve performans yarışı",
        s,
        "b",
        note="events_per_symbol = 100 hissede ~1.5 yıllık arşivde hisse başına ortalama kaç kez işaret çıktığını gösterir.",
    )

    # RCL-14: TELEGRAM KARTI AKILLI STABIL SATIRLARI — Tüm 107 bin 4H mumun karnesi
    s = ready.copy()
    dist = s["dist_atr_4h"].to_numpy(dtype=float)
    near_touch = (dist >= 0.0) & (dist <= 0.25)
    just_stepped_dn = (dist >= 0.0) & (s["support_delta_4h_atr"].fillna(0.0) < -1e-6)
    long_flat = (dist > 0.25) & (s["bars_since_support"] >= 20)
    strong_recl = s["true_reclaim"] & s["strong_body"] & s["clean_close"]
    weak_recl = s["true_reclaim"] & (~(s["strong_body"] & s["clean_close"]))
    touch_bull_vol = near_touch & (~s["true_reclaim"]) & s["h4_bull_disp"].astype(bool) & s["h4_volume_pass"].astype(bool)
    touch_2nd = near_touch & (~s["true_reclaim"]) & (~touch_bull_vol) & (s["touch_seq"] == 2) & s["episode_known"]
    touch_3plus = near_touch & (~s["true_reclaim"]) & (s["touch_seq"] >= 3) & s["episode_known"]
    touch_other = near_touch & (~s["true_reclaim"]) & (~touch_bull_vol) & (~touch_2nd) & (~touch_3plus)
    below_shallow = (dist < 0.0) & (dist >= -0.50) & (s["bars_since_support"] >= 1)
    below_deep = (dist < -0.50)

    card_label = np.select(
        [
            strong_recl,
            weak_recl,
            just_stepped_dn,
            touch_3plus,
            touch_bull_vol,
            touch_2nd,
            touch_other,
            long_flat,
            dist > 0.25,
            below_shallow,
            below_deep,
        ],
        [
            "01_destek_geri_alindi_(guclu_mum)",
            "02_destek_geri_alindi_(zayif_mum)",
            "03_destek_asagi_kaydi_(pasif_ustte)",
            "04_destekte_(3+_temas_yorulma)",
            "05_destekte_(hacimli_alici)",
            "06_destekte_(2._temas)",
            "07_destekte_(ilk/normal_temas)",
            "08_destek_ustunde_(uzun_yatay)",
            "09_destek_ustunde_(normal)",
            "10_destek_altinda_(sig_sarkma_izleniyor)",
            "11_destek_altinda_(kirik)",
        ],
        default="99_diger",
    )
    s["card_label"] = card_label
    add_q("RCL-14", "Telegram kartı için aday Stabil satırlarının tüm evrendeki (107 bin mum) gerçek karnesi", s, "card_label")

    # RCL-15: Yukarı Yönlü Kırılım / Alıcı Mumlarında (Alarm Anı Benzeri) Kart Etiketleri
    s_alarm = s[s["h4_bull_disp"].astype(bool)].copy()
    add_q("RCL-15", "Yukarı atak / kırılım mumlarında (alarm anı benzeri) kart etiketleri nasıl ayrışıyor?", s_alarm, "card_label")

    # RCL-16: Destek Üstünde Temas Kalitesi (2. Temas + Hacimli Alıcı vs Diğerleri)
    s_touch = s[near_touch & (~s["true_reclaim"]) & s["episode_known"]].copy()
    t_seq = s_touch["touch_seq"].to_numpy(dtype=int)
    hv = s_touch["h4_bull_disp"].astype(bool) & s_touch["h4_volume_pass"].astype(bool)
    s_touch["b"] = np.select(
        [
            (t_seq == 2) & hv,
            (t_seq == 2) & (~hv),
            (t_seq == 1) & hv,
            (t_seq == 1) & (~hv),
            t_seq >= 3,
        ],
        [
            "1_ikinci_temas_VE_hacimli_alici",
            "2_ikinci_temas_normal",
            "3_ilk_temas_VE_hacimli_alici",
            "4_ilk_temas_normal",
            "5_uc_ve_uzeri_temas_(yorulma)",
        ],
        default="diger",
    )
    add_q("RCL-16", "Destek temasında kaçıncı temas olduğu ile 4H hacimli alıcı mumu birleşince ne veriyor?", s_touch, "b")

    return out


def main() -> None:
    t0 = time.perf_counter()
    symbols = select_bist_equity_universe(100)
    xu100_lookup = build_xu100_regime_lookup()
    frames = []
    for sym in symbols:
        res = replay_single_symbol(sym, xu100_lookup=xu100_lookup)
        if not res.checkpoint_df.empty:
            frames.append(res.checkpoint_df)
    all_cp = pd.concat(frames, ignore_index=True)
    enriched = _enrich(all_cp)
    questions = evaluate_16_questions(enriched)
    elapsed = round(time.perf_counter() - t0, 2)

    out_dir = Path("docs/arastirma/stabil_100_sonuclar")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbols_count": len(symbols),
        "total_checkpoints": int(len(enriched)),
        "true_reclaim_events": int(enriched["true_reclaim"].sum()),
        "elapsed_sec": elapsed,
        "questions": questions,
    }
    json_path = out_dir / "STABIL_GERI_ALIM_16_SONUCLAR.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK | symbols={len(symbols)} | cps={len(enriched)} | reclaims={payload['true_reclaim_events']} | elapsed={elapsed}s")


if __name__ == "__main__":
    main()
