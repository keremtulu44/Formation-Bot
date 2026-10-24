# -*- coding: utf-8 -*-
"""Aşama 4 · Kalibrasyon (H4): hücre taban oranları gerçeği tutuyor mu?

SALT OKUNUR. Ön kayıt: docs/arastirma/PUAN_DOGRULAMA_ON_KAYIT.md

Yöntem: **walk-forward**. Her gözlem için tahmin, YALNIZCA o tarihten en az
1 hafta önce kapanmış gözlemlerden hesaplanır (24 barlık etiket penceresinin
sızmaması için). Hücreler ön kayıtta tanımlı: TF × endeks uyumu × likidite.

Kabul barı (H4): her hücrede |gözlenen − tahmin| ≤ 5 puan VE Brier skoru sabit
tahminciden düşük.

Kullanım:
    python scripts/kalibrasyon.py --girdi var/replay/gozlemler177.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402
from puan_sorular import likidite_tablosu  # noqa: E402


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aşama 4 kalibrasyon")
    ap.add_argument("--girdi", default="var/replay/gozlemler177.csv")
    ap.add_argument("--rapor", default="var/replay/kalibrasyon.md")
    ap.add_argument("--gecikme-gun", type=int, default=7)
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi)
    d = d[d.pencere_tam == 1].copy()
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["zaman"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].sort_values("tarih").reset_index(drop=True)

    d["uyum"] = np.where(np.sign(d.yon) == np.sign(d.endeks_egim), "uyumlu",
                         np.where(np.sign(d.yon) == -np.sign(d.endeks_egim), "uyumsuz", "düz"))
    lik = likidite_tablosu()
    d = d.merge(lik, on="sembol", how="left")
    kes = d.hacim_tl.median()
    d["likidite"] = np.where(d.hacim_tl >= kes, "üst", "alt")
    d["hucre"] = d.tf + "|" + d.uyum + "|" + d.likidite

    # --- walk-forward tahmin
    gecikme = pd.Timedelta(days=args.gecikme_gun)
    tahmin = np.full(len(d), np.nan)
    for i in range(len(d)):
        t = d.tarih.iloc[i]
        gecmis = d[(d.tarih <= t - gecikme)]
        if len(gecmis) < 200:
            continue
        hucre = d.hucre.iloc[i]
        h = gecmis[gecmis.hucre == hucre]
        genel = float(gecmis.y.mean())
        # hücre verisi azsa genel orana yumuşat (prior ağırlığı 20)
        n = len(h)
        tahmin[i] = (h.y.sum() + 20.0 * genel) / (n + 20.0)
    d["tahmin"] = tahmin
    gecerli = d[d.tahmin.notna()].copy()

    out = ["# Aşama 4 · Kalibrasyon\n",
           f"Gözlem {len(d)} · tahmin üretilebilen {len(gecerli)} · "
           f"hücre sayısı {d.hucre.nunique()}\n"]

    if len(gecerli) < 100:
        out.append("Yeterli gözlem yok.")
        metin = "\n".join(out)
        print(metin)
        return 1

    brier = float(np.mean((gecerli.tahmin - gecerli.y) ** 2))
    taban = float(gecerli.y.mean())
    brier_sabit = float(np.mean((taban - gecerli.y) ** 2))

    out.append("## Genel\n")
    out.append(f"- Brier (hücre tahmini): **{brier:.4f}**")
    out.append(f"- Brier (sabit tahmin %{taban*100:.1f}): {brier_sabit:.4f}")
    out.append(f"- Fark: {brier_sabit - brier:+.4f} "
               f"({'hücre tahmini daha iyi' if brier < brier_sabit else 'sabit tahmin daha iyi'})\n")

    # --- güvenilirlik tablosu (tahmin dilimleri)
    gecerli["dilim"] = pd.cut(gecerli.tahmin, [0, .30, .34, .38, .42, .50, 1.0],
                              labels=["<30%", "30-34%", "34-38%", "38-42%", "42-50%", ">50%"])
    out.append("## Güvenilirlik (tahmin dilimi → gözlenen)\n")
    out.append("| tahmin dilimi | n | ortalama tahmin | gözlenen | fark |")
    out.append("|---|---|---|---|---|")
    en_buyuk = 0.0
    for k, g in gecerli.groupby("dilim", observed=True):
        if len(g) < 30:
            continue
        f = (g.y.mean() - g.tahmin.mean()) * 100
        en_buyuk = max(en_buyuk, abs(f))
        out.append(f"| {k} | {len(g)} | %{g.tahmin.mean()*100:.1f} | "
                   f"%{g.y.mean()*100:.1f} | {f:+.1f} puan |")

    out.append("\n## Hücre tablosu (walk-forward)\n")
    out.append("| hücre | n | tahmin | gözlenen | fark |")
    out.append("|---|---|---|---|---|")
    for h, g in gecerli.groupby("hucre"):
        if len(g) < 50:
            continue
        f = (g.y.mean() - g.tahmin.mean()) * 100
        out.append(f"| {h} | {len(g)} | %{g.tahmin.mean()*100:.1f} | "
                   f"%{g.y.mean()*100:.1f} | {f:+.1f} |")

    # --- karttaki %76 iddiası
    out.append("\n## Kart iddiası\n")
    out.append(f"Kartta yazan: %76 · ölçülen taban: %{taban*100:.1f} · "
               f"fark: {(taban-0.76)*100:+.1f} puan\n")

    karar = "GEÇTİ" if (brier < brier_sabit and en_buyuk <= 5.0) else "KALDI"
    out.append(f"Ön kayıt barı (Brier daha iyi ve her hücrede sapma ≤ 5 puan): **{karar}**")
    out.append(f"(En büyük dilim sapması: {en_buyuk:.1f} puan)")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
