# -*- coding: utf-8 -*-
"""Beş bedava soru: formasyon şekli dışındaki koşullar sonucu ayırıyor mu?

Replay YOK, üretim kodu YOK. Girdi: `var/replay/gozlemler.csv` + `backfill_data/`.

S1 · Sıra      — aynı sembolde art arda gelen kırılımların ilki mi iyi?
S2 · Hafta     — başarı haftalar arasında kümeleniyor mu? Geçen hafta tahmin ediyor mu?
S3 · Sembol    — bir sembolün geçmiş başarısı geleceğini öngörüyor mu?
S4 · Likidite  — hacim ve oynaklık düzeyi sonucu ayırıyor mu?
S5 · Rejim     — kırılım yönü endeksin yönüyle uyumlu olunca daha mı iyi?
S6 · Göreli    — rejim sabit tutulunca (aynı sembol+TF+hafta) puan ayırıyor mu?

Her soru iki bağımsız bölmede (ayrık sembol, uzak dönem) ayrı ayrı raporlanır;
tek bölmede çıkan fark "bulgu" sayılmaz.

Kullanım:
    python scripts/puan_sorular.py
"""

from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402
from puan_tarama import bolmeler, bootstrap_auc, ozellikler  # noqa: E402


def oran(y: pd.Series) -> Tuple[float, float, int]:
    y = y.dropna()
    if len(y) == 0:
        return float("nan"), float("nan"), 0
    p = float(y.mean())
    se = float(np.sqrt(max(p * (1 - p), 1e-9) / len(y)))
    return p, 1.96 * se, len(y)


def hucre(p: float, h: float, n: int) -> str:
    if n == 0:
        return "—"
    return f"%{p*100:.1f} ±{h*100:.1f} (n={n})"


def likidite_tablosu() -> pd.DataFrame:
    """Sembol bazlı ortalama işlem hacmi (TL) — backfill'den, motor çalışmadan."""
    satir = []
    for p in sorted((REPO / "backfill_data").glob("*_1h.csv.gz")):
        sembol = p.name.rsplit("_", 1)[0]
        if sembol.startswith("XU"):
            continue
        try:
            d = pd.read_csv(p, compression="gzip", usecols=["close", "volume"])
        except Exception:
            continue
        tl = (d.close * d.volume).replace([np.inf, -np.inf], np.nan).dropna()
        tl = tl[tl > 0]
        if len(tl) == 0:
            continue
        satir.append({"sembol": sembol, "hacim_tl": float(tl.median())})
    return pd.DataFrame(satir)


def endeks_serisi(tf: str) -> pd.Series:
    p = REPO / "backfill_data" / f"XU100_{tf}.csv.gz"
    d = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d["close"]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Beş bedava soru")
    ap.add_argument("--girdi", default="var/replay/gozlemler.csv")
    ap.add_argument("--leh", type=float, default=2.0)
    ap.add_argument("--ters", type=float, default=1.0)
    ap.add_argument("--ufuk", type=int, default=24)
    ap.add_argument("--rapor", default="var/replay/sorular.md")
    args = ap.parse_args(argv)

    yol = Path(args.girdi)
    d = pd.read_csv(yol if yol.is_absolute() else REPO / yol)
    d = d[d.pencere_tam == 1]
    d = ozellikler(d)
    d["y"] = etiketle(d, args.leh, args.ters, args.ufuk)
    d = d[d.y.notna()].sort_values(["sembol", "tf", "bar"]).reset_index(drop=True)
    d["hafta"] = (d.tarih.dt.isocalendar().year.astype(str) + "-"
                  + d.tarih.dt.isocalendar().week.astype(str).str.zfill(2))

    b = bolmeler(d)
    S, Z = b["S"], b["Z"]
    out: List[str] = []
    out.append("# Beş bedava soru\n")
    out.append(f"n={len(d)} · taban %{d.y.mean()*100:.1f} · "
               f"ayrık sembol keşif {len(S[0])}/doğrulama {len(S[1])} · "
               f"uzak dönem keşif {len(Z[0])}/doğrulama {len(Z[1])}\n")

    # ---------------- S1 · kırılım sırası ----------------
    out.append("## S1 · İlk kırılım mı, sonrakiler mi?\n")
    g = d.groupby(["sembol", "tf"])
    d["onceki_bar"] = g.bar.shift(1)
    d["aralik"] = d.bar - d.onceki_bar
    d["ilk_mi"] = d.onceki_bar.isna() | (d.aralik > 100)
    kova = pd.cut(d.aralik, [0, 5, 24, 100, 10000],
                  labels=["0-5 bar", "6-24 bar", "25-100 bar", ">100 bar"])
    d["sira"] = kova.astype(object)
    d.loc[d.ilk_mi, "sira"] = "ilk kırılım (100+ bar)"
    b = bolmeler(d)          # `sira` sütunu eklendikten sonra bölmeleri tazele
    S, Z = b["S"], b["Z"]
    out.append("| kesim | ayrık sembol keşif | ayrık sembol doğrulama | uzak dönem doğrulama |")
    out.append("|---|---|---|---|")
    for ad in ["ilk kırılım (100+ bar)", "0-5 bar", "6-24 bar", "25-100 bar"]:
        s1 = S[0][S[0].sira == ad] if "sira" in S[0] else S[0].assign(sira=d.loc[S[0].index, "sira"]).query("sira==@ad")
        s2 = S[1].assign(sira=d.loc[S[1].index, "sira"]).query("sira==@ad")
        z2 = Z[1].assign(sira=d.loc[Z[1].index, "sira"]).query("sira==@ad")
        out.append(f"| {ad} | {hucre(*oran(s1.y))} | {hucre(*oran(s2.y))} | {hucre(*oran(z2.y))} |")
    out.append("")

    # ---------------- S2 · hafta kümelenmesi ----------------
    out.append("## S2 · Başarı haftalar arasında kümeleniyor mu?\n")
    hafta = d.groupby("hafta").y.agg(["mean", "size"])
    hafta = hafta[hafta["size"] >= 30]
    p_ort = float(d.y.mean())
    # beklenen (binom) varyans ile gözlenen arasındaki oran
    beklenen = float(np.sum(hafta["size"] * p_ort * (1 - p_ort))) / max(1.0, float(np.sum(hafta["size"])))
    gozlenen = float(np.sum(hafta["size"] * (hafta["mean"] - p_ort) ** 2) / max(1, len(hafta) - 1))
    out.append(f"- Hafta sayısı (n≥30): **{len(hafta)}** · haftalık başarı %{hafta['mean'].min()*100:.0f}"
               f"–%{hafta['mean'].max()*100:.0f} · ortanca %{hafta['mean'].median()*100:.0f}")
    out.append(f"- Beklenen (saf şans) hafta-arası sd: %{np.sqrt(beklenen)*100:.1f} · "
               f"gözlenen: %{np.sqrt(gozlenen)*100:.1f}")
    oran_sd = float(np.sqrt(gozlenen) / max(1e-9, np.sqrt(beklenen)))
    out.append(f"- **Kümelenme katsayısı: {oran_sd:.2f}** (1,00 = saf şans, >1,3 = gerçek rejim etkisi)\n")

    # geçen 2 haftanın piyasa başarısı bu haftayı öngörüyor mu?
    sirali = hafta.sort_index()
    gecmis = sirali["mean"].shift(1).rolling(2).mean()
    d["gecen_hafta"] = d.hafta.map(gecmis)
    out.append("Geçen 2 haftanın piyasa başarı oranı, bu haftanın kırılımını öngörüyor mu?\n")
    out.append("| bölme | n | AUC | %95 GA |")
    out.append("|---|---|---|---|")
    for ad, te in (("ayrık sembol (doğrulama)", S[1]), ("uzak dönem (doğrulama)", Z[1])):
        s = te.copy()
        s["g"] = s.hafta.map(gecmis)
        a, lo, hi = bootstrap_auc(s, "y", "g", tekrar=300)
        out.append(f"| {ad} | {int(s.g.notna().sum())} | {a:.3f} | [{lo:.3f}, {hi:.3f}] |")
    out.append("")

    # ---------------- S3 · sembol kalıcılığı ----------------
    out.append("## S3 · Sembol kalıcılığı (geçmiş başarı geleceği öngörüyor mu?)\n")
    satirlar = []
    for sembol, s in d.groupby("sembol"):
        s = s.sort_values("tarih")
        n = len(s)
        if n < 30:
            continue
        yarim = n // 2
        ilk, son = s.iloc[:yarim], s.iloc[yarim:]
        if len(ilk) < 15 or len(son) < 15:
            continue
        satirlar.append({"sembol": sembol, "ilk": ilk.y.mean(), "son": son.y.mean(),
                         "n_ilk": len(ilk), "n_son": len(son)})
    sy = pd.DataFrame(satirlar)
    if len(sy) >= 10:
        r = float(sy["ilk"].rank().corr(sy["son"].rank()))
        out.append(f"- Sembol sayısı: **{len(sy)}** · ilk yarı ↔ ikinci yarı spearman: **{r:+.3f}**")
        out.append(f"- Sembol başarı oranı dağılımı: %{sy['ilk'].min()*100:.0f} – %{sy['ilk'].max()*100:.0f}, "
                   f"ortanca %{sy['ilk'].median()*100:.0f}")
        en_iyi = sy.nlargest(3, "ilk")
        out.append("- İlk yarıda en iyi 3: " + ", ".join(
            f"{r.sembol} %{r.ilk*100:.0f}→%{r.son*100:.0f}" for r in en_iyi.itertuples()))
    else:
        out.append("- Yeterli sembol yok.")
    out.append("")

    # ---------------- S4 · likidite / oynaklık ----------------
    out.append("## S4 · Likidite ve oynaklık düzeyi\n")
    lik = likidite_tablosu()
    d2 = d.merge(lik, on="sembol", how="left")
    d2["hacim_kova"] = pd.qcut(d2.hacim_tl, 4, labels=["en düşük", "düşük", "yüksek", "en yüksek"],
                               duplicates="drop")
    d2["oynak_kova"] = pd.qcut(d2.atr_yuzde, 4, labels=["sakin", "normal", "oynak", "çok oynak"],
                               duplicates="drop")
    out.append("| kesim | n | devam |")
    out.append("|---|---|---|")
    for kolon in ("hacim_kova", "oynak_kova"):
        for k, s in d2.groupby(kolon, observed=True):
            out.append(f"| {kolon} = {k} | {len(s)} | {hucre(*oran(s.y))} |")
    out.append("")

    # ---------------- S5 · endeks uyumu ----------------
    out.append("## S5 · Kırılım yönü endeksin yönüyle uyumlu mu?\n")
    for tf in ("1h", "2h", "4h", "1d"):
        idx = endeks_serisi("1h" if tf in ("1h", "2h", "4h") else "1d")
        egim = (idx / idx.shift(20) - 1.0).dropna()
        s = d[d.tf == tf].copy()
        if len(s) == 0:
            continue
        # gözlem zamanına en yakın endeks barı (geriye doğru eşleştir)
        # tz farkına takılmamak için her iki tarafı da UTC nanosaniyeye çevir
        idx_ns = pd.to_datetime(egim.index, utc=True).asi8
        obs_ns = pd.to_datetime(s["tarih"], utc=True, errors="coerce").astype("int64").to_numpy()
        konum = np.searchsorted(idx_ns, obs_ns, side="right") - 1
        gecerli = (konum >= 0) & (konum < len(egim))
        s = s[gecerli].copy()
        s["endeks_egim"] = egim.to_numpy()[konum[gecerli]]
        s["uyum"] = np.sign(s.yon) == np.sign(s.endeks_egim)
        uy, uydeg = s[s.uyum], s[~s.uyum]
        out.append(f"- **{tf}**: uyumlu {hucre(*oran(uy.y))} · ters {hucre(*oran(uydeg.y))}")
    out.append("")

    # ---------------- S6 · göreli (rejim sabit) ----------------
    out.append("## S6 · Rejim sabitken puan ayırıyor mu? (aynı sembol+TF+hafta içinde)\n")
    out.append("Her hücrede kalitenin ayırt etme gücü ayrı hesaplanır, sonra ağırlıklı ortalanır "
               "(0,50 = hiç ayırmıyor).\n")
    out.append("| bölme | hücre sayısı | n | ortalama AUC |")
    out.append("|---|---|---|---|")
    for ad, s in (("ayrık sembol (keşif)", S[0]), ("ayrık sembol (doğrulama)", S[1]),
                  ("uzak dönem (doğrulama)", Z[1])):
        deger, agirlik = [], []
        for _k, g in s.groupby(["sembol", "tf", "hafta"]):
            if len(g) < 4 or g.y.nunique() < 2:
                continue
            # küçük hücreler için eşiksiz AUC
            gg = g[["y", "kalite"]].dropna()
            if len(gg) < 4 or gg.y.nunique() < 2:
                continue
            rr = gg.kalite.rank().to_numpy()
            n1 = gg.y.sum()
            n0 = len(gg) - n1
            a = float((rr[gg.y.to_numpy() == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
            if np.isfinite(a):
                deger.append(a)
                agirlik.append(len(g))
        if deger:
            ort = float(np.average(deger, weights=agirlik))
            out.append(f"| {ad} | {len(deger)} | {int(sum(agirlik))} | **{ort:.3f}** |")
        else:
            out.append(f"| {ad} | 0 | 0 | — |")
    out.append("")

    metin = "\n".join(out)
    print(metin)
    p = Path(args.rapor)
    if not p.is_absolute():
        p = REPO / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(metin, encoding="utf-8")
    print(f"\nRapor: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
