# -*- coding: utf-8 -*-
"""Puan sınaması — 50 sembollük bağımsız replay üzerinde matematik.

SALT OKUNUR. Girdi: yeni replay (`var/replay/ozellikler50.csv`) +
o 50 sembol için üretilmiş taban (`var/replay/taban50/`).

Neden ayrı bir replay: 177 sembollük arşivde ağırlıklar **seçildi**; aynı
veride ölçmek kendini doğrulamak olur. Burada 50 sembollük yeni koşu var.

Üç hesap yapılır:

1. **Araştırma puanı** — `mtf_uyum` (4 zaman diliminin yön uyumu) ile.
   Bu, ağırlıkların türetildiği tanım.
2. **Üretim puanı** — kartın gerçekten kullanacağı alanlarla: `mtf_uyum`
   üretimde yalnız 1h→4h ve 4h→1g için hesaplanıyor ve **ikili** (4 ya da 0).
   2h ve 1g zaman dilimlerinde hiç hesaplanmıyor.
3. **Kalite (eski)** — kıyas için.

Ölçütler: bant tekdüzeliği, en iyi %10/20/30 dilim getirisi, sembol bootstrap
GA, çeyrek kararlılığı, sıralama AUC'si.

Kullanım:
    python scripts/puan_sinama.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import devamlilik as dev  # noqa: E402
from puan_analiz import etiketle  # noqa: E402


def ga(seri: pd.Series, tekrar: int = 2000, rng=None):
    v = seri.dropna().to_numpy()
    if len(v) < 12:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng(11)
    idx = rng.integers(0, len(v), (tekrar, len(v)))
    o = v[idx].mean(axis=1) * 100
    return float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))


def auc(puan: np.ndarray, y: np.ndarray) -> float:
    """İkili hedef için AUC (Mann-Whitney U, scipy yok)."""
    ok = ~np.isnan(puan)
    p, t = puan[ok], np.asarray(y)[ok]
    if len(np.unique(t)) != 2:
        return float("nan")
    siralar = pd.Series(p).rank().to_numpy()
    n1 = int((t == 1).sum())
    n0 = int((t == 0).sum())
    if not n1 or not n0:
        return float("nan")
    return float((siralar[t == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def korelasyon(puan: np.ndarray, y: np.ndarray) -> float:
    """Sürekli hedef için sıra korelasyonu (Spearman, scipy yok)."""
    ok = ~np.isnan(puan) & ~np.isnan(y)
    if ok.sum() < 20:
        return float("nan")
    a = pd.Series(puan[ok]).rank().to_numpy()
    b = pd.Series(y[ok]).rank().to_numpy()
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="50 sembollük puan sınaması")
    ap.add_argument("--girdi", default="var/replay/ozellikler50.csv")
    ap.add_argument("--taban", default="var/replay/taban50/taban_2_1_24.csv")
    ap.add_argument("--rapor", default="var/replay/puan_sinama.md")
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

    # --- üretim mtf_uyum: main.py ile aynı mantık (yalnız 1h ve 4h, ikili)
    def uretim_mtf(satir) -> int:
        tf = str(satir.tf)
        yon = np.sign(satir.yon)
        if tf == "1h":
            ust = satir.get("4h_ust_ma20")
        elif tf == "4h":
            ust = satir.get("d_ust_ma50")
        else:
            return 0
        try:
            if ust != ust or ust == 0:
                return 0
        except Exception:
            return 0
        return 4 if np.sign(ust) == yon else 0

    d["mtf_uretim"] = [uretim_mtf(s) for _, s in d.iterrows()]

    d["puan_arastirma"] = [dev.devamlilik_puani(a, m, x) for a, m, x in
                           zip(d.aile, d.mtf_uyum, d.bant_mesafe_atr)]
    d["puan_uretim"] = [dev.devamlilik_puani(a, m, x) for a, m, x in
                        zip(d.aile, d.mtf_uretim, d.bant_mesafe_atr)]

    kapsam = d[d.puan_arastirma.notna()].copy()
    kapsam["aile_"] = kapsam.aile
    out = ["# Puan sınaması — 50 sembollük yeni replay\n",
           f"gözlem {len(d)} · puanlanabilen {len(kapsam)} · sembol "
           f"{d.sembol.nunique()} · taban %{d.taban.mean()*100:.1f} · "
           f"ortalama fazla {d.fazla.mean()*100:+.1f}\n"]

    # --- 1. bantlar
    out.append("\n## 1. Bant tekdüzeliği\n")
    out.append("| bant | n | pay | ham devam | taban | fazla | %95 GA (sembol) |")
    out.append("|---|---|---|---|---|---|---|")
    for puan_kolon, ad in (("puan_arastirma", "araştırma"), ("puan_uretim", "üretim")):
        out.append(f"\n**{ad} puanı**\n")
        kapsam["bant"] = kapsam[puan_kolon].apply(dev.bant)
        for b in ("yüksek", "iyi", "normal", "zayıf"):
            g = kapsam[kapsam.bant == b]
            if not len(g):
                out.append(f"| {b} | 0 | — | — | — | — | — |")
                continue
            lo, hi = ga(g.groupby("sembol").fazla.mean())
            out.append(f"| {b} | {len(g)} | %{len(g)/len(kapsam)*100:.0f} | "
                       f"%{g.y.mean()*100:.1f} | %{g.taban.mean()*100:.1f} | "
                       f"**{g.fazla.mean()*100:+.1f}** | [{lo:+.1f}, {hi:+.1f}] |")

    # --- 2. dilimler
    out.append("\n## 2. En iyi dilimler (sembol GA)\n")
    genel = kapsam.fazla.mean() * 100
    out.append(f"Tüm kümenin ortalama fazlası **{genel:+.1f}** puan. Rastgele bir dilim "
               f"de bu kadar verir; asıl ölçü **aşırı** sütunu (dilim − tüm küme).\n")
    out.append("| sıralayıcı | dilim | n | ham devam | taban | fazla | aşırı | %95 GA |")
    out.append("|---|---|---|---|---|---|---|---|")
    rng = np.random.default_rng(23)
    for ad, kolon in (("araştırma puanı", "puan_arastirma"),
                      ("üretim puanı", "puan_uretim"),
                      ("eski kalite", "kalite"),
                      ("rastgele (kıyas)", None)):
        for k in (0.10, 0.20, 0.30):
            n_sec = max(1, int(len(kapsam) * k))
            fazlalar = []
            for _ in range(20):
                jitter = rng.random(len(kapsam)) * 1e-6
                if kolon is None:
                    idx = rng.permutation(len(kapsam))[:n_sec]
                    g = kapsam.iloc[idx]
                else:
                    j = np.argsort(-(kapsam[kolon].to_numpy(float) + jitter))[:n_sec]
                    g = kapsam.iloc[j]
                fazlalar.append(g.groupby("sembol").fazla.mean())
            ort = pd.concat(fazlalar, axis=1).mean(axis=1)
            lo, hi = ga(ort)
            sec = kapsam.nlargest(n_sec, kolon) if kolon else kapsam.sample(n_sec, random_state=1)
            f_ort = np.mean([f.mean() for f in fazlalar]) * 100
            out.append(f"| {ad} | %{int(k*100)} | {n_sec} | %{sec.y.mean()*100:.1f} | "
                       f"%{sec.taban.mean()*100:.1f} | {f_ort:+.1f} | "
                       f"**{f_ort - genel:+.1f}** | [{lo:+.1f}, {hi:+.1f}] |")

    # --- 3. AUC
    out.append("\n## 3. Sıralama gücü (AUC)\n")
    out.append("`AUC` ikili sonuç için; `ρ(fazla)` sürekli fazla ile sıra korelasyonu.\n")
    out.append("| sıralayıcı | AUC (başarı) | ρ (fazla) |")
    out.append("|---|---|---|")
    for ad, kolon in (("araştırma puanı", "puan_arastirma"),
                      ("üretim puanı", "puan_uretim"),
                      ("eski kalite", "kalite"),
                      ("MTF tek başına (araştırma)", "mtf_uyum"),
                      ("mesafe tek başına", "bant_mesafe_atr")):
        p = kapsam[kolon].to_numpy(float)
        if kolon == "bant_mesafe_atr":
            p = -p   # yakın olan iyi
        out.append(f"| {ad} | {auc(p, kapsam.y.to_numpy()):.3f} | "
                   f"{korelasyon(p, kapsam.fazla.to_numpy()):+.3f} |")

    # --- 4. çeyrek
    kapsam["ceyrek"] = kapsam.tarih.dt.to_period("Q").astype(str)
    out.append("\n## 4. Çeyrek kararlılığı (en iyi %20)\n")
    out.append("| çeyrek | n | araştırma | üretim | rastgele taban |")
    out.append("|---|---|---|---|---|")
    for q, g in kapsam.groupby("ceyrek"):
        if len(g) < 80:
            continue
        n_sec = max(1, int(len(g) * 0.20))
        a = g.nlargest(n_sec, "puan_arastirma")
        u = g.nlargest(n_sec, "puan_uretim")
        out.append(f"| {q} | {len(g)} | {(a.y.mean()-a.taban.mean())*100:+.1f} | "
                   f"{(u.y.mean()-u.taban.mean())*100:+.1f} | %{g.taban.mean()*100:.1f} |")

    # --- 5. zaman dilimi
    out.append("\n## 5. Zaman dilimi kırılımı (araştırma puanı)\n")
    out.append("| TF | n | ort puan | fazla | üretim mtf kapsamı |")
    out.append("|---|---|---|---|---|")
    for tf, g in kapsam.groupby("tf"):
        out.append(f"| {tf} | {len(g)} | {g.puan_arastirma.mean():.0f} | "
                   f"{g.fazla.mean()*100:+.1f} | %{(g.mtf_uretim > 0).mean()*100:.0f} |")

    # --- 6. puan nerede çalışıyor: aile içi sıralama
    out.append("\n## 6. Puan aile içinde ne yapıyor?\n")
    out.append("| küme | n | puan aralığı | en iyi %20 fazla | en kötü %20 fazla |")
    out.append("|---|---|---|---|---|")
    for ad, maske in (("kama", kapsam.aile_ == "Kama"), ("üçgen", kapsam.aile_ == "Üçgen")):
        g = kapsam[maske]
        if len(g) < 100:
            continue
        n_sec = max(1, int(len(g) * 0.20))
        iyi = g.nlargest(n_sec, "puan_arastirma")
        kotu = g.nsmallest(n_sec, "puan_arastirma")
        out.append(f"| {ad} | {len(g)} | {g.puan_arastirma.min():.0f}–{g.puan_arastirma.max():.0f} | "
                   f"{(iyi.y.mean()-iyi.taban.mean())*100:+.1f} | "
                   f"{(kotu.y.mean()-kotu.taban.mean())*100:+.1f} |")

    out.append("\n## 7. Katkı ayrıştırması (tek tek maddeler, 50 sembol)\n")
    out.append("| kural | kapsam | fazla | aşırı |")
    out.append("|---|---|---|---|")
    for ad, maske in (
        ("kama & MTF4 & ≤1 ATR", (kapsam.aile_ == "Kama") & (kapsam.mtf_uyum >= 4)
         & (kapsam.bant_mesafe_atr <= 1.0)),
        ("kama & MTF4 & >2 ATR", (kapsam.aile_ == "Kama") & (kapsam.mtf_uyum >= 4)
         & (kapsam.bant_mesafe_atr > 2.0)),
        ("kama & MTF4", (kapsam.aile_ == "Kama") & (kapsam.mtf_uyum >= 4)),
        ("kama", kapsam.aile_ == "Kama"),
        ("üçgen", kapsam.aile_ == "Üçgen"),
        ("MTF4 (her aile)", kapsam.mtf_uyum >= 4),
        ("≤0,3 ATR", kapsam.bant_mesafe_atr <= 0.3),
        (">2 ATR", kapsam.bant_mesafe_atr > 2),
    ):
        g = kapsam[maske]
        if len(g) < 40:
            out.append(f"| {ad} | {len(g)} | (yetersiz) | — |")
            continue
        f_ = g.fazla.mean() * 100
        out.append(f"| {ad} | {len(g)} | {f_:+.1f} | {f_ - genel:+.1f} |")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
