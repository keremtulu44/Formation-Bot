# -*- coding: utf-8 -*-
"""Kontrol deneyi 2: MTF uyumu formasyona mı ait, trende mi?

SALT OKUNUR.

Soru: "çoklu zaman dilimi uyumu" kırılımlarda devam oranını yükseltiyor
(gözlem: kademe 4 → %39,9 · kademe 0 → %30,8). Aynı uyum ölçüsü RASTGELE
girişlerde de aynı işi yapıyor mu? Yapıyorsa kazanç formasyondan değil,
trend filtresinden geliyor demektir.

Yöntem: her sembolde, her bar için (kırılım TF'sinde) sanal giriş üretilir;
o barın MTF uyumu kırılım gözlemleriyle BİREBİR aynı formülle hesaplanır:
    1s kapanış/MA20, 2s kapanış/MA20, 4s kapanış/MA20, 1g kapanış/MA50
Yön = endeks eğiminin işareti (uyumlu giriş). Etiket 2/1/24, ATR normalizasyonu
kırılım tarafıyla aynı.

Kullanım:
    python scripts/kontrol_mtf.py
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
from ozellik_deposu import piyasa_serileri  # noqa: E402

_SERI: Dict[str, Dict[str, pd.Series]] = {}


def uyum_serileri(sembol: str) -> Optional[Dict[str, pd.Series]]:
    """Sembol için dört TF'de (kapanış/MA) işareti serisi."""
    if sembol in _SERI:
        return _SERI[sembol]
    p = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
    if not p.exists():
        return None
    d1h = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    d1h = d1h[~d1h.index.duplicated(keep="last")].sort_index()
    d1d = pd.read_csv(REPO / "backfill_data" / f"{sembol}_1d.csv.gz", compression="gzip",
                      parse_dates=["bar_time"]).set_index("bar_time")
    d1d = d1d[~d1d.index.duplicated(keep="last")].sort_index()
    seri: Dict[str, pd.Series] = {}
    for tf in ("1h", "2h", "4h"):
        dd = d1h if tf == "1h" else resample_ohlcv(d1h, tf)
        k = dd["close"]
        ma = k.rolling(20, min_periods=7).mean()
        seri[tf] = np.sign(k / ma - 1.0)
    kd = d1d["close"]
    seri["1d"] = np.sign(kd / kd.rolling(50, min_periods=17).mean() - 1.0)
    _SERI[sembol] = seri
    return seri


def uyum_sayisi(seri: Dict[str, pd.Series], zaman_index, yon: int) -> np.ndarray:
    toplam = np.zeros(len(zaman_index))
    for tf, s in seri.items():
        v = s.reindex(zaman_index, method="ffill").to_numpy(float)
        toplam += (np.sign(v) == yon).astype(float)
    return toplam


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="MTF kontrol deneyi")
    ap.add_argument("--gozlem", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/kontrol_mtf.md")
    args = ap.parse_args(argv)

    goz = pd.read_csv(REPO / args.gozlem, low_memory=False)
    goz["y"] = etiketle(goz, 2.0, 1.0, 24)
    goz = goz[goz.y.notna()]

    piyasa = piyasa_serileri()
    pns = pd.to_datetime(piyasa.index, utc=True).astype("int64").to_numpy()
    print(f"breadth serisi: {len(piyasa)} gün")

    semboller = sorted(goz.sembol.unique())
    satirlar: List[Dict] = []
    for i, sembol in enumerate(semboller, 1):
        seri = uyum_serileri(sembol)
        if seri is None:
            continue
        p = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
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
            idx = np.arange(0, max(0, son))
            if len(idx) < 50:
                continue
            idx = idx[(atr[idx] > 0) & np.isfinite(atr[idx])]
            konum = np.searchsorted(idx_ns, pd.to_datetime(d.index[idx], utc=True)
                                    .astype("int64").to_numpy(), side="right") - 1
            ok = (konum >= 0) & (konum < len(egim))
            isaret = np.zeros(len(idx))
            isaret[ok] = np.sign(egim.to_numpy()[konum[ok]])
            gecerli = ok & (isaret != 0)
            if gecerli.sum() < 50:
                continue

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
            y_uyum = np.where(isaret > 0, y_long, y_short)

            # her barın MTF uyumu (giriş yönüne göre)
            uyum = np.zeros(len(idx))
            for j, yon in enumerate(np.where(isaret > 0, 1, -1)):
                pass
            # toplu hesap: iki yön için uyum serisi
            uyum_uzun = uyum_sayisi(seri, d.index[idx], 1)
            uyum_kisa = uyum_sayisi(seri, d.index[idx], -1)
            uyum = np.where(isaret > 0, uyum_uzun, uyum_kisa)

            m = gecerli & np.isfinite(y_uyum)
            if m.sum() == 0:
                continue
            # breadth: gözlem zamanındaki piyasa genişliği
            kn = np.searchsorted(pns, pd.to_datetime(d.index[idx], utc=True)
                                 .astype("int64").to_numpy(), side="right") - 1
            br = np.full(len(idx), np.nan)
            gb = (kn >= 0) & (kn < len(piyasa))
            br[gb] = piyasa["breadth"].to_numpy()[kn[gb]]
            df = pd.DataFrame({"uyum": uyum[m], "y": y_uyum[m], "tf": tf, "breadth": br[m]})
            df["b_kov"] = pd.cut(df.breadth, [-1, 0.5, 0.65, 1.01],
                                 labels=["<0.50", "0.50-0.65", ">=0.65"])
            df["b_kov"] = df["b_kov"].astype(str).where(df.breadth.notna(), "yok")
            for (k, bk), g in df.groupby([df.uyum.astype(int), df.b_kov]):
                satirlar.append({"sembol": sembol, "tf": tf, "kademe": int(k),
                                 "b_kov": str(bk), "n": len(g), "basari": int(g.y.sum())})
        if i % 20 == 0 or i == len(semboller):
            print(f"  {i}/{len(semboller)} sembol", flush=True)

    rnd = pd.DataFrame(satirlar)
    rnd.to_csv(REPO / "var/replay/rastgele_mtf.csv", index=False)

    out = ["# Kontrol 2 · MTF uyumu formasyona mı ait?\n",
           "Rastgele girişler aynı MTF uyum formülüyle kademelendirildi.\n",
           "| kademe | kırılım n | kırılım devam | rastgele n | rastgele devam | fark |",
           "|---|---|---|---|---|---|"]
    for k in range(5):
        gk = goz[goz.mtf_uyum == k]
        gr = rnd[rnd.kademe == k]
        if len(gk) == 0 or len(gr) == 0:
            continue
        pk = gk.y.mean()
        pr = gr.basari.sum() / gr.n.sum()
        out.append(f"| {k} | {len(gk)} | %{pk*100:.1f} | {int(gr.n.sum()):,} | "
                   f"%{pr*100:.1f} | **{(pk-pr)*100:+.1f}** |")

    out.append("\n## Bileşik koşul: MTF≥4 VE breadth≥0,65\n")
    out.append("| kesim | kırılım n | kırılım devam | rastgele n | rastgele devam | fark |")
    out.append("|---|---|---|---|---|---|")
    for ad, mm_k, mm_r in (
            ("MTF≥4 + breadth≥0,65", (goz.mtf_uyum >= 4) & (goz.p_breadth >= 0.65),
             (rnd.kademe >= 4) & (rnd.b_kov == ">=0.65")),
            ("MTF≥4 (breadth fark etmez)", goz.mtf_uyum >= 4, rnd.kademe >= 4),
            ("breadth≥0,65 (MTF fark etmez)", goz.p_breadth >= 0.65, rnd.b_kov == ">=0.65")):
        gk = goz[mm_k]
        gr = rnd[mm_r]
        if len(gk) < 50 or gr.n.sum() < 100:
            continue
        pk = gk.y.mean()
        pr = gr.basari.sum() / gr.n.sum()
        out.append(f"| {ad} | {len(gk)} | %{pk*100:.1f} | {int(gr.n.sum()):,} | "
                   f"%{pr*100:.1f} | **{(pk-pr)*100:+.1f}** |")

    out.append("\n## TF kırılımı (kademe 3-4)\n")
    out.append("| TF | kırılım | rastgele | fark |")
    out.append("|---|---|---|---|")
    for tf in ("1h", "2h", "4h", "1d"):
        gk = goz[(goz.mtf_uyum >= 3) & (goz.tf == tf)]
        gr = rnd[(rnd.kademe >= 3) & (rnd.tf == tf)]
        if len(gk) < 50 or gr.n.sum() < 100:
            continue
        pk = gk.y.mean()
        pr = gr.basari.sum() / gr.n.sum()
        out.append(f"| {tf} | %{pk*100:.1f} (n={len(gk)}) | %{pr*100:.1f} "
                   f"(n={int(gr.n.sum()):,}) | {(pk-pr)*100:+.1f} |")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
