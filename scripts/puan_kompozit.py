# -*- coding: utf-8 -*-
"""Kompozit puan: hayatta kalan özelliklerden puan kur, walk-forward sına.

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv`.

Tasarım kuralları (önceden sabit):
  * Ağırlıklar UYDURULMAZ: seçilen özellikler eşit ağırlıklı, her biri kendi
    yönüne göre yüzdelik sıraya çevrilip toplanır (0-100 puan).
  * Puan her gözlem için YALNIZCA geçmiş veriyle hesaplanır (expanding window,
    en az 500 geçmiş gözlem). Böylece "bugünün puanı bugünün verisini görmez".
  * Ürün ölçüsü: puanın en iyi %X'lik dilimi, taban oranla kıyaslanır.
  * Kıyas tabanı: (a) taban oran, (b) mevcut kalite puanı aynı kapsamda,
    (c) endeks uyumu tek başına.

Kullanım:
    python scripts/puan_kompozit.py --ozellikler "endeks_uyum:1,mtf_uyum:1,hacim_orani:-1"
    python scripts/puan_kompozit.py --kapsam 0.3 --rapor var/replay/kompozit.md
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


def yuzdelik_gecmis(s: pd.Series, min_gecmis: int = 500) -> pd.Series:
    """Her nokta için, o noktaya kadarki geçmişin içindeki yüzdelik sıra."""
    v = s.to_numpy(float)
    n = len(v)
    out = np.full(n, np.nan)
    gecerli_idx = []
    gecerli_val = []
    for i in range(n):
        x = v[i]
        if np.isfinite(x) and len(gecerli_val) >= min_gecmis:
            dizi = np.asarray(gecerli_val)
            out[i] = (dizi < x).mean() * 100.0
        if np.isfinite(x):
            gecerli_idx.append(i)
            gecerli_val.append(x)
    return pd.Series(out, index=s.index)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Kompozit puan")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--ozellikler", default="endeks_uyum:1,mtf_uyum:1,yapi_uyum:1,hacim_orani:-1",
                    help="kolon:yön (1 = yüksek iyi, -1 = düşük iyi)")
    ap.add_argument("--kapsam", type=float, default=0.30)
    ap.add_argument("--rapor", default="var/replay/kompozit.md")
    args = ap.parse_args(argv)

    secim: List[Tuple[str, int]] = []
    for parca in args.ozellikler.split(","):
        kolon, _, yon = parca.partition(":")
        secim.append((kolon.strip(), int(yon) if yon.strip() else 1))

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["zaman"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].sort_values("tarih").reset_index(drop=True)

    # --- puan (yalnızca geçmiş veriyle)
    toplam = np.zeros(len(d))
    sayi = np.zeros(len(d))
    for kolon, yon in secim:
        if kolon not in d:
            print(f"UYARI: {kolon} yok, atlandı")
            continue
        x = d[kolon] * yon
        yuz = yuzdelik_gecmis(x, min_gecmis=300)
        gecerli = yuz.notna()
        toplam[gecerli] += yuz[gecerli].to_numpy()
        sayi[gecerli] += 1
    d["puan"] = np.where(sayi > 0, toplam / np.maximum(sayi, 1), np.nan)

    gecerli = d[d.puan.notna()].copy()
    out = ["# Kompozit puan (walk-forward)\n",
           f"Özellikler: {', '.join(f'{k}({v:+d})' for k, v in secim)}\n",
           f"Puanı üretilebilen gözlem {len(gecerli)} / {len(d)} · "
           f"taban %{gecerli.y.mean()*100:.1f}\n"]

    if len(gecerli) < 500:
        out.append("Yeterli gözlem yok.")
        metin = "\n".join(out)
        print(metin)
        return 1

    def dilim(df: pd.DataFrame, kolon: str, kapsam: float) -> Tuple[float, int]:
        kes = df[kolon].quantile(1 - kapsam)
        s = df[df[kolon] >= kes]
        return (float(s.y.mean()) if len(s) else float("nan")), len(s)

    out.append(f"## Kapsam %{args.kapsam*100:.0f} · üç kıyas\n")
    out.append("| kesim | n | taban | kompozit | kalite | endeks uyumu |")
    out.append("|---|---|---|---|---|---|")
    for ad, s in (("tümü", gecerli),
                  ("1s", gecerli[gecerli.tf == "1h"]),
                  ("2s", gecerli[gecerli.tf == "2h"]),
                  ("4s", gecerli[gecerli.tf == "4h"]),
                  ("1g", gecerli[gecerli.tf == "1d"])):
        if len(s) < 200:
            continue
        p_kom, n = dilim(s, "puan", args.kapsam)
        p_kal, _ = dilim(s, "kalite", args.kapsam)
        p_end, _ = dilim(s, "endeks_uyum", args.kapsam) if "endeks_uyum" in s else (np.nan, 0)
        out.append(f"| {ad} | {len(s)} | %{s.y.mean()*100:.1f} | **%{p_kom*100:.1f}** | "
                   f"%{p_kal*100:.1f} | %{p_end*100:.1f} |")

    # --- puan dilimleri (tekdüzelik)
    gecerli["dilim"] = pd.qcut(gecerli.puan, 5, labels=["1", "2", "3", "4", "5"])
    out.append("\n## Puan dilimleri (walk-forward)\n")
    out.append("| dilim | n | devam |")
    out.append("|---|---|---|")
    for k, s in gecerli.groupby("dilim", observed=True):
        out.append(f"| {k} | {len(s)} | %{s.y.mean()*100:.1f} |")

    # --- dönem bazında kararlılık (uzak dilimler)
    gecerli["yil_ceyrek"] = gecerli.tarih.dt.to_period("Q").astype(str)
    out.append("\n## Çeyrek bazında (puan üst %30 vs taban)\n")
    out.append("| çeyrek | n | taban | üst %30 | fark |")
    out.append("|---|---|---|---|---|")
    for k, s in gecerli.groupby("yil_ceyrek"):
        if len(s) < 150:
            continue
        p, n = dilim(s, "puan", args.kapsam)
        out.append(f"| {k} | {len(s)} | %{s.y.mean()*100:.1f} | %{p*100:.1f} | "
                   f"{(p-s.y.mean())*100:+.1f} |")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
