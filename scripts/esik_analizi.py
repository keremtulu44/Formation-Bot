# -*- coding: utf-8 -*-
"""Eşik analizi — geometri tabanı ne kadar aşağı inebilir?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/taban_2_1_24.csv`

Önemli ayrım: `ALERT_MIN_QUALITY` (1h 80 · 2h 78 · 4h 75 · 1d 70) **motorun**
değil **bildirim katmanının** eşiği (main.py:2951). Motor bütün kırılımları
üretiyor; replay de onların hepsini görüyor. Yani arşivde eşiğin altında kalan
kırılımlar da var ve "eşiği düşürürsek ne gelir" sorusu **yeniden oynatmadan**
cevaplanabilir.

Ölçüm:
1. Kalite dağılımı (TF bazında, mevcut eşiğin altı/üstü).
2. Kalite kovası başına fazla (eşleştirilmiş rastgele tabana göre) + sembol GA.
3. Eşik senaryoları: mevcut, −5, −10, −15. Her senaryoda eklenen grubun
   fazlası ve uyarı hacmindeki artış.

Karar kuralı (doküman 3.3): eklenen grubun fazlası +1,0 puanın altındaysa eşik
düşürülmez; üstündeyse düşürülebilir.

Kullanım:
    python scripts/esik_analizi.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402

ESIK = {"1h": 80, "2h": 78, "4h": 75, "1d": 70}


def ga(seri: pd.Series, tekrar: int = 1200, rng=None):
    v = seri.dropna().to_numpy()
    if len(v) < 15:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng(5)
    idx = rng.integers(0, len(v), (tekrar, len(v)))
    o = v[idx].mean(axis=1) * 100
    return float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Eşik analizi")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/esik.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()

    r = pd.read_csv(REPO / "var/replay/taban_2_1_24.csv")
    t = r.groupby(["sembol", "tf", "ay", "yon"]).agg(n=("n", "sum"), b=("basari", "sum")).reset_index()
    t["taban"] = t.b / t.n
    t.loc[t.n < 30, "taban"] = np.nan
    yed = r.groupby(["sembol", "tf", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))
    yed["taban_y"] = yed.b / yed.n
    d = d.merge(t[["sembol", "tf", "ay", "yon", "taban"]], on=["sembol", "tf", "ay", "yon"],
                how="left").merge(yed[["taban_y"]], on=["sembol", "tf", "yon"], how="left")
    d["taban"] = d.taban.fillna(d.taban_y)
    d = d[d.taban.notna()].reset_index(drop=True)
    d["fazla"] = d.y - d.taban
    d["esik"] = d.tf.map(ESIK)
    d["gecti"] = d.kalite >= d.esik

    out = ["# Eşik analizi — geometri tabanı ne kadar kaba olabilir?\n",
           f"gözlem {len(d)} · ortalama fazla {d.fazla.mean()*100:+.1f} puan · "
           f"ortalama kalite {d.kalite.mean():.1f}\n"]

    out.append("\n## 1. Kalite dağılımı\n")
    out.append("| TF | eşik | n | geçen | geçen % | medyan kalite | min |")
    out.append("|---|---|---|---|---|---|---|")
    for tf, g in d.groupby("tf"):
        out.append(f"| {tf} | {ESIK.get(tf, '')} | {len(g)} | {int(g.gecti.sum())} | "
                   f"%{g.gecti.mean()*100:.0f} | {g.kalite.median():.1f} | {g.kalite.min():.1f} |")
    out.append(f"| **tümü** | — | {len(d)} | {int(d.gecti.sum())} | "
               f"%{d.gecti.mean()*100:.0f} | {d.kalite.median():.1f} | {d.kalite.min():.1f} |")

    out.append("\n## 2. Kalite kovası ve fazla (eşiğin altı dahil)\n")
    out.append("| kalite | n | geçen oranı | ham devam | fazla | %95 GA (sembol) |")
    out.append("|---|---|---|---|---|---|")
    d["kova"] = pd.cut(d.kalite, [0, 55, 60, 65, 70, 75, 80, 85, 101])
    for k, g in d.groupby("kova", observed=True):
        s = g.groupby("sembol").fazla.mean()
        lo, hi = ga(s)
        out.append(f"| {k} | {len(g)} | %{g.gecti.mean()*100:.0f} | %{g.y.mean()*100:.1f} | "
                   f"**{g.fazla.mean()*100:+.1f}** | [{lo:+.1f}, {hi:+.1f}] |")

    out.append("\n## 3. Eşik senaryoları\n")
    out.append("`eklenen` = düşürülen eşikle içeri girecek, bugün girmeyen kırılımlar.\n")
    out.append("| senaryo | uyarı sayısı | artış | eklenenin fazlası | %95 GA | eklenen ham devam |")
    out.append("|---|---|---|---|---|---|")
    baz = int(d.gecti.sum())
    for dus in (0, 5, 10, 15, 20):
        esik2 = d.esik - dus
        yeni = d.kalite >= esik2
        gecen = int(yeni.sum())
        ek = d[yeni & ~d.gecti]
        if dus == 0:
            out.append(f"| mevcut | {gecen} | — | — | — | — |")
            continue
        if len(ek) < 30:
            out.append(f"| −{dus} | {gecen} | %{(gecen/baz-1)*100:+.0f} | (n={len(ek)}, yetersiz) | — | — |")
            continue
        s = ek.groupby("sembol").fazla.mean()
        lo, hi = ga(s)
        out.append(f"| −{dus} | {gecen} | %{(gecen/baz-1)*100:+.0f} | "
                   f"**{ek.fazla.mean()*100:+.1f}** | [{lo:+.1f}, {hi:+.1f}] | %{ek.y.mean()*100:.1f} |")

    out.append("\n## 4. Bant bazında (puan bantları, bilgi)\n")
    d["bant"] = pd.cut(d.kalite, [0, 70, 80, 90, 101], labels=["<70", "70-80", "80-90", "90+"])
    out.append("| kalite bandı | n | fazla | kama oranı | ortalama fazla (kama) | ortalama fazla (üçgen) |")
    out.append("|---|---|---|---|---|---|")
    for b, g in d.groupby("bant", observed=True):
        k = g[g.aile == "Kama"]
        u = g[g.aile == "Üçgen"]
        out.append(f"| {b} | {len(g)} | {g.fazla.mean()*100:+.1f} | %{(g.aile=='Kama').mean()*100:.0f} | "
                   f"{k.fazla.mean()*100:+.1f} | {u.fazla.mean()*100:+.1f} |")

    # --- 5. taban + puan birlikte: hacim/getiri sınırı
    kama = (d.aile == "Kama").to_numpy(float)
    mes = np.where(d.bant_mesafe_atr <= 0.3, 1.7,
                   np.where(d.bant_mesafe_atr <= 1.0, 0.9,
                            np.where(d.bant_mesafe_atr <= 2.0, 0.0, -1.3)))
    etk = kama * (d.mtf_uyum >= 4).to_numpy(float) * 3.7
    d["puan"] = np.clip(50 + 5 * (np.where(kama > 0, 4.1, -1.9) + etk + mes), 5, 95)

    out.append("\n## 5. Taban + puan birlikte: hacim / getiri sınırı\n")
    out.append("Geometri yalnız kaba taban (junk elenir), hacmi **puan** belirler.\n")
    out.append("| taban | puan eşiği | uyarı | hacim (mevcut=100) | fazla | %95 GA | kapsam |")
    out.append("|---|---|---|---|---|---|---|")
    for taban in (80, 75, 70, 65):
        d["gecer"] = d.kalite >= taban
        for pe in (None, 75, 65, 55):
            m = d.gecer.to_numpy() & (np.ones(len(d), bool) if pe is None else (d.puan >= pe).to_numpy())
            if m.sum() < 100:
                continue
            g = d[m]
            s_ = g.groupby("sembol").fazla.mean()
            lo, hi = ga(s_)
            out.append(f"| {taban} | {'—' if pe is None else pe} | {len(g)} | "
                       f"{len(g)/11384*100:.0f} | **{g.fazla.mean()*100:+.1f}** | "
                       f"[{lo:+.1f}, {hi:+.1f}] | %{len(g)/len(d)*100:.0f} |")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
