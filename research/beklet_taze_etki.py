"""§18 BEKLE etki ölçümü — as-of taze-ok (≤60dk) filtresi.

Ön-kayıt: FAZ9 §18 (eşik60dk sonuçla değişmez; okuma ≥15pp iki dönem aynı yön).
Özellik: son_ok_asof_dk = plandan geriye doğru en son K1/K2/U1 ok'u (dakika,
yalnız geçmiş — as-of). Filtre: ≤60dk ise plan BEKLE'ye düşer (plan katmanı;
tetik/kör baz değişmez).

Çıktı: etki.json + konsol tablosu (K1–K6 + net, filtresiz vs filtreli).
K4/K5 defter kaynaklıdır; bu ölçümde K5=0 (filtre ihlal ekleyemez), K4
"zincir koşusunda" notuyla raporlanır.

Kullanım: PYTHONPATH=. python research/beklet_taze_etki.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from research.golge_kapi import kapi_degerlendir
from research.harita_giris_zamanlama import sembol_verisi

ROOT = Path(__file__).resolve().parents[1]
PLAN_YOL = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
            "faz9d_baz_176/olcum/plan_sonuc.csv")
KOR_OLCUM = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
             "faz9d_baz_176/olcum/olcum_ozet.json")
CIKTI = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
         "beklet_taze_ok/etki.json")
ESIK_DK = 60.0  # §18.1 — sonuçla değişmez


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


def kosullu(df: pd.DataFrame) -> float | None:
    sayim = df["sonuc"].value_counts()
    h, s = int(sayim.get("hedef", 0)), int(sayim.get("stop", 0))
    return round(100 * h / (h + s), 2) if h + s > 0 else None


def beklenti(df: pd.DataFrame) -> float | None:
    coz = df[df["sonuc"].isin(["hedef", "stop", "zaman"])]
    return round(float(coz["pnl_atr"].mean()), 4) if len(coz) else None


def kapi_girdisi_hesap(planlar: pd.DataFrame, kor_kos: float | None) -> dict:
    dog = planlar[planlar["donem"] == "dogrulama"]
    kes = planlar[planlar["donem"] == "kesif"]
    uyk = kosullu(dog)
    return {
        "K1_dogrulama_uygun_n": int(len(dog)),
        "K2_kor_farki_puan": (round(uyk - kor_kos, 2)
                              if (uyk is not None and kor_kos is not None)
                              else None),
        "K2_uygun_kosullu": uyk,
        "K2_kor_kosullu": kor_kos,
        "K3_dogrulama_beklenti": beklenti(dog),
        "K4_g1_kapali_plan_orani": None,  # defter kaynaklı — zincir koşusunda
        "K5_ret_sonrasi_plan_ihlal": 0,   # filtre ihlal ekleyemez (kaldırma)
        "K6_kesif_beklenti": beklenti(kes),
        "K6_dogrulama_beklenti": beklenti(dog),
    }


def main() -> int:
    df = pd.read_csv(PLAN_YOL).sort_values("t").reset_index(drop=True)
    df["t_utc"] = pd.to_datetime(df["t"], utc=True)
    kor = json.loads(KOR_OLCUM.read_text(encoding="utf-8"))
    kor_kos = kor["kapi_girdisi"].get("K2_kor_kosullu")

    # as-of son ok yaşı (dakika)
    oklar: dict[str, list[pd.Timestamp]] = {}
    semboller = sorted(df["sembol"].unique())
    for n, s in enumerate(semboller, 1):
        _, ok_set, _ = sembol_verisi(s)
        oklar[s] = sorted(ok_set)
        if n % 40 == 0:
            print(f"  ok verisi {n}/{len(semboller)}", flush=True)

    yaslar = []
    for _, p in df.iterrows():
        gecmis = [o for o in oklar.get(p["sembol"], []) if o <= p["t_utc"]]
        yaslar.append((p["t_utc"] - max(gecmis)).total_seconds() / 60.0
                      if gecmis else None)
    df["son_ok_asof_dk"] = yaslar
    df["taze"] = df["son_ok_asof_dk"].notna() & (df["son_ok_asof_dk"] <= ESIK_DK)
    print(f"plan {len(df)} | as-of ok yok {df['son_ok_asof_dk'].isna().sum()} | "
          f"taze(≤{ESIK_DK:.0f}dk) {int(df.taze.sum())} "
          f"({df.taze.mean()*100:.1f}%)")

    # §18.2 okuma: kâr oranı taze vs değil — iki dönem
    okuma = {}
    for d in ("kesif", "dogrulama"):
        s = df[df.donem == d]
        t, k = s[s.taze], s[~s.taze]
        kt = t["pnl_atr"].gt(0).mean() * 100 if len(t) else None
        kk = k["pnl_atr"].gt(0).mean() * 100 if len(k) else None
        okuma[d] = {
            "taze_n": int(len(t)), "degil_n": int(len(k)),
            "kar_taze_yuzde": round(kt, 1) if kt is not None else None,
            "kar_degil_yuzde": round(kk, 1) if kk is not None else None,
            "fark_pp": round(kk - kt, 1) if (kt is not None and kk is not None) else None,
            "net_taze": round(float(t["pnl_atr"].sum()), 1),
            "net_degil": round(float(k["pnl_atr"].sum()), 1),
        }
    kf, df_ = okuma["kesif"]["fark_pp"], okuma["dogrulama"]["fark_pp"]
    sinyal = (kf is not None and df_ is not None
              and kf >= 15.0 and df_ >= 15.0 and (kf > 0) == (df_ > 0))
    print("\n§18.2 okuma (kâr oranı, değil−taze):")
    for d, o in okuma.items():
        print(f"  {d}: taze n{o['taze_n']} kâr%{o['kar_taze_yuzde']} | "
              f"değil n{o['degil_n']} kâr%{o['kar_degil_yuzde']} → "
              f"fark {o['fark_pp']}pp | net taze {o['net_taze']} / değil {o['net_degil']}")
    print(f"  SİNYAL: {'VAR' if sinyal else 'YOK'} (≥15pp iki dönem + aynı yön)")

    # K1–K6 etkisi
    girdi_f = kapi_girdisi_hesap(df, kor_kos)
    girdi_l = kapi_girdisi_hesap(df[~df.taze], kor_kos)
    karar_f, karar_l = kapi_degerlendir(girdi_f), kapi_degerlendir(girdi_l)
    print("\nK1–K6 etkisi (filtresiz → ≤60dk BEKLE):")
    for kod in ("K1_dogrulama_uygun_n", "K2_kor_farki_puan",
                "K3_dogrulama_beklenti", "K6_kesif_beklenti",
                "K6_dogrulama_beklenti"):
        print(f"  {kod}: {girdi_f.get(kod)} → {girdi_l.get(kod)}")
    print(f"  kapı: {karar_f['karar']} ({karar_f['gecen']}/{karar_f['toplam_esik']}) → "
          f"{karar_l['karar']} ({karar_l['gecen']}/{karar_l['toplam_esik']})")
    print(f"  net: kesif {df[df.donem=='kesif'].pnl_atr.sum():.1f} → "
          f"{df[(df.donem=='kesif') & ~df.taze].pnl_atr.sum():.1f} | "
          f"dogrulama {df[df.donem=='dogrulama'].pnl_atr.sum():.1f} → "
          f"{df[(df.donem=='dogrulama') & ~df.taze].pnl_atr.sum():.1f}")

    cikti = {
        "onkayit": "FAZ9 §18 (bceb2cb) — eşik60dk, as-of, dakika",
        "esik_dk": ESIK_DK,
        "plan_n": int(len(df)),
        "taze_n": int(df.taze.sum()),
        "asof_ok_yok_n": int(df["son_ok_asof_dk"].isna().sum()),
        "okuma": okuma,
        "sinyal_var": bool(sinyal),
        "kapi_girdisi_filtresiz": girdi_f,
        "kapi_girdisi_filtreli": girdi_l,
        "karar_filtresiz": karar_f,
        "karar_filtreli": karar_l,
        "k4_not": "K4 defter kaynaklı; zincir koşusunda doğrulanacak. K5 filtreyle0 kalır.",
        "net_kesif": {"filtresiz": round(float(df[df.donem=='kesif'].pnl_atr.sum()), 1),
                      "filtreli": round(float(df[(df.donem=='kesif') & ~df.taze].pnl_atr.sum()), 1)},
        "net_dogrulama": {"filtresiz": round(float(df[df.donem=='dogrulama'].pnl_atr.sum()), 1),
                          "filtreli": round(float(df[(df.donem=='dogrulama') & ~df.taze].pnl_atr.sum()), 1)},
    }
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(cikti, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\nyazıldı: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
