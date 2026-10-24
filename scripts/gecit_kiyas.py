# -*- coding: utf-8 -*-
"""Aşama 3 · Geçit mi, yumuşak eşik mi? (H3)

SALT OKUNUR. Ön kayıt: docs/arastirma/PUAN_DOGRULAMA_ON_KAYIT.md

İki kural, aynı bildirim hacminde (kapsam %50) yarışır:

  (a) yumuşak eşik : 0,5·koşul puanı + 0,5·şekil (kalite) puanı, en yüksek %50
  (b) sert geçit   : geçit (endeks uyumu VE likidite üst yarı) sağlamayan
                     hiç gitmez; kalanlar kaliteye göre sıralanır, %50 alınır

Koşul puanı = (uyum ? 50 : 0) + (likidite üst ? 50 : 0)
Şekil puanı = kalite (60-100 aralığı 0-100'e gerilir)

Kabul barı (H3): geçit, eşiği ≥ +3 puan geçerse geçit önerilir.
Karar yalnızca doğrulama dilimlerinde verilir (ayrık sembol ve uzak dönem).

Kullanım:
    python scripts/gecit_kiyas.py --girdi var/replay/gozlemler177.csv
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
from puan_sorular import likidite_tablosu  # noqa: E402
from puan_tarama import bolmeler  # noqa: E402

KAPSAM = 0.50


def hazirla(girdi: str) -> pd.DataFrame:
    d = pd.read_csv(REPO / girdi)
    d = d[d.pencere_tam == 1].copy()
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["zaman"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].copy()
    d["uyum"] = (np.sign(d.yon) == np.sign(d.endeks_egim)).astype(float)
    lik = likidite_tablosu()
    d = d.merge(lik, on="sembol", how="left")
    d["likit"] = (d.hacim_tl >= d.hacim_tl.median()).astype(float)
    d["gecit"] = (d.uyum * d.likit)
    d["kosul_puan"] = d.uyum * 50 + d.likit * 50
    d["sekil_puan"] = ((d.kalite - 60) / 40).clip(0, 1) * 100
    d["yumusak"] = 0.5 * d.kosul_puan + 0.5 * d.sekil_puan
    d["sert"] = d.gecit * 1000 + d.kalite
    return d


def kesip_olc(s: pd.DataFrame, kolon: str) -> float:
    if len(s) < 50:
        return float("nan")
    kes = s[kolon].quantile(1 - KAPSAM)
    sec = s[s[kolon] >= kes]
    return float(sec.y.mean()) if len(sec) else float("nan")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aşama 3 geçit/eşik kıyası")
    ap.add_argument("--girdi", default="var/replay/gozlemler177.csv")
    ap.add_argument("--rapor", default="var/replay/gecit.md")
    args = ap.parse_args(argv)

    d = hazirla(args.girdi)
    b = bolmeler(d)
    out = ["# Aşama 3 · Geçit mi, yumuşak eşik mi?\n",
           f"Gözlem {len(d)} · kapsam sabit %{KAPSAM*100:.0f}\n",
           "| bölme | yumuşak eşik | sert geçit | fark |",
           "|---|---|---|---|"]
    farklar = []
    for ad, (tr, te) in b.items():
        if ad == "Y":
            continue
        y = kesip_olc(te, "yumusak")
        g = kesip_olc(te, "sert")
        farklar.append((g - y) * 100)
        out.append(f"| {ad} (doğrulama) | %{y*100:.1f} | %{g*100:.1f} | {(g-y)*100:+.1f} |")

    out.append("")
    if farklar:
        ort = float(np.nanmean(farklar))
        karar = "GEÇTİ (geçit önerilir)" if ort >= 3.0 else "KALDI (geçit üstün değil)"
        out.append(f"Ortalama fark: **{ort:+.1f} puan** · Ön kayıt barı (≥ +3,0): **{karar}**")

    # geçit kapsamı ve tanı bilgisi
    out.append("\n## Tanı\n")
    out.append(f"- Geçidi sağlayan gözlem oranı: %{d.gecit.mean()*100:.0f}")
    out.append(f"- Geçit sağlayanların devam oranı: %{d[d.gecit==1].y.mean()*100:.1f} · "
               f"sağlamayanların: %{d[d.gecit==0].y.mean()*100:.1f}")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
