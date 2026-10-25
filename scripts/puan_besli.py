# -*- coding: utf-8 -*-
"""Beşli puanlama — doğrulanmış maddelerin toplam katkısı.

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv`

Kural (ağırlıklar **keşif kümesinde** fit edilir, doğrulamada sabit kalır):

    puan = a·[aile=Kama] + b·(−mesafe_sıra) + c·mtf + d·breadth

* a, b, c, d: doğrusal en küçük kareler, yalnız **S bölmesi** (ayrık semboller).
* Değerlendirme: **Z bölmesi** (uzak dönem) + bölme karışımı, çeyrek bazında.
* Kıyas 1: formasyonsuz kural (yalnız mtf + breadth) — formasyonun katkısı.
* Kıyas 2: aynı kapsamda rastgele taban.

Amaç: "bu maddelerle puanlama yapılırsa ne kazanılır" sorusuna
kapsam/başarı eğrisi vermek.

Kullanım:
    python scripts/puan_besli.py
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
from fazla_model import fazla_serisi  # noqa: E402


def _sec(puan: np.ndarray, oran: float, rng) -> np.ndarray:
    """Eşit puanlı gözlemlerde sıralamayı rastgele kır (20 çekim ortalaması)."""
    return rng.random(len(puan)) * 1e-6 + puan


def kapsam_tablosu(ad: str, kesif: pd.DataFrame, dogru: pd.DataFrame,
                   puan_k: np.ndarray, puan_z: np.ndarray) -> List[str]:
    rng = np.random.default_rng(21)
    out = [f"\n### {ad}\n", "| kapsam | keşif (S) | doğrulama (Z) | n_Z | taban_Z | fazla |",
           "|---|---|---|---|---|---|"]
    for k in (0.05, 0.10, 0.20, 0.30, 0.50):
        n_k = max(1, int(len(kesif) * k))
        n_z = max(1, int(len(dogru) * k))
        e = np.mean([kesif.y.to_numpy()[np.argsort(-_sec(puan_k, k, rng))[:n_k]].mean()
                     for _ in range(20)])
        sec_list = [np.argsort(-_sec(puan_z, k, rng))[:n_z] for _ in range(20)]
        bas = np.mean([dogru.y.to_numpy()[i].mean() for i in sec_list])
        tab = np.mean([dogru.taban.to_numpy()[i].mean() for i in sec_list])
        out.append(f"| %{int(k*100)} | %{e*100:.1f} | %{bas*100:.1f} | {n_z} | "
                   f"%{tab*100:.1f} | {(bas-tab)*100:+.1f} |")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Beşli puanlama")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/puan_besli.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["_idx"] = np.arange(len(d))
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()

    r = pd.read_csv(REPO / "var/replay/taban_2_1_24.csv")
    t = r.groupby(["sembol", "tf", "ay", "yon"]).agg(n=("n", "sum"), b=("basari", "sum")).reset_index()
    t["taban"] = t.b / t.n
    t.loc[t.n < 30, "taban"] = np.nan
    yed = r.groupby(["sembol", "tf", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))
    yed["taban_yedek"] = yed.b / yed.n
    d = d.merge(t[["sembol", "tf", "ay", "yon", "taban"]], on=["sembol", "tf", "ay", "yon"],
                how="left").merge(yed[["taban_yedek"]], on=["sembol", "tf", "yon"], how="left")
    d["taban"] = d.taban.fillna(d.taban_yedek)
    d = d[d.taban.notna()].reset_index(drop=True)

    # özellikler — hepsi girişte biliniyor
    kama = (d.aile == "Kama").to_numpy(float)
    mesafe = np.where(d.bant_mesafe_atr <= 0.3, 2.0,
                      np.where(d.bant_mesafe_atr <= 1.0, 1.0,
                               np.where(d.bant_mesafe_atr <= 2.0, -0.5, -1.5)))
    mtf = d.mtf_uyum.to_numpy(float) / 4.0
    breadth = d.p_breadth.fillna(0.5).to_numpy(float)

    import zlib
    d["ds"] = d.sembol.apply(lambda s: zlib.crc32(s.encode()) % 2)
    kes = d.tarih.quantile(0.70)
    Z = d.tarih > kes
    S = d.ds == 1

    d["fazla"] = d.y - d.taban
    print(f"ortalama fazla {d.fazla.mean()*100:+.1f} puan")

    kayitlar = {}
    for ad, X in {
        "tam (kama + mesafe + mtf + breadth)": np.column_stack([kama, mesafe, mtf, breadth]),
        "yalnız formasyon (kama + mesafe)": np.column_stack([kama, mesafe]),
        "yalnız koşul (mtf + breadth)": np.column_stack([mtf, breadth]),
        "mesafe tek başına": mesafe.reshape(-1, 1),
        "aile tek başına": kama.reshape(-1, 1),
    }.items():
        Xk = np.column_stack([np.ones(len(d)), X])
        m_kesif = (S & ~Z).to_numpy() if (S & ~Z).sum() > 1500 else S.to_numpy()
        b = np.linalg.pinv(Xk[m_kesif].T @ Xk[m_kesif]) @ (Xk[m_kesif].T @ d.fazla.to_numpy()[m_kesif])
        puan = Xk @ b
        d_kesif = d.loc[m_kesif]
        d_dogru = d.loc[Z.to_numpy()].reset_index(drop=True)
        kayitlar[ad] = (d_kesif, d_dogru, puan[m_kesif], puan[Z.to_numpy()], b)

    out = ["# Beşli puanlama — doğrulanmış maddelerin toplam katkısı\n",
           "Hedef **fazla** (y − eşleşmiş rastgele taban); mutlak başarıya göre fit "
           "etmek, tabanı düşük hücreleri haksız yere cezalandırıyordu.\n",
           f"gözlem {len(d)} · ana etiket 2/1/24 · taban %{d.taban.mean()*100:.1f}",
           f"keşif {int(((S & ~Z)).sum())} gözlem · doğrulama {int(Z.sum())} gözlem\n"]
    for ad, (dk, dz, pk, pz, b) in kayitlar.items():
        out.append(f"\n## {ad}\n")
        out.append("ağırlıklar: " + ", ".join(f"{v:+.3f}" for v in b))
        out += kapsam_tablosu(ad, dk, dz, pk, pz)

    # çeyrek kararlılığı — tam kural, en iyi %20
    dk, dz, pk, pz, b = kayitlar["tam (kama + mesafe + mtf + breadth)"]
    oran = 0.20
    tum = pd.concat([dk.assign(puan=pk), dz.assign(puan=pz)]).reset_index(drop=True)
    tum["ceyrek"] = tum.tarih.dt.to_period("Q").astype(str)
    out.append("\n## Çeyrek kararlılığı (en iyi %20, tüm dönem)\n")
    out.append("| çeyrek | n | başarı | taban | fazla |")
    out.append("|---|---|---|---|---|")
    for q, g in tum.groupby("ceyrek"):
        if len(g) < 100:
            continue
        sec = g.nlargest(max(1, int(len(g) * oran)), "puan")
        out.append(f"| {q} | {len(sec)} | %{sec.y.mean()*100:.1f} | %{sec.taban.mean()*100:.1f} | "
                   f"{(sec.y.mean()-sec.taban.mean())*100:+.1f} |")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
