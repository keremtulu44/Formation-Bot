# -*- coding: utf-8 -*-
"""Fazla analizi: hangi formasyon trendin üstüne daha çok katıyor?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/rastgele_aylik.csv`

Her kırılım için "fazla" = sonuç − (aynı sembol + TF + ay + yön rastgele tabanı).
Böylece trend/mevsim/yön etkisi çıkar; geriye formasyona ait katkı kalır.

Bu betik fazlayı alt gruplarda kırar: desen, TF, kalite kovası, MTF kademesi,
mesafe, hacim, yaş, saat, gün. Amaç: "hangi formasyon gerçekten daha iyi"
sorusuna, trend etkisinden arındırılmış cevap.

Her hücre için n, fazla (puan) ve sembol kümesi bootstrap %95 GA verilir.

Kullanım:
    python scripts/fazla_analizi.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402


def bootstrap_ga(g: pd.DataFrame, tekrar: int = 400) -> Tuple[float, float]:
    if len(g) < 40:
        return float("nan"), float("nan")
    rng = np.random.default_rng(3)
    gruplar = [x.fazla.to_numpy() for _, x in g.groupby("sembol")]
    if len(gruplar) < 5:
        return float("nan"), float("nan")
    deger = []
    for _ in range(tekrar):
        sec = rng.integers(0, len(gruplar), len(gruplar))
        deger.append(np.concatenate([gruplar[i] for i in sec]).mean() * 100)
    return float(np.percentile(deger, 2.5)), float(np.percentile(deger, 97.5))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Fazla analizi")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--taban", default="var/replay/rastgele_aylik.csv")
    ap.add_argument("--rapor", default="var/replay/fazla.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].copy()
    d["ay"] = d.tarih.dt.to_period("M").astype(str)

    r = pd.read_csv(REPO / args.taban)
    anahtar = ["sembol", "tf", "ay", "yon"]
    tab = r.groupby(anahtar).agg(n_r=("n", "sum"), b_r=("basari", "sum")).reset_index()
    tab["taban"] = tab.b_r / tab.n_r
    tab.loc[tab.n_r < 30, "taban"] = np.nan
    yedek = r.groupby(["sembol", "tf", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))
    yedek["taban_yedek"] = yedek.b / yedek.n

    d = d.merge(tab[anahtar + ["taban"]], on=anahtar, how="left")
    d = d.merge(yedek[["taban_yedek"]], on=["sembol", "tf", "yon"], how="left")
    d["taban"] = d["taban"].fillna(d["taban_yedek"])
    d = d[d.taban.notna()].copy()
    d["fazla"] = d.y - d.taban

    out = ["# Fazla analizi — formasyonun trend üstü katkısı\n",
           f"gözlem {len(d)} · ortalama fazla {d.fazla.mean()*100:+.1f} puan · "
           f"taban (rastgele) %{d.taban.mean()*100:.1f}\n"]

    def tablo(baslik: str, kolon: str, etiketler: Optional[List[str]] = None) -> None:
        out.append(f"\n## {baslik}\n")
        out.append("| grup | n | ham devam | fazla | %95 GA |")
        out.append("|---|---|---|---|---|")
        for k, g in d.groupby(kolon, observed=True):
            if len(g) < 100:
                continue
            lo, hi = bootstrap_ga(g)
            out.append(f"| {k} | {len(g)} | %{g.y.mean()*100:.1f} | "
                       f"**{g.fazla.mean()*100:+.1f}** | [{lo:+.1f}, {hi:+.1f}] |")

    tablo("Desen tipi", "desen")
    tablo("Aile", "aile")
    tablo("Zaman dilimi", "tf")
    d["kalite_k"] = pd.qcut(d.kalite, 5, labels=["1 (düşük)", "2", "3", "4", "5 (yüksek)"])
    tablo("Kalite kovası", "kalite_k")
    tablo("MTF uyum kademesi", "mtf_uyum")
    d["mesafe_k"] = pd.cut(d.bant_mesafe_atr, [-0.01, 0.3, 1.0, 2.0, 100],
                           labels=["≤0,3 ATR", "0,3-1", "1-2", ">2"])
    tablo("Seviyeye mesafe", "mesafe_k")
    d["hacim_k"] = pd.qcut(d.hacim_orani.fillna(d.hacim_orani.median()), 4,
                           labels=["Q1", "Q2", "Q3", "Q4"])
    tablo("Kırılım hacmi kovası", "hacim_k")
    d["yas_k"] = pd.cut(d.bar - d.dogum_bar, [0, 3, 6, 12, 30, 10000],
                        labels=["1-3 bar", "4-6", "7-12", "13-30", "30+"])
    tablo("Formasyon yaşı", "yas_k")
    d["saat_k"] = pd.cut(d.seans_saati, [-0.01, 11, 13, 15, 17, 19],
                         labels=["10-11", "11-13", "13-15", "15-17", "17-18"])
    tablo("Seans saati", "saat_k")

    # --- en iyi / en kötü hücreler (desen × TF)
    out.append("\n## Desen × TF\n")
    out.append("| desen | TF | n | fazla | %95 GA |")
    out.append("|---|---|---|---|---|")
    for (desen, tf), g in d.groupby(["desen", "tf"], observed=True):
        if len(g) < 150:
            continue
        lo, hi = bootstrap_ga(g)
        out.append(f"| {desen} | {tf} | {len(g)} | {g.fazla.mean()*100:+.1f} | "
                   f"[{lo:+.1f}, {hi:+.1f}] |")

    # --- bölme tutarlılığı: en yüksek fazlalı gruplar S ve Z'de
    out.append("\n## Bölme tutarlılığı (desen × TF, S ve Z)\n")
    out.append("| grup | S fazla | Z fazla | n |")
    out.append("|---|---|---|---|")
    d["ds"] = d.sembol.apply(lambda s: __import__("zlib").crc32(s.encode()) % 2)
    kes = d.tarih.quantile(0.7)
    d["z_dogrulama"] = d.tarih > kes
    for (desen, tf), g in d.groupby(["desen", "tf"], observed=True):
        if len(g) < 250:
            continue
        a = g[g.ds == 1].fazla.mean() * 100
        b_ = g[g.z_dogrulama].fazla.mean() * 100
        out.append(f"| {desen} · {tf} | {a:+.1f} | {b_:+.1f} | {len(g)} |")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
