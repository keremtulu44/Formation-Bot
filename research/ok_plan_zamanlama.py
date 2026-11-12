"""§13 ön-kayıdı: giriş-zamanlaması — K1/K2▲ oku plandan önce son5 barda var mı?

Salt-okunur: üretim koduna dokunmaz; `evaluate_stabil_symbol` + `denetle`
çıktısını plan_sonuc.csv ile eşler, keşif/doğrulama kırılımında raporlar.
Ön-kayıt: FAZ9_PLAN_VE_SONUCLAR.md §13 + §13.4 (pencere = planın kendi
TF'inde5 bar; ok akışı =4h kanonu).

Kullanım:
    PYTHONPATH=. python research/ok_plan_zamanlama.py [--plan <csv>] [--cikti <dir>]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd

from data import resample_ohlcv
from domain_engines.stabil.runtime import evaluate_stabil_symbol
from research.stabil_ok_denetimi import denetle

ROOT = Path(__file__).resolve().parents[1]
VARSAYILAN_PLAN = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
                   "faz9d_baz_176/olcum/plan_sonuc.csv")
VARSAYILAN_CIKTI = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
                    "ok_plan_zamanlama")
PENCERE = 5  # §13.2: giriş barı + önceki4 (planın kendi TF'inde — §13.4)


def _utc_serit(x):
    t = pd.Timestamp(x)
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


def sembol_verisi(sembol: str) -> tuple[set[pd.Timestamp], dict[str, list[pd.Timestamp]]]:
    """K1/K2 ok zamanları (4h kanonu) + TF başına bar zamanları."""
    d = (pd.read_csv(ROOT / f"backfill_data/{sembol}_1d.csv.gz",
                     compression="gzip", parse_dates=["bar_time"])
         .set_index("bar_time").reset_index()
         .rename(columns={"bar_time": "timestamp"}))
    h = (pd.read_csv(ROOT / f"backfill_data/{sembol}_1h.csv.gz",
                     compression="gzip", parse_dates=["bar_time"])
         .set_index("bar_time"))
    h4 = (resample_ohlcv(h, "4h").reset_index()
          .rename(columns={"bar_time": "timestamp"}))
    out = evaluate_stabil_symbol(sembol, "4h", h4,
                                 daily_frame=d, h4_frame=h4)
    oklar = {_utc_serit(k.bar_close_time) for k in denetle(out.bar_behaviors)
             if k.kural_adi in ("K1", "K2")}
    h2 = resample_ohlcv(h, "2h").reset_index()
    stamps = {
        "1h": [_utc_serit(t) for t in h.index],
        "2h": [_utc_serit(t) for t in h2["bar_time"]],
        "4h": [_utc_serit(t) for t in h4["timestamp"]],
        "1d": [_utc_serit(t) for t in d["timestamp"]],
    }
    return oklar, stamps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(VARSAYILAN_PLAN))
    ap.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    args = ap.parse_args()
    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)

    planlar = list(csv.DictReader(open(args.plan, encoding="utf-8")))
    semboller = sorted({p["sembol"] for p in planlar})
    print(f"plan={len(planlar)} sembol={len(semboller)}", flush=True)

    harita: dict[str, tuple[set, dict]] = {}
    t0 = time.time()
    for i, s in enumerate(semboller, 1):
        for _ in range(3):
            try:
                harita[s] = sembol_verisi(s)
                break
            except Exception as hata:
                harita[s] = (set(), {})
                son_hata = hata
        else:
            print(f"  {s}: ATLANDI {son_hata!r}", flush=True)
        if i % 20 == 0:
            print(f"  {i}/{len(semboller)} · {time.time()-t0:.0f}s", flush=True)

    satirlar = []
    for p in planlar:
        oklar, stamps = harita.get(p["sembol"], (set(), {}))
        t_plan = _utc_serit(p["t"])
        seri = stamps.get(p["tf"], [])
        idx = None
        for j in range(len(seri) - 1, -1, -1):
            if seri[j] <= t_plan:
                idx = j
                break
        pencere: set = set()
        if idx is not None:
            pencere = set(seri[max(0, idx - PENCERE + 1):idx + 1])
        kesisim = pencere & oklar
        satirlar.append({**p, "ok_var": int(bool(kesisim)),
                         "ok_sayi": len(kesisim)})

    with open(cikti / "plan_ok_eslesme.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        w.writeheader()
        w.writerows(satirlar)

    df = pd.DataFrame(satirlar)
    df["pnl"] = df["pnl_atr"].astype(float)
    rapor = []
    for (donem, ok), g in df.groupby(["donem", "ok_var"]):
        n = len(g)
        kaz = int((g["pnl"] > 0).sum())
        kay = g[g["pnl"] < 0]["pnl"].sum()
        poz = g[g["pnl"] > 0]["pnl"].sum()
        rapor.append({
            "donem": donem, "ok_var": int(ok), "n": n,
            "karli_yuzde": round(100 * kaz / n, 1) if n else None,
            "net_atr": round(float(g["pnl"].sum()), 2),
            "PF": round(float(poz / abs(kay)), 2) if kay else None,
            "stop_orani": round(100 * float((g["sonuc"] == "stop").sum()) / n, 1)
            if n else None,
            "beklenti_atr": round(float(g["pnl"].mean()), 4) if n else None,
        })
    ozet = {"ozellik": "K1/K2▲ (4h kanonu), pencere=plan TF'inde5 bar (§13.4)",
            "pencere": PENCERE, "plan_n": int(len(df)),
            "ok_var_toplam": int(df["ok_var"].sum()),
            "gruplar": rapor}
    (cikti / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))

    def karli(donem, ok):
        return next((x for x in rapor if x["donem"] == donem
                     and x["ok_var"] == ok), None)
    kr, ko = karli("kesif", 1), karli("kesif", 0)
    dr, do = karli("dogrulama", 1), karli("dogrulama", 0)
    if all(x and x["n"] >= 100 for x in (kr, ko, dr, do)):
        yon = kr["karli_yuzde"] > ko["karli_yuzde"]
        fark = dr["karli_yuzde"] - do["karli_yuzde"]
        kabul = yon and fark >= 10.0
        print(f"KESIF: var {kr['karli_yuzde']} vs yok {ko['karli_yuzde']} → "
              f"{'aynı yön' if yon else 'TERS YÖN'}")
        print(f"DOGRULAMA fark: {fark:+.1f} puan (≥+10) → "
              f"{'KABUL' if kabul else 'RED'}")
    else:
        print("n YETERSİZ (her grup×dönem ≥100) — HÜKÜM YOK")
    print(f"yazıldı: {cikti}/plan_ok_eslesme.csv, ozet.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
