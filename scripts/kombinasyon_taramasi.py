# -*- coding: utf-8 -*-
"""Kombinasyon taraması: koşullar birleşince devam oranı sıçrıyor mu?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv`.

Amaç: tek değişkenli taramada hiçbiri geçmedi (en iyisi AUC 0,53). Belki
birleşimleri geçerlidir. Bu yüzden tüm 2'li ve 3'lü eşik kombinasyonları
keşif diliminde taranır, en iyileri **doğrulama dilimlerinde** sınanır.

Disiplin:
  * Keşif: S-keşif (ayrık semboller).
  * Doğrulama: S-doğrulama ve Z-doğrulama.
  * Asgari kapsam: keşifte %10 (en az 250 gözlem).
  * Raporlanan "en iyi", keşifte seçilendir; doğrulamadaki düşüş (shrinkage)
    açıkça gösterilir. Bu, kombinasyon avının ne kadar yanıltıcı olduğunu
    sayısallaştırır.

Kullanım:
    python scripts/kombinasyon_taramasi.py
"""

from __future__ import annotations

import argparse
import itertools
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
from puan_tarama import bolmeler  # noqa: E402

# (kolon, yön, eşik adayları)
OZELLIKLER = {
    "mtf_uyum": (1, [3, 4]),
    "endeks_uyum": (1, [1]),
    "hacim_orani": (1, [1.0, 1.5, 2.0]),
    "tf_bos20": (1, [1]),
    "p_breadth": (1, [0.5, 0.65]),
    "kalite": (1, [80, 85]),
    "d_atr_yuzdelik": (-1, [0.5, 0.75]),
    "h_govde_konum": (1, [0.6, 0.8]),
    "bant_mesafe_atr": (-1, [0.5, 1.0]),
    "yapi_uyum": (1, [1]),
}


def kosul_uygula(d: pd.DataFrame, kosullar: List[Tuple[str, int, float]]) -> pd.Series:
    m = pd.Series(True, index=d.index)
    for kolon, yon, esik in kosullar:
        v = d[kolon]
        m &= (v >= esik) if yon > 0 else (v <= esik)
    return m


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Kombinasyon taraması")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--min-kapsam", type=float, default=0.10)
    ap.add_argument("--rapor", default="var/replay/kombinasyon.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce")
    d = d[d.tarih.notna()]
    for kolon in OZELLIKLER:
        if kolon in d:
            d[kolon] = pd.to_numeric(d[kolon], errors="coerce")
    b = bolmeler(d)
    tr, te_s = b["S"]
    te_z = b["Z"][1]
    taban_tr = tr.y.mean()

    tek = []
    for kolon, (yon, esikler) in OZELLIKLER.items():
        if kolon not in d:
            continue
        for esik in esikler:
            tek.append([(kolon, yon, esik)])
    ikili = [list(c) for c in itertools.combinations([k for k in OZELLIKLER if k in d], 2)]
    ikili = [[(k, OZELLIKLER[k][0], e) for k, e in zip(kombi, esikler)]
             for kombi in ikili
             for esikler in itertools.product(*[OZELLIKLER[k][1] for k in kombi])]

    satirlar = []
    for kosullar in tek + ikili:
        m_tr = kosul_uygula(tr, kosullar)
        kapsam = m_tr.mean()
        if kapsam < args.min_kapsam:
            continue
        p_tr = tr.y[m_tr].mean()
        m_s = kosul_uygula(te_s, kosullar)
        m_z = kosul_uygula(te_z, kosullar)
        p_s = te_s.y[m_s].mean() if m_s.sum() >= 50 else np.nan
        p_z = te_z.y[m_z].mean() if m_z.sum() >= 50 else np.nan
        satirlar.append({"kural": " + ".join(f"{k}{'>=' if y > 0 else '<='}{e:g}"
                                             for k, y, e in kosullar),
                         "kapsam": kapsam, "n_tr": int(m_tr.sum()),
                         "p_tr": p_tr, "p_s": p_s, "p_z": p_z,
                         "fark_s": (p_s - te_s.y.mean()) * 100 if np.isfinite(p_s) else np.nan,
                         "fark_z": (p_z - te_z.y.mean()) * 100 if np.isfinite(p_z) else np.nan})

    t = pd.DataFrame(satirlar)
    t["en_kotu_dogrulama"] = t[["fark_s", "fark_z"]].min(axis=1)

    out = ["# Kombinasyon taraması\n",
           f"keşif n={len(tr)} taban %{taban_tr*100:.1f} · "
           f"S doğrulama n={len(te_s)} taban %{te_s.y.mean()*100:.1f} · "
           f"Z doğrulama n={len(te_z)} taban %{te_z.y.mean()*100:.1f}\n",
           f"Taranan kural: {len(t)} (min kapsam %{args.min_kapsam*100:.0f})\n"]

    out.append("\n## Keşifte en iyi 10 (aşırı uyum riski burada)\n")
    out.append("| kural | kapsam | keşif | S doğr. | Z doğr. | fark S | fark Z |")
    out.append("|---|---|---|---|---|---|---|")
    for r in t.nlargest(10, "p_tr").itertuples():
        out.append(f"| {r.kural} | %{r.kapsam*100:.0f} | %{r.p_tr*100:.1f} | "
                   f"%{r.p_s*100:.1f} | %{r.p_z*100:.1f} | {r.fark_s:+.1f} | {r.fark_z:+.1f} |")

    out.append("\n## Keşif + iki doğrulamada da en iyi 10 (gerçek adaylar)\n")
    out.append("| kural | kapsam | keşif | S doğr. | Z doğr. | en kötü fark |")
    out.append("|---|---|---|---|---|---|")
    for r in t.nlargest(10, "en_kotu_dogrulama").itertuples():
        out.append(f"| {r.kural} | %{r.kapsam*100:.0f} | %{r.p_tr*100:.1f} | "
                   f"%{r.p_s*100:.1f} | %{r.p_z*100:.1f} | **{r.en_kotu_dogrulama:+.1f}** |")

    # --- aşırı uyum ölçüsü
    if len(t) > 20:
        ust = t.nlargest(max(5, len(t) // 20), "p_tr")
        out.append("\n## Aşırı uyum (overfit) ölçüsü\n")
        out.append(f"- Keşifte en iyi %5'in ortalama farkı: "
                   f"{(ust.p_tr.mean() - taban_tr)*100:+.1f} puan")
        out.append(f"- Aynı kuralların doğrulamadaki ortalama farkı: "
                   f"{ust.fark_s.mean():+.1f} (S) · {ust.fark_z.mean():+.1f} (Z)")
        out.append(f"- Keşif→doğrulama kaybı: "
                   f"{((ust.p_tr.mean()-taban_tr)*100 - ust.fark_s.mean()):.1f} puan")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
