# -*- coding: utf-8 -*-
"""Devamlılık puanı doğrulaması — arşivde gerçekten çalışıyor mu?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/taban_2_1_24.csv`

`devamlilik.py` sözleşmesi testlerde doğrulandı; bu betik **veriye** bakar:

1. Kapsam: kaç gözleme puan verilebiliyor (Bayrak/Flama hariç).
2. Bant tekdüzeliği: puan bandı yükseldikçe gerçekleşen fazla da yükseliyor mu.
3. Eski kalite ile yan yana: aynı kapsamda hangisi daha iyi sıralıyor.
4. Çeyrek kararlılığı: her çeyrekte en iyi %20'nin fazlası pozitif mi.

Kullanım:
    python scripts/devamlilik_dogrulama.py
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

import devamlilik as dev  # noqa: E402
from puan_analiz import etiketle  # noqa: E402


def ga(seri: pd.Series, tekrar: int = 1200, rng=None):
    v = seri.dropna().to_numpy()
    if len(v) < 15:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng(5)
    idx = rng.integers(0, len(v), (tekrar, len(v)))
    o = v[idx].mean(axis=1) * 100
    return float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Devamlılık puanı doğrulaması")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--taban", default="var/replay/taban_2_1_24.csv")
    ap.add_argument("--rapor", default="var/replay/devamlilik.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["y"] = etiketle(d, 2.0, 1.0, 24)
    d = d[d.y.notna()].copy()

    r = pd.read_csv(REPO / args.taban)
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

    # --- puan
    d["puan"] = [dev.devamlilik_puani(a, m, x) for a, m, x in
                 zip(d.aile, d.mtf_uyum, d.bant_mesafe_atr)]
    d["bant"] = d.puan.apply(dev.bant)
    kapsam = d[d.puan.notna()].copy()

    out = ["# Devamlılık puanı — arşiv doğrulaması\n",
           f"gözlem {len(d)} · puanlanabilen {len(kapsam)} (%{len(kapsam)/len(d)*100:.1f}) · "
           f"kapsam dışı {len(d)-len(kapsam)} (Bayrak/Flama)\n",
           f"\npuan dağılımı: ort {kapsam.puan.mean():.1f} · medyan {kapsam.puan.median():.0f} · "
           f"min {kapsam.puan.min():.0f} · maks {kapsam.puan.max():.0f}\n",
           "\n## 1. Bant tekdüzeliği (asıl sözleşme)\n",
           "| bant | n | pay | ham devam | taban | fazla | %95 GA (sembol) |",
           "|---|---|---|---|---|---|---|"]
    sira = ["yüksek", "iyi", "normal", "zayıf"]
    for b in sira:
        g = kapsam[kapsam.bant == b]
        if not len(g):
            out.append(f"| {b} | 0 | — | — | — | — | — |")
            continue
        lo, hi = ga(g.groupby("sembol").fazla.mean())
        out.append(f"| {b} | {len(g)} | %{len(g)/len(kapsam)*100:.0f} | %{g.y.mean()*100:.1f} | "
                   f"%{g.taban.mean()*100:.1f} | **{g.fazla.mean()*100:+.1f}** | [{lo:+.1f}, {hi:+.1f}] |")

    ort = kapsam.groupby("bant", observed=True).fazla.mean()
    tekduze = all(ort.get(a, -9) >= ort.get(b, -9)
                  for a, b in zip(sira, sira[1:]) if a in ort and b in ort)
    out.append(f"\n**Tekdüzelik:** {'✅ sağlanıyor' if tekduze else '❌ bozuk'} "
               f"(yüksek > iyi > normal > zayıf)\n")

    # --- 2. eski kalite ile kıyas
    out.append("\n## 2. Eski kalite ile kıyas (aynı gözlemler)\n")
    out.append("| sıralayıcı | kapsam | ham devam | taban | fazla |")
    out.append("|---|---|---|---|---|")
    # Puan tamsayı olduğu için eşitlik çok; eşik kırma rastgele yapılır ve
    # 20 çekimin ortalaması alınır (yoksa %20 ile %30 aynı kümeyi seçiyor).
    rng = np.random.default_rng(17)
    for ad, kolon in (("eski kalite", "kalite"), ("yeni puan", "puan")):
        for k in (0.10, 0.20, 0.30):
            n_sec = max(1, int(len(kapsam) * k))
            bas, tab, faz = [], [], []
            for _ in range(20):
                jitter = rng.random(len(kapsam)) * 1e-6
                idx = np.argsort(-(kapsam[kolon].to_numpy(float) + jitter))[:n_sec]
                g = kapsam.iloc[idx]
                bas.append(g.y.mean())
                tab.append(g.taban.mean())
                faz.append(g.y.mean() - g.taban.mean())
            out.append(f"| {ad} · en iyi %{int(k*100)} | {n_sec} | %{np.mean(bas)*100:.1f} | "
                       f"%{np.mean(tab)*100:.1f} | **{np.mean(faz)*100:+.1f}** |")

    # --- 3. çeyrek
    kapsam["ceyrek"] = kapsam.tarih.dt.to_period("Q").astype(str)
    out.append("\n## 3. Çeyrek kararlılığı (en iyi %20)\n")
    out.append("| çeyrek | n | ham devam | taban | fazla |")
    out.append("|---|---|---|---|---|")
    poz = 0
    toplam = 0
    for q, g in kapsam.groupby("ceyrek"):
        if len(g) < 100:
            continue
        sec = g.nlargest(max(1, int(len(g) * 0.20)), "puan")
        f = (sec.y.mean() - sec.taban.mean()) * 100
        toplam += 1
        poz += 1 if f > 0 else 0
        out.append(f"| {q} | {len(sec)} | %{sec.y.mean()*100:.1f} | %{sec.taban.mean()*100:.1f} | {f:+.1f} |")
    out.append(f"\n**Kararlılık:** {poz}/{toplam} çeyrek pozitif\n")

    # --- 4. TF ve örnek kart satırı
    out.append("\n## 4. TF kırılımı\n")
    out.append("| TF | n | ort puan | fazla |")
    out.append("|---|---|---|---|")
    for tf, g in kapsam.groupby("tf"):
        out.append(f"| {tf} | {len(g)} | {g.puan.mean():.0f} | {g.fazla.mean()*100:+.1f} |")

    ornek = kapsam.nlargest(1, "puan").iloc[0]
    out.append("\n## 5. Örnek satır (LOG)\n")
    out.append("Kartta puan/etiket YOK (2026-10-25 gece, §11–§12). Bu satır yalnız "
               "logda görünür:\n")
    out.append("```")
    out.append(f"devamlilik puanı (log) = {int(ornek.puan)} · bant (log) = "
               f"{dev.bant(int(ornek.puan))}")
    out.append("```")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
