# -*- coding: utf-8 -*-
"""Eşleştirilmiş kontrol: her kırılımın "fazlası" kaç puan?

SALT OKUNUR.

Fikir: kırılımın ham devam oranı, içinde bulunduğu trendin eseridir. Bu yüzden
her kırılım, **aynı sembol + aynı zaman dilimi + aynı ay + aynı yön** için
hesaplanan rastgele giriş tabanıyla eşleştirilir:

    fazla = kırılım sonucu (0/1) − rastgele taban (aynı hücre)

Böylece trend, sembol, mevsim ve yön etkisi çıkar; geriye "formasyon, o ay o
sembolde rastgele girmekten daha mı iyi" sorusu kalır.

Sonra: hangi özellik bu fazlayı öngörüyor? (AUC ve kova ortalamaları)

Kullanım:
    python scripts/kontrol_eslesmis.py
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

from data import resample_ohlcv  # noqa: E402
from patterns.indicators import calculate_atr  # noqa: E402
from puan_analiz import etiketle  # noqa: E402
from kontrol_deneyi import ilk_vurus, etiketle_np, endeks, UFUK_MAX  # noqa: E402


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Eşleştirilmiş kontrol deneyi")
    ap.add_argument("--gozlem", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/eslesmis.md")
    args = ap.parse_args(argv)

    goz = pd.read_csv(REPO / args.gozlem, low_memory=False)
    goz["y"] = etiketle(goz, 2.0, 1.0, 24)
    goz = goz[goz.y.notna()].copy()
    goz["tarih"] = pd.to_datetime(goz["zaman"], utc=True, errors="coerce")
    goz["ay"] = goz.tarih.dt.to_period("M").astype(str)

    print("rastgele tabanlar hesaplanıyor (sembol × TF × ay × yön)...")
    satir: List[Dict] = []
    semboller = sorted(goz.sembol.unique())
    for i, sembol in enumerate(semboller, 1):
        p = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
        if not p.exists():
            continue
        d1h = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
        d1h = d1h[~d1h.index.duplicated(keep="last")].sort_index()
        for tf in ("1h", "2h", "4h", "1d"):
            d = d1h if tf == "1h" else resample_ohlcv(d1h, tf)
            n = len(d)
            if n < 120:
                continue
            atr = calculate_atr(d, 14).to_numpy(float)
            high = d["high"].to_numpy(float)
            low = d["low"].to_numpy(float)
            close = d["close"].to_numpy(float)
            egim = endeks(tf)
            idx_ns = pd.to_datetime(egim.index, utc=True).astype("int64").to_numpy()
            son = n - UFUK_MAX - 1
            if son < 50:
                continue
            idx = np.arange(0, son)
            idx = idx[(atr[idx] > 0) & np.isfinite(atr[idx])]
            if len(idx) < 50:
                continue
            konum = np.searchsorted(idx_ns, pd.to_datetime(d.index[idx], utc=True)
                                    .astype("int64").to_numpy(), side="right") - 1
            ok = (konum >= 0) & (konum < len(egim))
            isaret = np.zeros(len(idx))
            isaret[ok] = np.sign(egim.to_numpy()[konum[ok]])
            gecerli = ok & (isaret != 0)
            pencere = np.arange(1, UFUK_MAX + 1)
            kollar = np.clip(idx[:, None] + pencere[None, :], 0, n - 1)
            yukari = high[kollar] - close[idx][:, None]
            asagi = close[idx][:, None] - low[kollar]
            a = atr[idx]
            up_leh = ilk_vurus(yukari, 2.0 * a)
            up_ters = ilk_vurus(yukari, 1.0 * a)
            dn_leh = ilk_vurus(asagi, 2.0 * a)
            dn_ters = ilk_vurus(asagi, 1.0 * a)
            y_long = etiketle_np(up_leh, dn_ters, 24)
            y_short = etiketle_np(dn_leh, up_ters, 24)
            for yon, y in ((1, y_long), (-1, y_short)):
                m = gecerli & np.isfinite(y)
                if m.sum() < 20:
                    continue
                sub = pd.DataFrame({"ay": d.index[idx[m]].strftime("%Y-%m"), "y": y[m]})
                for ay, g in sub.groupby("ay"):
                    satir.append({"sembol": sembol, "tf": tf, "ay": ay, "yon": yon,
                                  "n": len(g), "basari": int(g.y.sum())})
        if i % 25 == 0 or i == len(semboller):
            print(f"  {i}/{len(semboller)}", flush=True)

    rnd = pd.DataFrame(satir)
    rnd.to_csv(REPO / "var/replay/rastgele_aylik.csv", index=False)

    # --- eşleştir
    anahtar = ["sembol", "tf", "ay", "yon"]
    tab = rnd.groupby(anahtar).agg(n_r=("n", "sum"), b_r=("basari", "sum")).reset_index()
    tab["taban"] = tab.b_r / tab.n_r
    tab.loc[tab.n_r < 30, "taban"] = np.nan          # az örnekli hücreleri at

    # yedek: sembol × TF × yön (ay yok)
    yedek = rnd.groupby(["sembol", "tf", "yon"]).agg(n_r=("n", "sum"), b_r=("basari", "sum"))
    yedek["taban_yedek"] = yedek.b_r / yedek.n_r

    m = goz.merge(tab[anahtar + ["taban", "n_r"]], on=anahtar, how="left")
    m = m.merge(yedek[["taban_yedek"]], on=["sembol", "tf", "yon"], how="left")
    m["taban"] = m["taban"].fillna(m["taban_yedek"])
    m["fazla"] = m.y - m.taban
    m = m[m.taban.notna()].copy()

    out = ["# Eşleştirilmiş kontrol · formasyonun fazlası\n",
           f"Eşleşen gözlem {len(m)} · kapsam %{len(m)/len(goz)*100:.0f}\n",
           f"Ham devam oranı %{m.y.mean()*100:.1f} · eşleşen rastgele taban %{m.taban.mean()*100:.1f} · "
           f"**ortalama fazla {(m.fazla.mean())*100:+.1f} puan**\n"]

    # güven: sembol kümesi bootstrap
    rng = np.random.default_rng(5)
    gruplar = [g.fazla.to_numpy() for _, g in m.groupby("sembol")]
    bs = []
    for _ in range(500):
        sec = rng.integers(0, len(gruplar), len(gruplar))
        bs.append(np.concatenate([gruplar[i] for i in sec]).mean() * 100)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    out.append(f"%95 GA [{lo:+.1f}, {hi:+.1f}] puan (sembol kümesi bootstrap)\n")

    # --- özellik taraması: fazlayı ne öngörüyor?
    def auc_eslesen(x: pd.Series) -> float:
        g = m[["fazla", x.name]].dropna()
        if len(g) < 200:
            return float("nan")
        poz = g.fazla > 0
        if poz.sum() < 50 or (~poz).sum() < 50:
            return float("nan")
        r = g[x.name].rank().to_numpy()
        n1 = poz.sum()
        n0 = len(g) - n1
        return float((r[poz.to_numpy()].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    ADAYLAR = ["kalite", "mtf_uyum", "yapi_uyum", "d_yapi", "d_ust_ma50", "d_ust_ma200",
               "h_ust_ma20", "h_ust_ma50", "d_donchian20", "d_donchian55", "h_donchian20",
               "d_zirve_mesafe", "d_engel_atr", "zirve_uyum", "h_kosu_atr", "d_ret20",
               "d_ret60", "h_ret20", "hacim_orani", "h_hacim_trend", "h_hacim_kuruma",
               "d_atr_yuzdelik", "h_atr_yuzdelik", "h_aralik_atr", "h_govde_konum",
               "h_gap_atr", "seans_saati", "p_breadth", "p_dispersion", "e_x_ust_ma50",
               "endeks_uyum", "beta60", "kore60", "goreli_guc", "bant_mesafe_atr",
               "bant_genislik_atr", "daralma", "olgunluk", "temas_puan", "guc"]
    out.append("## Fazlayı öngören özellikler\n")
    out.append("| özellik | AUC (fazla>0) | n |")
    out.append("|---|---|---|")
    deger = []
    for k in ADAYLAR:
        if k not in m:
            continue
        a = auc_eslesen(m[k])
        if np.isfinite(a):
            deger.append((k, a))
    for k, a in sorted(deger, key=lambda t: -abs(t[1] - 0.5))[:15]:
        out.append(f"| {k} | {a:.3f} | {int(m[k].notna().sum())} |")

    # --- kırılım içi en iyi / en kötü dilimler (fazla cinsinden)
    out.append("\n## Fazla kovaları (örnek: mtf_uyum, kalite)\n")
    for k in ("mtf_uyum", "kalite", "hacim_orani", "yapi_uyum"):
        if k not in m:
            continue
        g = m[[k, "fazla", "y"]].dropna()
        if len(g) < 300:
            continue
        if k == "kalite":
            g["kova"] = pd.qcut(g[k], 5, labels=["1", "2", "3", "4", "5"], duplicates="drop")
        else:
            try:
                g["kova"] = pd.qcut(g[k], 4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
            except ValueError:
                continue
        out.append(f"\n**{k}**\n")
        out.append("| kova | n | ham devam | fazla (puan) |")
        out.append("|---|---|---|---|")
        for kk, gg in g.groupby("kova", observed=True):
            out.append(f"| {kk} | {len(gg)} | %{gg.y.mean()*100:.1f} | "
                       f"{gg.fazla.mean()*100:+.1f} |")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
