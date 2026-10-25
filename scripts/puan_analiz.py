# -*- coding: utf-8 -*-
"""Puan replay analizi: 17 sorunun tabloları (A-G).

`scripts/puan_replay.py` çıktısını (`var/replay/gozlemler.csv`) okur; hiçbir
şeyi yeniden oynatmaz, hiçbir yere yazmaz (rapor stdout + `--rapor`).

Etiket, replay'in kademe ızgarasından türetilir: "lehte k1 ATR, ters k2 ATR'den
önce ve `ufuk` bar içinde vuruldu mu". Böylece baraj/ufuk seçimi replay'i
tekrar çalıştırmadan denenebilir.

Disiplin: etiket ve baraj, tablolar **zamanın ilk %70'inde** seçilir; son %30
"dondurulmuş doğrulama" olarak ayrı raporlanır ve kural sabitlenmeden
kullanılmaz.

Kullanım:
    python scripts/puan_analiz.py --girdi var/replay/gozlemler.csv
    python scripts/puan_analiz.py --leh 2 --ters 1 --ufuk 24 --rapor var/replay/rapor.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

KOVA_SINIR = [45, 65, 75, 80, 85, 101]
KOVA_ET = ["<65", "65-74", "75-79", "80-84", "85+"]
TFLER = ["1h", "2h", "4h", "1d"]
BILESENLER = ["kalite", "guc", "geometri", "temas_puan", "olgunluk", "ihlal_cezasi",
              "egim", "daralma_puan", "daralma", "ilerleme", "ust_temas", "alt_temas",
              "direk", "duzeltme", "bant_mesafe_atr", "dogum_mesafe_atr"]


# --------------------------------------------------------------------------- #
# araçlar
# --------------------------------------------------------------------------- #

def auc(y: pd.Series, x: pd.Series) -> float:
    """Mann-Whitney AUC (scipy yok)."""
    m = y.notna() & x.notna()
    yy, xx = y[m].to_numpy(dtype=float), x[m].to_numpy(dtype=float)
    if len(yy) < 30 or yy.min() == yy.max():
        return float("nan")
    r = pd.Series(xx).rank().to_numpy()
    n1 = yy.sum()
    n0 = len(yy) - n1
    return float((r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def spear(a: pd.Series, b: pd.Series) -> float:
    m = a.notna() & b.notna()
    if m.sum() < 10:
        return float("nan")
    return float(a[m].rank().corr(b[m].rank()))


def ga(y: pd.Series, x: pd.Series) -> Tuple[float, float, float]:
    """AUC + sembol kümelemesine saygılı bootstrap %95 aralık."""
    a = auc(y, x)
    m = y.notna() & x.notna()
    d = pd.DataFrame({"y": y[m], "x": x[m], "s": x[m].index.map(lambda _i: _i)})
    return a, float("nan"), float("nan")


def bootstrap_auc(df: pd.DataFrame, ycol: str, xcol: str, tekrar: int = 400,
                  tohum: int = 7) -> Tuple[float, float, float]:
    """Sembol bazlı kümeleme bootstrap'i (aynı sembolün olayları bağımsız değil)."""
    s = df[["sembol", ycol, xcol]].dropna()
    a = auc(s[ycol], s[xcol])
    if not np.isfinite(a):
        return a, float("nan"), float("nan")
    rng = np.random.default_rng(tohum)
    semboller = s.sembol.unique()
    gruplar = {k: g for k, g in s.groupby("sembol")}
    ornekler = []
    for _ in range(tekrar):
        sec = rng.choice(semboller, size=len(semboller), replace=True)
        parca = pd.concat([gruplar[k] for k in sec], ignore_index=True)
        v = auc(parca[ycol], parca[xcol])
        if np.isfinite(v):
            ornekler.append(v)
    if len(ornekler) < 20:
        return a, float("nan"), float("nan")
    return a, float(np.percentile(ornekler, 2.5)), float(np.percentile(ornekler, 97.5))


def etiketle(d: pd.DataFrame, leh: float, ters: float, ufuk: int) -> pd.Series:
    """Lehte `leh` ATR, ters `ters` ATR'den önce mi? (ufuk bar içinde)"""
    tl = d.get(f"tl_{leh:g}")
    tt = d.get(f"tt_{ters:g}")
    if tl is None or tt is None:
        return pd.Series(np.nan, index=d.index)
    l_ok = (tl > 0) & (tl <= ufuk)
    t_ok = (tt > 0) & (tt <= ufuk)
    y = pd.Series(np.nan, index=d.index)
    y[l_ok & (~t_ok | (tl < tt))] = 1.0
    y[t_ok & (~l_ok | (tt < tl))] = 0.0
    return y


def kova(s: pd.Series) -> pd.Series:
    return pd.cut(s, KOVA_SINIR, labels=KOVA_ET)


def oran_ga(y: pd.Series) -> Tuple[float, float, int]:
    y = y.dropna()
    if len(y) == 0:
        return float("nan"), float("nan"), 0
    p = float(y.mean())
    se = float(np.sqrt(max(p * (1 - p), 1e-9) / len(y)))
    return p, 1.96 * se, len(y)


def yuzde(p: float) -> str:
    return "—" if not np.isfinite(p) else f"{p*100:.1f}%"


# --------------------------------------------------------------------------- #
# tablolar
# --------------------------------------------------------------------------- #

def sekil_A(d: pd.DataFrame, satir: List[str]) -> None:
    satir.append("\n## A · Sıralama (kalite kovası → devam oranı)\n")
    satir.append("| TF | kova | n | devam | ±%95 GA | medyan MFE | medyan MAE |")
    satir.append("|---|---|---|---|---|---|---|")
    for tf in TFLER + ["TÜM"]:
        s = d if tf == "TÜM" else d[d.tf == tf]
        s = s.assign(kova=kova(s.kalite))
        for k in KOVA_ET:
            g = s[s.kova == k]
            p, h, n = oran_ga(g.y)
            if n == 0:
                continue
            satir.append(f"| {tf} | {k} | {n} | {yuzde(p)} | ±{h*100:.1f} | "
                         f"{g.bb_mfe.median():.2f} | {g.bb_mae.median():.2f} |")
        a, lo, hi = bootstrap_auc(s, "y", "kalite")
        rho = spear(s.kalite, s.y)
        satir.append(f"| **{tf}** | **AUC** | {int(s.y.notna().sum())} | **{a:.3f}** | "
                     f"[{lo:.3f}, {hi:.3f}] | spearman {rho:+.3f} | |")


def sekil_B(d: pd.DataFrame, satir: List[str], kart_orani: float) -> None:
    satir.append("\n## B · Kalibrasyon (karttaki yüzde tutuyor mu)\n")
    satir.append(f"Kartta yazan: %{kart_orani*100:.0f}. Tabloda 80–84 kovası:\n")
    satir.append("| TF | 80–84 n | gözlenen devam | kart farkı |")
    satir.append("|---|---|---|---|")
    for tf in TFLER + ["TÜM"]:
        s = d if tf == "TÜM" else d[d.tf == tf]
        g = s[(s.kalite >= 80) & (s.kalite < 85)]
        p, h, n = oran_ga(g.y)
        if n:
            satir.append(f"| {tf} | {n} | {yuzde(p)} ±{h*100:.1f} | {(p-kart_orani)*100:+.1f} puan |")


def sekil_C(d: pd.DataFrame, satir: List[str], esikler: Dict[str, int]) -> None:
    satir.append("\n## C · Eşik taraması\n")
    satir.append("Eşik = o TF'de bildirim için gereken en düşük kalite. "
                 "`kapsam` = eşiği geçen gözlemlerin payı.\n")
    satir.append("| TF | eşik | n | kapsam | devam | taban farkı |")
    satir.append("|---|---|---|---|---|---|")
    for tf in TFLER:
        s = d[d.tf == tf]
        taban = s.y.mean()
        for esik in range(60, 96, 5):
            g = s[s.kalite >= esik]
            p, h, n = oran_ga(g.y)
            if n < 30:
                continue
            im = " ←" if esikler.get(tf) == esik else ""
            satir.append(f"| {tf} | {esik}{im} | {n} | {n/len(s)*100:.0f}% | "
                         f"{yuzde(p)} | {(p-taban)*100:+.1f} |")


def sekil_D(d: pd.DataFrame, satir: List[str]) -> None:
    satir.append("\n## D · Bileşenler\n")
    satir.append("| bileşen | AUC | ±%95 GA | dolu n |")
    satir.append("|---|---|---|---|")
    for c in BILESENLER:
        if c not in d:
            continue
        a, lo, hi = bootstrap_auc(d, "y", c, tekrar=250)
        satir.append(f"| {c} | {a:.3f} | [{lo:.3f}, {hi:.3f}] | {int(d[c].notna().sum())} |")

    satir.append("\n**Bileşen korelasyonu (spearman, 0,85 üstü = çift sayım):**\n")
    var = [c for c in BILESENLER if c in d and d[c].notna().sum() > 500]
    satir.append("| | " + " | ".join(v[:6] for v in var) + " |")
    satir.append("|---" * (len(var) + 1) + "|")
    for a in var:
        hucre = []
        for b in var:
            m = d[a].notna() & d[b].notna()
            v = d[a][m].rank().corr(d[b][m].rank()) if m.sum() > 100 else float("nan")
            hucre.append("—" if not np.isfinite(v) else f"{v:+.2f}")
        satir.append(f"| **{a}** | " + " | ".join(hucre[:6]) + " |")


def sekil_E(d: pd.DataFrame, satir: List[str]) -> None:
    satir.append("\n## E · TF ve desen ayrımı\n")
    satir.append("| kesim | n | devam | AUC (kalite) |")
    satir.append("|---|---|---|---|")
    for tf in TFLER:
        s = d[d.tf == tf]
        a = auc(s.y, s.kalite)
        satir.append(f"| TF {tf} | {int(s.y.notna().sum())} | {yuzde(s.y.mean())} | {a:.3f} |")
    for aile in d.aile.dropna().unique():
        s = d[d.aile == aile]
        if len(s) < 100:
            continue
        satir.append(f"| {aile} | {int(s.y.notna().sum())} | {yuzde(s.y.mean())} | "
                     f"{auc(s.y, s.kalite):.3f} |")
    satir.append("")
    satir.append("| desen | n | devam | AUC |")
    satir.append("|---|---|---|---|")
    for desen, s in d.groupby("desen"):
        if len(s) < 100:
            continue
        satir.append(f"| {desen} | {int(s.y.notna().sum())} | {yuzde(s.y.mean())} | "
                     f"{auc(s.y, s.kalite):.3f} |")


def sekil_F(d: pd.DataFrame, satir: List[str]) -> None:
    satir.append("\n## F · Sızıntı ve rejim\n")
    a_d = auc(d.y, d.kalite)
    a_m = auc((d.motor_sonuc == "COMPLETED").astype(float), d.motor_kalite)
    satir.append(f"- Kırılımda dondurulmuş kalite → AUC **{a_d:.3f}** (kullandığımız)")
    satir.append(f"- Sonuç anındaki kalite (`motor_kalite`, sızmış) → AUC **{a_m:.3f}**")
    satir.append("- İkisi arasındaki fark, sızıntı olsaydı ne kadar şişerdi sorusunun cevabı.\n")

    # hafta etkisi: aynı hafta içinde kova ortalaması
    d2 = d.copy()
    d2["tarih"] = pd.to_datetime(d2["zaman"], errors="coerce", utc=True)
    d2 = d2[d2.tarih.notna()]
    d2["hafta"] = d2.tarih.dt.isocalendar().year.astype(str) + "-" + \
        d2.tarih.dt.isocalendar().week.astype(str).str.zfill(2)
    hafta_ort = d2.groupby(["sembol", "hafta"]).y.transform("mean")
    d2["arti"] = d2.y - hafta_ort
    d2["kova"] = kova(d2.kalite)
    satir.append("**Hafta etkisi çıkarıldıktan sonra kova farkı (ham vs artık):**\n")
    satir.append("| kova | n | ham devam | hafta-içi artık |")
    satir.append("|---|---|---|---|")
    for k in KOVA_ET:
        g = d2[d2.kova == k]
        if len(g) < 30:
            continue
        satir.append(f"| {k} | {len(g)} | {yuzde(g.y.mean())} | {g.arti.mean()*100:+.1f} puan |")


def sekil_G(d: pd.DataFrame, satir: List[str], kesim: float = 0.70) -> None:
    d2 = d.copy()
    d2["tarih"] = pd.to_datetime(d2["zaman"], errors="coerce", utc=True)
    d2 = d2[d2.tarih.notna()].sort_values("tarih")
    if len(d2) < 200:
        return
    n_kes = int(len(d2) * kesim)
    kes_tarih = d2.tarih.iloc[n_kes]
    ilk, son = d2.iloc[:n_kes], d2.iloc[n_kes:]
    satir.append(f"\n## G · Genellenebilirlik (kesim: {kes_tarih.date()})\n")
    satir.append("| dilim | n | taban | AUC | spearman |")
    satir.append("|---|---|---|---|---|")
    for ad, s in (("keşif (ilk %70)", ilk), ("dondurulmuş doğrulama (son %30)", son)):
        satir.append(f"| {ad} | {int(s.y.notna().sum())} | {yuzde(s.y.mean())} | "
                     f"{auc(s.y, s.kalite):.3f} | {spear(s.kalite, s.y):+.3f} |")


# --------------------------------------------------------------------------- #
# ana akış
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Puan replay analizi (salt okunur)")
    ap.add_argument("--girdi", default="var/replay/gozlemler.csv")
    ap.add_argument("--leh", type=float, default=2.0, help="lehte baraj (ATR)")
    ap.add_argument("--ters", type=float, default=1.0, help="ters baraj (ATR)")
    ap.add_argument("--ufuk", type=int, default=24)
    ap.add_argument("--kart", type=float, default=0.76, help="karttaki devam yüzdesi")
    ap.add_argument("--rapor", default=None)
    ap.add_argument("--etiket-taramasi", action="store_true",
                    help="baraj/ufuk duyarlılık tablosunu bas")
    args = ap.parse_args(argv)

    yol = Path(args.girdi)
    if not yol.is_absolute():
        yol = REPO / yol
    d = pd.read_csv(yol)
    d = d[d.pencere_tam == 1].copy()
    d["y"] = etiketle(d, args.leh, args.ters, args.ufuk)

    satir: List[str] = []
    satir.append(f"# Puan replay raporu — {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    satir.append(f"\nGözlem: **{len(d)}** kırılım · etiket: lehte {args.leh:g} ATR / "
                 f"ters {args.ters:g} ATR / {args.ufuk} bar · "
                 f"taban oran **{yuzde(d.y.mean())}**")

    if args.etiket_taramasi:
        satir.append("\n### Etiket duyarlılığı (kalite AUC)\n")
        satir.append("| lehte | ters | ufuk | n | taban | AUC |")
        satir.append("|---|---|---|---|---|---|")
        for leh in (1.0, 1.5, 2.0, 3.0):
            for ters in (0.8, 1.0, 1.5):
                for ufuk in (12, 24, 48):
                    y = etiketle(d, leh, ters, ufuk)
                    a = auc(y, d.kalite)
                    satir.append(f"| {leh:g} | {ters:g} | {ufuk} | {int(y.notna().sum())} | "
                                 f"{yuzde(y.mean())} | {a:.3f} |")

    sekil_A(d, satir)
    sekil_B(d, satir, args.kart)
    sekil_C(d, satir, {"1h": 80, "2h": 78, "4h": 75, "1d": 70})
    sekil_D(d, satir)
    sekil_E(d, satir)
    sekil_F(d, satir)
    sekil_G(d, satir)

    metin = "\n".join(satir)
    print(metin)
    if args.rapor:
        p = Path(args.rapor)
        if not p.is_absolute():
            p = REPO / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(metin, encoding="utf-8")
        print(f"\nRapor: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
